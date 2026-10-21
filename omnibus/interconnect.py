# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import copy
import sys
from collections import defaultdict
from importlib import import_module

import ruamel.yaml

from .types import AddressMapEntry, Component, Edge, Path, Port


def InterconnectBuilder(frontend="yaml", backend="topwrap_pulpplatform"):
    """
    Creates Interconnect class with customizable frontend and backend
    All frontends are read from `frontend/` and backends from `backend/` directories
    To create new one, simply add it in corresponding directory with class 'frontend' or 'backend' inside

    It is achieved via dynamic inheritance
    A module given in filename is imported and then used as parent to Interconnect class
    This allows interconnect to be customized with different methods while maintaining illusion that it is singular class

    For example, backend can be swapped between topwrap_pulpplatform and graphviz
    This allows user to decide whether they need full verilog output or whether they are interested in visual representation of interconnect
    While also keeping methods logically grouped together and preventing accidental use of methods from different backend
    """
    fe = import_module(f".frontend.{frontend}", "omnibus")
    be = import_module(f".backend.{backend}", "omnibus")

    class Interconnect(fe.Frontend, be.Backend):
        def __init__(self):
            be.Backend.__init__(self)

            self.name = ""
            self.version = 0
            self.clocks = {}
            self.globals = {}
            self.defaults = {}

            self.ports = {}
            self.components = {}
            self.address_map = {}

            self.srcports = set()
            self.dstports = set()

            self.parse_global |= {"addr_width": self._parse_positive_int}

            self.parse_default |= {
                "clock": self._parse_str,
                "protocol": self._parse_protocol,
                "frequency": self._parse_frequency,
                "data_width": self._parse_positive_int,
            }

            self.parse_connections |= {
                "data_width": self._parse_positive_int,
                "registers": self._parse_positive_int,
                "cdc": self._parse_bool,
                "protocol": self._parse_bool,
            }

            self.errors = []
            self.warns = []

            self._print_dest = sys.stdout

        def process(self):
            """Shorthand for internal processing"""
            self.find_routing_paths()
            self.propagate_parameters()
            self.insert_new_components()

        def find_routing_paths(self):
            """
            Finds all paths from interconnect managers to subordinates and sets up address map for each crossbar

            Assumes there is at most one valid path from each manager to each subordinate

            Internally, performs BFS on the graph, finding what crossbars are used to get to a given port
            then for each path, add appropriate entry to each crossbar on the path
            """
            self.paths_to_search = []
            self.paths_complete = {}
            self.ports_reaching_crossbars = defaultdict(set)

            for port in self.srcports:
                self.paths_to_search.append(Path(port))

            while len(self.paths_to_search) > 0:
                curpath = self.paths_to_search.pop(0)

                curport = self.ports[curpath.curport]

                if curport.attributes["role"] == "manager":
                    # on toplevel, search is complete
                    # on crossbar, expand address map
                    if curport.parent is None:
                        # curport used above is Port object, while endport should be string identifier
                        pathname = curpath.startport + " -> " + curpath.curport

                        if pathname in self.paths_complete:
                            self.errors.append(
                                f"ERROR: path {pathname} defined more than once, only one path between two ports can exist"
                            )
                            return

                        self.paths_complete[pathname] = curpath.crossbars
                        continue

                    # again, we need portname not port
                    curpath.crossbars[curport.parent] = curpath.curport
                    self.ports_reaching_crossbars[curport.parent].add(curpath.startport)

                # for each outgoing node create new path
                for destport in curport.edges:
                    newpath = copy.deepcopy(curpath)
                    newpath.curport = destport.dest
                    self.paths_to_search.append(newpath)

            # generate address maps here
            for name, entry in self.address_map.items():
                sources = entry.src
                dest = entry.dest
                base = entry.base
                size = entry.size

                for source in sources:
                    if not self.paths_complete.get(source + " -> " + dest):
                        self.errors.append(
                            f"ERROR: no path from '{source}' to '{dest}', required by address map entry '{name}'"
                        )
                        return
                    for crossbar, port in self.paths_complete[
                        source + " -> " + dest
                    ].items():
                        self.components[crossbar].address_map.append(
                            AddressMapEntry(source, port, base, size)
                        )

            # sort each address map by (source, dest port, base) in that order
            # after that, check whether one entry is followed directly by another
            # if so, merge them
            for crossbarname, params in self.components.items():
                if params.kind != "crossbar":
                    continue

                if len(params.address_map) == 0:
                    continue

                params.address_map = sorted(
                    params.address_map, key=lambda x: (x.src, x.dest, x.base)
                )

                ii = 0
                while ii < len(params.address_map) - 1:
                    cur = params.address_map[ii]
                    nxt = params.address_map[ii + 1]

                    if (
                        cur.src == nxt.src
                        and cur.dest == nxt.dest
                        and nxt.base == cur.base + cur.size
                    ):
                        cur.size = cur.size + nxt.size
                        params.address_map.pop(ii + 1)
                        continue

                    ii = ii + 1

                # for now, it is not possible to have address map entries with different source IDs
                # if two rules match in all but first name, merge them, otherwise throw an error
                # TODO: there should be check to ensure address map has indeed entries for each source->dest pair, but assume this is the case for now
                params.address_map = sorted(
                    params.address_map, key=lambda x: (x.dest, x.src)
                )

                ii = 0
                while ii < len(params.address_map) - 1:
                    cur = params.address_map[ii]
                    nxt = params.address_map[ii + 1]

                    if type(cur.src) is not list:
                        cur.src = [cur.src]

                    if (
                        cur.dest == nxt.dest
                        and cur.base == nxt.base
                        and cur.size == nxt.size
                    ):
                        cur.src.append(nxt.src)
                        params.address_map.pop(ii + 1)
                        continue

                    ii = ii + 1

                last = params.address_map[-1]
                if type(last.src) is not list:
                    last.src = [last.src]

                for entry in params.address_map:
                    if sorted(entry.src) != sorted(
                        self.ports_reaching_crossbars[crossbarname]
                    ):
                        # TODO: this should somehow figure out exact conflict source
                        self.errors.append(
                            "ERROR: it is not yet possible to have address map rules that are different based on source "
                        )

        def propagate_parameters(self):
            """
            Propagate all parameters such that each port has all parameters assigned

            Must be called before insert_new_components()

            Internally the tool copies parameters from one port to each of its neighbors, ignoring direction of edges

            Connection parameters the backend lists in port_connection_params are also
            copied to the port each connection starts at
            This means that there might be situation where no valid configuration exists
            (for example when two connections of a port have different value)
            If valid configuration exists, handle it like most other parameters

            id width is handled as fully separate case
            finding it requires some degree of backtracking and rewriting already found results

              assign all top level subordinate ports id to 1, add them to list
              until the list is empty:
                pick any port P from the list
                remove P from the list
                for each destination port D thru crossbar N:1:
                  if D.id_width >= P.id_width + ceil(log2(N))
                     continue
                  else
                     D.id_width = P.id_width + ceil(log2(N))
                     add D to list
              within each crossbar, set all subs to maximum id_width among subs
              later, id_width_extender might be needed
            """

            for param in ["data_width"] + self.port_connection_params:
                for portname, port in self.ports.items():
                    for edge in port.edges:
                        destname = edge.dest
                        dest = self.ports[destname]

                        val = edge.attributes.get(param)

                        if val is None:
                            continue

                        port_val = port.attributes.get(param)
                        dest_val = dest.attributes.get(param)

                        if port_val != val:
                            self.errors.append(
                                f"ERROR: no valid configuration exists for {param}, port {portname} has assigned value that is different than its outgoing connection to {destname}"
                            )
                            continue

                        if dest_val != val:
                            self.errors.append(
                                f"ERROR: no valid configuration exists for {param}, port {destname} has assigned value that is different than its incoming connection from {portname}"
                            )
                            continue

                        port.attributes[param] = val
                        dest.attributes[param] = val

            ports_to_process = []

            for attr, barrier in {
                ("clock", "cdc"),
                ("protocol", "protocol"),
                ("data_width", None),
            }:
                for portname, port in self.ports.items():
                    if port.attributes.get(attr):
                        ports_to_process.append(portname)

                if len(ports_to_process) == 0:
                    self.warns.append(
                        f"WARNING: parameter {attr} is never specified, propagation not possible"
                    )
                    continue

                while len(ports_to_process) > 0:
                    portname = ports_to_process.pop(0)

                    port = self.ports[portname]

                    for edge in port.edges + port.backedges:
                        destname = edge.dest
                        dest = self.ports[destname]

                        if dest.attributes.get(attr):
                            continue

                        if edge.attributes.get(barrier):
                            continue

                        if dest.parent is None:
                            dest.attributes[attr] = port.attributes[attr]
                            ports_to_process.append(destname)
                            continue

                        # all ports in crossbars must share the same parameters
                        # NOTE: this probably should be done smarter, include some metric for picking best attribute for crossbar
                        #       metrics can include: majority, throughput, latency, etc
                        parent = dest.parent
                        for childportname, childport in self.ports.items():
                            if childport.parent == parent:
                                childport.attributes[attr] = port.attributes[attr]
                                ports_to_process.append(childportname)

                # if by this point attribute is not populated, then this must be an error and proper propagation is impossible
                # this might happen eg when a region is fully surrounded by CDC and no clock is provided inside
                for portname, port in self.ports.items():
                    if not port.attributes.get(attr):
                        self.errors.append(
                            f"ERROR: could not propagate attribute '{attr}' to port '{portname}', it is likely surrounded by barriers that stop propagation"
                        )

            ports_to_process = []

            for portname in self.srcports:
                self.ports[portname].attributes["id_width"] = 1
                ports_to_process.append(portname)

            while len(ports_to_process) > 0:
                portname = ports_to_process.pop(0)
                port = self.ports[portname]
                id_width = port.attributes["id_width"]

                for edge in port.edges:
                    destname = edge.dest
                    dest = self.ports[destname]

                    # separate handling for crossbars, they expand id
                    if port.parent is not None and port.parent == dest.parent:
                        crossbar = self.components[port.parent]

                        if (
                            dest.attributes.get("id_width", 0)
                            <= id_width + crossbar.sub_log2
                        ):
                            ports_to_process.append(destname)
                            dest.attributes["id_width"] = id_width + crossbar.sub_log2

                            crossbar.attributes["sub_id_width"] = max(
                                crossbar.attributes.get("sub_id_width", 0), id_width
                            )

                    else:
                        if dest.attributes.get("id_width", 0) <= id_width:
                            ports_to_process.append(destname)
                            dest.attributes["id_width"] = id_width

            for comp in self.components.values():
                for portname in comp.srcports:
                    self.ports[portname].attributes["id_width"] = comp.attributes[
                        "sub_id_width"
                    ]

        def insert_new_components(self):
            """
            Insert components for each spill register and parameter value crossing, e.g. CDC between different clocks

            Must be called after propagate_parameters()

            insertion start with highest priority, AKA the ones that should be placed first in case of multiple components on single connection
            current prioretization is: registers > id width > data width > clock > protocol

            registers are inserted directly

            conversion components insertion algorithm is:
             1. go thru each connection, find connections between ports of different parameters
             2. insert two new ports under new component, the kind of component depends on the parameter
             3.
               a. for the parameter under consideration, get first's port param from source node, get second's port param from dest
               b. for other parameters, get both ports' params from source port
            note: source/dest are regarding edge direction, on graph view, source is on the left
            """

            newports = {}
            for portname, port in self.ports.items():
                for edge in port.edges:
                    reg_count = edge.attributes.get("registers", 0)

                    while reg_count > 0:
                        name_comp = f"register_{portname}_to_{edge.dest}_{reg_count}"
                        name1 = f"{name_comp}_src"
                        name2 = f"{name_comp}_dst"

                        self.components[name_comp] = Component("register", {})
                        self.components[name_comp].srcports = [name1]
                        self.components[name_comp].dstports = [name2]

                        newports[name1] = Port(
                            name_comp, copy.deepcopy(port.attributes)
                        )
                        newports[name2] = Port(
                            name_comp, copy.deepcopy(port.attributes)
                        )

                        newports[name1].edges.append(Edge(name2, {}))
                        newports[name2].edges.append(Edge(edge.dest, {}))
                        edge.dest = name1

                        # fix manager-subordinate port organization as they are copied from left port, which is not correct
                        # notice that the only case when both
                        #  1. port.parent is None
                        #  2. outgoing edges are not empty
                        # is when port.role = 'subordinate'
                        # therefore fix is always done by swapping the port name2
                        if port.parent is None:
                            newports[name2].attributes["role"] = "manager"
                        # when port.parent is not none, then notice that outgoing connection from port name2 is correct
                        #  as it was correct when similar connection was outgoing from src port
                        # but, srcport is always master
                        # therefore the fix is done by swapping port name1
                        else:
                            newports[name1].attributes["role"] = "subordinate"

                        reg_count -= 1

            self.ports |= newports

            for param, kind in [
                ("id_width", "iw_conv"),
                ("data_width", "dw_conv"),
                ("clock", "cdc"),
                ("protocol", "pr_conv"),
            ]:
                newports = {}

                for portname, port in self.ports.items():
                    for edge in port.edges:
                        destname = edge.dest
                        dest = self.ports[destname]

                        if port.parent is not None and dest.parent == port.parent:
                            continue

                        portattr = port.attributes[param]
                        destattr = dest.attributes[param]

                        if portattr == destattr:
                            continue

                        name_comp = (
                            f"{kind}_{portname}_{portattr}_to_{destname}_{destattr}"
                        )
                        name1 = f"{kind}_{portname}_{portattr}"
                        name2 = f"{kind}_{destname}_{destattr}"

                        self.components[name_comp] = Component(kind, {})
                        self.components[name_comp].srcports = [name1]
                        self.components[name_comp].dstports = [name2]

                        newports[name1] = Port(
                            name_comp, copy.deepcopy(port.attributes)
                        )
                        newports[name2] = Port(
                            name_comp, copy.deepcopy(port.attributes)
                        )

                        newports[name2].attributes[param] = destattr

                        edge.dest = name1
                        newports[name1].edges.append(Edge(name2, {}))
                        newports[name2].edges.append(Edge(destname, {}))

                        # fix manager-subordinate port organization as they are copied from left port, which is not correct
                        # as above
                        if port.parent is None:
                            newports[name2].attributes["role"] = "manager"
                        else:
                            newports[name1].attributes["role"] = "subordinate"

                self.ports = self.ports | newports

            # some fixup
            for comp in self.components.values():
                if comp.kind == "dw_conv":
                    comp.attributes["clock"] = self.ports[comp.srcports[0]].attributes[
                        "clock"
                    ]

        def _print_set_output(self, filename):
            self._print_dest = open(filename, "w")  # noqa: SIM115

        def _print_globals(self):
            print("### GLOBALS ###", file=self._print_dest)
            for k, v in self.globals.items():
                print(f"{k} = {v}", file=self._print_dest)

            self._print_dest.flush()

        def _print_defaults(self):
            print("### DEFAULTS ###", file=self._print_dest)
            for k, v in self.defaults.items():
                print(f"{k} = {v}", file=self._print_dest)

            self._print_dest.flush()

        def _print_clocks(self):
            print("### CLOCKS ###", file=self._print_dest)
            for k, v in self.clocks.items():
                print(f"{k} - freq {v['frequency']}", file=self._print_dest)

            self._print_dest.flush()

        def _print_ports(self):
            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False

            print("### PORTS ###", file=self._print_dest)
            for k, v in self.ports.items():
                print(f"== PORT {k} parent: {v.parent} ==", file=self._print_dest)
                yaml.dump(v.attributes, self._print_dest)

                for edge in v.edges:
                    print(f"- edge to {edge.dest} -", file=self._print_dest)
                    yaml.dump(edge.attributes, self._print_dest)

            self._print_dest.flush()

        def _print_components(self):
            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False

            print("### COMPONENTS ###", file=self._print_dest)
            for k, v in self.components.items():
                print(f"== COMP {k} {v.kind}", file=self._print_dest)
                yaml.dump(v.attributes, self._print_dest)

                print("ports:", file=self._print_dest)
                for port in sorted(v.srcports + v.dstports):
                    print(f"  {port}:", file=self._print_dest)
                    for attrname, attr in sorted(self.ports[port].attributes.items()):
                        print(f"    {attrname} = {attr}", file=self._print_dest)

            self._print_dest.flush()

        def _print_address_maps(self):
            print("### ADDR MAPS ###", file=self._print_dest)
            print("== INTERCONNECT ==", file=self._print_dest)
            for name, entry in self.address_map.items():
                print(f"-- {name} --", file=self._print_dest)
                print(sorted(entry.src), file=self._print_dest)
                print(entry.dest, file=self._print_dest)
                print(entry.base, file=self._print_dest)
                print(entry.size, file=self._print_dest)

            for comp, params in self.components.items():
                if params.kind != "crossbar":
                    continue

                print(f"== CROSSBAR {comp}==", file=self._print_dest)

                for entry in params.address_map:
                    print("--", file=self._print_dest)
                    print(sorted(entry.src), file=self._print_dest)
                    print(entry.dest, file=self._print_dest)
                    print(entry.base, file=self._print_dest)
                    print(entry.size, file=self._print_dest)

            self._print_dest.flush()

        def _print_elements(self, filename=None):
            """Dumps all internally used elements"""
            if filename is not None:
                self._print_set_output(filename)

            self._print_globals()
            self._print_defaults()
            self._print_clocks()
            self._print_ports()
            self._print_components()
            self._print_address_maps()

    return Interconnect()
