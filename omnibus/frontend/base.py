# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import math
import re

from ..types import AddressMapEntry, Component, Edge, Port


class FrontendBase:
    """
    Implements basic set of convenience methods to use by frontends
    """

    def _set_name(self, name):
        self.name = name

    def _set_version(self, version):
        self.version = version

    def _parse_frequency(self, name, freq, where):
        if type(freq) in [float, int]:
            return float(freq)

        if freq == "n/a":
            return freq

        ii = 0
        while ii < len(freq) and freq[ii].isdigit():
            ii += 1

        freqleft = 1
        freqright = "Hz"

        if ii > 0:
            freqleft = freq[0:ii]
        if len(freq) > ii:
            freqright = freq[ii:]

        if re.fullmatch("[Hh]z", freqright):
            return float(freqleft) * 1e0
        if re.fullmatch("k([Hh]z)?", freqright):
            return float(freqleft) * 1e3
        if re.fullmatch("M([Hh]z)?", freqright):
            return float(freqleft) * 1e6
        return float(freqleft) * 1e9

    def _add_global(self, name, val):
        if name not in self.parse_global:
            self.warns.append(f"WARNING: '{name}' not in the list of known globals")
            return
        errcount = len(self.errors)
        val = self.parse_global[name](name, val, "'global'")
        if errcount == len(self.errors):
            self.globals[name] = val

    def _add_default(self, name, val):
        if name not in self.parse_default:
            self.warns.append(f"WARNING: '{name}' not in the list of known defaults")
            return
        errcount = len(self.errors)
        val = self.parse_default[name](name, val, "'default'")
        if errcount == len(self.errors):
            self.defaults[name] = val

    def _parse_positive_int(self, name, val, where):
        return val

    def _parse_str(self, name, val, where):
        return val

    def _parse_bool(self, name, val, where):
        return val

    def _parse_protocol(self, name, val, where):
        if re.fullmatch("axi4?", val.lower()):
            return "axi4"
        if re.fullmatch("ahb3?", val.lower()):
            return "ahb3"
        if re.fullmatch("apb3?", val.lower()):
            return "apb3"
        return "axi4lite"

    def _connect(self, port1name, port2name, params):
        port1 = self.ports.get(port1name)
        port2 = self.ports.get(port2name)

        if port1 is None:
            self.errors.append(
                f"ERROR: cannot connect '{port1name}' to '{port2name}', '{port1name}' does not exist"
            )
            return
        if port2 is None:
            self.errors.append(
                f"ERROR: cannot connect '{port1name}' to '{port2name}', '{port2name}' does not exist"
            )
            return

        errcount = len(self.errors)
        nparams = {}
        for name, val in params.items():
            if name not in self.parse_connections:
                self.warns.append(
                    f"WARNING: while connecting '{port1name}' to '{port2name}', unknown parameter '{name}'"
                )
                continue

            errcount = len(self.errors)
            nval = self.parse_connections[name](
                name, val, f"'connections' from '{port1name}' to '{port2name}'"
            )

            if len(self.errors) > errcount:
                continue

            nparams[name] = nval

        if len(self.errors) > errcount:
            return

        if port2name in self.dstports:
            nparams["protocol"] = nparams.get("protocol", True)

        port1.edges.append(Edge(port2name, nparams))
        port2.backedges.append(Edge(port1name, nparams))

    def _add_address_map_entry(self, name, portsfrom, portto, base, size):
        errcount = len(self.errors)
        for port in portsfrom:
            if port not in self.srcports:
                self.errors.append(
                    f"ERROR: in 'address_map' entry '{name}', '{port}' is not a valid source port, must be a subordinate top level port"
                )

        if portto not in self.dstports:
            self.errors.append(
                f"ERROR: in 'address_map' entry '{name}', '{portto}' is not a valid destination port, must be a manager top level port"
            )

        if base + size > 2 ** self.globals["addr_width"]:
            self.errors.append(
                f"ERROR: in 'address_map' entry '{name}', end address exceeds available range, end address is {base + size - 1} while range ends at {2 ** self.globals['addr_width'] - 1}"
            )

        if len(self.errors) > errcount:
            return

        self.address_map[name] = AddressMapEntry(portsfrom, portto, base, size)

    def _add_clock(self, clkname, freq):
        self.clocks[clkname] = {
            "frequency": self._parse_frequency("frequency", freq, f"clock '{clkname}'")
        }

    def _add_port(self, portname, attrs, parent=None):
        params = ["clock", "protocol", "data_width"]

        where = f"top level port '{portname}'"
        if parent:
            params = []
            where = f"in crossbar '{parent}' port '{portname}'"

        nattrs = {}
        errcount = len(self.errors)

        for param in params:
            if param in attrs:
                nattrs[param] = self.parse_default[param](
                    param, attrs.pop(param), where
                )
                continue

            if param in self.defaults:
                nattrs[param] = self.defaults[param]
                continue

            self.errors.append(
                f"ERROR: {where} parameter '{param}' has no value and no default was provided"
            )

        nattrs["role"] = attrs.pop("role", "none")

        # all used ones are removed by this point, anything left is an error
        for attrname in attrs:
            self.errors.append(f"ERROR: {where} parameter '{attrname}' undefined")

        if nattrs.get("role") not in ["manager", "subordinate"]:
            self.errors.append(
                f"ERROR: {where} 'role' must be 'subordinate' or 'manager', instead found '{nattrs['role']}'"
            )
            return

        if len(self.errors) > errcount:
            return

        if parent:
            nattrs["clock"] = self.components[parent].attributes["clock"]

        self.ports[portname] = Port(parent, nattrs)

        if parent:
            comp = self.components[parent]

            if nattrs["role"] == "manager":
                comp.dstports.append(portname)

                for srcportname in comp.srcports:
                    self.ports[srcportname].edges.append(Edge(portname, {}))

            else:
                comp.srcports.append(portname)
                comp.sub_log2 = math.ceil(math.log2(len(comp.srcports)))

                for dstportname in comp.dstports:
                    self.ports[portname].edges.append(Edge(dstportname, {}))
        else:
            if nattrs["role"] == "manager":
                self.dstports.add(portname)
            else:
                self.srcports.add(portname)

    def _add_crossbar(self, name, attrs):
        where = f"crossbar {name}"

        nattrs = {}
        errcount = len(self.errors)

        attrs.pop("ports")

        nattrs["clock"] = attrs.pop("clock")

        # all used ones are removed by this point, anything left is an error
        for attrname in attrs:
            self.errors.append(f"ERROR: {where} parameter '{attrname}' undefined")

        if len(self.errors) > errcount:
            return

        self.components[name] = Component("crossbar", nattrs)
