# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import copy
import sys
from importlib import import_module

import yaml

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
    be = import_module(f".backend.{backend}",   "omnibus")

    class Interconnect(fe.Frontend, be.Backend):
        def __init__(self):
            self.name = 'interconnect'
            self.version = '0'
            self.clocks = {'clk': {'frequency': 'n/a'}}
            self.globals  = {'addr_width': 32}
            self.defaults = {}

            self.ports       = {}
            self.components  = {}
            self.address_map = {}

            # collects start points for later
            # also will be used for address map generation
            self.path_start_points = []

        def process(self):
            """Shorthand for internal processing"""
            self.find_routing_paths()
            self.propagate_parameters()
            self.insert_new_components()

        def find_routing_paths(self):
            """
            Finds all paths from interconnect masters to subordinates and sets up address map for each crossbar
            """
            self.paths_to_search = []
            self.paths_complete  = {}

            for port in self.path_start_points:
                self.paths_to_search.append(Path(port))

            while len(self.paths_to_search) > 0:
                curpath = self.paths_to_search.pop(0)

                curport = self.ports[curpath.curport]

                if curport.attributes['role'] == 'manager':
                    #on toplevel, search is complete
                    #on crossbar, expand address map
                    if curport.parent is None:
                        #curport used above is Port object, while endport should be string identifier
                        self.paths_complete[curpath.startport + ' -> ' + curpath.curport] = curpath.crossbars
                        continue
                    
                    #again, we need string not object 
                    curpath.crossbars[curport.parent] = curpath.curport 

                # for each outgoing node create new path
                for destport in curport.edges:
                    newpath = copy.deepcopy(curpath)
                    newpath.curport = destport.dest
                    self.paths_to_search.append(newpath)
            
            # generate address maps here
            for entry in self.address_map.values():
                sources = entry.get('from')
                if sources is None:
                    sources = self.path_start_points

                #fix the case where single port is provided which is parsed as string and not array of strings
                if type(sources) is str:
                    sources = [sources]

                dest = entry['to']
                base = entry['base']
                size = entry['size']

                for source in sources:
                    if not self.paths_complete.get(source + ' -> ' + dest):
                        print(f"ERROR: interconnect is not fully connected, lack of path from {source} to {dest}")
                        return
                    for crossbar, port in self.paths_complete[source + ' -> ' + dest].items():
                        self.components[crossbar].address_map.append(AddressMapEntry(source, port, base, size))

            #now sort each address map by (source, dest port, base) in that order
            #after that, check whether one entry is followed directly by another
            #if so, merge them 
            for params in self.components.values():
                if params.kind != 'crossbar':
                    continue

                params.address_map = sorted(params.address_map, key=lambda x: (x.src, x.dest, x.base))

                ii = 0
                while ii < len(params.address_map) - 1:
                    cur = params.address_map[ii]
                    nxt = params.address_map[ii + 1]
                    
                    if( 
                        cur.src  == nxt.src  and 
                        cur.dest == nxt.dest and 
                        nxt.base == cur.base + cur.size
                      ):
                        cur.size = cur.size + nxt.size
                        params.address_map.pop(ii + 1)
                        continue

                    ii = ii + 1

                #for now, it is not possible to have address map entries with different source IDs 
                #if two rules match in all but first name, merge them, otherwise throw an error
                #there should be check to ensure address map has indeed entries for each source->dest pair, but assume this is the case for now 
                params.address_map = sorted(params.address_map, key=lambda x: (x.dest, x.src))

                ii = 0
                while ii < len(params.address_map) - 1:
                    cur = params.address_map[ii]
                    nxt = params.address_map[ii + 1]
                    
                    if cur.dest == nxt.dest:

                        if cur.base == nxt.base and cur.size == nxt.size:
                            params.address_map.pop(ii + 1)
                        else:
                            print(f"ERROR: it is not possible yet to have address map rules that are different based on source id, rule to {cur.dest} has different paths from {cur.src} and {nxt.src}")
                            params.address_map.pop(ii + 1)

                        continue

                    ii = ii + 1

                for entry in params.address_map:
                    entry.src = '_'

        def propagate_parameters(self):
            """
            Propagate all parameters such that each port has all parameters assigned

            Must be called before insert_new_components()

            Internally the tool copies parameters from one port to each of its neighbors, ignoring direction of edges

            Certain parameters assignable to edge are also copied to neighboring ports

            data width is special in that it can be forced on connections
            to deal with this:
             1. find all connections that have it forced 
             2. assign it to connected ports
             3. if this process leads to conflict, there exists no valid configuration
            later handle it like most other parameters

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

            for portname, port in self.ports.items():
                for edge in port.edges:
                    if edge.attributes.get('axi_max_reads'):
                        port.attributes['axi_max_reads'] = edge.attributes['axi_max_reads']

            for portname, port in self.ports.items():
                for edge in port.edges:
                    destname = edge.dest
                    dest = self.ports[destname]

                    data_width = edge.attributes.get('data_width')

                    if data_width is None:
                        continue
                    
                    port_width = port.attributes.get('data_width')
                    dest_width = dest.attributes.get('data_width')

                    if port_width != data_width:
                        print(f"ERROR: no valid configuration exists for data width, port {portname} has assigned data width that is different than its outgoing connection to {destname}")

                        continue
                    if dest_width != data_width:
                        print(f"ERROR: no valid configuration exists for data width, port {destname} has assigned data width that is different than its incoming connection from {portname}")

                        continue

                    port.attributes['data_width'] = data_width
                    dest.attributes['data_width'] = data_width


            ports_to_process = []

            for attr, barrier in {('clock', 'cdc'), ('protocol', 'protocol'), ('data_width', None)}:

                for portname, port in self.ports.items():
                    if port.attributes.get(attr):
                        ports_to_process.append(portname)


                if len(ports_to_process) == 0:
                    print(f"WARNING: parameter {attr} is never specified, propagation not possible")
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

                        #all ports in crossbars must share the same parameter protocol
                        #NOTE: this probably should be done smarter, include some metric for picking best attribute for crossbar
                        #      metrics can include: majority, throughput, latency, etc
                        parent = dest.parent
                        for childportname, childport in self.ports.items():
                            if childport.parent == parent:
                                childport.attributes[attr] = port.attributes[attr]
                                ports_to_process.append(childportname)

                #if by this point attribute is not populated, then this must be an error and proper propagation is impossible
                #this might happen eg when a region is fully surrounded by CDC and no clock is provided inside
                for portname, port in self.ports.items():
                    if not port.attributes.get(attr):
                        print(f"ERROR: could not propagate attribute '{attr}' to port '{portname}', it is likely surrounded by barriers that stop propagation")

            ports_to_process = []

            for portname, port in self.ports.items():
                if port.parent is None and port.attributes['role'] == 'subordinate':
                    port.attributes['id_width'] = 1
                    ports_to_process.append(portname)

            while len(ports_to_process) > 0:
                portname = ports_to_process.pop(0)
                port     = self.ports[portname]
                id_width = port.attributes['id_width']

                for edge in port.edges:
                    destname = edge.dest
                    dest     = self.ports[destname]

                    #separate handling for crossbars 
                    if port.parent is not None and port.parent == dest.parent:
                        crossbar = self.components[port.parent]

                        if dest.attributes.get('id_width', 0) <= id_width + crossbar.sub_log2:
                            ports_to_process.append(destname)
                            dest.attributes['id_width'] = id_width + crossbar.sub_log2

                            crossbar.attributes['sub_id_width'] = max(crossbar.attributes.get('sub_id_width', 0), id_width) 

                    else:
                        if dest.attributes.get('id_width', 0) <= id_width :
                            ports_to_process.append(destname)
                            dest.attributes['id_width'] = id_width

            for comp in self.components.values():
                for portname in comp.srcports:
                    self.ports[portname].attributes['id_width'] = comp.attributes['sub_id_width']

        def insert_new_components(self):
            """
            Insert components for each parameter value crossing, e.g. CDC between different clocks
            
            Must be called after propagate_parameters()

            insertion start with highest priority, AKA the ones that should be placed first in case of multiple conversions on single connection
            current prioretization is: id width > data width > clock > protocol

            insertion algorithm is:
             1. go thru each connection, find connections between ports of different parameters
             2. insert two new ports under new component, the kind of component depends on the parameter
                also, note if new component kind was inserted, this info will be used during ip generation
             3. 
               a. for the parameter under consideration, get first's port param from source node, get second's port param from dest 
               b. for all the rest parameters, get both ports' params from source port 
            note: source/dest are regarding edge direction, on graph view, source is on the left 
            """
            for param, kind in [('id_width', 'iw_conv'), ('data_width', 'dw_conv'), ('clock', 'cdc'), ('protocol', 'pr_conv')]:
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

                        name_comp = f"{kind}_{portname}_{portattr}_to_{destname}_{destattr}"
                        name1 = f"{kind}_{portname}_{portattr}"
                        name2 = f"{kind}_{destname}_{destattr}"

                        self.components[name_comp] = Component(kind, {})
                        self.components[name_comp].srcports = [name1]
                        self.components[name_comp].dstports = [name2]

                        newports[name1] = Port(name_comp, copy.deepcopy(port.attributes))
                        newports[name2] = Port(name_comp, copy.deepcopy(port.attributes))

                        newports[name2].attributes[param] = destattr

                        edge.dest = name1
                        newports[name1].edges.append(Edge(name2, {}))
                        newports[name2].edges.append(Edge(destname, {}))


                        #fix manager-subordinate port organization as they are copied from left port, which is not correct
                        #notice that the only case when both 
                        #  1. port.parent is None
                        #  2. outgoing edges are not empty 
                        # is when port.role = 'subordinate' 
                        # therefore fix is always done by swapping the port name2
                        if port.parent is None:
                            newports[name2].attributes['role'] = 'manager'
                        # when port.parent is not none, then notice that outgoing connection from port name2 is correct
                        #  as it was correct when similar connection was outgoing from src port
                        # but, srcport is always master
                        # therefore the fix is done by swapping port name1
                        else:
                            newports[name1].attributes['role'] = 'subordinate'

                self.ports = self.ports | newports

            #some fixup 
            for comp in self.components.values():
                if comp.kind == 'dw_conv':
                    comp.attributes['clock'] = self.ports[comp.srcports[0]].attributes['clock']

        def print_elements(self):
            """Dumps all internally used elements"""

            print("### GLOBALS ###")
            for k, v in self.globals.items():
                print(f"{k} = {v}")

            print("### DEFAULTS ###")
            for k, v in self.defaults.items():
                print(f"{k} = {v}")

            print("### PORTS ###")
            for k, v in self.ports.items():
                print(f"== PORT {k} parent: {v.parent} ==")
                print(sorted(v.attributes.items()))

                for edge in v.edges:
                    print(f"- edge to {edge.dest} -")
                    print(sorted(edge.attributes.items()))

            print("### COMPONENTS ###")
            for k, v in self.components.items():
                print(f"== COMP {k} {v.kind}")
                yaml.dump(v.attributes, sys.stdout, sort_keys=True)

            print("### ADDR MAPS ###")
            print("== INTERCONNECT ==") 
            print(self.address_map)

            for comp, params in self.components.items():
                if params.kind != 'crossbar':
                    continue

                print(f"== CROSSBAR {comp}==")

                for entry in params.address_map:
                    print('--')
                    print(entry.src + ' ' + entry.dest)
                    print(hex(entry.base) + ' ' + hex(entry.size))

    return Interconnect()
