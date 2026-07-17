import yaml
import graphviz
import copy
import sys
import importlib.resources
import tempfile


class Path:
    def __init__(self, start):
        self.curport   = start
        self.startport = start
        self.crossbars = dict() 


class Edge:
    def __init__(self, dest, attributes):
        self.dest       = dest
        self.attributes = attributes

class Port:
    def __init__(self, parent, attributes):
        self.parent     = parent
        self.attributes = attributes
        self.edges      = list()
        self.backedges  = list()


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
        self.ports      = list()

        self.address_map = list()


class Interconnect:


    def __init__(self, filename):
        stream = open(filename, 'r')
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
            self.clocks = dict([('clk', dict([('frequency', 'n/a')]))])

        # process mandatory top level fields
        self.ports      = dict()
        self.components = dict()

        # collects start points for later
        # also will be used for address map generation
        self.path_start_points = list()

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
            self.spec['crossbars'] = {'main': {'clock': None, 'ports': dict()}}
            self.spec['connections'] = dict()

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
            subs     = list()
            managers = list()

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
                    subport.edges.append(Edge(manager, dict()))
                    self.ports[manager].backedges.append(Edge(sub, dict()))

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
                params = dict()

            #by default, protocol should not be propagated from subordinates 
            if not params.get('protocol') and port2.parent is None:
                params['protocol'] = True

            port1.edges.append(Edge(parts[2], params))
            port2.backedges.append(Edge(parts[0], params))

        self.address_map = self.spec['address_map']

    def find_routing_paths(self):
        self.paths_to_search = list()
        self.paths_complete  = dict()
        for port in self.path_start_points:
            self.paths_to_search.append(Path(port))

        while len(self.paths_to_search) > 0:
            curpath = self.paths_to_search[0]
            self.paths_to_search.pop(0)

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
        for k, v in self.address_map.items():
            sources = v.get('from')
            if sources is None:
                sources = self.path_start_points

            #fix the case where single port is provided which is parsed as string and not array of strings
            if type(sources) is str:
                sources = [sources]

            dest = v['to']
            base = v['base']
            size = v['size']

            for source in sources:
                for crossbar, port in self.paths_complete[source + ' -> ' + dest].items():
                    self.components[crossbar].address_map.append(AddressMapEntry(source, port, base, size))

        #now sort each address map by (source, dest port, base) in that order
        #after that, check whether one entry is followed directly by another
        #if so, merge them 
        for comp, params in self.components.items():
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

        ports_to_process = list()

        for attr, barrier in {('clock', 'cdc'), ('type', 'protocol'), ('data_width', None)}:

            for portname, port in self.ports.items():
                if port.attributes.get(attr):
                    ports_to_process.append(portname)


            if len(ports_to_process) == 0:
                print(f"WARNING: parameter {attr} is never specified, propagation not possible")
                continue

            while len(ports_to_process) > 0:
                portname = ports_to_process[0]
                ports_to_process.pop(0)

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


        return

    def map_components(self):
        
        for name, component in self.components.items():
            
            match component.kind:
                case "crossbar":
                    pass
                case _:
                    print("ERROR: invalid kind of component, currently accepted ones are: 'crossbar'")
                    return

    def generate_ip(self, outdir):
        #for now, assume that all crossbars map to AXI from pulp-platform
        #this will be changed as soon as some way of choosing objects is chosen 
        #for now, each crossbar is generated as its own IP, though this can be later reduced to generating separate IP for each n x m crossbar

        #it appears that the slave/master used in script generation describes connected device role, rather than crossbar port role 
        #therefore swap them internally
        plugin_path = importlib.resources.files("omnibus")
        sys.path.append(str(plugin_path / "third_party" / "axi" / "scripts"))
        import axi_intercon_gen
 
        for name, component in self.components.items():
            if component.kind != 'crossbar':
                pass
 
            slaves      = dict()
            slave_names = list()
            masters     = dict()
 
            for port in component.ports:
                if self.ports[port].attributes['role'] == 'subordinate':
                    #TODO: find proper id_width instead of using placeholder, requires parameter propagation
                    masters[port] = {"id_width": 2, "slaves": slave_names}
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

    def generate_hierarchy(self, outdir):
        tree = {
            'name': self.name,
            'ips': dict(), 
            'connections': {
                'ports': dict(), 
                'interfaces': dict()}, 
            'external': {
                'ports': {'in': []},
                'interfaces': {'in': [], 'out': []}
            }
        } 

        # external clocks
        tree_ports = tree['external']['ports']
        for clockname, clock in self.clocks.items():
            tree_ports['in'].append(clockname)    
            
            
        # external ports (actually interfaces)
        tree_interfaces  = tree['external']['interfaces']
        for name, port in self.ports.items():
            if port.parent is not None:
                continue

            if port.attributes['role'] == 'subordinate':
                tree_interfaces['in'].append(name)
            else:
                tree_interfaces['out'].append(name)

        #for now, assume that all crossbars map to AXI from pulp-platform
        for name, component in self.components.items():
            if component.kind != 'crossbar':
                pass

            tree['ips'][name] = dict()

            tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/{name}/module.yaml"
            tree['connections']['interfaces'][name] = dict()
            
            tree['connections']['ports'][name] = {'clk_i': component.attributes['clock']}

        for portname, port in self.ports.items():
            for dest in port.edges:
                destname = dest.dest
                destport = self.ports[destname]

                #connections are only added between components
                if port.parent == destport.parent:
                    continue

                #interfaces can only be defined from IPs 
                #ensure we are not in external interface
                if port.parent is None:
                    ip = tree['connections']['interfaces'][destport.parent]
                    ip[destname] = portname
                elif destport.parent is None:
                    ip = tree['connections']['interfaces'][port.parent]
                    ip[portname] = destname
                else:
                    ip = tree['connections']['interfaces'][port.parent]

                    ip[portname] = [destport.parent, destname]

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
        param_to_color_id = dict()
        color_nxt_id = 1
        color_max_id = 11

        crossbars = dict()

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

            cb = crossbars.get(params.parent)
            if not cb:
                #"cluster" is necessary to generate  grouping
                crossbars[params.parent] = graphviz.Digraph(name='cluster ' + params.parent)
                cb = crossbars[params.parent]
                cb.attr(label=params.parent)
                cb.attr(style='dashed', color='lightgrey')

            cb.node(port, fillcolor=color)

            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    cb.edge(port, dest)
                

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
            g.edge(list(self.ports.keys())[0], "none", style="invis")

            g.subgraph(legend)

            

        for k, v in crossbars.items():
            g.subgraph(v)
    
        if view:
            g.view()
        else:
            g.save()
