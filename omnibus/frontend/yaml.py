# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import sys

import ruamel.yaml

from .base import FrontendBase


class Frontend(FrontendBase):
    """
    YAML frontend

    This frontend reads specification from yaml file according to docs/specification.md
    Using this file, all interconnect attributes are populated

    It internally uses 'spec' dictionary for some processing and debug print
    """

    def _check_fields(self, where, keys, required, optional):
        err = False

        allowed = required | optional
        for fieldname in keys:
            if fieldname not in allowed:
                self.errors.append(
                    f"ERROR: {where} has invalid field '{fieldname}', allowed ones are {sorted(allowed)}"
                )
                err = True

        for fieldname in required:
            if fieldname not in keys:
                self.errors.append(f"ERROR: {where} lacks required field '{fieldname}'")
                err = True

        return err

    def read_yaml(self, filename):
        """Read yaml and populate internal representation according to the specification.md"""

        ## Filename
        if not (os.path.isfile(filename) and os.access(filename, os.R_OK)):
            self.errors.append(
                f"ERROR: file '{filename}' does not exist or is not readable"
            )
            return 1

        ## Yaml
        yaml = ruamel.yaml.YAML(typ="safe")
        with open(filename, "r") as stream:
            try:
                self.spec = yaml.load(stream)
            except Exception as ex:  # noqa: BLE001
                self.errors.append("ERROR: invalid yaml provided")
                self.errors.append(ex.problem)
                self.errors.append(str(ex.problem_mark))
                return 2

        ## Desc Version
        if self.spec.pop("desc_version", "none") != 1.0:
            self.errors.append("ERROR: specification version invalid or not provided")
            return 3

        ## Name
        self._set_name(self.spec.pop("name", "interconnect"))

        ## Version
        self._set_version(self.spec.pop("version", 0))

        ## Globals
        if "globals" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'globals', did you mean 'global'?"
            )
            self.spec.pop("globals")

        if self.spec.get("global") is None:
            self.spec["global"] = {}
        elif type(self.spec["global"]) is not dict:
            self.errors.append(
                "ERROR: field 'global' must contain dictionary of globals or be empty"
            )
            self.spec["global"] = {}
        self.spec["global"]["addr_width"] = self.spec["global"].get("addr_width", 32)

        for name, val in self.spec.pop("global", {}).items():
            self._add_global(name, val)

        ## Defaults
        if "defaults" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'defaults', did you mean 'default'?"
            )
            self.spec.pop("defaults")

        if self.spec.get("default") is None:
            self.spec["default"] = {}
        elif type(self.spec["default"]) is not dict:
            self.errors.append(
                "ERROR: field 'default' must contain dictionary of defaults or be empty"
            )
            self.spec["default"] = {}

        for name, val in self.spec.pop("default", {}).items():
            self._add_default(name, val)

        ## Clocks
        if "clock" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'clock', did you mean 'clocks'?"
            )
            self.spec.pop("clock")

        if "clocks" in self.spec:
            if type(self.spec["clocks"]) is not dict:
                self.errors.append(
                    "ERROR: field 'clocks' must contain dictionary of clocks"
                )
                self.spec["clocks"] = {}
            elif len(self.spec["clocks"].keys()) == 0:
                self.errors.append("ERROR: at least one clock has to be created")
        else:
            self.spec["clocks"] = {self.defaults.get("clock", "clock"): None}

        for clkname, clk in self.spec.pop("clocks").items():
            if clk is None:
                clk = {"frequency": None}
            elif type(clk) is not dict:
                self.errors.append(
                    f"ERROR: clock '{clkname}' does not have dictionary of attributes"
                )

            if len(clkname) == 0:
                self.errors.append("ERROR: clock name must not be empty")
                continue

            if self._check_fields(
                f"clock '{clkname}'", clk.keys(), set(), {"frequency"}
            ):
                continue

            if clk.get("frequency") in ["n/a", None]:
                if "frequency" in self.defaults:
                    clk["frequency"] = self.defaults["frequency"]
                else:
                    self.warns.append(
                        f"WARNING: clock '{clkname}' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable"
                    )
                    clk["frequency"] = "n/a"

            self._add_clock(clkname, clk["frequency"])

        if ("clock" in self.defaults) and (self.defaults["clock"] not in self.clocks):
            self.errors.append(
                f"ERROR: default clock provided ('{self.defaults['clock']}'), but no such entry in 'clocks'"
            )

        ## Ports
        if "port" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'port', did you mean 'ports'?"
            )
            self.spec.pop("port")

        top_level_ports = 0
        if "ports" in self.spec:
            if type(self.spec["ports"]) is not dict:
                self.errors.append(
                    "ERROR: field 'ports' must contain dictionary of ports"
                )
                self.spec["ports"] = {}
        else:
            self.errors.append("ERROR: lack of 'ports' field")
            self.spec["ports"] = {}

        for portname, port in self.spec.pop("ports").items():
            if type(port) is not dict:
                self.errors.append(
                    f"ERROR: top level port '{portname}' does not have dictionary of attributes"
                )
                port = {}

            self._add_port(portname, port)
            top_level_ports += 1

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
        if "crossbar" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'crossbar', did you mean 'crossbars'?"
            )
            self.spec.pop("crossbar")

        if ("crossbars" in self.spec) != ("connections" in self.spec):
            self.errors.append(
                "ERROR: 'crossbars' and 'connections' must be both either defined or left for inference"
            )

        if "crossbars" in self.spec:
            if type(self.spec["crossbars"]) is not dict:
                self.errors.append(
                    "ERROR: field 'crossbars' must contain dictionary of crossbars"
                )
                self.spec["crossbars"] = {}
        else:
            self.spec["crossbars"] = {"main": {"clock": None, "ports": {}}}
            self.spec["connections"] = {}

            xb_ports = self.spec["crossbars"]["main"]["ports"]

            for portname, port in self.ports.items():
                role = port.attributes["role"]
                xb_ports[portname] = {"role": role}

                if role == "subordinate":
                    self.spec["connections"][f"{portname} -> main.{portname}"] = {}
                else:
                    self.spec["connections"][f"main.{portname} -> {portname}"] = {}

        for crossbar, cpars in self.spec.pop("crossbars").items():
            if type(cpars) is not dict:
                self.errors.append(
                    f"ERROR: crossbar '{crossbar}' does not have dictionary of attributes"
                )
                cpars = {}

            if self._check_fields(
                f"crossbar '{crossbar}'", cpars.keys(), {"ports"}, {"clock"}
            ):
                continue

            clock = cpars.get("clock")

            if not clock:
                clock = self.defaults.get("clock")
                cpars["clock"] = clock
            # clock might still be null, in that case it is filled by propagation

            ports = cpars["ports"]

            if type(ports) is not dict:
                self.errors.append(
                    f"ERROR: crossbar '{crossbar}' field 'ports' must be a dictionary of ports"
                )
                continue

            self._add_crossbar(crossbar, cpars)

            # some error occurred and it was not added
            if crossbar not in self.components:
                continue

            for portname, port in ports.items():
                if type(port) is not dict:
                    self.errors.append(
                        f"ERROR: crossbar '{crossbar}' port '{portname}' does not have dictionary of attributes"
                    )
                    port = {}

                name = crossbar + "_" + portname
                self._add_port(name, port, parent=crossbar)

            comp = self.components[crossbar]
            srcportcnt = len(comp.srcports)
            dstportcnt = len(comp.dstports)
            if srcportcnt + dstportcnt < 2:
                self.errors.append(
                    f"ERROR: crossbar '{crossbar}' does not have enough valid ports, must be at least 2"
                )
            if srcportcnt < 1:
                self.errors.append(
                    f"ERROR: crossbar '{crossbar}' does not have enough valid subordinate ports, must be at least 1"
                )
            if dstportcnt < 1:
                self.errors.append(
                    f"ERROR: crossbar '{crossbar}' does not have enough valid manager ports, must be at least 1"
                )

        ## Connections
        if "connection" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'connection', did you mean 'connections'?"
            )
            self.spec.pop("connections")

        if "connections" not in self.spec:
            self.spec["connections"] = {}

        if type(self.spec["connections"]) is not dict:
            self.errors.append(
                "ERROR: field 'connections' must contain dictionary of connections"
            )
            self.spec["connections"] = {}
        elif len(self.spec["connections"].keys()) < top_level_ports:
            self.errors.append(
                "ERROR: insufficient number of connections, each top level port must include connection"
            )

        for conn, params in self.spec.pop("connections").items():
            parts = conn.split(" ")

            if len(parts) != 3 or parts[1] != "->":
                self.errors.append(
                    f"ERROR: entry in 'connections' '{conn}' invalid: expected format 'a -> b'"
                )
                continue

            if params is None:
                params = {}

            if type(params) is not dict:
                self.errors.append(
                    f"ERROR: connection '{conn}' should include dictionary of parameters"
                )
                continue

            self._connect(
                parts[0].replace(".", "_"), parts[2].replace(".", "_"), params
            )

        ## Address map
        if "address_maps" in self.spec:
            self.errors.append(
                "ERROR: invalid field name 'address_maps', did you mean 'address_map'?"
            )
            self.spec.pop("address_maps")

        if "address_map" not in self.spec:
            self.errors.append("ERROR: lack of 'address_map' field")
            self.spec["address_map"] = {}

        if type(self.spec["address_map"]) is not dict:
            self.errors.append(
                "ERROR: field 'address_map' must contain dictionary of mappings"
            )
            self.spec["address_map"] = {}

        for name, entry in self.spec.pop("address_map").items():
            if type(entry) is not dict:
                self.errors.append(
                    f"ERROR: 'address_map' entry '{name}' should include dictionary of fields"
                )
                continue

            if self._check_fields(
                f"'address_map' entry '{name}'", entry, {"to", "base", "size"}, {"from"}
            ):
                continue

            if type(entry["to"]) is not str:
                self.errors.append(
                    f"ERROR: 'address_map' entry '{name}' does not point to a valid port name - must be a single string"
                )
                continue

            if type(entry["base"]) is not int:
                self.errors.append(
                    f"ERROR: 'address_map' entry '{name}' 'base' is not an integer"
                )
                continue

            if type(entry["size"]) is not int:
                self.errors.append(
                    f"ERROR: 'address_map' entry '{name}' 'size' is not an integer"
                )
                continue

            if entry.get("from") is None:
                entry["from"] = list(self.srcports)
            elif type(entry["from"]) is str:
                entry["from"] = [entry["from"]]
            elif type(entry["from"]) is not list:
                self.errors.append(
                    f"ERROR: 'address_map' entry '{name}' does not start from valid ports name, must be either string or list of strings"
                )
                continue

            self._add_address_map_entry(
                name, entry["from"], entry["to"], entry["base"], entry["size"]
            )

        for entry in self.spec:
            self.errors.append(
                f"ERROR: invalid top level field '{entry}', see allowed ones at https://antmicro.github.io/omnibus/specification.html#yaml-syntax-specification"
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
