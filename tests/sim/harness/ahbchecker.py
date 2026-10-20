# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Passive AHB3 protocol checker for a single AHB manager port.

Supported checks:
  - address aligned to HSIZE, transfer within the data bus
  - stable address phase while HREADY is low (an ERROR response may cancel it)
  - SEQ and BUSY only inside a burst, at the address it continues with
  - constant HBURST, HSIZE and HWRITE inside a burst
  - INCR bursts not crossing 1KB
  - fixed-length bursts completed (unless an ERROR cancelled them), no burst ending with BUSY
  - no transfer after the second cycle of an ERROR response

The accepted NONSEQ and SEQ address phases and the BUSY cycles are kept in `xfers` and `busy`,
for tests that look at how a burst was split.
"""

import cocotb
from cocotb.handle import HierarchyObject, LogicObject
from cocotb.simtime import get_sim_time
from cocotb.triggers import RisingEdge

IDLE, BUSY, NONSEQ, SEQ = range(4)
# HBURST: SINGLE, INCR, WRAP4, INCR4, WRAP8, INCR8, WRAP16, INCR16
HBURST_BEATS = {0: 1, 2: 4, 3: 4, 4: 8, 5: 8, 6: 16, 7: 16}  # fixed-length bursts
HBURST_WRAP = {2, 4, 6}
MAX_REPORTED = 20


class AhbChecker:
    def __init__(
        self, dut: HierarchyObject, port: str, clock: LogicObject, reset: LogicObject
    ):
        self.port = port
        self.clock = clock
        self.reset = reset
        self.violations: list[str] = []
        self.xfers = []  # (htrans, hburst, haddr, hsize)
        self.busy = 0

        def signal(name: str) -> LogicObject:
            return getattr(dut, f"{port}_{name}")

        self.signals = {
            "htrans": signal("htrans"),
            "haddr": signal("haddr"),
            "hsize": signal("hsize"),
            "hburst": signal("hburst"),
            "hwrite": signal("hwrite"),
            "hready": signal("hready"),
            "hresp": signal("hresp"),
        }
        self.lanes = len(signal("hwdata")) // 8
        self._clear()
        self._task = cocotb.start_soon(self._run())

    def _clear(self):
        self.prev = None  # the previous cycle's address phase
        self.prev_ready = None
        # the running burst: hburst, hsize, hwrite, first and next address, beats left
        self.run = None

    def _violation(self, msg: str):
        if len(self.violations) < MAX_REPORTED:
            self.violations.append(f"{get_sim_time('ns'):.0f} ns {self.port}: {msg}")

    async def _run(self):
        while True:
            await RisingEdge(self.clock)

            if not int(self.reset.value):
                self._clear()
                continue

            trans, addr, hsize, hburst, hwrite, ready, resp = (
                int(self.signals[s].value)
                for s in (
                    "htrans",
                    "haddr",
                    "hsize",
                    "hburst",
                    "hwrite",
                    "hready",
                    "hresp",
                )
            )
            cur = (trans, addr, hsize, hburst, hwrite)
            nbytes = 1 << hsize
            run = self.run
            if resp and ready and trans != IDLE:
                self._violation(
                    "a transfer follows the second cycle of an ERROR response"
                )
            if trans >= NONSEQ:
                if addr % nbytes:
                    self._violation(f"{addr:#x} not aligned to HSIZE {hsize}")
                if (addr & (self.lanes - 1)) + nbytes > self.lanes:
                    self._violation(
                        f"HSIZE {hsize} is wider than the {self.lanes}-byte bus"
                    )
            # an ERROR response may cancel a pending address phase
            if (
                self.prev
                and self.prev[0] >= NONSEQ
                and not self.prev_ready
                and not resp
                and cur != self.prev
            ):
                self._violation(
                    f"address phase changed while HREADY low: {self.prev} -> {cur}"
                )
            self.prev, self.prev_ready = cur, ready
            if resp and run:
                run["cancelled"] = True
            if not ready:
                continue

            if run and trans in (BUSY, SEQ):
                if (run["hburst"], run["hsize"], run["hwrite"]) != (
                    hburst,
                    hsize,
                    hwrite,
                ):
                    self._violation(
                        f"burst controls changed inside a burst: {run} -> {cur}"
                    )
                if addr != run["next"]:
                    self._violation(
                        f"{trans} at {addr:#x}, burst continues at {run['next']:#x}"
                    )
            if trans == BUSY:
                if not run:
                    self._violation("BUSY outside a burst")
                    continue
                run["busy_last"] = True
                self.busy += 1
                continue
            if trans == SEQ:
                if not run:
                    self._violation("SEQ outside a burst")
                    continue
                if run["left"] == 0:
                    self._violation("SEQ after the last beat of a fixed-length burst")
                if (
                    hburst not in HBURST_BEATS or hburst in (3, 5, 7)
                ) and addr >> 10 != run["first"] >> 10:
                    self._violation(f"INCR burst crosses 1KB at {addr:#x}")
            else:  # IDLE or NONSEQ end the running burst
                if run and not run["cancelled"]:
                    if run["busy_last"]:
                        self._violation("burst ends with BUSY")
                    if run["left"] not in (None, 0):
                        self._violation(
                            f"fixed-length burst ended with {run['left']} beats left"
                        )
                run = self.run = None
            if trans >= NONSEQ:
                self.xfers.append((trans, hburst, addr, hsize))
                if run is None:
                    run = self.run = {
                        "hburst": hburst,
                        "hsize": hsize,
                        "hwrite": hwrite,
                        "first": addr,
                        "left": None if hburst == 1 else HBURST_BEATS[hburst] - 1,
                        "cancelled": False,
                        "busy_last": False,
                    }
                else:
                    run["busy_last"] = False
                    if run["left"] is not None:
                        run["left"] -= 1
                run["next"] = addr + nbytes
                if hburst in HBURST_WRAP:
                    size_all = nbytes * HBURST_BEATS[hburst]
                    low = addr // size_all * size_all
                    if run["next"] == low + size_all:
                        run["next"] = low
