# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Verilator build of the UVM test bench: UVM, the AXI4 and AHB AVIP forks, the bridge and
bridge_tb. The three dependencies are looked up in the environment variables UVM_CORE
(chipsalliance/uvm-verilator, branch uvm-2017-1.0-vlt), AXI4_AVIP and AHB_AVIP, and then in
third_party/ next to this file.
"""

import os
import subprocess
from pathlib import Path

UVM_DIR = Path(__file__).resolve().parent
REPO_ROOT = UVM_DIR.parent.parent


def dependency(var: str, name: str) -> Path | None:
    path = Path(os.environ.get(var, UVM_DIR / "third_party" / name))
    return path if path.is_dir() else None


def dependencies() -> dict[str, Path] | None:
    deps = {
        "uvm": dependency("UVM_CORE", "uvm-verilator"),
        "axi4": dependency("AXI4_AVIP", "axi4_avip"),
        "ahb": dependency("AHB_AVIP", "ahb_avip"),
    }
    return deps if all(deps.values()) else None


def build(
    out: Path,
    data_width: int,
    fifo_depth: int,
    waves: bool = False,
    jobs: int = 4,
    modules: Path = REPO_ROOT / "omnibus" / "modules",
) -> Path:
    """Build the simulator for one configuration in `out`, return the binary."""
    deps = dependencies()
    assert deps, "UVM_CORE, AXI4_AVIP and AHB_AVIP must point to the dependencies"
    uvm, axi, ahb = deps["uvm"] / "src", deps["axi4"] / "src", deps["ahb"] / "src"

    sources = [
        uvm / "uvm_pkg.sv",
        uvm / "dpi" / "uvm_dpi.cc",
        axi / "globals" / "axi4_globals_pkg.sv",
        axi / "hvl_top" / "master" / "axi4_master_pkg.sv",
        axi / "hdl_top" / "axi4_interface" / "axi4_if.sv",
        axi / "hdl_top" / "master_agent_bfm" / "axi4_master_driver_bfm.sv",
        axi / "hdl_top" / "master_agent_bfm" / "axi4_master_monitor_bfm.sv",
        axi / "hdl_top" / "master_agent_bfm" / "axi4_master_agent_bfm.sv",
        ahb / "globals" / "AhbGlobalPackage.sv",
        ahb / "hvlTop" / "slaveAgent" / "AhbSlavePackage.sv",
        ahb / "hdlTop" / "ahbInterface" / "AhbInterface.sv",
        ahb / "hdlTop" / "slaveAgentBFM" / "AhbSlaveDriverBFM.sv",
        ahb / "hdlTop" / "slaveAgentBFM" / "AhbSlaveMonitorBFM.sv",
        ahb / "hdlTop" / "slaveAgentBFM" / "AhbSlaveAgentBFM.sv",
        modules / "axi_prconv_fifo.sv",
        modules / "axi_prconv_axi_ahb.sv",
        UVM_DIR / "hvl" / "bridge_pkg.sv",
        UVM_DIR / "hdl" / "bridge_ahb_checker.sv",
        UVM_DIR / "hdl" / "bridge_tb.sv",
    ]
    incdirs = [
        uvm,
        axi / "hvl_top" / "master",
        ahb / "hvlTop" / "slaveAgent",
        UVM_DIR / "hvl",
    ]
    cmd = [
        "verilator",
        "--binary",
        "--timing",
        "--vpi",  # UVM's DPI layer
        "--public-flat-rw",
        "--top-module",
        "bridge_tb",
        "--timescale",
        "1ns/1ps",
        "-Wno-fatal",
        "-Wno-lint",
        "-Wno-style",
        "-j",
        str(jobs),
        f"+define+AXI4_DATA_WIDTH={data_width}",
        f"+define+AHB_DATA_WIDTH={data_width}",
        f"-GFifoDepth={fifo_depth}",
        "-Mdir",
        str(out),
        *(f"+incdir+{d}" for d in incdirs),
        *map(str, sources),
    ]
    if waves:
        cmd += ["--trace-fst", "--trace-structs"]
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "build.log", "w") as log:
        log.write(" ".join(cmd) + "\n")
        log.flush()
        subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    return out / "Vbridge_tb"


if __name__ == "__main__":
    import sys

    print(build(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])))
