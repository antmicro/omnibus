# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import sys
import tempfile
from importlib import resources

import ruamel.yaml

from ..types import MappedComponent

filelist = []


def set_clock_and_reset(ports, clk, prefix=""):
    clk = clk.removeprefix("clk_")
    clk = clk.removeprefix("clk")

    if len(clk) > 0:
        ports[f"{prefix}clk_i"] = f"clk_{clk}_i"
        ports[f"{prefix}rst_ni"] = f"rst_{clk}_ni"
    else:
        ports[f"{prefix}clk_i"] = "clk_i"
        ports[f"{prefix}rst_ni"] = "rst_ni"


class PulpCrossbar(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = f"axi_crossbar_{self.name}"

    def generate_verilog(self, outdir, exists, errors, warns):
        # the slave/master used in script generation describes connected device role, rather than crossbar port role
        # therefore swap them internally
        plugin_path = resources.files("omnibus")
        sys.path.append(os.path.join(plugin_path, "third_party", "axi", "scripts"))
        import axi_intercon_gen

        slaves = {}
        masters = {}

        for portname, port in self.srcports.items():
            masters[portname] = {
                "id_width": port.attributes["id_width"],
                "slaves": list(self.dstports.keys()),
            }

        for portname in self.dstports:
            offsets = []
            sizes = []

            for entry in self.address_map:
                if entry.dest == portname:
                    offsets.append(entry.base)
                    sizes.append(entry.size)

            if len(sizes) == 0:
                warns.append(
                    f"WARNING: lack of addresses in crossbars {self.name} leading to port {portname}"
                )
            for size in sizes:
                if size == 0:
                    warns.append(
                        f"WARNING: address range of size 0 in crossbar {self.name} leading to port {portname}"
                    )

            slaves[portname] = {"offsets": offsets, "sizes": sizes}

        with tempfile.NamedTemporaryFile("w") as file:
            srcattr = next(iter(self.srcports.values())).attributes
            config = {
                "parameters": {
                    "output_file": os.path.join("src", f"axi_crossbar_{self.name}.sv"),
                    "slaves": slaves,
                    "masters": masters,
                    "addr_width": self.glbattr["addr_width"],
                    "data_width": srcattr["data_width"],
                    "atop": 0,
                },
                "vlnv": f"vendor:library:axi_crossbar_{self.name}:1.0",
            }

            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False
            yaml.dump(config, file)
            file.flush()

            prevdir = os.getcwd()
            os.chdir(outdir)
            save_stdout = sys.stdout
            with open(os.devnull, "w") as sys.stdout:
                axi_intercon_gen.AxiIntercon(
                    f"axi_crossbar_{self.name}", file.name
                ).write()
            sys.stdout = save_stdout
            os.chdir(prevdir)

        filelist.append(str(os.path.join("src", f"axi_crossbar_{self.name}.sv")))

    def generate_hierarchy(self, ports, params):
        set_clock_and_reset(
            ports, next(iter(self.srcports.values())).attributes["clock"]
        )


class PulpCDC(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_cdc_wrapper"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpCDC"):
            return
        exists["PulpCDC"] = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        filename = f"{self.core}.sv"
        shutil.copyfile(os.path.join(src, filename), os.path.join(dst, filename))

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes
        dstattr = next(iter(self.dstports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"], prefix="src_")
        set_clock_and_reset(ports, dstattr["clock"], prefix="dst_")

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiIdWidth"] = srcattr["id_width"]

        params["AxiAddrWidth"] = self.glbattr["addr_width"]


class PulpDWConv(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_dw_conv_wrapper"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpDWConv"):
            return
        exists["PulpDWConv"] = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        filename = f"{self.core}.sv"
        shutil.copyfile(
            os.path.join(src, filename),
            os.path.join(dst, filename),
        )

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes
        dstattr = next(iter(self.dstports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiMaxReads"] = srcattr.get(
            "axi_max_reads", self.defattr["axi_max_reads"]
        )

        params["AxiSrcPortDataWidth"] = srcattr["data_width"]
        params["AxiDstPortDataWidth"] = dstattr["data_width"]
        params["AxiIdWidth"] = srcattr["id_width"]

        params["AxiAddrWidth"] = self.glbattr["addr_width"]


class IWConv(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_idwidth_expander"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("IWConv"):
            return
        exists["IWConv"] = True

        src = os.path.join(resources.files("omnibus"), "modules")
        dst = os.path.join(outdir, "src")

        filename = f"{self.core}.sv"
        shutil.copyfile(
            os.path.join(src, filename),
            os.path.join(dst, filename),
        )

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiMaxReads"] = srcattr.get(
            "axi_max_reads", self.defattr["axi_max_reads"]
        )

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiSrcIdWidth"] = srcattr["id_width"]
        params["AxiDstIdWidth"] = srcattr["id_width"]

        params["AxiAddrWidth"] = self.globals["addr_width"]


class PulpPrAXIAPB(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_prconv_axi_apb"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpPrAXIAPB"):
            return
        exists["PulpPrAXIAPB"] = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")
        inf = os.path.join(resources.files("omnibus"), "interfaces")
        dstinf = os.path.join(outdir, "interfaces", "interfaces")

        filename = f"{self.core}.sv"
        shutil.copyfile(
            os.path.join(src, filename),
            os.path.join(dst, filename),
        )

        shutil.copyfile(os.path.join(inf, "apb.yml"), os.path.join(dstinf, "apb.yml"))

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiAddrWidth"] = self.glbattr["addr_width"]

        params["AxiIdWidth"] = srcattr["id_width"]


class PulpPrAXIAXILite(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_prconv_axi_axilite"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpPrAXIAXILite"):
            return
        exists["PulpPrAXIAXILite"] = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        filename = f"{self.core}.sv"
        shutil.copyfile(
            os.path.join(src, filename),
            os.path.join(dst, filename),
        )

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiAddrWidth"] = self.glbattr["addr_width"]

        params["AxiIdWidth"] = srcattr["id_width"]


class PrAXIAHB(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_prconv_axi_ahb"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpPrAXIAHB"):
            return
        exists["PulpPrAXIAHB"] = True

        src = os.path.join(resources.files("omnibus"), "modules")
        dst = os.path.join(outdir, "src")
        inf = os.path.join(resources.files("omnibus"), "interfaces")
        dstinf = os.path.join(outdir, "interfaces", "interfaces")

        for filename in (f"{self.core}.sv", "axi_prconv_fifo.sv"):
            shutil.copyfile(
                os.path.join(src, filename),
                os.path.join(dst, filename),
            )
            filelist.append(str(os.path.join("src", filename)))

        shutil.copyfile(os.path.join(inf, "ahb.yml"), os.path.join(dstinf, "ahb.yml"))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiAddrWidth"] = self.glbattr["addr_width"]
        params["AxiIdWidth"] = srcattr["id_width"]


class PulpRegister(MappedComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core = "axi_buffer_wrapper"

    def generate_verilog(self, outdir, exists, errors, warns):
        if exists.get("PulpRegister"):
            return
        exists["PulpRegister"] = True

        src = os.path.join(resources.files("omnibus"), "wrappers", "pulp_platform")
        dst = os.path.join(outdir, "src")

        filename = f"{self.core}.sv"
        shutil.copyfile(os.path.join(src, filename), os.path.join(dst, filename))

        filelist.append(str(os.path.join("src", filename)))

    def generate_hierarchy(self, ports, params):
        srcattr = next(iter(self.srcports.values())).attributes

        set_clock_and_reset(ports, srcattr["clock"])

        params["AxiDataWidth"] = srcattr["data_width"]
        params["AxiAddrWidth"] = self.glbattr["addr_width"]

        params["AxiIdWidth"] = srcattr["id_width"]


class Backend:
    """
    Topwrap Pulp Platform backend

    This backend generates components from pulpplatform/axi and creates output readable by topwrap
    It requires somewhat large number of external commands due to how topwrap operates
    See .ci.yml and tests/test_topwrapintegration.py to see what is necessary to fully build existing example

    It contains 2 internal methods:
        map_components     - creates mapping from internal abstract component to real modules
        generate_hierarchy - generate real modules and create final topwrap hierarchy file
    """

    #: schema of the parameters this backend adds, next to this file
    SCHEMA_EXTENSION = "topwrap_pulpplatform.schema.yml"

    def __init__(self):
        self.parse_global = {}
        self.parse_default = {"axi_max_reads": self._parse_positive_int}

        self.parse_connections = {"axi_max_reads": self._parse_positive_int}
        # connection parameters copied onto the port the connection starts at,
        # where the components reading them look for them
        self.port_connection_params = ["axi_max_reads"]

    def generate(self, outdir):
        """Convenience method for internal operation"""
        self.map_components(outdir)
        self.generate_hierarchy(outdir)

    def map_components(self, outdir):
        """
        Map components to their corresponding IP type

        Must be called after all internal processing is done
        """

        # populate defaults
        self.defaults["axi_max_reads"] = self.defaults.get("axi_max_reads", 1)

        registry = {
            "crossbar": PulpCrossbar,
            "dw_conv": PulpDWConv,
            "cdc": PulpCDC,
            "iw_conv": IWConv,
            "register": PulpRegister,
            "pr_conv": {
                "axiaxilite": PulpPrAXIAXILite,
                "axiapb": PulpPrAXIAPB,
                "axiahb": PrAXIAHB,
            },
        }

        self.real_components = []

        # TODO: in the future when proper mapping is implemented, this should include actual choice
        for name, component in self.components.items():
            srcattr = self.ports[component.srcports[0]].attributes
            dstattr = self.ports[component.dstports[0]].attributes

            if component.kind == "pr_conv":
                srcattr = srcattr["protocol"]
                dstattr = dstattr["protocol"]

                if srcattr != "axi4":
                    self.errors.append(
                        f"ERROR: invalid protocol source, found '{srcattr}' but the only valid one is 'axi4'"
                    )
                    return

                if dstattr == "ahb3":
                    self.real_components.append(
                        registry["pr_conv"]["axiahb"](
                            name, self.globals, self.defaults, component.address_map
                        )
                    )
                elif dstattr == "apb3":
                    self.real_components.append(
                        registry["pr_conv"]["axiapb"](
                            name, self.globals, self.defaults, component.address_map
                        )
                    )
                elif dstattr == "axi4lite":
                    self.real_components.append(
                        registry["pr_conv"]["axiaxilite"](
                            name, self.globals, self.defaults, component.address_map
                        )
                    )
                else:
                    self.errors.append(
                        f"ERROR: invalid protocol destination, found '{dstattr}' but the only valid ones are 'ahb3', 'apb3', 'axi4_lite'"
                    )
            else:
                self.real_components.append(
                    registry[component.kind](
                        name, self.globals, self.defaults, component.address_map
                    )
                )

            for portname in component.srcports + component.dstports:
                port = self.ports[portname]
                if port.attributes["role"] == "subordinate":
                    self.real_components[-1].srcports[portname] = port
                else:
                    self.real_components[-1].dstports[portname] = port

    def generate_hierarchy(self, outdir):
        """
        Generate verilog files and topwrap hierarchy so the final output can be generated

        Must be called after map_components()
        """

        os.makedirs(os.path.join(outdir, "interfaces", "interfaces"), exist_ok=True)

        with open("topwrap.yaml", "w") as file:
            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False
            yaml.dump(
                {
                    "repositories": {
                        "repo": f"{os.path.join(outdir, 'modules')}",
                        # interface definitions get a repository of their own: `topwrap repo parse repo`
                        # saves all of `repo` and would add copies of them under other names (#102866)
                        "interfaces": f"{os.path.join(outdir, 'interfaces')}",
                    }
                },
                file,
            )

        global filelist
        filelist = []

        exists = {}
        # generate verilog files
        for comp in self.real_components:
            comp.generate_verilog(outdir, exists, self.errors, self.warns)

        # generate topwrap
        tree = {
            "name": self.name,
            "ips": {},
            "connections": {"ports": {}, "interfaces": {}},
            "external": {"ports": {"in": []}, "interfaces": {"in": [], "out": []}},
        }

        # external clocks
        tree_ports = tree["external"]["ports"]
        for clk in self.clocks:
            clk = clk.removeprefix("clk_")
            clk = clk.removeprefix("clk")

            if len(clk) > 0:
                tree_ports["in"].append(f"clk_{clk}_i")
                tree_ports["in"].append(f"rst_{clk}_ni")
            else:
                tree_ports["in"].append("clk_i")
                tree_ports["in"].append("rst_ni")

        # external ports (actually interfaces)
        tree_interfaces = tree["external"]["interfaces"]
        for name, port in self.ports.items():
            if port.parent is not None:
                continue

            if port.attributes["role"] == "subordinate":
                tree_interfaces["in"].append(name)
            else:
                tree_interfaces["out"].append(name)

        for comp in self.real_components:
            tree["ips"][comp.name] = {
                # relative to the design file, which topwrap resolves it against
                "file": f"{os.path.join('modules', 'cores', comp.core, 'module.yaml')}",
                "parameters": {},
            }

            tree["connections"]["interfaces"][comp.name] = {}
            tree["connections"]["ports"][comp.name] = {}

            comp.generate_hierarchy(
                ports=tree["connections"]["ports"][comp.name],
                params=tree["ips"][comp.name]["parameters"],
            )

        for portname, port in self.ports.items():
            for dest in port.edges:
                destname = dest.dest
                destport = self.ports[destname]

                # connections are only added between components
                if port.parent == destport.parent:
                    continue

                portcomp = self.components.get(port.parent)
                destcomp = self.components.get(destport.parent)

                # interfaces can only be defined from IPs
                # ensure we are not in external interface
                if port.parent is None:
                    core = tree["connections"]["interfaces"][destport.parent]

                    if destcomp.kind == "crossbar":
                        core[destname] = portname
                    else:
                        core["src"] = portname
                elif destport.parent is None:
                    core = tree["connections"]["interfaces"][port.parent]

                    if portcomp.kind == "crossbar":
                        core[portname] = destname
                    else:
                        core["dst"] = destname
                else:
                    core = tree["connections"]["interfaces"][port.parent]

                    if portcomp.kind == "crossbar" and destcomp.kind == "crossbar":
                        core[portname] = [destport.parent, destname]
                    elif portcomp.kind == "crossbar":
                        core[portname] = [destport.parent, "src"]
                    elif destcomp.kind == "crossbar":
                        core["dst"] = [destport.parent, destname]
                    else:
                        core["dst"] = [destport.parent, "src"]

        with open(os.path.join(outdir, f"{self.name}.yml"), "w") as file:
            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False
            yaml.dump(tree, file)

        with open(os.path.join(outdir, f"{self.name}.f"), "w") as fl:
            for file in filelist:
                fl.write(file)
                fl.write("\n")
