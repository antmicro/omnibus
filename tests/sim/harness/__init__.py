# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SIM_ROOT.parent.parent

# cocotb test modules in tiers/, in the order they run
TIERS = ("tier0_build", "tier1_smoke", "tier2_negative")
