# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
IcEnv: the test bench around one generated interconnect, built from its spec.

Every top-level port Omnibus calls a 'subordinate' gets a cocotbext-axi
AxiMaster; every 'manager' port gets a plain memory (AxiRam / AxiLiteRam).
Memories answer at absolute addresses, as the interconnect passes them through.

A memory accepts any address, so writing and reading back over the same path
can't tell a misrouted access from a correct one. Two checks close that gap:
`prime()` fills an address range in every memory with a pattern unique to that
memory (a read that lands in the wrong one returns the wrong tag), and
`check_write()` looks straight into the memories (backdoor access) after a write.
"""

import logging
import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, with_timeout
from cocotb_AHB.drivers.DutManager import DUTManager
from cocotbext.axi import AxiBus, AxiLiteBus, AxiLiteRam, AxiMaster, AxiRam, ApbBus, ApbRam

from omnibus.backend.topwrap_pulpplatform import set_clock_and_reset

from . import refmodel
from .ahb import AhbRam
from .ahbchecker import AhbChecker
from .apbchecker import ApbChecker
from .axichecker import AxiChecker

RESET_CYCLES = 10
# per bus operation, in cycles of the slowest clock
OP_TIMEOUT_CYCLES = 5000


def tag(mem_index: int, address: int) -> int:
    """Background byte memory `mem_index` holds at `address` after prime()."""
    return ((address * 0x9E3779B1) >> 13 ^ (0x5B + 0x3D * mem_index)) & 0xFF


class IcEnv:
    def __init__(self, dut):
        self.dut = dut
        self.model = refmodel.load(Path(os.environ["TOPWRAP_SIM_SPEC"]))
        self.clocks = {}
        self.resets = {}
        for name, freq in self.model.clocks.items():
            ports = {}
            set_clock_and_reset(ports, name)
            clk, rst = ports["clk_i"], ports["rst_ni"]
            # period in ps, even: cocotb's Clock splits it into two equal halves
            self.clocks[name] = (getattr(dut, clk), 2 * round(1e12 / freq / 2))
            self.resets[name] = getattr(dut, rst)
        self.slowest_ps = max(period for _, period in self.clocks.values())

        # cocotbext-axi logs every transaction at INFO
        logging.getLogger(f"cocotb.{dut._name}").setLevel(logging.WARNING)

        self.managers: dict[str, AxiMaster] = {}
        self.memories: dict[str, AxiRam | AxiLiteRam | ApbRam | AhbRam] = {}
        self.checkers: list[AxiChecker] = []
        mem_size = 2**self.model.addr_width
        for port in self.model.managers:
            clk, rst = self._clock_reset(port)
            bus = AxiBus.from_prefix(dut, port.name)
            self.managers[port.name] = AxiMaster(
                bus, clk, rst, reset_active_level=False
            )
            self.checkers.append(AxiChecker(dut, port.name, clk, rst))
        for port in self.model.memories:
            clk, rst = self._clock_reset(port)
            if port.protocol == "ahb3":
                manager = DUTManager(dut, port.data_width, name=port.name)
                windows = [
                    (w.base, w.size)
                    for w in self.model.windows
                    if w.target == port.name
                ]
                mem = AhbRam(manager, clk, rst, windows)
                self.checkers.append(AhbChecker(dut, port.name, clk, rst))
            elif port.protocol == "apb3":
                bus = ApbBus.from_prefix(dut, port.name)
                mem = ApbRam(bus, clk, rst, reset_active_level=False, size=mem_size)
                self.checkers.append(ApbChecker(dut, port.name, clk, rst))
            elif port.protocol == "axi4lite":
                bus = AxiLiteBus.from_prefix(dut, port.name)
                mem = AxiLiteRam(bus, clk, rst, reset_active_level=False, size=mem_size)
                self.checkers.append(AxiChecker(dut, port.name, clk, rst))
            else:
                bus = AxiBus.from_prefix(dut, port.name)
                mem = AxiRam(bus, clk, rst, reset_active_level=False, size=mem_size)
                self.checkers.append(AxiChecker(dut, port.name, clk, rst))
            self.memories[port.name] = mem
        self.mem_index = {name: i for i, name in enumerate(sorted(self.memories))}

    def _clock_reset(self, port: refmodel.Port):
        return self.clocks[port.clock][0], self.resets[port.clock]

    def start_clocks(self):
        for sig, period in self.clocks.values():
            cocotb.start_soon(Clock(sig, period, unit="ps").start())
        for mem in self.memories.values():
            if isinstance(mem, AhbRam):
                mem.start()

    async def reset(self):
        """Assert every reset, then release them in random order."""
        for rst in self.resets.values():
            rst.value = 0
        slowest = max(self.clocks.values(), key=lambda c: c[1])[0]
        await ClockCycles(slowest, RESET_CYCLES)
        for name in random.sample(list(self.resets), len(self.resets)):
            self.resets[name].value = 1
            await ClockCycles(self.clocks[name][0], 1)
        await ClockCycles(slowest, RESET_CYCLES)

    async def start(self):
        self.start_clocks()
        await self.reset()

    async def op(self, coro):
        """Await one bus operation, failing the test instead of hanging on a deadlock."""
        return await with_timeout(coro, OP_TIMEOUT_CYCLES * self.slowest_ps, "ps")

    def prime(self, address: int, length: int):
        """Fill [address, address+length) in every memory with that memory's tag bytes."""
        for name, mem in self.memories.items():
            idx = self.mem_index[name]
            mem.write(
                address, bytes(tag(idx, a) for a in range(address, address + length))
            )

    def tags(self, target: str, address: int, length: int) -> bytes:
        idx = self.mem_index[target]
        return bytes(tag(idx, a) for a in range(address, address + length))

    def check_write(
        self, target: str, address: int, data: bytes, primed: int, length: int
    ):
        """
        After writing `data` at `address` through the interconnect: `target` holds
        it, and every other memory still holds its tags over the primed range
        [primed, primed+length).
        """
        got = self.memories[target].read(address, len(data))
        assert got == data, (
            f"{target} holds {got.hex()} at {address:#x} after writing {data.hex()}"
        )
        for name, mem in self.memories.items():
            if name == target:
                continue
            assert mem.read(primed, length) == self.tags(name, primed, length), (
                f"write to {address:#x} for {target} also changed {name}"
            )

    def finish(self):
        """Fail on any protocol violation any checker has seen."""
        violations = [v for c in self.checkers for v in c.violations]
        assert not violations, "protocol violations:\n" + "\n".join(violations)
