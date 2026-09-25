# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import shutil
import sys
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parent
# the cocotb runner hands sys.path to the simulator's Python, which imports the
# tier modules and the harness from here
for path in (SIM_ROOT, SIM_ROOT / "tiers"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from harness import TIERS


def pytest_addoption(parser):
    parser.addoption(
        "--sim-waves", action="store_true", help="dump waveforms (FST/VCD)"
    )
    parser.addoption(
        "--sim-work-dir",
        type=Path,
        default=SIM_ROOT / ".build",
        help="where generated RTL and simulator builds are kept",
    )


def pytest_configure(config):
    for tier in TIERS:
        config.addinivalue_line("markers", f"{tier}: simulation tests of {tier}")


def pytest_collection_modifyitems(config, items):
    if shutil.which("verilator") is None:
        skip = pytest.mark.skip(reason="verilator not found on PATH")
        for item in items:
            item.add_marker(skip)
