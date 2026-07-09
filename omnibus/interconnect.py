import yaml
import graphviz
import copy


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
        if not self.spec.get('crossbars'):
            print("ERROR: lack of 'crossbars' field")
            err = True
        if not self.spec.get('connections'):
            print("ERROR: lack of 'connections' field")
            return
        if not self.spec.get('address_map'):
            print("ERROR: lack of 'address_map' field")
            return
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
        
        for crossbar, cpars in self.spec['crossbars'].items():
            #store which ports are subs and which are managers, later use this info to create edges
            subs     = list()
            managers = list()

            if not cpars.get('ports'):
                print(f"ERROR: crossbar '{crossbar}' does not have 'ports' field")
                return 

            self.components[crossbar] = Component('crossbar', cpars)

            for k, v in cpars['ports'].items():
                name = crossbar + '.' + k
                self.ports[name] = Port(crossbar, v)

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

        for conn, params in self.spec['connections'].items():
            parts = conn.split(' ')

            if len(parts) != 3 or parts[1] != '->':
                print("ERROR: entry in 'connections' '{conn}' invalid: expected format 'a -> b'")
                return

            port1 = self.ports.get(parts[0])
            port2 = self.ports.get(parts[2])

            if not port1:
                print("ERROR: entry in 'connections' '{conn}' invalid: first port does not exist")
                return
            if not port2:
                print("ERROR: entry in 'connections' '{conn}' invalid: second port does not exist")
                return

            port1.edges.append(Edge(parts[2], params))

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

    def print_spec(self):
        print(self.spec)

    def print_elements(self):
        print("### PORTS ###")
        for k, v in self.ports.items():
            print(f"== PORT {k} parent: {v.parent} ==")
            print(v.attributes)

            for edge in v.edges:
                print(f"- edge to {edge.dest} -")
                print(edge.attributes)

        print("### COMPONENTS ###")

        for k, v in self.components.items():
            print(f"== COMP {k} {v.kind}")

            print(v.attributes)
            print(v.ports)

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


    def generate_graph(self, filename='interconnect.gv', view=False):
        g = graphviz.Digraph(self.name, filename=filename)

        g.attr(rankdir='LR')

        crossbars = dict()

        for port, params in self.ports.items():

            if params.parent is None:
                g.node(port)

                for edge in params.edges:
                    g.edge(port, edge.dest)
                
                continue

            cb = crossbars.get(params.parent)
            if not cb:
                #"==cluster" is necessary to generate  grouping
                crossbars[params.parent] = graphviz.Digraph(name='cluster ' + params.parent)
                cb = crossbars[params.parent]
                cb.attr(label=params.parent)
                cb.attr(style='dashed', color='lightgrey')

            cb.node(port)

            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    cb.edge(port, dest)
                

        for k, v in crossbars.items():
            g.subgraph(v)
    
        if view:
            g.view()
        else:
            g.save()
        



            
