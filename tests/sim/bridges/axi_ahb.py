# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
cocotb tests of axi_prconv_axi_ahb on its own: cocotbext-axi channel sources and sinks
drive the AXI side, a cocotb-ahb memory answers on the AHB side. A Python model of AXI
addressing says which bytes each beat of a burst reads or writes, and the AHB memory is
compared with a byte-for-byte model after every write.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.simtime import get_sim_time
from cocotb.triggers import ClockCycles, with_timeout
from cocotb_AHB.drivers.DutManager import DUTManager
from cocotbext.axi import AxiBus
from cocotbext.axi.axi_channels import (
    AxiARSource,
    AxiARTransaction,
    AxiAWSource,
    AxiAWTransaction,
    AxiBSink,
    AxiRSink,
    AxiWSource,
    AxiWTransaction,
)
from harness.ahb import AhbRam
from harness.ahbchecker import NONSEQ, SEQ, AhbChecker

FIXED, INCR, WRAP = 0, 1, 2
OKAY, SLVERR = 0, 2
BASE = 0x2000_0000
SIZE = 0x4000
OP_TIMEOUT_NS = 100_000


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.lanes = len(dut.src_wstrb)
        self.id_max = 2 ** len(dut.src_awid)
        clk, rst = dut.clk_i, dut.rst_ni
        bus = AxiBus.from_prefix(dut, "src")
        args = (clk, rst)
        self.aw = AxiAWSource(bus.write.aw, *args, reset_active_level=False)
        self.w = AxiWSource(bus.write.w, *args, reset_active_level=False)
        self.b = AxiBSink(bus.write.b, *args, reset_active_level=False)
        self.ar = AxiARSource(bus.read.ar, *args, reset_active_level=False)
        self.r = AxiRSink(bus.read.r, *args, reset_active_level=False)
        manager = DUTManager(dut, self.lanes * 8, name="dst")
        self.mem = AhbRam(manager, clk, rst, [(BASE, SIZE)])
        self.model = bytearray(SIZE)
        self.depth = int(os.environ["FIFO_DEPTH"])
        self.ahb = AhbChecker(dut, "dst", clk, rst)

    @property
    def transfers(self):
        return len(self.ahb.xfers)

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk_i, 10, unit="ns").start())
        self.mem.start()
        self.dut.rst_ni.value = 0
        await ClockCycles(self.dut.clk_i, 10)
        self.dut.rst_ni.value = 1
        await ClockCycles(self.dut.clk_i, 5)
        self.prime()

    def prime(self):
        """Fill the memory and the model with the same random bytes."""
        self.model[:] = random.randbytes(SIZE)
        self.mem.write(BASE, bytes(self.model))

    def beats(self, addr, n, size, burst):
        """[(word address, first lane, end lane)] of every beat, per the AXI address rules."""
        nbytes = 1 << size
        out = []
        for i in range(n):
            lo = addr % self.lanes
            out.append((addr - lo, lo, lo // nbytes * nbytes + nbytes))
            aligned = addr // nbytes * nbytes
            if burst == INCR:
                addr = aligned + nbytes
            elif burst == WRAP:
                low = addr // (nbytes * n) * (nbytes * n)
                addr = aligned + nbytes
                if addr == low + nbytes * n:
                    addr = low
        return out

    async def write(self, addr, size, burst, beats, awid=0):
        """`beats`: [(data bytes, wstrb)]; updates the model with the beats inside the window, returns BRESP."""
        n = len(beats)
        await self.aw.send(
            AxiAWTransaction(
                awid=awid, awaddr=addr, awlen=n - 1, awsize=size, awburst=burst
            )
        )
        for i, (data, strb) in enumerate(beats):
            await self.w.send(
                AxiWTransaction(
                    wdata=int.from_bytes(data, "little"), wstrb=strb, wlast=i == n - 1
                )
            )
        b = await with_timeout(self.b.recv(), OP_TIMEOUT_NS, "ns")
        assert b.bid == awid, f"BID {b.bid}, expected {awid}"
        good = self.good_beats_count(addr, n, size, burst)
        for (word, lo, hi), (data, strb) in list(
            zip(self.beats(addr, n, size, burst), beats)
        )[:good]:
            for lane in range(lo, hi):
                if strb >> lane & 1:
                    self.model[word - BASE + lane] = data[lane]
        return b.bresp

    def good_beats_count(self, addr, n, size, burst):
        """Returns the number of beats before the first one outside the window, where the AHB side answers with ERROR."""
        beats = self.beats(addr, n, size, burst)
        return next(
            (
                i
                for i, (word, _, _) in enumerate(beats)
                if not BASE <= word < BASE + SIZE
            ),
            n,
        )

    async def read(self, addr, n, size, burst, arid=0):
        """Returns [(data bytes, RRESP)] after checking RID and RLAST; data is not checked."""
        await self.ar.send(
            AxiARTransaction(
                arid=arid, araddr=addr, arlen=n - 1, arsize=size, arburst=burst
            )
        )
        out = []
        for i in range(n):
            r = await with_timeout(self.r.recv(), OP_TIMEOUT_NS, "ns")
            assert r.rid == arid, f"RID {r.rid}, expected {arid}"
            assert r.rlast == (i == n - 1), f"RLAST {r.rlast} on beat {i} of {n}"
            out.append((int(r.rdata).to_bytes(self.lanes, "little"), r.rresp))
        return out

    async def check_read(self, addr, n, size, burst, arid=0):
        """Read a burst and compare the bytes each beat carries with the model."""
        got = await self.read(addr, n, size, burst, arid)
        good = self.good_beats_count(addr, n, size, burst)
        for i, ((word, lo, hi), (data, resp)) in enumerate(
            zip(self.beats(addr, n, size, burst), got)
        ):
            if i >= good:
                assert resp == SLVERR, (
                    f"read {addr:#x} beat {i} follows an AHB error: RRESP {resp}"
                )
                continue
            assert resp == OKAY, f"read {addr:#x} beat {i}: RRESP {resp}"
            want = bytes(self.model[word - BASE + lo : word - BASE + hi])
            assert data[lo:hi] == want, (
                f"read {addr:#x} size {size} burst {burst} beat {i}: "
                f"lanes {lo}:{hi} are {data[lo:hi].hex()}, expected {want.hex()}"
            )

    def finish(self):
        """Fail on any AHB protocol violation the checker has seen."""
        assert not self.ahb.violations, "AHB protocol violations:\n" + "\n".join(
            self.ahb.violations
        )

    def check_memory(self):
        assert self.mem.read(BASE, SIZE) == bytes(self.model), self.diff()

    def diff(self):
        got = self.mem.read(BASE, SIZE)
        bad = [i for i in range(SIZE) if got[i] != self.model[i]]
        return (
            f"AHB memory differs from the model at {[hex(BASE + i) for i in bad[:8]]}"
        )

    def full_beats(self, n, strb=None):
        return [
            (
                random.randbytes(self.lanes),
                (1 << self.lanes) - 1 if strb is None else strb,
            )
            for _ in range(n)
        ]

    def random_burst(self, base, span):
        """(address, beats, size, burst) that is legal AXI and stays inside [base, base+span)."""
        size = random.randint(0, self.lanes.bit_length() - 1)
        burst = random.choice([INCR, INCR, INCR, WRAP, FIXED])
        addr = base + random.randrange(span - 4096)
        if burst == WRAP:
            n = random.choice([2, 4, 8, 16])
            addr = addr // (1 << size) * (1 << size)
        else:
            n = random.randint(1, 16)
        if burst == INCR:  # no 4KB crossing
            n = min(n, (0x1000 - addr % 0x1000 + (1 << size) - 1) // (1 << size))
        return addr, n, size, burst


@cocotb.test()
async def regular(dut):
    """Full-width single beats and short bursts: write, read back, memory equals the model."""
    t = Bench(dut)
    await t.start()
    for _ in range(50):
        addr = BASE + random.randrange(SIZE // t.lanes - 16) * t.lanes
        n = random.randint(1, 8)
        size = t.lanes.bit_length() - 1
        before = t.transfers
        assert await t.write(addr, size, INCR, t.full_beats(n)) == OKAY
        assert t.transfers - before == n, (
            f"{t.transfers - before} AHB transfers for {n} full-width beats"
        )
        await t.check_read(addr, n, size, INCR)
        assert t.transfers - before == 2 * n
    t.check_memory()
    t.finish()


@cocotb.test()
async def narrow(dut):
    """Every size below the bus width on every naturally aligned lane."""
    t = Bench(dut)
    await t.start()
    for size in range(t.lanes.bit_length() - 1):
        for lane in range(0, t.lanes, 1 << size):
            addr = BASE + 0x100 + lane
            before = t.transfers
            assert await t.write(addr, size, INCR, t.full_beats(1)) == OKAY
            await t.check_read(addr, 1, size, INCR)
            assert t.transfers - before == 2, "a narrow beat takes one AHB transfer"
    t.check_memory()
    t.finish()


@cocotb.test()
async def unaligned(dut):
    """Start addresses that are not a multiple of the size, the first beat is partial."""
    t = Bench(dut)
    await t.start()
    for size in range(1, t.lanes.bit_length()):
        for offset in range(1, 1 << size):
            for n in (1, 2, 5):
                addr = BASE + 0x200 + offset
                assert await t.write(addr, size, INCR, t.full_beats(n)) == OKAY
                await t.check_read(addr, n, size, INCR)
    t.check_memory()
    t.finish()


@cocotb.test()
async def burst_types(dut):
    """FIXED, WRAP and INCR bursts of every size, checked against the AXI address rules."""
    t = Bench(dut)
    await t.start()
    for size in range(t.lanes.bit_length()):
        nbytes = 1 << size
        for burst, n in [
            (FIXED, 4),
            (INCR, 16),
            (WRAP, 2),
            (WRAP, 4),
            (WRAP, 8),
            (WRAP, 16),
        ]:
            for offset in random.sample(range(0, 0x40, nbytes), 3):
                addr = BASE + 0x400 + offset
                assert await t.write(addr, size, burst, t.full_beats(n)) == OKAY
                await t.check_read(addr, n, size, burst)
    t.check_memory()
    t.finish()


@cocotb.test()
async def strobes(dut):
    """Sparse and empty WSTRB: only the enabled bytes of the beat are written."""
    t = Bench(dut)
    await t.start()
    for _ in range(100):
        size = random.randint(0, t.lanes.bit_length() - 1)
        addr = BASE + 0x800 + random.randrange(0x100)
        n = random.randint(1, 4)
        beats = [
            (random.randbytes(t.lanes), random.getrandbits(t.lanes)) for _ in range(n)
        ]
        assert await t.write(addr, size, INCR, beats) == OKAY
        await t.check_read(addr, n, size, INCR)
    t.check_memory()
    t.finish()


@cocotb.test()
async def ids(dut):
    """BID and RID follow the request."""
    t = Bench(dut)
    await t.start()
    for i in range(t.id_max):
        assert await t.write(BASE + 8 * i, 2, INCR, t.full_beats(1), awid=i) == OKAY
        await t.check_read(BASE + 8 * i, 1, 2, INCR, arid=i)
    t.finish()


@cocotb.test()
async def random_traffic(dut):
    """
    Random legal bursts with random backpressure, a writer and a reader running at once.
    The reader stays in a part of the window the writer doesn't touch.
    """
    t = Bench(dut)
    await t.start()
    for chan in (t.w, t.b, t.r):
        chan.set_pause_generator(iter(lambda: random.random() < 0.3, None))
    half = SIZE // 2

    async def writer():
        for _ in range(100):
            addr, n, size, burst = t.random_burst(BASE, half)
            beats = [
                (random.randbytes(t.lanes), random.getrandbits(t.lanes))
                for _ in range(n)
            ]
            assert (
                await t.write(addr, size, burst, beats, random.randrange(t.id_max))
                == OKAY
            )

    async def reader():
        for _ in range(100):
            addr, n, size, burst = t.random_burst(BASE + half, half)
            await t.check_read(addr, n, size, burst, random.randrange(t.id_max))

    tasks = [cocotb.start_soon(writer()), cocotb.start_soon(reader())]
    for task in tasks:
        await with_timeout(task, 100 * OP_TIMEOUT_NS, "ns")
    t.check_memory()
    t.finish()


@cocotb.test()
async def ahb_error(dut):
    """
    An AHB error stops the AHB transfers of the burst: the beats before it complete, the
    read beats from it on and the B of a write are SLVERR, and the next transaction is fine.
    """
    t = Bench(dut)
    await t.start()
    size = t.lanes.bit_length() - 1
    for start, n in [
        (BASE + SIZE + 0x1000, 3),  # fails at once
        (BASE - 2 * t.lanes, 6),  # fails first, would succeed later
        (BASE + SIZE - 3 * t.lanes, 8),  # fails in the middle
    ]:
        assert t.good_beats_count(start, n, size, INCR) < n
        assert await t.write(start, size, INCR, t.full_beats(n)) == SLVERR
        await t.check_read(start, n, size, INCR)
        t.check_memory()
        assert await t.write(BASE, 2, INCR, t.full_beats(1)) == OKAY
        await t.check_read(BASE, 1, 2, INCR)
    t.finish()


@cocotb.test()
async def arbitration(dut):
    """A read is served while a queue of back-to-back writes is pending, not after all of them."""
    t = Bench(dut)
    await t.start()
    done = []

    async def writes():
        for i in range(20):
            addr = BASE + 0x1000 + 4 * i
            t.aw.send_nowait(
                AxiAWTransaction(awaddr=addr, awlen=0, awsize=2, awburst=INCR)
            )
            t.w.send_nowait(AxiWTransaction(wdata=i, wstrb=0xF, wlast=1))
        for _ in range(20):
            await t.b.recv()
        done.append("writes")

    async def read():
        await ClockCycles(dut.clk_i, 20)
        await t.check_read(BASE + 0x2000, 1, 2, INCR)
        done.append("read")

    for task in [cocotb.start_soon(writes()), cocotb.start_soon(read())]:
        await with_timeout(task, 100 * OP_TIMEOUT_NS, "ns")
    assert done == ["read", "writes"], f"the read finished after the writes: {done}"
    t.finish()


def kinds(xfers):
    """[(htrans, hburst)] of a transfer log."""
    return [(trans, hburst) for trans, hburst, _, _ in xfers]


@cocotb.test()
async def ahb_bursts(dut):
    """Which AHB bursts an AXI burst turns into."""
    t = Bench(dut)
    await t.start()
    size = t.lanes.bit_length() - 1

    async def log_of(coro):
        before = t.transfers
        await coro
        return t.ahb.xfers[before:]

    # INCR: one burst
    addr = BASE + 0x100
    log = await log_of(t.check_read(addr, 8, size, INCR))
    assert kinds(log) == [(NONSEQ, 1)] + [(SEQ, 1)] * 7, kinds(log)
    assert [x[2] for x in log] == [addr + i * t.lanes for i in range(8)]

    # INCR over a 1KB boundary: a new burst starts there
    addr = BASE + 0x400 - 3 * t.lanes
    log = await log_of(t.check_read(addr, 8, size, INCR))
    assert (
        kinds(log) == [(NONSEQ, 1)] + [(SEQ, 1)] * 2 + [(NONSEQ, 1)] + [(SEQ, 1)] * 4
    ), kinds(log)
    assert log[3][2] == BASE + 0x400

    # WRAP4, WRAP8 and WRAP16 reads: fixed-length bursts
    for n, hburst in [(4, 2), (8, 4), (16, 6)]:
        addr = BASE + 0x800 + 3 * t.lanes
        log = await log_of(t.check_read(addr, n, size, WRAP))
        assert kinds(log) == [(NONSEQ, hburst)] + [(SEQ, hburst)] * (n - 1), (
            n,
            kinds(log),
        )

    # no AHB equivalent: FIXED, WRAP2
    for burst, n in [(FIXED, 4), (WRAP, 2)]:
        log = await log_of(t.check_read(BASE + 0x900, n, size, burst))
        assert kinds(log) == [(NONSEQ, 0)] * n, (burst, kinds(log))

    # writes: INCR is a burst, WRAP is not
    addr = BASE + 0xA00
    log = await log_of(t.write(addr, size, INCR, t.full_beats(8)))
    if t.depth >= 2:  # a one-beat W FIFO can't hold the next beat in time
        assert kinds(log) == [(NONSEQ, 1)] + [(SEQ, 1)] * 7, kinds(log)
    log = await log_of(t.write(addr, size, WRAP, t.full_beats(4)))
    assert kinds(log) == [(NONSEQ, 0)] * 4, kinds(log)

    # a beat that has to be split ends the burst and is sent as singles
    beats = t.full_beats(3)
    beats[1] = (beats[1][0], 0b101 if t.lanes >= 4 else 1)
    log = await log_of(t.write(addr, size, INCR, beats))
    assert kinds(log)[0] == (NONSEQ, 1) and kinds(log)[-1] == (NONSEQ, 1), kinds(log)
    assert all(k == (NONSEQ, 0) for k in kinds(log)[1:-1]), kinds(log)
    assert len(log) >= 4
    t.check_memory()
    t.finish()


@cocotb.test()
async def busy(dut):
    """A running read burst waits with BUSY while the R channel is blocked."""
    t = Bench(dut)
    await t.start()
    size = t.lanes.bit_length() - 1
    t.r.pause = True
    task = cocotb.start_soon(t.check_read(BASE, 8 + t.depth, size, INCR))
    await ClockCycles(dut.clk_i, 40)
    t.r.pause = False
    await with_timeout(task, OP_TIMEOUT_NS, "ns")
    assert t.ahb.busy > 0, "no BUSY while the R channel was blocked"
    t.finish()


@cocotb.test()
async def throughput(dut):
    """Aligned full-width INCR bursts with no wait states run at about one beat per cycle."""
    t = Bench(dut)
    await t.start()
    t.mem.sub.min_wait_cycles = t.mem.sub.max_wait_cycles = 0
    size = t.lanes.bit_length() - 1
    n = 16

    async def cycles(coro):
        start = get_sim_time("ns")
        await coro
        return (get_sim_time("ns") - start) // 10

    rd = await cycles(t.read(BASE, n, size, INCR))
    wr = await cycles(t.write(BASE, size, INCR, t.full_beats(n)))
    dut._log.warning(
        f"FifoDepth {t.depth}: {n} beats read in {rd} cycles, written in {wr}"
    )
    if t.depth >= 2:
        assert wr <= n + 8, f"{n} beats written in {wr} cycles"
    # a read beat is issued 3 cycles before it can be taken off the FIFO
    if t.depth >= 3:
        assert rd <= n + 8, f"{n} beats read in {rd} cycles"
    elif t.depth == 2:
        assert rd <= 3 * n // 2 + 8, f"{n} beats read in {rd} cycles"
    t.finish()
