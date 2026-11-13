# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Topwrap plugin providing the ``omnibus`` IP generator::

    ips:
      axi_ic:
        generate:
          provider: omnibus
          options:
            spec: interconnect.yml

The interconnect specification is the only source of interconnect data, the design
only connects peripherals to its ports. Parameters of those peripherals' interfaces
are checked against the generated interconnect.
"""

import contextlib
import importlib.metadata
import logging
import shutil
import tempfile
from importlib import resources
from pathlib import Path

import yaml
from topwrap.backend.yaml.common.interface_schema import InterfaceDefinitionDescription
from topwrap.cli import load_interfaces_from_repos
from topwrap.frontend.frontend import FrontendApproach
from topwrap.frontend.sv.frontend import SystemVerilogFrontend
from topwrap.frontend.yaml.design import DesignDescriptionFrontend
from topwrap.frontend.yaml.interface import InterfaceDefinitionDescriptionFrontend
from topwrap.model.connections import InterfaceConnection
from topwrap.model.hdl_types import ElabvalueEvaluator
from topwrap.model.inference.inference import infer_interfaces_from_module
from topwrap.model.module import Module
from topwrap.plugin.base import (
    BasePlugin,
    BuildContext,
    IPGenerationException,
    IPGeneratorOptionsException,
    OutputDir,
)

from .interconnect import InterconnectBuilder

logger = logging.getLogger(__name__)

#: Interface parameters compared between interconnect ports and connected peripherals,
#: mismatches of the ones mapped to True abort the build
CHECKED_PARAMS = {"DATA_WIDTH": True, "ADDR_WIDTH": False, "ID_WIDTH": False}


class OmnibusPlugin(BasePlugin):
    def __init__(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="omnibus-")
        #: Generated interconnect modules with their instance names, source directories
        #: and core VLNVs
        self.generated: dict[int, tuple[Module, str, Path, str]] = {}

    def ip_generators(self):
        return {"omnibus": self.generate}

    def pre_ir_generation(self, ctx: BuildContext):
        self.generated.clear()

    def generate(self, name: str, options, base_dir: Path) -> Module:
        if any(n == name for _, n, _, _ in self.generated.values()):
            raise IPGenerationException(
                f"another omnibus IP is named '{name}', the names prefix the generated "
                "modules so they must be unique across the whole design"
            )
        if set(options) != {"spec"}:
            raise IPGeneratorOptionsException(
                f"expected only the 'spec' option, got {sorted(options)}"
            )
        spec = base_dir / options["spec"]
        if not spec.is_file():
            raise IPGeneratorOptionsException(f"spec file '{spec}' does not exist")

        ic = InterconnectBuilder()
        if ic.read_yaml(str(spec)) == 0:
            ic.process()
        if not ic.errors:
            outdir = Path(tempfile.mkdtemp(dir=self.tmpdir.name))
            (outdir / "src").mkdir()
            # the backend writes a legacy topwrap.yaml into the working directory
            with contextlib.chdir(outdir):
                ic.generate(str(outdir), name)
        for warn in ic.warns:
            logger.warning(warn)
        if ic.errors:
            raise IPGenerationException("\n".join(ic.errors))

        interfaces = list(load_interfaces_from_repos()) + [
            InterfaceDefinitionDescriptionFrontend().parse(
                InterfaceDefinitionDescription.load(Path(str(f)))
            )
            for f in (resources.files("omnibus") / "interfaces").iterdir()
        ]
        modules = (
            SystemVerilogFrontend(
                interfaces=interfaces, approach=FrontendApproach.BEST_EFFORT
            )
            .parse_files(sorted((outdir / "src").glob("*.sv")))
            .modules
        )
        for mod in modules:
            infer_interfaces_from_module(mod, interfaces)

        # refer to the modules parsed above instead of the IP core files the backend points to
        tree = yaml.safe_load((outdir / f"{ic.name}.yml").read_text())
        ids = {mod.id.name: str(mod.id) for mod in modules}
        for ip in tree["ips"].values():
            ip["core"] = ids[Path(ip.pop("file")).parent.name]
        design, _ = DesignDescriptionFrontend(modules).parse_str(yaml.safe_dump(tree))

        vlnv = f"antmicro.com:omnibus:{ic.name}:{ic.version}"
        self.generated[id(design.parent)] = (design.parent, name, outdir, vlnv)
        return design.parent

    def post_ir_generation(self, ctx: BuildContext):
        if ctx.top_module is None:
            return
        ctx.fusesoc_dependencies += [vlnv for _, _, _, vlnv in self.generated.values()]

        errors = []
        for mod in ctx.top_module.hierarchy():
            if mod.design is None:
                continue
            for conn in mod.design.connections:
                if (
                    not isinstance(conn, InterfaceConnection)
                    or conn.source.instance is None
                    or conn.target.instance is None
                ):
                    continue
                ic, periph = conn.source, conn.target
                if id(ic.instance.module) not in self.generated:
                    ic, periph = periph, ic
                if id(ic.instance.module) not in self.generated:
                    continue

                where = (
                    f"{mod.id.name}: interconnect port '{ic.instance.name}.{ic.io.name}' "
                    f"connected to '{periph.instance.name}.{periph.io.name}'"
                )
                if ic.io.definition.id != periph.io.definition.id:
                    errors.append(
                        f"{where} uses protocol {ic.io.definition.id.name}, "
                        f"peripheral uses {periph.io.definition.id.name}"
                    )
                    continue
                if ic.io.mode == periph.io.mode:
                    errors.append(f"{where}: both sides are {ic.io.mode.value}s")

                ic_params, _ = ElabvalueEvaluator.resolve_intf_values(
                    ic.io, ic.instance.parameters
                )
                periph_params, _ = ElabvalueEvaluator.resolve_intf_values(
                    periph.io, periph.instance.parameters
                )
                ic_params = {p.resolve().name: v for p, v in ic_params.items()}
                periph_params = {p.resolve().name: v for p, v in periph_params.items()}
                for name, fatal in CHECKED_PARAMS.items():
                    if name not in ic_params or name not in periph_params:
                        continue
                    if ic_params[name] != periph_params[name]:
                        msg = (
                            f"{where}: {name} is {ic_params[name]} in the interconnect, "
                            f"{periph_params[name]} in the peripheral"
                        )
                        if fatal:
                            errors.append(msg)
                        else:
                            logger.warning(msg)

        if errors:
            raise IPGenerationException("\n".join(errors))

    def post_output_writing(self, ctx: BuildContext, target_dir: OutputDir):
        # the Pulp sources come from the pulp-platform.org::axi core and its dependencies,
        # github.com/antmicro/axi provides the version omnibus is developed against
        common_vlnv = (
            f"antmicro.com:omnibus:common:{importlib.metadata.version('omnibus')}"
        )
        common_dir = target_dir.gensrc_dir / "omnibus_common"

        def write_core(
            core_dir: Path, vlnv: str, sources: list[Path], depend: list[str]
        ):
            core_dir.mkdir(parents=True, exist_ok=True)
            for f in sources:
                shutil.copy(f, core_dir)
            files = [
                {f.name: {"is_include_file": True}}
                if f.suffix in (".vh", ".svh")
                else f.name
                for f in sorted(core_dir.iterdir())
                if f.suffix != ".core"
            ]
            core = {
                "name": vlnv,
                "filesets": {
                    "rtl": {
                        "files": files,
                        "file_type": "systemVerilogSource",
                        "depend": depend,
                    }
                },
                "targets": {"default": {"filesets": ["rtl"]}},
            }
            (core_dir / f"{vlnv.split(':')[2]}.core").write_text(
                "CAPI=2:\n" + yaml.safe_dump(core, sort_keys=False)
            )

        common = []
        for _, name, outdir, vlnv in self.generated.values():
            # only the crossbars carry the name prefix, the other sources are the same
            # for every interconnect and go to the shared core
            sources = sorted((outdir / "src").iterdir())
            own = [f for f in sources if f.name.startswith(f"{name}_")]
            common += [f for f in sources if f not in own]
            write_core(target_dir.gensrc_dir / name, vlnv, own, [common_vlnv])
        if self.generated:
            write_core(common_dir, common_vlnv, common, ["pulp-platform.org::axi"])
