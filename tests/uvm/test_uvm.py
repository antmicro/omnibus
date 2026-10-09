# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
UVM tests of axi_prconv_axi_ahb on Verilator: the AXI4 AVIP master drives the bridge, the AHB
AVIP slave answers it, and a scoreboard checks the conversion. The simulator is built once for
every configuration, then each UVM test runs in it by name.
"""

import hashlib
import shutil
import subprocess

import pytest
from uvm_build import REPO_ROOT, UVM_DIR, build, dependencies

TESTS = [
    "smoke",
    "regular",
    "narrow",
    "unaligned",
    "burst_types",
    "strobes",
    "ids",
    "random",
    "error",
    "arbitration",
    "shapes",
    "busy",
    "throughput",
]

# (data width, FifoDepth)
CONFIGS = [(64, 3), (32, 2)]


@pytest.fixture(scope="session", autouse=True)
def requirements():
    if shutil.which("verilator") is None:
        pytest.skip("verilator not found on PATH")
    if dependencies() is None:
        pytest.skip(
            "UVM_CORE (uvm-verilator, branch uvm-2017-1.0-vlt), AXI4_AVIP and AHB_AVIP "
            "must point to the dependencies"
        )


def digest(*roots) -> str:
    """Everything a build depends on: the Verilator version (a string) and the sources."""
    h = hashlib.sha256()
    for root in roots:
        if isinstance(root, str):
            h.update(root.encode())
            continue
        files = [root] if root.is_file() else root.rglob("*")
        for path in sorted(files):
            if path.is_file() and path.suffix in {
                ".sv",
                ".svh",
                ".cc",
                ".c",
                ".h",
                ".py",
            }:
                h.update(str(path.name).encode())
                h.update(path.read_bytes())
    return h.hexdigest()[:16]


@pytest.fixture(scope="session")
def simulators(request):
    cache = {}
    work_dir = request.config.getoption("--uvm-work-dir")
    waves = request.config.getoption("--uvm-waves")

    def get(width: int, depth: int):
        if (width, depth) not in cache:
            deps = dependencies()
            key = digest(
                subprocess.run(
                    ["verilator", "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout,
                REPO_ROOT / "omnibus" / "modules",
                UVM_DIR / "hdl",
                UVM_DIR / "hvl",
                UVM_DIR / "uvm_build.py",
                *(d / "src" for d in deps.values()),
            )
            out = work_dir / f"w{width}_d{depth}{'_waves' if waves else ''}-{key}"
            binary = out / "Vbridge_tb"
            if not binary.exists():
                for old in work_dir.glob(f"w{width}_d{depth}*"):
                    shutil.rmtree(old, ignore_errors=True)
                try:
                    cache[(width, depth)] = build(out, width, depth, waves=waves)
                except subprocess.CalledProcessError as e:
                    cache[(width, depth)] = e
            else:
                cache[(width, depth)] = binary
        if isinstance(cache[(width, depth)], Exception):
            raise cache[(width, depth)]
        return cache[(width, depth)]

    return get


@pytest.mark.parametrize(
    "width, depth", CONFIGS, ids=[f"{w}b-fifo{d}" for w, d in CONFIGS]
)
@pytest.mark.parametrize("test", TESTS)
def test_uvm(test, width, depth, simulators, request):
    binary = simulators(width, depth)
    log = binary.parent / f"{test}.log"
    waves = [f"+WAVES={test}.fst"] if request.config.getoption("--uvm-waves") else []
    result = subprocess.run(
        [
            str(binary),
            f"+UVM_TESTNAME=bridge_{test}_test",
            f"+FIFO_DEPTH={depth}",
            "+UVM_NO_RELNOTES",
            *waves,
        ],
        cwd=binary.parent,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    log.write_text(result.stdout + result.stderr)
    counts = {
        line.split(":")[0].strip(): int(line.split(":")[1])
        for line in result.stdout.splitlines()
        if line.startswith(("UVM_ERROR :", "UVM_FATAL :"))
    }
    assert result.returncode == 0, (
        f"the simulator exited with {result.returncode}, see {log}"
    )
    assert counts == {"UVM_ERROR": 0, "UVM_FATAL": 0}, (
        f"UVM reported {counts or 'no summary'}, see {log}"
    )
