# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Spec -> simulator build, following tests/generate.sh: Omnibus generates the
interconnect and a topwrap design for it, topwrap turns that into a top-level
SystemVerilog module, and cocotb's runner builds it with Verilator. Builds are
cached per spec.
"""

import hashlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import topwrap
from cocotb_tools.runner import get_runner

import omnibus

from . import REPO_ROOT, SIM_ROOT, refmodel

DEFAULT_WORK_DIR = SIM_ROOT / ".build"
PULP_FILELIST = REPO_ROOT / "tests" / "verilator" / "pulp_platform_filelist.f"

VERILATOR_ARGS = [
    "-Wno-fatal",
    "-Wno-lint",
    "-Wno-style",
    # Verilator is 2-state: randomize what would be X, so undriven data shows up
    # as a data mismatch instead of a quiet 0
    "--x-assign",
    "unique",
    "--x-initial",
    "unique",
]


@dataclass(frozen=True)
class Build:
    spec: Path
    model: refmodel.SpecModel
    toplevel: str
    sim_build: Path
    # modules Omnibus generated (crossbars, converters, register slices, ...)
    modules: frozenset[str]


def _filelist(path: Path, base: Path) -> tuple[list[Path], list[Path], list[str]]:
    """(sources, include dirs, other options) of a Verilator filelist, relative to `base`."""
    sources, includes, options = [], [], []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("+incdir+"):
            includes.append(base / line.removeprefix("+incdir+"))
        elif line.startswith("+"):
            options.append(line)
        else:
            sources.append(base / line)
    return sources, includes, options


def _tree_digest(digest, root: Path, patterns: tuple[str, ...]) -> None:
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())


def _cache_key(spec: Path) -> str:
    """Everything a build depends on: the spec, both generators and this harness."""
    digest = hashlib.sha256(spec.read_bytes())
    _tree_digest(digest, Path(topwrap.__file__).parent, ("*.py", "*.yaml", "*.j2"))
    _tree_digest(digest, Path(omnibus.__file__).parent, ("*.py", "*.sv", "*.yml"))
    digest.update(Path(__file__).read_bytes())
    digest.update(PULP_FILELIST.read_bytes())
    return digest.hexdigest()[:16]


def _check_generation(spec: Path):
    """The Omnibus CLI exits 0 even when process() records errors; fail on them here."""
    ic = omnibus.InterconnectBuilder()
    rc = ic.read_yaml(str(spec))
    if rc == 0:
        ic.process()
    if rc != 0 or ic.errors:
        raise RuntimeError(f"Omnibus rejected {spec.name}:\n" + "\n".join(ic.errors))


def _run(cmd: list[str], cwd: Path, log):
    log.write(f"$ {' '.join(cmd)}\n")
    log.flush()
    subprocess.run(cmd, cwd=cwd, check=True, stdout=log, stderr=subprocess.STDOUT)


def build(spec: Path, work_dir: Path = DEFAULT_WORK_DIR, waves: bool = False) -> Build:
    spec = spec.resolve()
    model = refmodel.load(spec)
    out = work_dir / f"{spec.stem}-{_cache_key(spec)}{'-waves' if waves else ''}"
    sim_build = out / "sim_build"
    done = out / "built"
    if done.exists():
        return Build(spec, model, model.name, sim_build, _generated_modules(out))

    _check_generation(spec)
    # drop stale builds of this spec made with older inputs
    for old in work_dir.glob(f"{spec.stem}-*"):
        shutil.rmtree(old, ignore_errors=True)
    out.mkdir(parents=True)

    # the same steps as tests/generate.sh; the backend writes topwrap.yaml into the cwd
    bindir = Path(sys.executable).parent
    with open(out / "generate.log", "w") as log:
        _run([str(bindir / "omnibus"), str(spec)], out, log)
        _run(
            [str(bindir / "topwrap"), "repo", "parse", "repo", "out/src", "-I"]
            + ["--log-level", "error"],
            out,
            log,
        )
        _run(
            [str(bindir / "topwrap"), "generate", "--verilog", f"out/{model.name}.yml"]
            + ["--log-level", "error", "--flatten-interfaces"],
            out,
            log,
        )

    # pulp sources from the omnibus/third_party submodules, relative to the repo root
    pulp_sources, pulp_includes, pulp_options = _filelist(PULP_FILELIST, REPO_ROOT)
    generated, _, _ = _filelist(out / "out" / f"{model.name}.f", out / "out")
    get_runner("verilator").build(
        # pulp first: the generated RTL relies on macros leaking from axi/typedef.svh
        sources=[*pulp_sources, *generated, out / "build" / "src" / f"{model.name}.sv"],
        includes=pulp_includes,
        build_args=[
            *VERILATOR_ARGS,
            *pulp_options,
            *(["--trace-fst"] if waves else []),
        ],
        hdl_toplevel=model.name,
        build_dir=sim_build,
        timescale=("1ns", "1ps"),
        waves=waves,
        log_file=out / "build.log",
    )
    done.touch()
    return Build(spec, model, model.name, sim_build, _generated_modules(out))


def _generated_modules(out: Path) -> frozenset[str]:
    return frozenset(
        m
        for f in (out / "out" / "src").glob("*.sv")
        for m in re.findall(r"^module\s+(\w+)", f.read_text(), re.MULTILINE)
    )
