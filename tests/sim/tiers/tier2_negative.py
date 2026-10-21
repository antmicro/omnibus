# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
Tier 2: accesses the interconnect has to refuse. Here, to addresses no window covers:
the interconnect answers them itself, so the response is exact and nothing may reach a
target.
"""

import random

import cocotb
from cocotbext.axi import AxiResp
from harness.env import IcEnv

MAX_BURST_BEATS = 16
PAGE = 4096
TRANSACTIONS = 20  # per manager and direction, in mixed_legal_and_unmapped


def burst_in(lo: int, hi: int, nbytes: int, beats: int, position: str = "random"):
    """
    (address, beats, size) of a legal burst of at most `beats` beats inside [lo, hi) and
    within one 4 KiB page, at the start, at the end or anywhere in the range. A beat is
    `size` bytes: a bus word (`nbytes`), or less where the range is too small for one,
    so any non-empty range holds a burst. The range must not be empty.
    """
    assert hi > lo, f"empty range [{lo:#x}, {hi:#x})"
    size = nbytes
    while size > 1 and -(-lo // size) * size + size > hi:
        size //= 2
    first = -(-lo // size) * size
    words = (hi - first) // size
    beats = min(beats, words)
    index = {
        "first": 0,
        "last": words - beats,
        "random": random.randrange(words - beats + 1),
    }[position]
    address = first + index * size
    return address, min(beats, (PAGE - address % PAGE) // size), size


async def check_unmapped(env, port, address: int, beats: int, size: int, write: bool):
    """One access to an unmapped address: DECERR, and no memory changes."""
    manager = env.managers[port.name]
    length = beats * size
    log2_size = size.bit_length() - 1
    env.prime(address, length)
    kind = "write" if write else "read"
    if write:
        rsp = await env.op(
            manager.write(
                address,
                random.randbytes(length),
                awid=random.randrange(2 ** len(getattr(env.dut, f"{port.name}_awid"))),
                size=log2_size,
            )
        )
    else:
        rsp = await env.op(
            manager.read(
                address,
                length,
                arid=random.randrange(2 ** len(getattr(env.dut, f"{port.name}_arid"))),
                size=log2_size,
            )
        )
    assert rsp.resp == AxiResp.DECERR, (
        f"{port.name} {kind} of {beats} beats of {size} bytes at {address:#x}: "
        f"{rsp.resp!r}"
    )
    for name, mem in env.memories.items():
        assert mem.read(address, length) == env.tags(name, address, length), (
            f"{port.name} {kind} to unmapped {address:#x} changed {name}"
        )


@cocotb.test()
async def unmapped_access(dut):
    """
    Single reads and writes and bursts to every gap of the address map are answered
    with DECERR, and no memory changes. A gap smaller than a bus word is accessed with
    narrower beats, so every gap is tested. The specification has to leave a gap.
    """
    env = IcEnv(dut)
    await env.start()
    gaps = env.model.gaps()
    assert gaps, "the windows cover the whole address space: nothing is unmapped"

    for port in env.model.managers:
        for start, end in gaps:
            for beats in (1, MAX_BURST_BEATS):
                # a burst at the start and at the end of the gap, where a wrong window
                # edge shows, and one anywhere in it
                for position in ("first", "last", "random"):
                    burst = burst_in(start, end, port.data_width // 8, beats, position)
                    for write in (True, False):
                        await check_unmapped(env, port, *burst, write)

    env.finish()


@cocotb.test()
async def mixed_legal_and_unmapped(dut):
    """
    Every manager reads and writes at the same time, each access going to a random legal
    or unmapped address: the legal ones are answered OKAY with the right data, the
    unmapped ones DECERR, in whatever order the responses come back.
    Every reader and writer issues both kinds of access, in random order. Reads use the
    lower half of a window, which nothing writes; every manager writes only to its own
    part of the upper half.
    """
    env = IcEnv(dut)
    await env.start()
    managers = env.model.managers

    async def traffic(port, write: bool, legal: list, unmapped: list):
        manager = env.managers[port.name]
        nbytes = port.data_width // 8
        # both kinds at least once, the rest random, in random order
        kinds = [legal, unmapped]
        kinds += random.choices(kinds, k=TRANSACTIONS - len(kinds))
        random.shuffle(kinds)

        for ranges in kinds:
            lo, hi, target = random.choice(ranges)
            address, beats, size = burst_in(
                lo, hi, nbytes, random.randint(1, MAX_BURST_BEATS)
            )
            if target is None:
                await check_unmapped(env, port, address, beats, size, write)
                continue

            length = beats * size
            log2_size = size.bit_length() - 1
            env.prime(address, length)
            if write:
                data = random.randbytes(length)
                wr = await env.op(manager.write(address, data, size=log2_size))
                assert wr.resp == AxiResp.OKAY, (
                    f"{port.name} write at {address:#x}: {wr.resp!r}"
                )
                env.check_write(target, address, data, address, length)
            else:
                rd = await env.op(manager.read(address, length, size=log2_size))
                assert rd.resp == AxiResp.OKAY, (
                    f"{port.name} read at {address:#x}: {rd.resp!r}"
                )
                assert rd.data == env.tags(target, address, length), (
                    f"{port.name} read {rd.data.hex()} at {address:#x}, not "
                    f"{target}'s contents"
                )

    tasks = []
    for port in managers:
        for write in (True, False):
            legal = []
            for window in env.model.testable_windows(port.name):
                half = window.size // 2
                if write:
                    share = half // len(managers)
                    lo = window.base + half + managers.index(port) * share
                    hi = lo + share
                else:
                    lo, hi = window.base, window.base + half
                if hi > lo:
                    legal.append((lo, hi, window.target))
            unmapped = [(start, end, None) for start, end in env.model.gaps()]
            direction = "write" if write else "read"
            assert legal and unmapped, (
                f"{port.name} {direction}: needs a legal and an unmapped range to mix, "
                f"has {len(legal)} and {len(unmapped)}"
            )
            tasks.append(cocotb.start_soon(traffic(port, write, legal, unmapped)))
    for task in tasks:
        await task

    env.finish()
