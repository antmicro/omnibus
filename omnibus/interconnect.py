import copy
import math
import shutil
import sys
import tempfile
from importlib import resources

import graphviz
import yaml


class Path:
    def __init__(self, start):
        self.curport   = start
        self.startport = start
        self.crossbars = {} 


class Edge:
    def __init__(self, dest, attributes):
        self.dest       = dest
        self.attributes = attributes

class Port:
    def __init__(self, parent, attributes):
        self.parent     = parent
        self.attributes = attributes
        self.edges      = []
        self.backedges  = []


class AddressMapEntry:
    def __init__(self, src, dest, base, size):
        self.src  = src
        self.dest = dest
        self.base = base
        self.size = size

class Component:
    def __init__(self, kind, attributes):
        self.kind       = kind
        self.attributes = attributes
        self.sub_log2   = 0
        self.ports      = []

        self.address_map = []


class Interconnect:
    def __init__(self, filename):
        with open(filename, 'r') as stream:
            self.spec = yaml.load(stream, yaml.Loader)

        # check for mandatory top level fields before any processing
        err = False
        if not self.spec.get('ports'):
            print("ERROR: lack of 'ports' field")
            err = True
        if bool(self.spec.get('crossbars')) ^ bool(self.spec.get('connections')):
            print("ERROR: 'crossbar' and 'connections' must be both either defined or left for inference")
            err = True
        if not self.spec.get('address_map'):
            print("ERROR: lack of 'address_map' field")
            err = True
        if err:
            return

        # process optional top level fields
        if self.spec.get('name'):
            self.name = self.spec['name']
        else:
            self.name = 'interconnect'

        if self.spec.get('version'):
            self.version = self.spec['version']
        else:
            self.version = '0'
        
        if self.spec.get('clocks'):
            self.clocks = self.spec['clocks']
        else:
            self.clocks = {'clk': {'frequency': 'n/a'}}

        # process mandatory top level fields
        self.ports      = {}
        self.components = {}

        # collects start points for later
        # also will be used for address map generation
        self.path_start_points = []

        for k, v in self.spec['ports'].items():
            self.ports[k] = Port(None, v)

            if v['role'] == 'subordinate':
                self.path_start_points.append(k)
            elif v['role'] == 'manager':
                pass
            else:
                print(f"ERROR: entry '{k}' in ports has wrong role, should be either 'manager' or 'subordinate'")
                return

        #if not present, generate all to all
        if not self.spec.get('crossbars'):
            self.spec['crossbars'] = {'main': {'clock': None, 'ports': {}}}
            self.spec['connections'] = {}

            xb_ports = self.spec['crossbars']['main']['ports']
            
            for portname, port in self.ports.items():
                role = port.attributes['role']
                xb_ports[portname] = {'role': role}

                if role == 'subordinate':
                    self.spec['connections'][f"{portname} -> main.{portname}"] = {}
                else:
                    self.spec['connections'][f"main.{portname} -> {portname}"] = {}
                        
        for crossbar, cpars in self.spec['crossbars'].items():
            #store which ports are subs and which are managers, later use this info to create edges
            subs     = []
            managers = []

            if not cpars.get('ports'):
                print(f"ERROR: crossbar '{crossbar}' does not have 'ports' field")
                return 

            self.components[crossbar] = Component('crossbar', cpars)

            clock = cpars.get('clock')

            for k, v in cpars['ports'].items():
                name = crossbar + '_' + k
                self.ports[name] = Port(crossbar, v)
                self.ports[name].attributes['clock'] = clock

                self.components[crossbar].ports.append(name)

                if not v.get('role'):
                    print(f"ERROR: crossbar '{crossbar}'s port '{k}' lacks field 'role'")
                    return

                if v['role'] == "subordinate":
                    subs.append(name)
                elif v['role'] == "manager":
                    managers.append(name)
                else:
                    print(f"ERROR: crossbar '{crossbar}'s port '{k}'s field 'role' should be set either to 'master' or to 'subordinate', was instead set to '{v['role']}'")
           
            for sub in subs: 
                subport = self.ports[sub]

                for manager in managers:
                    subport.edges.append(Edge(manager, {}))
                    self.ports[manager].backedges.append(Edge(sub, {}))
            self.components[crossbar].sub_log2 = math.ceil(math.log2(len(subs)))

        for conn, params in self.spec['connections'].items():
            parts = conn.split(' ')

            if len(parts) != 3 or parts[1] != '->':
                print("ERROR: entry in 'connections' '{conn}' invalid: expected format 'a -> b'")
                return

            parts[0] = parts[0].replace('.','_')
            parts[2] = parts[2].replace('.','_')

            port1 = self.ports.get(parts[0])
            port2 = self.ports.get(parts[2])

            if not port1:
                print(f"ERROR: entry in 'connections' '{conn}' invalid: first port does not exist")
                return
            if not port2:
                print(f"ERROR: entry in 'connections' '{conn}' invalid: second port does not exist")
                return

            
            if params is None:
                params = {}

            #by default, protocol should not be propagated from subordinates 
            if not params.get('protocol') and port2.parent is None:
                params['protocol'] = True

            port1.edges.append(Edge(parts[2], params))
            port2.backedges.append(Edge(parts[0], params))

        self.address_map = self.spec['address_map']

    def find_routing_paths(self):
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
        #data width is a bit special in that it can be forced on connections
        #to deal with this:
        # 1. find all connections that have it forced 
        # 2. assign it to connected ports
        # 3. if this process leads to conflict, there exists no valid configuration

        #id width is handled as fully separate case 
        #finding it requires some degree of backtracking and rewriting already found results
        #
        #  assign all top level subordinate ports id to 1, add them to list 
        #  until the list is empty:
        #    pick any port P from the list 
        #    remove P from the list 
        #    for each destination port D thru crossbar N:1:
        #      if D.id_width >= P.id_width + ceil(log2(N))
        #         continue
        #      else
        #         D.id_width = P.id_width + ceil(log2(N))
        #         add D to list 
        #  within each crossbar, set all subs to maximum id_width among subs 
        #  later, id_width_extender might be needed
        #
        #notice that some nodes WILL be overwritten 

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

        for attr, barrier in {('clock', 'cdc'), ('type', 'protocol'), ('data_width', None)}:

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

                    #all ports in crossbars must share the same parameter type
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
            for portname in comp.ports:
                port = self.ports[portname]

                if port.attributes['role'] == 'subordinate':
                    port.attributes['id_width'] = comp.attributes['sub_id_width']

    def insert_new_components(self):
        #insert components from manager to subordinate components (left to right on graph view)
        #start with highest priority, AKA the ones that should be placed first in case of any conflict
        #current prioretization is: id width > data width > clock > protocol

        #insertion algorithm is:
        # 1. go thru each connection, find connections between ports of different parameters
        # 2. insert two new ports under new component, the kind of component depends on the parameter
        #    also, note if new component kind was inserted, this info will be used during ip generation
        # 3. 
        #   a. for the parameter under consideration, get first's port param from source node, get second's port param from dest 
        #   b. for all the rest parameters, get both ports' params from source port 
        #note: source/dest are regarding edge direction, on graph view, source is on the left 
        for param, kind in [('id_width', 'iw_conv'), ('data_width', 'dw_conv'), ('clock', 'cdc'), ('type', 'pr_conv')]:
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
                    self.components[name_comp].ports = [name1, name2]

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
                comp.attributes['clock'] = self.ports[comp.ports[0]].attributes['clock']

    def map_components(self):
        self.ip_to_gen = set()

        for component in self.components.values():
            #this is mostly a placeholder for now
            #TODO: in the future when proper mapping is implemented, this should include actual choice 
            match component.kind:
                case "crossbar":
                    pass
                case "pr_conv":
                    srcattr = self.ports[component.ports[0]].attributes['type']
                    dstattr = self.ports[component.ports[1]].attributes['type']
                    srcattr = srcattr.lower()
                    dstattr = dstattr.lower()
                
                    if srcattr not in ['axi', 'axi4']:
                        print(f"ERROR: invalid protocol type source, found '{srcattr}' but the only valid one is 'axi4'")
                        return

                    if   dstattr in ['ahb', 'ahb3']:
                        self.ip_to_gen.add('axi_prconv_axi_ahb')
                        component.attributes['ip_type'] = 'axi_prconv_axi_ahb'
                    elif dstattr in ['apb', 'apb3']:
                        self.ip_to_gen.add('axi_prconv_axi_apb')
                        component.attributes['ip_type'] = 'axi_prconv_axi_apb'
                    elif dstattr in ['axi4lite', 'axilite', 'axi_lite', 'axi4_lite']:
                        self.ip_to_gen.add('axi_prconv_axi_axilite')
                        component.attributes['ip_type'] = 'axi_prconv_axi_axilite'
                    else:
                        print(f"ERROR: invalid protocol type destination, found '{component.attributes['to']}' but the only valid ones are 'ahb3', 'apb3', 'axi4_lite'")
                case "dw_conv":
                    self.ip_to_gen.add('axi_dwconv')
                case "cdc":
                    self.ip_to_gen.add("axi_cdc")
                case "iw_conv":
                    self.ip_to_gen.add("iw_conv")
                case _:
                    print("ERROR: invalid kind of component, currently accepted ones are: 'crossbar', 'pr_conv', 'dw_conv', 'cdc'")
                    return

    def generate_ip(self, outdir):
        #for now, assume that all crossbars map to AXI from pulp-platform
        #this will be changed as soon as some way of choosing objects is chosen 
        #for now, each crossbar is generated as its own IP, though this can be later reduced to generating separate IP for each n x m crossbar

        #other IPs are generated manually below

        #it appears that the slave/master used in script generation describes connected device role, rather than crossbar port role 
        #therefore swap them internally
        plugin_path = resources.files("omnibus")
        sys.path.append(str(plugin_path / "third_party" / "axi" / "scripts"))
        import axi_intercon_gen
 
        for name, component in self.components.items():
            if component.kind in ['dw_conv', 'cdc', 'pr_conv', 'iw_conv']:
                pass
            elif component.kind == 'crossbar':
                slaves      = {}
                slave_names = []
                masters     = {}
     
                for port in component.ports:
                    if self.ports[port].attributes['role'] == 'subordinate':
                        masters[port] = {"id_width": self.ports[port].attributes['id_width'], "slaves": slave_names}
                    else:
                        offset = 0
                        size   = 0

                        for entry in component.address_map:
                            if entry.dest == port:
                                offset = entry.base
                                size   = entry.size
                                break

                        if size == 0:
                            print(f"WARNING: rule of size 0 or lack of rule in crossbar {name} leading to port {port}")
                                
                        slaves[port] = {"offset": offset, "size": size}
                        slave_names.append(port)
                
                with tempfile.NamedTemporaryFile("w") as file:
                    config = {
                        "parameters": {
                            "output_file": f"{outdir}/src/axi_crossbar_{name}.sv",
                            "slaves": slaves,
                            "masters": masters,
                            "atop": 0,
                        },
                        "vlnv": f"vendor:library:axi_crossbar_{name}:1.0",
                    }
     
                    yaml.dump(config, file)
     
                    axi_intercon_gen.AxiIntercon(name, file.name).write()
            else:
                print(f"ERROR: cannot generate IP for component '{name}' of type '{component.kind}'")


        pulp_platform = resources.files("omnibus") / "wrappers" / "pulp_platform"
        interfaces    = resources.files("omnibus") / "interfaces"
        modules       = resources.files("omnibus") / "modules"

        if 'axi_dwconv' in self.ip_to_gen:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            shutil.copyfile(pulp_platform / "axi_dw_converter.sv", f"{outdir}/src/axi_dw_converter.sv")

        if 'axi_cdc' in self.ip_to_gen:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            shutil.copyfile(pulp_platform / "axi_cdc.sv", f"{outdir}/src/axi_cdc.sv")

        if 'axi_prconv_axi_axilite' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(pulp_platform / "axi_pr_axi_axilite.sv", f"{outdir}/src/axi_pr_axi_axilite.sv")

        if 'axi_prconv_axi_apb' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(pulp_platform / "axi_pr_axi_apb.sv", f"{outdir}/src/axi_pr_axi_apb.sv")

            shutil.copyfile(interfaces / "apb.yml", f"{outdir}/src/apb.yml")

        if 'axi_prconv_axi_ahb' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(pulp_platform / "axi_pr_axi_ahb.sv", f"{outdir}/src/axi_pr_axi_ahb.sv")

            shutil.copyfile(interfaces / "ahb.yml", f"{outdir}/src/ahb.yml")

        if 'iw_conv' in self.ip_to_gen:
            shutil.copyfile(modules / "axi_idwidth_expander.sv", f"{outdir}/src/axi_idwidth_expander.sv")

    def generate_hierarchy(self, outdir):
        tree = {
            'name': self.name,
            'ips': {}, 
            'connections': {
                'ports': {}, 
                'interfaces': {}}, 
            'external': {
                'ports': {'in': []},
                'interfaces': {'in': [], 'out': []}
            }
        } 

        # external clocks
        tree_ports = tree['external']['ports']
        for name in self.clocks:
            tree_ports['in'].append(name)    
            
            
        # external ports (actually interfaces)
        tree_interfaces  = tree['external']['interfaces']
        for name, port in self.ports.items():
            if port.parent is not None:
                continue

            if port.attributes['role'] == 'subordinate':
                tree_interfaces['in'].append(name)
            else:
                tree_interfaces['out'].append(name)

        #for now, assume that all components map to AXI from pulp-platform
        #TODO: unify this somehow
        for name, component in self.components.items():
            if component.kind == 'crossbar':
                tree['ips'][name] = {}

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/{name}/module.yaml"
                tree['connections']['interfaces'][name] = {}
                
                port = self.ports[component.ports[0]]

                tree['connections']['ports'][name] = {'clk_i': port.attributes['clock']}
            elif component.kind == 'dw_conv':
                tree['ips'][name] = {}

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/axi_dw_conv_wrapper/module.yaml"
                tree['ips'][name]['parameters'] = {}

                tree['connections']['interfaces'][name] = {}
                
                port = self.ports[component.ports[0]]
                tree['connections']['ports'][name] = {'clk_i': port.attributes['clock']}

                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                params = tree['ips'][name]['parameters']

                params['AxiMaxReads']         = 1
                params['AxiSrcPortDataWidth'] = srcport.attributes['data_width']
                params['AxiOutPortDataWidth'] = dstport.attributes['data_width']
                params['AxiAddrWidth']        = 32
                params['AxiIdWidth']          = srcport.attributes['id_width']
            elif component.kind == 'pr_conv':
                tree['ips'][name] = {}

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/{component.attributes['ip_type']}/module.yaml"
                tree['ips'][name]['parameters'] = {}

                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                tree['connections']['ports'][name] = {'clk_i': srcport.attributes['clock']}

                params = tree['ips'][name]['parameters']

                params['AxiDataWidth'] = srcport.attributes['data_width']
                params['AxiAddrWidth'] = 32
                params['AxiIdWidth']   = srcport.attributes['id_width']
            elif component.kind == 'cdc':
                tree['ips'][name] = {}

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/axi_cdc_wrapper/module.yaml"
                tree['ips'][name]['parameters'] = {}

                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                tree['connections']['ports'][name] = {'src_clk_i': srcport.attributes['clock'], 'dst_clk_i': dstport.attributes['clock']}

                params = tree['ips'][name]['parameters']

                params['AxiMaxReads'] = 1
                params['AxiDataWidth'] = srcport.attributes['data_width']
                params['AxiAddrWidth'] = 32
                params['AxiIdWidth']   = srcport.attributes['id_width']
            elif component.kind == 'iw_conv':
                tree['ips'][name] = {}

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/axi_idwidth_expander/module.yaml"
                tree['ips'][name]['parameters'] = {}

                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                tree['connections']['ports'][name] = {'clk_i': srcport.attributes['clock']}

                params = tree['ips'][name]['parameters']

                params['AxiMaxReads']  = 1
                params['AxiDataWidth'] = srcport.attributes['data_width']
                params['AxiAddrWidth'] = 32
                params['AxiSrcIdWidth'] = srcport.attributes['id_width']
                params['AxiDstIdWidth'] = srcport.attributes['id_width']

        for portname, port in self.ports.items():
            for dest in port.edges:
                destname = dest.dest
                destport = self.ports[destname]

                #connections are only added between components
                if port.parent == destport.parent:
                    continue

                portcomp = self.components.get(port.parent)
                destcomp = self.components.get(destport.parent)

                #interfaces can only be defined from IPs 
                #ensure we are not in external interface
                #TODO: this is a bit ugly, find some nicer way
                if port.parent is None:
                    ip = tree['connections']['interfaces'][destport.parent]

                    if destcomp.kind == 'crossbar':
                        ip[destname] = portname
                    else:
                        ip['src'] = portname
                elif destport.parent is None:
                    ip = tree['connections']['interfaces'][port.parent]

                    if portcomp.kind == 'crossbar':
                        ip[portname] = destname
                    else:
                        ip['dst'] = destname
                else:
                    ip = tree['connections']['interfaces'][port.parent]

                    if portcomp.kind == 'crossbar' and destcomp.kind == 'crossbar':
                        ip[portname] = [destport.parent, destname]
                    elif portcomp.kind == 'crossbar':
                        ip[portname] = [destport.parent, 'src']
                    elif destcomp.kind == 'crossbar':
                        ip['dst'] = [destport.parent, destname]
                    else:
                        ip['dst'] = [destport.parent, 'src']

        with open(f"{outdir}/interconnect.yml", 'w') as file:
            yaml.dump(tree, file)

    def print_spec(self):
        yaml.dump(self.spec, sys.stdout)

    def print_elements(self):
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

    def generate_graph(self, filename='interconnect.gv', view=False, color_by=""):
        g = graphviz.Digraph(self.name, filename=filename, node_attr={'style': 'filled', 'colorscheme': 'paired12'})
        g.attr(rankdir='LR')

        #max color id determined by paired12 colorscheme
        param_to_color_id = {}
        color_nxt_id = 1
        color_max_id = 11

        subgraphs = {}

        for port, params in self.ports.items():
            
            color = "white"

            if color_by != "":
                color = None

                paramval = params.attributes.get(color_by)

                if paramval is not None:
                    if not param_to_color_id.get(paramval):
                        if color_nxt_id > color_max_id:
                            print("ERROR: too many different parameter's values to color by")
                            return

                        param_to_color_id[paramval] = str(color_nxt_id)
                        color_nxt_id += 1 

                    color = param_to_color_id[paramval]

                if color is None:
                    color = '12'
            
            if params.parent is None:
                g.node(port, fillcolor=color)

                for edge in params.edges:
                    g.edge(port, edge.dest)
                
                continue

            sg = subgraphs.get(params.parent)
            if not sg:
                #"cluster" is necessary to generate  grouping
                subgraphs[params.parent] = graphviz.Digraph(name='cluster ' + params.parent)
                sg = subgraphs[params.parent]
                sg.attr(label=params.parent)
                sg.attr(style='dashed', color='lightgrey')

            sg.node(port, fillcolor=color)

            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    sg.edge(port, dest)
                

        # create a legend
        if color_by != "":
            legend = graphviz.Digraph(name="cluster legend")
            legend.attr(label="legend")
            legend.attr(color='lightgrey')
            legend.attr(rank="same")
            
            for name, color in param_to_color_id.items():
                name = str(name)
                legend.node(name, fillcolor=color)
                #force layout
                legend.edge(name, "none", style="invis")

            legend.node("none", fillcolor=str(color_max_id + 1))

            #force layout
            g.edge(next(iter(self.ports.keys())), "none", style="invis")

            g.subgraph(legend)

        for sg in subgraphs.values():
            g.subgraph(sg)
    
        if view:
            g.view()
        else:
            g.save()
