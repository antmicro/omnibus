# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Simulation tests of single Omnibus converter modules, without an interconnect around
them: the module is the Verilator top level, bridges/<name>.py holds its cocotb tests.
"""

import pytest

pytest.importorskip("cocotb")
pytest.importorskip("cocotbext.axi")
pytest.importorskip("cocotb_AHB")

from cocotb_tools.check_results import get_results
from cocotb_tools.runner import get_runner
from harness import REPO_ROOT
from harness.generate import VERILATOR_ARGS


@pytest.mark.parametrize(
    "data_width, fifo_depth", [(32, 2), (64, 2), (64, 3), (32, 1), (64, 4)]
)
def test_axi_ahb(data_width, fifo_depth, request):
    work_dir = (
        request.config.getoption("--sim-work-dir")
        / f"axi_ahb_{data_width}_{fifo_depth}"
    )
    waves = request.config.getoption("--sim-waves")
    seed = request.config.getoption("--sim-seed")
    request.node.user_properties.append(("seed", seed))
    runner = get_runner("verilator")
    runner.build(
        sources=[
            REPO_ROOT / "omnibus" / "modules" / "axi_prconv_fifo.sv",
            REPO_ROOT / "omnibus" / "modules" / "axi_prconv_axi_ahb.sv",
        ],
        hdl_toplevel="axi_prconv_axi_ahb",
        parameters={
            "AxiDataWidth": data_width,
            "AxiIdWidth": 4,
            "FifoDepth": fifo_depth,
        },
        build_args=[*VERILATOR_ARGS, *(["--trace-fst"] if waves else [])],
        build_dir=work_dir / "sim_build",
        timescale=("1ns", "1ps"),
        waves=waves,
        always=True,
        log_file=work_dir / "build.log",
    )
    log = work_dir / "sim.log"
    results = runner.test(
        hdl_toplevel="axi_prconv_axi_ahb",
        test_module="axi_ahb",
        build_dir=work_dir / "sim_build",
        test_dir=work_dir,
        results_xml=str(work_dir / "results.xml"),
        extra_env={"FIFO_DEPTH": str(fifo_depth), "COCOTB_RANDOM_SEED": str(seed)},
        waves=waves,
        log_file=log,
    )
    total, failed = get_results(results)
    assert failed == 0, (
        f"{failed} of {total} cocotb tests failed with seed {seed} (--sim-seed {seed}), see {log}"
    )
