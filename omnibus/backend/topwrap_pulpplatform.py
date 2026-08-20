# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import sys
import tempfile
from importlib import resources

import yaml

from ..types import MappedComponent


class PulpCrossbar(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = self.name

    def generate_verilog(self, outdir):
        #it appears that the slave/master used in script generation describes connected device role, rather than crossbar port role 
        #therefore swap them internally
        plugin_path = resources.files("omnibus")
        sys.path.append(os.path.join(plugin_path, "third_party", "axi", "scripts"))
        import axi_intercon_gen

        slaves      = {}
        masters     = {}
        
        for portname, port in self.srcports.items():
            masters[portname] = {"id_width": port.attributes['id_width'], "slaves": list(self.dstports.keys())}

        for portname in self.dstports:
            offset = 0
            size   = 0
            
            for entry in self.address_map:
                if entry.dest == portname:
                    offset = entry.base
                    size   = entry.size
                    break
            
            if size == 0:
                print(f"WARNING: rule of size 0 or lack of rule in crossbar {self.name} leading to port {portname}")
                    
            slaves[portname] = {"offset": offset, "size": size}
            
        with tempfile.NamedTemporaryFile("w") as file:
            config = {
                "parameters": {
                    "output_file": os.path.join("src", f"axi_crossbar_{self.name}.sv"),
                    "slaves": slaves,
                    "masters": masters,
                    "atop": 0,
                },
                "vlnv": f"vendor:library:axi_crossbar_{self.name}:1.0",
            }
        
            yaml.dump(config, file)
        
            prevdir = os.getcwd()
            os.chdir(outdir)
            axi_intercon_gen.AxiIntercon(self.name, file.name).write()
            os.chdir(prevdir)

    def generate_hierarchy(self, ports, params):
        port = next(iter(self.srcports.values()))
        ports['clk_i'] = port.attributes['clock']

class PulpCDC(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_cdc_wrapper'

    def generate_verilog(self, outdir):
        if PulpCDC.exists:
            return

        PulpCDC.exists = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        shutil.copyfile(
            os.path.join(src, "axi_cdc.sv"), 
            os.path.join(dst, "axi_cdc_wrapper.sv"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes
        dstattr = next(iter(self.dstports.values())).attributes

        ports['src_clk_i'] = srcattr['clock'] 
        ports['dst_clk_i'] = dstattr['clock']

        params['AxiDataWidth'] = srcattr['data_width']
        params['AxiIdWidth']   = srcattr['id_width']

        params['AxiAddrWidth'] = self.glbattr['addr_width']

class PulpDWConv(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_dw_conv_wrapper'

    def generate_verilog(self, outdir):
        if PulpDWConv.exists:
            return

        PulpDWConv.exists = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        shutil.copyfile(
            os.path.join(src, "axi_dw_converter.sv"), 
            os.path.join(dst, "axi_dw_converter_wrapper.sv"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes
        dstattr = next(iter(self.dstports.values())).attributes

        ports['clk_i'] = srcattr['clock']

        params['AxiMaxReads']         = srcattr.get('axi_max_reads', self.defattr['axi_max_reads'])
        
        params['AxiSrcPortDataWidth'] = srcattr['data_width']
        params['AxiDstPortDataWidth'] = dstattr['data_width']
        params['AxiIdWidth']          = srcattr['id_width']

        params['AxiAddrWidth']        = self.glbattr['addr_width']

class IWConv(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_idwidth_expander'

    def generate_verilog(self, outdir):
        if IWConv.exists:
            return

        IWConv.exists = True

        src = os.path.join(resources.files("omnibus"), "modules")
        dst = os.path.join(outdir, "src")

        shutil.copyfile(
            os.path.join(src, "axi_idwidth_expander.sv"), 
            os.path.join(dst, "axi_idwidth_expander.sv"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        ports['clk_i'] = srcattr['clock']
        
        params['AxiMaxReads']   = srcattr.get('axi_max_reads', self.defattr['axi_max_reads'])

        params['AxiDataWidth']  = srcattr['data_width']
        params['AxiSrcIdWidth'] = srcattr['id_width']
        params['AxiDstIdWidth'] = srcattr['id_width']

        params['AxiAddrWidth']  = self.globals['addr_width']

class PulpPrAXIAPB(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_prconv_axi_apb'

    def generate_verilog(self, outdir):
        if PulpPrAXIAPB.exists:
            return

        PulpDWConv.exists = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")
        inf = os.path.join(resources.files("omnibus"), "interfaces")

        shutil.copyfile(
            os.path.join(src, "axi_pr_axi_apb.sv"), 
            os.path.join(dst, "axi_pr_axi_apb.sv"))
    
        shutil.copyfile(
            os.path.join(inf, "apb.yml"), 
            os.path.join(dst, "apb.yml"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        ports['clk_i'] = srcattr['clock']
    
        params['AxiDataWidth'] = srcattr['data_width']
        params['AxiAddrWidth'] = self.glbattr['addr_width']

        params['AxiIdWidth']   = srcattr['id_width']

class PulpPrAXIAXILite(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_prconv_axi_axilite'

    def generate_verilog(self, outdir):
        if PulpPrAXIAXILite.exists:
            return

        PulpDWConv.exists = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        shutil.copyfile(
            os.path.join(src, "axi_pr_axi_axilite.sv"), 
            os.path.join(dst, "axi_pr_axi_axilite.sv"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        ports['clk_i'] = srcattr['clock']
    
        params['AxiDataWidth'] = srcattr['data_width']
        params['AxiAddrWidth'] = self.glbattr['addr_width']

        params['AxiIdWidth']   = srcattr['id_width']

class PrAXIAHB(MappedComponent):
    exists = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = 'axi_prconv_axi_ahb'

    def generate_verilog(self, outdir):
        if PrAXIAHB.exists:
            return

        PulpDWConv.exists = True

        src = os.path.join(resources.files("omnibus"), "modules")
        dst = os.path.join(outdir, "src")
        inf = os.path.join(resources.files("omnibus"), "interfaces")

        shutil.copyfile(
            os.path.join(src, "axi_pr_axi_ahb.sv"), 
            os.path.join(dst, "axi_pr_axi_ahb.sv"))

        shutil.copyfile(
            os.path.join(src, "beh_lib.sv"), 
            os.path.join(dst, "beh_lib.sv"))

        shutil.copyfile(
            os.path.join(inf, "ahb.yml"), 
            os.path.join(dst, "ahb.yml"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        ports['clk_i'] = srcattr['clock']
    
        params['AxiIdWidth']   = srcattr['id_width']

class Backend:
    """
    Topwrap Pulp Platform backend

    This backend generates components from pulpplatform/axi and creates output readable by topwrap
    It requires somewhat large number of external commands due to how topwrap operates
    See .ci.yml to see what is necessary to fully build existing example

    It contains 3 internal methods:
        map_components     - creates mapping from internal abstract component to real modules
        generate_hierarchy - generate real modules and create final topwrap hierarchy file 
    """
    def generate(self, outdir):
        """Convenience method for internal operation"""
        self.map_components(outdir)
        self.generate_hierarchy(outdir)

    def map_components(self, outdir):
        """
        Map components to their corresponding IP type

        Must be called after all internal processing is done
        """

        #populate defaults
        self.defaults['axi_max_reads'] = self.defaults.get('axi_max_reads', 1)

        registry = {
            'crossbar': PulpCrossbar,
            'dw_conv' : PulpDWConv,
            'cdc'     : PulpCDC,
            'iw_conv' : IWConv,
            'pr_conv' : {'axiaxilite': PulpPrAXIAXILite,
                         'axiapb'    : PulpPrAXIAPB,
                         'axiahb'    : PrAXIAHB
                        }
            }

        self.real_components = []

         #TODO: in the future when proper mapping is implemented, this should include actual choice 
        for name, component in self.components.items():
            srcattr = self.ports[component.srcports[0]].attributes
            dstattr = self.ports[component.dstports[0]].attributes

            if component.kind == 'pr_conv':
                srcattr = srcattr['protocol'].lower()
                dstattr = dstattr['protocol'].lower()
                
                if srcattr not in ['axi', 'axi4']:
                    print(f"ERROR: invalid protocol source, found '{srcattr}' but the only valid one is 'axi4'")
                    return

                if   dstattr in ['ahb', 'ahb3']:
                    self.real_components.append(registry['pr_conv']['axiahb'](name, self.globals, self.defaults, component.address_map))
                elif dstattr in ['apb', 'apb3']:
                    self.real_components.append(registry['pr_conv']['axiapb'](name, self.globals, self.defaults, component.address_map))
                elif dstattr in ['axi4lite', 'axilite', 'axi_lite', 'axi4_lite', 'axi lite', 'axi4 lite']:
                    self.real_components.append(registry['pr_conv']['axiaxilite'](name, self.globals, self.defaults, component.address_map))
                else:
                    print(f"ERROR: invalid protocol destination, found '{dstattr}' but the only valid ones are 'ahb3', 'apb3', 'axi4_lite'")
            else:
                
                self.real_components.append(registry[component.kind](name, self.globals, self.defaults, component.address_map))

            for portname in component.srcports + component.dstports:
                port = self.ports[portname]
                if port.attributes['role'] == "subordinate":
                    self.real_components[-1].srcports[portname] = port
                else:
                    self.real_components[-1].dstports[portname] = port
    
    def generate_hierarchy(self, outdir):
        """
        Generate verilog files and topwrap hierarchy so the final output can be generated
    
        Must be called after map_components()
    
        Currently hardcoded to use modules from pulp-platform/axi
        """

        verilator     = os.path.join(resources.files("omnibus"), "verilator")

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

        #generate verilog files
        for comp in self.real_components:
            comp.generate_verilog(outdir)
     
        #generate topwrap
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

        for comp in self.real_components:
            tree['ips'][comp.name] = {
                'file'      : f"file:{os.path.join(outdir, 'modules', 'cores', comp.ip, 'module.yaml')}",
                'parameters': {}
                }


            tree['connections']['interfaces'][comp.name] = {}
            tree['connections']['ports']     [comp.name] = {}

            comp.generate_hierarchy(
                ports  = tree['connections']['ports'][comp.name],
                params = tree['ips'][comp.name]['parameters']
                )

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
    
        with open(os.path.join(outdir, f"{self.name}.yml"), 'w') as file:
            yaml.dump(tree, file)
    
