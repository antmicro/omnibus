# UVM Tests of the AXI4 -> AHB3 Bridge

`tests/uvm` tests `omnibus/modules/axi_prconv_axi_ahb.sv` with UVM on [Verilator](https://verilator.org), using two verification IPs:

- the [AXI4 AVIP](https://github.com/mbits-mirafra/axi4_avip) master drives the bridge,
- the [AHB AVIP](https://github.com/mbits-mirafra/ahb_avip) slave answers it.

It tests the same things as the cocotb tests in `tests/sim/bridges` (see [simulationtests.md](simulationtests.md)), with a scoreboard that has a model of the conversion instead of a memory.

## Requirements

- Verilator newer than v5.052, with `--binary` and `--timing`: v5.052 deadlocks in the outstanding write path of the AXI4 AVIP ([issue 7](../tests/uvm/verilator_issues.md)), so it has to be a commit of master until a release has the fix.
- The UVM library for Verilator, `uvm-2017-1.0-vlt` branch of [chipsalliance/uvm-verilator](https://github.com/chipsalliance/uvm-verilator).
- Forks of the two AVIPs, with the changes listed in [The AVIP forks](#the-avip-forks).

They are looked up in the environment variables `UVM_CORE`, `AXI4_AVIP` and `AHB_AVIP`, then in `tests/uvm/third_party/{uvm-verilator,axi4_avip,ahb_avip}`.
The tests skip themselves when any of them is missing.

```
export UVM_CORE=/path/to/uvm-verilator AXI4_AVIP=/path/to/axi4_avip AHB_AVIP=/path/to/ahb_avip
pytest tests/uvm                         # everything
pytest tests/uvm -k "error and 64b"      # one test of one configuration
pytest tests/uvm --uvm-waves             # also write <test>.fst next to every log
```

The simulator is built once for every configuration, in `tests/uvm/.build/w<width>_d<depth>-<hash>/`, about 1 to 2 minutes each, and rebuilt when anything it depends on changes.
Every test runs in it by name and takes a few seconds; its log is `<test>.log` in the same directory.
The configurations are the data width and the bridge's `FifoDepth`, `CONFIGS` in `test_uvm.py`: 64 bits with depth 3 (the default), and 32 bits with depth 2.

## Layout

```
tests/uvm/
|-- uvm_build.py              Verilator build: sources, defines, flags
|-- test_uvm.py               pytest: builds, runs every UVM test, reads its UVM report
|-- conftest.py               --uvm-work-dir, --uvm-waves
|-- hdl/
|   |-- bridge_tb.sv          top: clock, reset, both BFMs, the bridge, run_test()
|   `-- bridge_ahb_checker.sv AHB protocol rules, checked on every cycle
|-- hvl/
|   |-- bridge_pkg.sv         the UVM package
|   |-- bridge_scoreboard.svh model of the conversion and the checks
|   |-- bridge_env.svh        the two VIP agents and the scoreboard
|   `-- bridge_tests.svh      sequences and tests
`-- verilator_issues.md       Verilator bugs found building this
```

## How a test works

```
AXI4 AVIP master agent --> bridge --> AHB AVIP slave agent
   |  monitor: AW W B AR R           |  monitor: every transfer, with its data phase
   +-------------> scoreboard <------+
```

The tests build AXI transactions directly (not randomized with constraints, so the strobes, addresses and lengths are exactly what the test says) and run them on the write and read sequencers of the AXI4 master agent, which can run at the same time.
The AHB subordinate answers every transfer with random read data and a random number of wait states, and with an ERROR outside of the address window the test sets.

The scoreboard is given the order of the bridge's transactions by the AW and AR handshakes, and for each one:

- works out, from the AXI address rules, which byte lanes every beat covers;
- splits every beat into naturally aligned AHB transfers (for a write, only the lanes WSTRB enables): the largest chunk that starts at the first lane of the beat still to be transferred and fits;
- checks every AHB transfer: HADDR, HSIZE, HWRITE, HPROT (from AWPROT, AWCACHE), HMASTLOCK, and for a write the data lane by lane;
- checks that (HTRANS, HBURST) is allowed there: only a beat that is a single transfer of the beat's size may be part of an AHB burst, as INCR for an INCR burst, and as WRAP4, WRAP8 or WRAP16 for a read of a WRAP burst of 4, 8 or 16 beats; everything else is NONSEQ SINGLE;
- for a read, builds each beat from the data the AHB slave returned and compares it with the R beat, and checks RID, RLAST and RRESP;
- for a write, checks BID and BRESP;
- after an AHB ERROR expects no more transfers of the transaction, SLVERR on the R beats from the failing one on or on B, and no write data after it.

It also keeps, for every transaction, the timing and the HTRANS and HBURST of every transfer, which the `shapes`, `busy`, `throughput` and `arbitration` tests look at.
At the end it checks that nothing the monitors saw is left unexplained.

`bridge_ahb_checker` is a procedural port of the AHB monitor of the cocotb tests, and reports through UVM as well: alignment, a stable address phase while HREADY is low, no transfer after the second cycle of an ERROR, SEQ and BUSY only inside a burst at the address it continues with, constant HBURST, HSIZE and HWRITE in a burst, INCR within 1KB, fixed length bursts completed, and no burst ending with BUSY.

## The tests

| Test | What it covers |
|------|----------------|
| `smoke` | one write and one read |
| `regular` | full-width INCR bursts of 1 to 8 beats |
| `narrow` | every size below the bus width on every aligned lane |
| `unaligned` | start addresses that are not a multiple of the size, bursts of 1, 2 and 5 beats |
| `burst_types` | FIXED, INCR 16, WRAP 2, 4, 8 and 16 of every size |
| `strobes` | random, sparse and empty WSTRB |
| `ids` | all 16 IDs on B and R |
| `random` | 100 writes and 100 reads at once with random sizes, bursts, B and R backpressure and AHB wait states |
| `error` | AHB errors at the start, before and in the middle of a burst, for writes and reads, and a good transaction after each |
| `arbitration` | a write and a read ready at the same time, 20 times, are served in turn |
| `shapes` | INCR, 1KB boundary, WRAP4/8/16, FIXED and WRAP2 reads, INCR and WRAP writes: the AHB bursts they become |
| `busy` | a read burst while the R channel is blocked: BUSY on AHB |
| `throughput` | cycles of 16-beat bursts with no wait states |

`FifoDepth` is passed to the tests as `+FIFO_DEPTH`; `shapes` and `throughput` expect less of a build with a FIFO of 1 or 2 beats, as the cocotb tests do.

## The AVIP forks

Neither AVIP builds on Verilator as it is, and neither one can verify a pipelined AHB manager, so both were forked.
The changes are on the `verilator-support` branches, and they keep the AVIPs working on other simulators:

**AXI4 AVIP**
- `bind` of the assertion modules in the agent BFMs is under ``ifndef VERILATOR`` (Verilator issue 2 in [verilator_issues.md](../tests/uvm/verilator_issues.md)); the build leaves the assertion modules out.
- `REQ` and `RSP` are replaced by the transaction types in the driver proxies and the base sequences (issue 3).
- `uvm_test_done` does not exist in 1800.2 UVM, the drain time is set with `phase.get_objection()` in `run_phase`.
- The data width and the address width can be set with the macros `AXI4_DATA_WIDTH` and `AXI4_ADDRESS_WIDTH` (default 512 and 32, as before).
- The sequence item converter dropped words that were zero and reversed the order of the beats when it turned what a BFM sampled into a transaction, and did not copy RLAST; it keeps every beat in order now.
- The monitor sampled BID and BRESP a cycle after the B handshake; it samples them at it.

**AHB AVIP**
- `bind`, `uvm_test_done`, and the data and address width macros (`AHB_DATA_WIDTH`, `AHB_ADDR_WIDTH`), as above.
- `AhbSlaveDriverBFM` is rewritten as a pipelined subordinate: it queues every accepted address phase and answers it in its data phase, with the wait states, the read data and the ERROR response the sequence item says, or ERROR outside of `[minimumAddress, maximumAddress]`. The original served a whole burst in one loop, with no data phase of its own, and drove HRESP high during wait states.
- `AhbSlaveMonitorBFM` is rewritten to follow the pipeline: it returns one item per transfer once its data phase has ended (and one for every BUSY), with the data of the last cycle of the phase, HRESP and the number of wait states.
- Both keep their queues in a new class, `AhbTransferFifo` (Verilator issue 5).
- The converter that turns a monitor sample into a transaction copied elements into empty queues, which lost the data; it fills them now.
