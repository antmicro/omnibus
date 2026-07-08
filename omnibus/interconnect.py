import yaml
import graphviz


class Edge:
    def __init__(self, dest, attributes):
        self.dest       = dest
        self.attributes = attributes

class Port:
    def __init__(self, kind, attributes):
        self.kind       = kind
        self.attributes = attributes
        self.edges      = list()

class Component:
    def __init__(self, kind, attributes):
        self.kind       = kind
        self.attributes = attributes
        self.ports      = list()

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

        for k, v in self.spec['ports'].items():
            self.ports[k] = Port('toplevel', v)
        
        for crossbar, cpars in self.spec['crossbars'].items():
            #store which ports are subs and which are managers, later use this info to create egdes
            subs     = list()
            managers = list()


            if not cpars.get('ports'):
                print(f"ERROR: crossbar '{crossbar}' does not have 'ports' field")
                return 


            self.components[crossbar] = Component('crossbar', cpars)


            for k, v in cpars['ports'].items():
                name = crossbar + '.' + k
                self.ports[name] = Port('crossbar ' + crossbar, v)

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
            #ignore params for now

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


    def print_spec(self):
        print(self.spec)

    def print_elements(self):
        print("### PORTS ###")
        for k, v in self.ports.items():
            print(f"== PORT {k} {v.kind} ==")
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
        print(self.address_map)


    def generate_graph(self, filename='interconnect.gv', view=False):
        g = graphviz.Digraph(self.name, filename=filename)

        g.attr(rankdir='LR')

        crossbars = dict()

        for port, params in self.ports.items():

            if params.kind == 'toplevel':
                g.node(port)

                for edge in params.edges:
                    g.edge(port, edge.dest)
                
                continue

            cb = crossbars.get(params.kind)
            if not cb:
                #"cluster" is necessary to generate  grouping
                crossbars[params.kind] = graphviz.Digraph(name='cluster_' + params.kind)
                cb = crossbars[params.kind]
                cb.attr(label=params.kind)
                cb.attr(style='dashed', color='lightgrey')

            cb.node(port)

            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].kind != self.ports[port].kind:
                    g.edge(port, dest)
                else:
                    cb.edge(port, dest)
                

        for k, v in crossbars.items():
            g.subgraph(v)
    
        if view:
            g.view()
        else:
            g.save()
        



            
