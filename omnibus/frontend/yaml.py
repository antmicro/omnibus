# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import difflib
import functools
import io
import os
import sys
from importlib import resources

import jsonschema
import ruamel.yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .base import FrontendBase


def _load_schema(package, name):
    yaml = ruamel.yaml.YAML(typ="safe")
    with resources.files(package).joinpath(name).open() as stream:
        return yaml.load(stream)


#: JSON Schema of the specification format, see spec.schema.yml.
SCHEMA = _load_schema(__package__, "spec.schema.yml")

#: where SCHEMA expects the selected backend's schema extension
BACKEND_SCHEMA_URI = "urn:omnibus:backend"
_NO_BACKEND_EXTENSION = {"$defs": {"default": {}, "connection": {}}}


@functools.cache
def _validator(extension):
    """
    Validator for SCHEMA with a backend's extension registered: `extension` is
    a file name in omnibus/backend, or None for a backend without one.
    """
    fragment = (
        _NO_BACKEND_EXTENSION
        if extension is None
        else _load_schema("omnibus.backend", extension)
    )
    registry = Registry().with_resource(
        BACKEND_SCHEMA_URI, Resource(fragment, specification=DRAFT202012)
    )
    return jsonschema.Draft202012Validator(SCHEMA, registry=registry)


def _suggestion(name, allowed, fold_case=False):
    """
    ", did you mean 'x'?" if `name` closely resembles one of `allowed` (e.g. a
    singular/plural mix-up or a simple typo), else "".
    """
    name = str(name).lower() if fold_case else str(name)
    match = difflib.get_close_matches(name, allowed, n=1, cutoff=0.6)
    return f", did you mean '{match[0]}'?" if match else ""


# JSON Schema types, as someone writing YAML would call them
_TYPE_WORDS = {
    "object": "a mapping",
    "array": "a list",
    "string": "a string",
    "integer": "an integer",
    "number": "a number",
    "boolean": "true or false",
    "null": "nothing",
}


def _describe_value(value):
    """What a parsed YAML value is, and how it was (roughly) written."""
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return f"a boolean ({str(value).lower()})"
    if isinstance(value, str):
        return f"a string ('{value}')"
    if isinstance(value, (list, dict)):
        yaml = ruamel.yaml.YAML(typ="safe")
        yaml.default_flow_style = True
        yaml.width = 4096
        stream = io.StringIO()
        yaml.dump(value, stream)
        kind = "a list" if isinstance(value, list) else "a mapping"
        return f"{kind} ({stream.getvalue().strip()})"
    kind = "an integer" if isinstance(value, int) else "a number"
    return f"{kind} ({value})"


def _leaves(error):
    """Innermost errors under anyOf/oneOf alternatives: what actually failed."""
    return (
        [leaf for e in error.context for leaf in _leaves(e)]
        if error.context
        else [error]
    )


def _expected_types(error):
    """The types the value should have had, or None if its type is acceptable."""
    leaves = _leaves(error)
    if any(
        l.validator != "type" or l.absolute_path != error.absolute_path for l in leaves
    ):
        return None
    types = [leaf.validator_value for leaf in leaves]
    types = [t for ts in types for t in ([ts] if isinstance(ts, str) else ts)]
    return list(dict.fromkeys(types))


def _custom_message(error):
    """
    Message from the `x-error-message` annotation on the failing schema node, if
    any. For anyOf/oneOf, the annotation may sit on one of the alternatives (e.g.
    "frequency, or null"), so look into their errors too.

    A value of the wrong type gets the generic type message instead: annotations
    describe what's wrong with a value of the right type. `{instance}` in the
    message is the value; `{suggestion}` is a "did you mean" hint from the
    node's `x-suggestions` list, compared case-insensitively.
    """
    if _expected_types(error) is not None:
        return None

    schema = error.schema if isinstance(error.schema, dict) else {}
    message = schema.get("x-error-message")
    if message is not None:
        suggestion = _suggestion(
            error.instance, schema.get("x-suggestions", []), fold_case=True
        )
        return message.format(instance=error.instance, suggestion=suggestion)

    for suberror in error.context or []:
        message = _custom_message(suberror)
        if message is not None:
            return message

    return None


def _value_message(error):
    """Readable text for an error about a value; jsonschema's own if there's none."""
    types = _expected_types(error)
    if types is not None:
        words = [_TYPE_WORDS[t] for t in types]
        expected = (
            ", ".join(words[:-1]) + " or " + words[-1] if len(words) > 1 else words[0]
        )
        return f"expected {expected}, got {_describe_value(error.instance)}"
    if error.context:
        # anyOf/oneOf: report what's wrong in the alternative of the right type
        leaf = next((l for l in _leaves(error) if l.validator != "type"), None)
        return _value_message(leaf) if leaf else error.message
    if error.validator == "minProperties":
        names = ", ".join(f"'{name}'" for name in error.instance)
        entries = "entry" if error.validator_value == 1 else "entries"
        got = f"{len(error.instance)} ({names})" if error.instance else "none"
        return f"expected at least {error.validator_value} {entries}, got {got}"
    if error.validator == "minLength":
        return "must not be empty"
    return error.message


