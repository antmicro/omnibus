# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Passive APB protocol checker for a single APB port.

Supported checks:
  - enable and ready assertions and deassertions
  - stability of signals during write
  - stability of signals during read
"""

import cocotb
from cocotb.handle import HierarchyObject, LogicObject
from cocotb.simtime import get_sim_time
from cocotb.triggers import RisingEdge

CHANNELS = {
    "paddr",
    "pprot",
    "psel",
    "penable",
    "pwrite",
    "pwdata",
    "pstrb",
    "pready",
    "prdata",
    "pslverr",
}
MAX_REPORTED = 20

class ApbChecker:
    def __init__(
        self, dut: HierarchyObject, port: str, clock: LogicObject, reset: LogicObject
    ):
        self.port = port
        self.clock = clock
        self.reset = reset
        self.violations: list[str] = []
        self.channels = {}
        for ch in CHANNELS:
            self.channels[ch] = getattr(dut, f"{port}_{ch}", None)
        self._clear()
        self._task = cocotb.start_soon(self._run())

    def _clear(self):
        self.prev = None
        self.transfer = False
        self.write_transfer  = False

    def _violation(self, msg: str):
        if len(self.violations) < MAX_REPORTED:
            self.violations.append(f"{get_sim_time('ns'):.0f} ns {self.port}: {msg}")

    async def _run(self):
        while True:
            await RisingEdge(self.clock)

            if not int(self.reset.value):
                self._clear()
                continue

            if not self.transfer and int(self.channels["psel"]):
                self.transfer = True
                self.write_transfer = bool(self.channels["pwrite"].value)

            if self.transfer:
                if not int(self.channels["psel"].value):
                    self._violation("PSEL deasserted while transfer in progress");

                stable = (self.channels["paddr"], self.channels["pwrite"], self.channels["pprot"])
                if self.write_transfer:
                    stable = (self.channels["paddr"], self.channels["pwrite"], self.channels["pwdata"], self.channels["pstrb"], self.channels["pprot"])

                if self.prev is None:
                    # first cycle of transfer here
                    if int(self.channels["penable"].value):
                        self._violation("PENABLE asserted on first cycle of transfer")

                    self.prev = stable
                else:
                    if not int(self.channels["penable"].value):
                        self._violation("PENABLE deasserted while still in transfer")

                    if self.prev != stable:
                        if self.write_transfer:
                            self._violation("PADDR/PWRITE/PWDATA/PSTRB/PPROT changed before transfer end")
                        else:
                            self._violation("PADDR/PWRITE/PPROT changed before transfer end")
                    
                    if int(self.channels["pready"].value):
                        self.write_transfer = False
                        self.transfer = False
                        self.prev = None
                    else:
                        self.prev = stable
