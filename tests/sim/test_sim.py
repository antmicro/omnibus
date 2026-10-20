# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Simulation tests of Omnibus-generated interconnects: every spec in specs/
is generated and built once, then every tier module in tiers/ runs against it.
"""

from pathlib import Path

import pytest

pytest.importorskip("cocotb")
pytest.importorskip("cocotbext.axi")
pytest.importorskip("topwrap")

from cocotb_tools.check_results import get_results
from cocotb_tools.runner import get_runner
from harness import SIM_ROOT, TIERS, generate

SPECS = sorted((SIM_ROOT / "specs").glob("*.yml"))

# Modules a spec's generated RTL must contain, so a spec can't silently stop
# exercising the feature it's in the corpus for.
EXPECTED_MODULES = {
    "ahb": {"axi_prconv_axi_ahb"},
    "cdc": {"axi_cdc_wrapper"},
    "chain": {"axi_crossbar_near", "axi_crossbar_far"},
    "dw_mix": {"axi_dw_conv_wrapper"},
    "lite": {"axi_prconv_axi_axilite"},
    "regslice": {"axi_buffer_wrapper"},
    "apb": {"axi_prconv_axi_apb"},
}

# Known failures, keyed by (spec, tier or "build"). strict: a fix makes the test
# XPASS and fail, so the entry gets removed together with the fix.
XFAIL = {
    ("two_windows", "build"): (
        "a target with two address windows: process() records a misleading 'rules different "
        "based on source id' error, the CLI still exits 0, and the generated crossbar keeps "
        "only the first window"
    ),
}


def _xfail(request, spec: Path, key: str):
    reason = XFAIL.get((spec.stem, key))
    if reason:
        request.applymarker(pytest.mark.xfail(reason=reason, strict=True))


@pytest.fixture(scope="session")
def builds(request):
    cache = {}
    work_dir = request.config.getoption("--sim-work-dir")
    waves = request.config.getoption("--sim-waves")

    def get(spec: Path) -> generate.Build:
        if spec not in cache:
            try:
                cache[spec] = generate.build(spec, work_dir, waves=waves)
            except Exception as e:  # noqa: BLE001 -- reported once per spec, see test_build
                cache[spec] = e
        if isinstance(cache[spec], Exception):
            raise cache[spec]
        return cache[spec]

    return get


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_build(spec, builds, request):
    """Generate the spec's RTL with Omnibus and Topwrap, build it with Verilator."""
    _xfail(request, spec, "build")
    build = builds(spec)
    missing = EXPECTED_MODULES.get(spec.stem, set()) - build.modules
    assert not missing, (
        f"generated RTL lacks {sorted(missing)}, has {sorted(build.modules)}"
    )


@pytest.mark.parametrize(
    "tier", [pytest.param(t, marks=getattr(pytest.mark, t)) for t in TIERS]
)
@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_tier(spec, tier, builds, request):
    try:
        build = builds(spec)
    except Exception as e:  # noqa: BLE001 -- the failure itself is reported by test_build
        pytest.skip(f"build failed ({type(e).__name__}), see test_build[{spec.stem}]")
    _xfail(request, spec, tier)
    run_dir = build.sim_build.parent / "run" / tier
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "sim.log"
    results = get_runner("verilator").test(
        hdl_toplevel=build.toplevel,
        hdl_toplevel_lang="verilog",
        test_module=tier,
        build_dir=build.sim_build,
        test_dir=run_dir,
        results_xml=str(run_dir / "results.xml"),
        extra_env={"TOPWRAP_SIM_SPEC": str(build.spec)},
        waves=request.config.getoption("--sim-waves"),
        log_file=log,
    )
    total, failed = get_results(results)
    assert failed == 0, f"{failed} of {total} cocotb tests failed, see {log}"
