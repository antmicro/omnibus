# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

UVM_ROOT = Path(__file__).resolve().parent


def pytest_addoption(parser):
    parser.addoption(
        "--uvm-work-dir",
        type=Path,
        default=UVM_ROOT / ".build",
        help="where the UVM simulators are built",
    )
    parser.addoption(
        "--uvm-waves",
        action="store_true",
        help="build with waveform tracing, every test writes <test>.fst next to its log",
    )
