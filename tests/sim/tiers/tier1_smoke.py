# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Tier 1: every manager reaches every window the spec gives it, with single-beat
reads and writes. Each access is checked three ways: the response code, the data
read back, and (through the tagged preload and backdoor checks) that it landed
in the right memory at the right address.
"""

import random

import cocotb
from cocotbext.axi import AxiResp
from harness.env import IcEnv


def word_bytes(env, manager: str) -> int:
    return env.model.ports[manager].data_width // 8


async def check_word(env, manager: str, target: str, address: int, nbytes: int):
    """Read the primed tags, write a random word, read it back."""
    m = env.managers[manager]
    env.prime(address, nbytes)

    rd = await env.op(m.read(address, nbytes))
    assert rd.resp == AxiResp.OKAY, f"{manager} read {address:#x}: {rd.resp!r}"
    assert rd.data == env.tags(target, address, nbytes), (
        f"{manager} read {address:#x} returned {rd.data.hex()}, not {target}'s contents"
    )

    data = random.randbytes(nbytes)
    wr = await env.op(m.write(address, data))
    assert wr.resp == AxiResp.OKAY, f"{manager} write {address:#x}: {wr.resp!r}"
    env.check_write(target, address, data, address, nbytes)

    rd = await env.op(m.read(address, nbytes))
    assert rd.data == data, (
        f"{manager} read back {rd.data.hex()} at {address:#x}, wrote {data.hex()}"
    )


def one_window_per_target(env, manager: str):
    seen = {}
    for w in env.model.testable_windows(manager):
        seen.setdefault(w.target, w)
    return list(seen.values())


@cocotb.test()
async def rw_every_window(dut):
    """First, middle and last word of every window, from every manager allowed to use it."""
    env = IcEnv(dut)
    await env.start()
    for manager in env.managers:
        n = word_bytes(env, manager)
        for w in env.model.testable_windows(manager):
            middle = w.base + (w.size // 2) // n * n
            for address in sorted({w.base, middle, w.end - n}):
                await check_word(env, manager, w.target, address, n)
    env.finish()


@cocotb.test()
async def address_bit_walk(dut):
    """base + 2**k for every address bit inside each window: catches decode and aliasing bugs."""
    env = IcEnv(dut)
    await env.start()
    for manager in env.managers:
        n = word_bytes(env, manager)
        for w in env.model.testable_windows(manager):
            offsets = [1 << k for k in range(n.bit_length() - 1, w.size.bit_length())]
            for off in offsets:
                if off <= w.size - n:
                    await check_word(env, manager, w.target, w.base + off, n)
    env.finish()


@cocotb.test()
async def byte_lanes(dut):
    """Narrow writes (every size below the bus width, on every lane) change only their bytes."""
    env = IcEnv(dut)
    await env.start()
    for manager, m in env.managers.items():
        n = word_bytes(env, manager)
        for w in one_window_per_target(env, manager):
            word = w.base
            size = 0
            while (1 << size) <= n:
                nb = 1 << size
                for off in range(0, n, nb):
                    env.prime(word, n)
                    data = random.randbytes(nb)
                    wr = await env.op(m.write(word + off, data, size=size))
                    assert wr.resp == AxiResp.OKAY, (
                        f"{manager} {nb}-byte write +{off}: {wr.resp!r}"
                    )
                    expected = bytearray(env.tags(w.target, word, n))
                    expected[off : off + nb] = data
                    env.check_write(w.target, word, bytes(expected), word, n)
                    rd = await env.op(m.read(word, n))
                    assert rd.data == bytes(expected), (
                        f"{manager} {nb}-byte write at +{off}: read {rd.data.hex()}, "
                        f"expected {bytes(expected).hex()}"
                    )
                size += 1
    env.finish()


@cocotb.test()
async def shared_visibility(dut):
    """What one manager writes to a window, every other manager allowed there reads back."""
    env = IcEnv(dut)
    await env.start()
    if len(env.managers) < 2:
        return
    for w in env.model.windows:
        if w.target in env.model.unsupported:
            continue
        sources = [s for s in w.sources if s in env.managers]
        if len(sources) < 2:
            continue
        writer, readers = sources[0], sources[1:]
        n = min(word_bytes(env, s) for s in sources)
        env.prime(w.base, n)
        data = random.randbytes(n)
        wr = await env.op(env.managers[writer].write(w.base, data))
        assert wr.resp == AxiResp.OKAY, f"{writer} write {w.base:#x}: {wr.resp!r}"
        for reader in readers:
            rd = await env.op(env.managers[reader].read(w.base, n))
            assert rd.resp == AxiResp.OKAY, f"{reader} read {w.base:#x}: {rd.resp!r}"
            assert rd.data == data, (
                f"{reader} read {rd.data.hex()} at {w.base:#x}, {writer} wrote {data.hex()}"
            )
    env.finish()