class Frontend(FrontendBase):
    """
    YAML frontend

    This frontend reads specification from yaml file according to docs/specification.md
    Using this file, all interconnect attributes are populated

    The document is first validated against spec.schema.yml, which covers its
    structure: allowed and required fields, types and value formats. Only
    specifications passing it are parsed further, which covers the remaining
    checks: references between sections, defaults, and address ranges.

    It internally uses 'spec' dictionary for some processing and debug print
    """

    def _location(self, error, key=None):
        """
        "file:line:col: " of the deepest key on the error's path, or of `key` in
        the mapping the path leads to (an unknown field, a malformed key). Errors
        with nothing to point at, e.g. a missing top-level field, get "file: ".
        """
        node, pos = self._positions, None
        for step in error.absolute_path:
            try:
                pos = (
                    node.lc.key(step) if isinstance(node, dict) else node.lc.item(step)
                )
                node = node[step]
            except (AttributeError, KeyError, IndexError, TypeError):
                break
        if key is not None:
            try:
                pos = node.lc.key(key)
            except (AttributeError, KeyError, TypeError):
                pass
        if pos is None:
            return f"{self._filename}: "
        return f"{self._filename}:{pos[0] + 1}:{pos[1] + 1}: "

    def _schema_error_messages(self, error):
        """Translate a single jsonschema ValidationError into error messages"""
        path = [str(p) for p in error.absolute_path]
        where = "top level" if not path else "'" + ".".join(path) + "'"
        # errors about a key rather than its value: a malformed key (e.g. a connection
        # name), or a key that requires another one to be present
        key = None
        if "propertyNames" in error.schema_path:
            key = error.instance
        elif error.validator == "dependentRequired":
            key = next(
                k
                for k, deps in error.validator_value.items()
                if k in error.instance and any(d not in error.instance for d in deps)
            )

        message = _custom_message(error)
        if message is not None:
            return [f"{self._location(error, key)}ERROR: in {where}, {message}"]

        if error.validator == "additionalProperties":
            known = error.schema.get("properties", {})
            allowed = sorted(known)
            return [
                f"{self._location(error, name)}ERROR: in {where}, unknown field '{name}'"
                f"{_suggestion(name, allowed)}, allowed ones are {allowed}"
                for name in error.instance
                if name not in known
            ]

        message = _value_message(error)
        return [f"{self._location(error, key)}ERROR: in {where}, {message}"]

    def _validate_schema(self):
        """
        Validate self.spec against the specification schema, reporting all
        violations at once. Returns True if any were found.
        """
        errors = sorted(
            # the backend this frontend is combined with may extend the schema
            _validator(getattr(self, "SCHEMA_EXTENSION", None)).iter_errors(self.spec),
            key=lambda error: [str(p) for p in error.absolute_path],
        )

        # a value of the wrong type fails most other rules on it too -- report
        # only the type mismatch
        type_errors = {tuple(e.absolute_path) for e in errors if e.validator == "type"}
        errors = [
            e
            for e in errors
            if e.validator == "type" or tuple(e.absolute_path) not in type_errors
        ]

        for error in errors:
            self.errors.extend(self._schema_error_messages(error))

        return len(errors) > 0

    def read_yaml(self, filename):
        """Read yaml and populate internal representation according to the specification.md"""

        ## Filename
        if not (os.path.isfile(filename) and os.access(filename, os.R_OK)):
            self.errors.append(
                f"ERROR: file '{filename}' does not exist or is not readable"
            )
            return 1

        ## Yaml
        with open(filename, "r") as stream:
            try:
                self.spec = ruamel.yaml.YAML(typ="safe").load(stream)
            except Exception as ex:  # noqa: BLE001
                self.errors.append("ERROR: invalid yaml provided")
                self.errors.append(ex.problem)
                self.errors.append(str(ex.problem_mark))
                return 2
            # a second, round-trip load only for positions of keys in error
            # messages; the parser itself uses the plain safe-loaded data
            stream.seek(0)
            self._filename = filename
            self._positions = ruamel.yaml.YAML(typ="rt").load(stream)

        ## Schema
        # everything below can rely on the document's structure being valid
        if self._validate_schema():
            return 3

        ## Name, Version
        self._set_name(self.spec.get("name", "interconnect"))
        self._set_version(self.spec.get("version", 0))

        ## Globals
        global_ = dict(self.spec.get("global") or {})
        global_.setdefault("addr_width", 32)
        for name, val in global_.items():
            self._add_global(name, val)

        ## Defaults
        for name, val in (self.spec.get("default") or {}).items():
            self._add_default(name, val)

        ## Clocks
        clocks = self.spec.get("clocks") or {self.defaults.get("clock", "clock"): None}
        for clkname, clk in clocks.items():
            frequency = (clk or {}).get("frequency")

            if frequency in ["n/a", None]:
                if "frequency" in self.defaults:
                    frequency = self.defaults["frequency"]
                else:
                    self.warns.append(
                        f"WARNING: clock '{clkname}' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable"
                    )
                    frequency = "n/a"

            self._add_clock(clkname, frequency)

        if ("clock" in self.defaults) and (self.defaults["clock"] not in self.clocks):
            self.errors.append(
                f"ERROR: default clock provided ('{self.defaults['clock']}'), but no such entry in 'clocks'"
            )

        ## Ports
        top_level_ports = len(self.spec["ports"])
        for portname, port in self.spec["ports"].items():
            self._add_port(portname, dict(port))

        # ports missing a parameter that has no default are not added
        if len(self.ports) < 2:
            self.errors.append(
                "ERROR: at least two valid top level ports must be provided"
            )
        if len(self.srcports) < 1:
            self.errors.append(
                "ERROR: at least one subordinate top level port must be provided"
            )
        if len(self.dstports) < 1:
            self.errors.append(
                "ERROR: at least one manager top level port must be provided"
            )

        # errors by this point generally make proper crossbar, connection, and address_map read impossible
        if len(self.errors) > 0:
            return 4

        ## Crossbars
        # the schema guarantees crossbars and connections are either both present or both absent
        crossbars = self.spec.get("crossbars")
        connections = self.spec.get("connections")

        if crossbars is None:
            crossbars = {"main": {"clock": None, "ports": {}}}
            connections = {}

            for portname, port in self.ports.items():
                role = port.attributes["role"]
                crossbars["main"]["ports"][portname] = {"role": role}

                if role == "subordinate":
                    connections[f"{portname} -> main.{portname}"] = {}
                else:
                    connections[f"main.{portname} -> {portname}"] = {}

        for crossbar, cpars in crossbars.items():
            cpars = dict(cpars)
            # clock might still be null, in that case it is filled by propagation
            cpars["clock"] = cpars.get("clock") or self.defaults.get("clock")
            ports = cpars["ports"]

            self._add_crossbar(crossbar, cpars)
            for portname, port in ports.items():
                self._add_port(crossbar + "_" + portname, dict(port), parent=crossbar)

        ## Connections
        if len(connections) < top_level_ports:
            self.errors.append(
                "ERROR: insufficient number of connections, each top level port must include connection"
            )

        for conn, params in connections.items():
            source, _, dest = conn.split(" ")
            self._connect(
                source.replace(".", "_"), dest.replace(".", "_"), params or {}
            )

        ## Address map
        for name, entry in self.spec["address_map"].items():
            sources = entry.get("from")
            if sources is None:
                sources = list(self.srcports)
            elif isinstance(sources, str):
                sources = [sources]

            self._add_address_map_entry(
                name, sources, entry["to"], entry["base"], entry["size"]
            )

        if len(self.errors) > 0:
            return 4
        return 0

    def _print_spec(self, filename=None):
        """Dumps current spec to filename, if filename is None then dumps to stdout"""
        yaml = ruamel.yaml.YAML(typ="safe")
        yaml.default_flow_style = False

        file = sys.stdout
        if filename:
            file = open(filename, "w")  # noqa SIM115

        print(f"name: {self.name}", file=file)
        print(f"version: {self.version}", file=file)
        print("globals:", file=file)
        for name, val in sorted(self.globals.items()):
            print(f"  {name} = {val}", file=file)
        print("defaults:", file=file)
        for name, val in sorted(self.defaults.items()):
            print(f"  {name} = {val}", file=file)
        print("clocks:", file=file)
        for clkname, clk in sorted(self.clocks.items()):
            print(f"  {clkname} = {clk['frequency']} Hz", file=file)
        print("ports:", file=file)
        for portname, port in sorted(self.ports.items()):
            print(f"  {portname} - {port.parent}", file=file)
            for name, val in sorted(port.attributes.items()):
                print(f"    {name} = {val}", file=file)
            for edge in port.edges:
                print(f"    edge to {edge.dest}", file=file)
                for name, val in sorted(edge.attributes.items()):
                    print(f"      {name} = {val}", file=file)
        print("crossbars:", file=file)
        for compname, comp in sorted(self.components.items()):
            print(f"  {compname}", file=file)
            for name, val in sorted(comp.attributes.items()):
                print(f"    {name} = {val}", file=file)
            print("    subordinates:", file=file)
            for port in sorted(comp.srcports):
                print(f"      {port}", file=file)
            print("    managers:", file=file)
            for port in sorted(comp.dstports):
                print(f"      {port}", file=file)
        print("address maps:", file=file)
        for entry in self.address_map.values():
            print(f"  {sorted(entry.src)}", file=file)
            print(f"  {entry.dest}", file=file)
            print(f"  {entry.base}", file=file)
            print(f"  {entry.size}", file=file)

        if filename:
            file.close()
