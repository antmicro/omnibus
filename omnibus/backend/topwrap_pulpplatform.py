# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import sys
import tempfile
from importlib import resources

import yaml


class Backend:
    """
    Topwrap Pulp Platform backend

    This backend generates components from pulpplatform/axi and creates output readable by topwrap
    It requires somewhat large number of external commands due to how topwrap operates
    See .ci.yml to see what is necessary to fully build existing example

    It contains 3 internal methods:
        map_components     - creates mapping from internal abstract component to real modules
        generate_ip        - creates IP for all used modules
        generate_hierarchy - create final topwrap hierarchy file 
    """
    def generate(self, outdir):
        """Convenience method for internal operation"""
        self.map_components()
        self.generate_ip(outdir)
        self.generate_hierarchy(outdir)

    def map_components(self):
        """
        Map components to their corresponding IP type

        Must be called after all internal processing is done
        """
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
        """
        Generate actual IP for each component type needed
    
        Must be called after map_components()
    
        Currently hardcoded to use modules from pulp-platform/axi
        this will be changed as soon as some way of choosing objects is chosen 
    
        Each crossbar is generated as its own IP, though this can be later reduced to generating separate IP for each n x m crossbar
    
        other IPs are generated manually below
        """
    
        #it appears that the slave/master used in script generation describes connected device role, rather than crossbar port role 
        #therefore swap them internally
        plugin_path = resources.files("omnibus")
        sys.path.append(os.path.join(plugin_path, "third_party", "axi", "scripts"))
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
                            "output_file": os.path.join("src", f"axi_crossbar_{name}.sv"),
                            "slaves": slaves,
                            "masters": masters,
                            "atop": 0,
                        },
                        "vlnv": f"vendor:library:axi_crossbar_{name}:1.0",
                    }
     
                    yaml.dump(config, file)
     
                    prevdir = os.getcwd()
                    os.chdir(outdir)
                    axi_intercon_gen.AxiIntercon(name, file.name).write()
                    os.chdir(prevdir)
            else:
                print(f"ERROR: cannot generate IP for component '{name}' of type '{component.kind}'")
    
    
        pulp_platform = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        interfaces    = os.path.join(resources.files("omnibus"), "interfaces")
        modules       = os.path.join(resources.files("omnibus"), "modules")
        verilator     = os.path.join(resources.files("omnibus"), "verilator")
    
        if 'axi_dwconv' in self.ip_to_gen:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            shutil.copyfile(
                os.path.join(pulp_platform, "axi_dw_converter.sv"), 
                os.path.join(outdir, "src", "axi_dw_converter_wrapper.sv"))
    
        if 'axi_cdc' in self.ip_to_gen:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            shutil.copyfile(
                os.path.join(pulp_platform, "axi_cdc.sv"), 
                os.path.join(outdir, "src", "axi_cdc_wrapper.sv"))
    
        if 'axi_prconv_axi_axilite' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(
                os.path.join(pulp_platform, "axi_pr_axi_axilite.sv"), 
                os.path.join(outdir, "src", "axi_pr_axi_axilite.sv"))
    
        if 'axi_prconv_axi_apb' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(
                os.path.join(pulp_platform, "axi_pr_axi_apb.sv"), 
                os.path.join(outdir, "src", "axi_pr_axi_apb.sv"))
    
            shutil.copyfile(
                os.path.join(interfaces,    "apb.yml"), 
                os.path.join(outdir, "src", "apb.yml"))
    
        if 'axi_prconv_axi_ahb' in self.ip_to_gen:
            #NOTE: this file is currently only a stub 
            shutil.copyfile(
                os.path.join(modules, "axi_pr_axi_ahb.sv"), 
                os.path.join(outdir,  "src", "axi_pr_axi_ahb.sv"))

            shutil.copyfile(
                os.path.join(modules, "beh_lib.sv"), 
                os.path.join(outdir,  "src", "beh_lib.sv"))

            shutil.copyfile(
                os.path.join(interfaces,    "ahb.yml"), 
                os.path.join(outdir, "src", "ahb.yml"))
    
        if 'iw_conv' in self.ip_to_gen:
            shutil.copyfile(
                os.path.join(modules,       "axi_idwidth_expander.sv"), 
                os.path.join(outdir, "src", "axi_idwidth_expander.sv"))

        #create waivers for verilator
        shutil.copyfile(
            os.path.join(verilator,             "general_config.vlt"), 
            os.path.join(outdir,   "verilator", "general_config.vlt"))
        shutil.copyfile(
            os.path.join(verilator,             "pulp_platform_config.vlt"), 
            os.path.join(outdir,   "verilator", "pulp_platform_config.vlt"))

        #create filelists
        shutil.copyfile(
            os.path.join(verilator,             "general_filelist.vc"), 
            os.path.join(outdir,   "verilator", "general_filelist.vc"))
        shutil.copyfile(
            os.path.join(verilator,             "pulp_platform_filelist.vc"), 
            os.path.join(outdir,   "verilator", "pulp_platform_filelist.vc"))
    
    def generate_hierarchy(self, outdir):
        """
        Generate topwrap hierarchy so the final verilog output can be generated
    
        Must be called after generate_ip()
    
        Currently hardcoded to use modules from pulp-platform/axi
        """
    
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
    
                tree['ips'][name]['file'] = f"file:{os.path.join(outdir, 'modules', 'cores', name, 'module.yaml')}"
                tree['connections']['interfaces'][name] = {}
                
                port = self.ports[component.ports[0]]
    
                tree['connections']['ports'][name] = {'clk_i': port.attributes['clock']}
            elif component.kind == 'dw_conv':
                tree['ips'][name] = {}
    
                tree['ips'][name]['file'] = f"file:{os.path.join(outdir, 'modules', 'cores' , 'axi_dw_conv_wrapper', 'module.yaml')}"
                tree['ips'][name]['parameters'] = {}
    
                tree['connections']['interfaces'][name] = {}
                
                port = self.ports[component.ports[0]]
                tree['connections']['ports'][name] = {'clk_i': port.attributes['clock']}
    
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]
    
                params = tree['ips'][name]['parameters']
    
                axi_max_reads = srcport.attributes.get('axi_max_reads')

                if axi_max_reads is None:
                    axi_max_reads = self.globals.get('axi_max_reads')
                if axi_max_reads is None:
                    print("WARNING: nonexistent parameter axi_max_reads, defaulting to 1")
                    axi_max_reads = 1

                params['AxiMaxReads']         = axi_max_reads
                params['AxiSrcPortDataWidth'] = srcport.attributes['data_width']
                params['AxiDstPortDataWidth'] = dstport.attributes['data_width']
                params['AxiAddrWidth']        = self.globals['addr_width']
                params['AxiIdWidth']          = srcport.attributes['id_width']
            elif component.kind == 'pr_conv':
                tree['ips'][name] = {}
    
                tree['ips'][name]['file'] = f"file:{os.path.join(outdir, 'modules', 'cores' , component.attributes['ip_type'], 'module.yaml')}"
                tree['ips'][name]['parameters'] = {}
    
                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]
    
                tree['connections']['ports'][name] = {'clk_i': srcport.attributes['clock']}
    
                params = tree['ips'][name]['parameters']
    
                if dstport.attributes['type'] not in ['ahb', 'ahb3']:
                    params['AxiDataWidth'] = srcport.attributes['data_width']
                    params['AxiAddrWidth'] = self.globals['addr_width']
                    #TODO: error checking

                params['AxiIdWidth']   = srcport.attributes['id_width']

            elif component.kind == 'cdc':
                tree['ips'][name] = {}
    
                tree['ips'][name]['file'] = f"file:{os.path.join(outdir, 'modules', 'cores' , 'axi_cdc_wrapper', 'module.yaml')}"
                tree['ips'][name]['parameters'] = {}
    
                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]
    
                tree['connections']['ports'][name] = {'src_clk_i': srcport.attributes['clock'], 'dst_clk_i': dstport.attributes['clock']}
    
                params = tree['ips'][name]['parameters']
    
                params['AxiDataWidth'] = srcport.attributes['data_width']
                params['AxiAddrWidth'] = self.globals['addr_width']
                params['AxiIdWidth']   = srcport.attributes['id_width']

            elif component.kind == 'iw_conv':
                tree['ips'][name] = {}
    
                tree['ips'][name]['file'] = f"file:{os.path.join(outdir, 'modules', 'cores' , 'axi_idwidth_expander', 'module.yaml')}"
                tree['ips'][name]['parameters'] = {}
    
                tree['connections']['interfaces'][name] = {}
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]
    
                tree['connections']['ports'][name] = {'clk_i': srcport.attributes['clock']}
    
                params = tree['ips'][name]['parameters']
    
                axi_max_reads = srcport.attributes.get('axi_max_reads')

                if axi_max_reads is None:
                    axi_max_reads = self.globals.get('axi_max_reads')
                if axi_max_reads is None:
                    print("WARNING: nonexistent parameter axi_max_reads, defaulting to 1")
                    axi_max_reads = 1


                params['AxiMaxReads']   = axi_max_reads
                params['AxiDataWidth']  = srcport.attributes['data_width']
                params['AxiAddrWidth']  = self.globals['addr_width']
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
    
        with open(os.path.join(outdir, "interconnect.yml"), 'w') as file:
            yaml.dump(tree, file)
    
