# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Passive AXI4 / AXI4-Lite protocol checker for one port. It watches both
directions, so it checks the DUT's outputs and the test bench's own stimulus.

Checked so far:
  - a VALID that is not yet accepted stays high, with its payload unchanged
  - W bursts are AWLEN+1 beats long with WLAST on the last one (AXI4)
  - R bursts are ARLEN+1 beats long with RLAST on the last one, per ID (AXI4)
  - no B or R response without an outstanding request with that ID
"""

from collections import defaultdict, deque

import cocotb
from cocotb.simtime import get_sim_time
from cocotb.triggers import RisingEdge

CHANNELS = {
    "aw": (
        "awid",
        "awaddr",
        "awlen",
        "awsize",
        "awburst",
        "awlock",
        "awcache",
        "awprot",
    ),
    "w": ("wdata", "wstrb", "wlast"),
    "b": ("bid", "bresp"),
    "ar": (
        "arid",
        "araddr",
        "arlen",
        "arsize",
        "arburst",
        "arlock",
        "arcache",
        "arprot",
    ),
    "r": ("rid", "rdata", "rresp", "rlast"),
}
MAX_REPORTED = 20


class AxiChecker:
    def __init__(self, dut, port: str, clock, reset):
        self.port = port
        self.clock = clock
        self.reset = reset
        self.violations: list[str] = []
        self.channels = {}
        for ch, fields in CHANNELS.items():
            handles = {f: getattr(dut, f"{port}_{f}", None) for f in fields}
            self.channels[ch] = (
                getattr(dut, f"{port}_{ch}valid"),
                getattr(dut, f"{port}_{ch}ready"),
                {f: h for f, h in handles.items() if h is not None},
            )
        self.full_axi = "awlen" in self.channels["aw"][2]
        self._clear()
        self._task = cocotb.start_soon(self._run())

    def _clear(self):
        self.prev = {}
        self.aw_lens = deque()
        self.w_bursts = deque()
        self.w_beats = 0
        self.ar_lens = defaultdict(deque)
        self.r_beats = defaultdict(int)
        self.writes = defaultdict(int)

    def _violation(self, msg: str):
        if len(self.violations) < MAX_REPORTED:
            self.violations.append(f"{get_sim_time('ns'):.0f} ns {self.port}: {msg}")

    async def _run(self):
        while True:
            await RisingEdge(self.clock)
            if not int(self.reset.value):
                self._clear()
                continue
            for ch, (valid, ready, fields) in self.channels.items():
                v = int(valid.value)
                r = int(ready.value)
                payload = {f: h.value for f, h in fields.items()} if v else None
                if ch in self.prev:
                    pv, pr, pp = self.prev[ch]
                    if pv and not pr:
                        if not v:
                            self._violation(
                                f"{ch.upper()}VALID dropped before {ch.upper()}READY"
                            )
                        elif payload != pp:
                            changed = [f for f in fields if payload[f] != pp[f]]
                            self._violation(
                                f"{ch} payload changed while stalled: {changed}"
                            )
                self.prev[ch] = (v, r, payload)
                if v and r:
                    self._handshake(ch, payload)

    def _id(self, payload, field):
        return int(payload[field]) if field in payload else 0

    def _handshake(self, ch, p):
        if ch == "aw":
            self.writes[self._id(p, "awid")] += 1
            if self.full_axi:
                self.aw_lens.append(int(p["awlen"]))
        elif ch == "w" and self.full_axi:
            self.w_beats += 1
            if int(p["wlast"]):
                self.w_bursts.append(self.w_beats)
                self.w_beats = 0
        elif ch == "b":
            bid = self._id(p, "bid")
            if self.writes[bid] == 0:
                self._violation(f"B with ID {bid} and no outstanding write")
            else:
                self.writes[bid] -= 1
        elif ch == "ar":
            self.ar_lens[self._id(p, "arid")].append(
                int(p["arlen"]) if self.full_axi else 0
            )
        elif ch == "r":
            rid = self._id(p, "rid")
            if not self.ar_lens[rid]:
                self._violation(f"R with ID {rid} and no outstanding read")
                return
            self.r_beats[rid] += 1
            last = int(p["rlast"]) if "rlast" in p else 1
            expected = self.ar_lens[rid][0] + 1
            if last or self.r_beats[rid] > expected:
                if self.r_beats[rid] != expected:
                    self._violation(
                        f"R burst for ID {rid}: {self.r_beats[rid]} beats, ARLEN+1 is {expected}"
                    )
                self.ar_lens[rid].popleft()
                self.r_beats[rid] = 0
        while self.aw_lens and self.w_bursts:
            awlen, beats = self.aw_lens.popleft(), self.w_bursts.popleft()
            if beats != awlen + 1:
                self._violation(f"W burst of {beats} beats, AWLEN+1 is {awlen + 1}")
