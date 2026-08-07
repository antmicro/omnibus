# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import math
import sys

import yaml

from ..types import Component, Edge, Port


class Frontend:
    """
    YAML frontend

    This frontend reads specification from yaml file according to docs/specification.md
    Using this file, all interconnect attributes are populated

    It internally uses 'spec' dictionary for some processing and debug print
    """
    def read_yaml(self, filename):
        """Read yaml and populate internal representation according to the specification.md"""
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

        if self.spec.get('version'):
            self.version = self.spec['version']
        
        if self.spec.get('clocks'):
            self.clocks = self.spec['clocks']

        if self.spec.get('global'):
            #loop because it must overrwrite default parameters but also must not remove non overwritten defaults
            for name, val in self.spec['global'].items():
                self.globals[name] = val
                
            self.name = self.spec['name']

        # mandatory top level fields

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

        for entry in self.address_map.values():
            dest = entry['to']
            base = entry['base']
            size = entry['size']

            if base + size > 2 ** int(self.globals['addr_width']):
                print(f"ERROR: address map entry to {dest} cannot fit in {self.globals['addr_width']} bits, end address is {int(dest) + int(base) - 1}")
    
    def print_spec(self):
        """Dumps current spec to stdout"""
        yaml.dump(self.spec, sys.stdout)
