# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""Tier 0: the generated top matches the spec and is quiet around reset."""

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge
from harness.env import RESET_CYCLES, IcEnv

IDLE_CYCLES = 100


@cocotb.test()
async def port_widths(dut):
    """Every modeled port exists with the spec's data width and the global address width."""
    env = IcEnv(dut)
    for port in env.model.ports.values():
        if port.name in env.model.unsupported:
            continue

        if port.protocol == "apb3":
            for sig, width in [("pwdata", port.data_width), ("prdata", port.data_width)]:
                handle = getattr(dut, f"{port.name}_{sig}")
                assert len(handle) == width, (
                    f"{port.name}_{sig} is {len(handle)} bits, spec: {width}"
                )
            for sig in ["paddr"]:
                handle = getattr(dut, f"{port.name}_{sig}")
                assert len(handle) == env.model.addr_width, (
                    f"{port.name}_{sig} is {len(handle)} bits, spec addr_width: {env.model.addr_width}"
                )
        else:
            for sig, width in [("wdata", port.data_width), ("rdata", port.data_width)]:
                handle = getattr(dut, f"{port.name}_{sig}")
                assert len(handle) == width, (
                    f"{port.name}_{sig} is {len(handle)} bits, spec: {width}"
                )
            for sig in ("awaddr", "araddr"):
                handle = getattr(dut, f"{port.name}_{sig}")
                assert len(handle) == env.model.addr_width, (
                    f"{port.name}_{sig} is {len(handle)} bits, spec addr_width: {env.model.addr_width}"
                )


@cocotb.test()
async def reset_idle(dut):
    """No VALID driven by DUT rises during reset or in the idle cycles after it."""
    env = IcEnv(dut)
    outputs = []
    for port in env.model.managers:
        if port.protocol == "apb3":
            continue
        outputs += [getattr(dut, f"{port.name}_{s}valid") for s in ("b", "r")]
    for port in env.model.memories:
        if port.protocol == "apb3":
            continue
        outputs += [getattr(dut, f"{port.name}_{s}valid") for s in ("aw", "w", "ar")]

    env.start_clocks()
    slowest = max(env.clocks.values(), key=lambda c: c[1])[0]
    reset_done = cocotb.start_soon(env.reset())
    cycles = 0
    while not reset_done.done() or cycles < IDLE_CYCLES:
        await RisingEdge(slowest)
        high = [o._name for o in outputs if int(o.value)]
        assert not high, f"asserted with no traffic: {high}"
        if reset_done.done():
            cycles += 1
    await ClockCycles(slowest, RESET_CYCLES)
    env.finish()
