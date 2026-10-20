# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
AHB memory for an AHB manager port of the generated RTL, built on cocotb-ahb: a
DUTManager on the port pins, a SimMem1PSubordinate behind it, and a
SimInterconnect between them that moves commands and responses every cycle.
Reads and writes go to the same byte memory the bus accesses hit, like AxiRam's.
"""

import random

import cocotb
from cocotb_AHB.AHB_common.InterconnectInterface import InterconnectWrapper
from cocotb_AHB.drivers.SimMem1PSubordinate import SimMem1PSubordinate
from cocotb_AHB.interconnect.SimInterconnect import SimInterconnect
from numpy.random import default_rng


class AhbRam:
    def __init__(self, manager, clock, reset, windows, min_wait=0, max_wait=3):
        """`manager`: the DUTManager on the AHB pins, `windows`: (base, size) of every range served."""
        self.sub = SimMem1PSubordinate(
            max(size for _, size in windows),
            manager.bus_width,
            min_wait_states=min_wait,
            max_wait_states=max_wait,
        )
        # cocotb-ahb draws wait states from an unseeded generator: derive it from the seeded
        # random module, so that a seed reproduces the timing of the AHB side as well
        self.sub.random_gen = default_rng(random.getrandbits(64))
        self.sub.register_clock(clock).register_reset(reset, inverted=True)

        interconnect = SimInterconnect()
        interconnect.register_clock(clock).register_reset(reset, inverted=True)
        interconnect.register_manager(manager)
        interconnect.register_subordinate(self.sub)
        for base, size in windows:
            interconnect.register_manager_subordinate_addr(
                manager, self.sub, base, size
            )
        self.bus = (
            InterconnectWrapper()
            .register_clock(clock)
            .register_reset(reset, inverted=True)
            .register_interconnect(interconnect)
        )

    def start(self):
        cocotb.start_soon(self.bus.start())
        cocotb.start_soon(self.sub.start())

    def read(self, address: int, length: int) -> bytes:
        return bytes(self.sub.mem.get(a, 0) for a in range(address, address + length))

    def write(self, address: int, data: bytes):
        for a, byte in enumerate(data, address):
            self.sub.mem[a] = byte
