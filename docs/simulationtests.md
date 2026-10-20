# Simulation Tests

`tests/sim` holds simulation tests of the RTL Omnibus generates.
Each specification in `tests/sim/specs/` is turned into SystemVerilog, compiled with [Verilator](https://verilator.org), and exercised by [cocotb](https://www.cocotb.org/) 2.0 tests using [cocotbext-axi](https://github.com/alexforencich/cocotbext-axi) managers and memories, and a [cocotb-ahb](https://github.com/antmicro/cocotb-ahb) memory for AHB3 ports.

The bridge `axi_prconv_axi_ahb` also has UVM tests, with the AXI4 and AHB AVIPs on Verilator; see [uvmtests.md](uvmtests.md).

This page describes how the suite is organized, what it generates while running, and how a single test runs, for reviewers of the suite and for anyone extending it.

## Quick start

Requirements:
- Verilator on `PATH`; the suite was run with v5.052, 5.053 and a newer commit of Verilator's master.
- Topwrap (see [Installation](installation.md)).
- The Python packages in the `sim` extra: `pip install ".[sim]"` (cocotb, cocotbext-axi, cocotb-ahb, pytest).
- The pulp submodules in `omnibus/third_party` (`axi`, `common_cells`, `tech_cells_generic`): `git submodule update --init`.

The tests skip themselves when Verilator, cocotb, cocotbext-axi or Topwrap are missing.
The bridge tests (see [Converter tests](#converter-tests)) also need cocotb-ahb.

```
pytest tests/sim                                # everything
pytest tests/sim -m tier1_smoke                 # one tier
pytest tests/sim -k dw_mix                      # one specification
pytest tests/sim -k "dw_mix and tier1_smoke"    # one specification and tier
COCOTB_TEST_FILTER=byte_lanes pytest tests/sim -k "dw_mix and tier1_smoke"
                                                # one cocotb test
pytest tests/sim --sim-waves                    # also dump waveforms
pytest tests/sim/test_bridges.py --sim-seed 42   # repeat the random stimulus of the bridge tests
```

## Layout

```
tests/sim/
|-- conftest.py          pytest options, tier markers, skip without Verilator
|-- test_sim.py          pytest entry point: specifications x tiers
|-- specs/*.yml          the specifications under test, one feature each
|-- harness/
|   |-- __init__.py      paths and the list of tiers
|   |-- generate.py      specification -> RTL -> Verilator build, cached
|   |-- refmodel.py      what a specification says the interconnect must do
|   |-- env.py           the test bench: clocks, resets, managers, memories
|   |-- ahb.py           AHB memory (cocotb-ahb) with the same backdoor access as AxiRam
|   |-- axichecker.py    passive AXI protocol checker
|   |-- apbchecker.py    passive APB protocol checker
|   `-- ahbchecker.py    passive AHB protocol checker
|-- tiers/
|   |-- tier0_build.py   cocotb tests of tier 0
|   `-- tier1_smoke.py   cocotb tests of tier 1
|-- test_bridges.py      pytest entry point of the converter tests
|-- bridges/axi_ahb.py   cocotb tests of the AXI4 -> AHB3 bridge module alone
`-- .build/              generated, git-ignored: RTL, simulator builds, logs
```

Two kinds of tests are involved, and it helps to keep them apart:
- **pytest tests**, in `test_sim.py`, which is what `pytest` collects and reports:
  - `test_build[<spec>]` generates and builds one specification;
  - `test_tier[<spec>-<tier>]` runs one tier module against one build.
- **cocotb tests**, the `@cocotb.test()` functions in `tiers/*.py`. They run inside the simulator. One `test_tier` runs all cocotb tests of its tier module in a single simulator process, and fails if any of them fails.

## How a test run works

The whole path of one `pytest tests/sim` run, for one specification:

```
pytest                                 simulator process (Verilator + cocotb)
------                                 --------------------------------------
collect specs/*.yml x TIERS
test_build[spec]
  builds fixture -> generate.build()
    refmodel.load(spec)
    cached build? -- yes ---------+
    _check_generation(spec)       |
    omnibus <spec>                |
    topwrap repo parse ...        |
    topwrap build ...             |
    Verilator build (runner)      |
  check EXPECTED_MODULES  <-------+
test_tier[spec-tier]  (per tier)
  runner.test(test_module=tier,
    TOPWRAP_SIM_SPEC=spec)  ----------> import tiers/<tier>.py
                                        for each @cocotb.test():
                                          IcEnv(dut): load $TOPWRAP_SIM_SPEC,
                                            models and checkers per port
                                          env.start(): clocks, reset
                                          accesses, checks, env.finish()
                                        write run/<tier>/results.xml
  get_results(results.xml)  <----------
  assert no cocotb test failed
```

### Collection

`test_sim.py` parametrizes both pytest tests over every `specs/*.yml` and, for `test_tier`, over `TIERS` from `harness/__init__.py`.
Each tier gets a pytest marker of the same name (registered in `conftest.py`), which is what `-m tier1_smoke` selects.

The session-scoped `builds` fixture builds each specification once and hands the same build to `test_build` and every `test_tier` of that specification.
If the build fails, the fixture remembers the exception: `test_build` reports it, and every `test_tier` of that specification is skipped with a pointer to `test_build`, instead of failing with the same error.

### Generating the DUT

`generate.build()` (in `harness/generate.py`) runs the same steps as `tests/generate.sh`, in a build directory of its own:

1. `_check_generation()` runs `read_yaml()` and `process()` in-process and fails on any recorded error.
   The `omnibus` command line tool exits 0 even when `process()` records errors, so without this a broken specification would still produce RTL.
2. `omnibus <spec>` generates the interconnect RTL and a Topwrap design of it into `out/`.
   It also writes `topwrap.yaml`, a Topwrap configuration that registers `out/modules` as a repository named `repo`.
3. `topwrap repo parse repo out/src -I` infers Topwrap IP core descriptions for the generated modules and stores them in that repository.
   Vendor interface definitions it writes there are then deleted (workaround for #102866).
4. The design `out/<name>.yml` is copied next to `out/` (workaround for #102867), and `topwrap build --design <name>.yml` writes the top-level module `build/<name>.sv`.
5. cocotb's runner builds that top level with Verilator (see [Building the simulator](#building-the-simulator)).

All commands and their output go to `generate.log`, so a failed generation can be read, and re-run by hand, from there.

### What is generated

Everything below `tests/sim/.build/` is generated during the run.
For a specification `specs/<spec>.yml` with `name: <name>`:

```
tests/sim/.build/<spec>-<hash>[-waves]/
|-- generate.log                   commands of steps 2-4 and their output
|-- topwrap.yaml                   step 2: Topwrap config, repository `repo`
|-- out/                           step 2, omnibus:
|   |-- src/*.sv, *.vh             RTL: crossbars (from axi_intercon_gen),
|   |                              converter and register slice wrappers
|   |-- <name>.yml                 Topwrap design of the interconnect
|   |-- <name>.f                   filelist of the RTL in src/ to compile
|   |-- *.core                     FuseSoC cores written by axi_intercon_gen
|   `-- modules/                   the `repo` repository:
|       |-- cores/<m>/module.yaml  step 3: inferred IP core descriptions
|       `-- interfaces/            step 2: AHB/APB interfaces, when used
|-- <name>.yml                     step 4, copy of out/<name>.yml
|-- build/<name>.sv                step 4, topwrap build: the top level (DUT)
|-- sim_build/                     step 5: Verilator model, simulator binary
|-- build.log                      Verilator's output
|-- built                          marker: the build completed
`-- run/<tier>/                    one per tier, written while the tier runs:
    |-- sim.log                    cocotb's log
    |-- results.xml                cocotb's JUnit results
    `-- dump.fst                   waveform, with --sim-waves
```

Nothing is generated outside `.build/`: the harness runs every command inside the build directory, because the Omnibus backend writes `topwrap.yaml` into the working directory.

### Building the simulator

The Verilator build compiles, in this order:

1. the pulp sources listed in `tests/verilator/pulp_platform_filelist.f`, from the `omnibus/third_party` submodules;
2. the generated RTL listed in `out/<name>.f`;
3. the top level `build/<name>.sv`.

The order matters: the generated wrappers use the `axi/typedef.svh` macros without including the file, and get them from the pulp files compiled before them.
That is also why the generated filelist is passed as sources and not with `-F`: cocotb's runner puts build arguments before the sources.

Other options:
- The `+incdir+` and `+define+` lines of the pulp filelist, including `COMMON_CELLS_NO_DEPRECATED_WARNINGS`, which silences a deprecation `$warning` in `common_cells`.
- `-Wno-fatal -Wno-lint -Wno-style`: warnings don't fail the build. Linting is the job of `tests/generate.sh`.
- `--x-assign unique --x-initial unique`: Verilator has no X state. These randomize what would be X, so an undriven signal shows up as a wrong value instead of a quiet 0.
- A 1 ns / 1 ps timescale. The top-level module is the specification's `name`.

### The build cache

A build is reused as long as its inputs are unchanged. The directory name carries a hash (`_cache_key()`) of:
- the specification;
- the installed `topwrap` package (`*.py`, `*.yaml`, `*.j2`);
- the `omnibus` package (`*.py`, `*.sv`, `*.yml`, including the `.sv` files of the pulp submodules);
- `harness/generate.py` and the pulp filelist.

A directory is reused only if its `built` marker exists, so an interrupted build starts over.
Starting a new build of a specification deletes its older builds.

Changes to the test bench (`env.py`, the checkers, `refmodel.py`) or to `tiers/` don't need a rebuild: they're Python, loaded when a tier runs.
To force a rebuild, delete the build directory.

### Running a tier

`test_tier` calls cocotb's `runner.test()`, which starts the simulator binary once per specification and tier.
It runs with `run/<tier>/` as its working directory, and with:
- `TOPWRAP_SIM_SPEC`: the specification's path. The test bench reads it to know what it's testing.
- The pytest process's `sys.path` as `PYTHONPATH`, which cocotb's runner passes on. `conftest.py` puts `tests/sim` and `tests/sim/tiers` on it, so the simulator's Python can import the tier module and `harness`.
- The rest of the environment. That's why `COCOTB_TEST_FILTER` and `COCOTB_RANDOM_SEED` work from the command line.

cocotb runs the tier module's tests one after another in the same simulation.
Each test builds its own test bench (`IcEnv`) and resets the DUT, and cocotb stops the tasks a test started (clocks, models, checkers) when it ends.

When the simulator exits, `test_tier` reads `results.xml` and fails if any cocotb test failed, naming the log to look at.

## The DUT's interface

The top-level module exposes flat ports:
- `<port>_<signal>` for each top-level port of the specification, e.g. `cpu_awaddr`;
- one clock and one active-low reset per clock of the specification: `clk_<name>_i` / `rst_<name>_ni`, where a leading `clk_` or `clk` is removed from the clock name, so `clk` gives `clk_i` / `rst_ni`.

The test bench attaches to them by name:

:::{list-table}
* - **Specification port**
  - **Driven by the test bench as**
* - `role: subordinate` (an external manager connects to it)
  - `AxiMaster`
* - `role: manager`, AXI4
  - `AxiRam`
* - `role: manager`, AXI4-Lite
  - `AxiLiteRam`
* - `role: manager`, AHB3
  - `AhbRam`: a cocotb-ahb `DUTManager` on the port pins, a `SimMem1PSubordinate` with random wait states behind it
* - `role: manager`, APB3
  - `ApbRam`
:::

## Inside the test bench

### Reference model

`harness/refmodel.py` turns a specification into `SpecModel`: its ports, clocks, address windows, and which ports the test bench can't model.

Port attributes and clock frequencies are read through Omnibus's own YAML frontend, because they're inputs to the generator.
The address map, however, is read from the file and decoded by the model itself (`decode()`, `testable_windows()`), without Omnibus's routing code, so that the expected results don't inherit the generator's bugs.
A window with no `from` is reachable from every manager.

### Test bench

`IcEnv` in `harness/env.py`, created at the start of each cocotb test:
- **Clocks:** one per specification clock, from its frequency (100 MHz if `n/a`), with the period rounded to an even number of picoseconds as cocotb's `Clock` requires.
- **Resets:** `start()` holds every reset low for `RESET_CYCLES` cycles of the slowest clock, then releases them in random order.
- **Managers and memories:** one `AxiMaster` per manager port, one memory per memory port (see [The DUT's interface](#the-duts-interface)).
  - Memories have size `2**addr_width` and are sparse, so they answer at the absolute addresses the interconnect passes through at no cost. cocotbext-axi's default size of 2**64 doesn't work: it overflows Python's `len()`.
- **Protocol checker:** one per port: `AxiChecker`, `ApbChecker` or `AhbChecker`, by the port's protocol.
- **Logging:** cocotbext-axi logs every transaction at INFO, so its loggers are raised to WARNING.
- **Timeouts:** every bus operation goes through `op()`, which fails the test after `OP_TIMEOUT_CYCLES` cycles of the slowest clock instead of hanging on a deadlock.

A memory accepts any address, so writing a value and reading it back over the same path can't tell a misrouted access from a correct one. Two checks close that gap:
- `prime(address, length)` fills that range in *every* memory with bytes unique to the memory (`tag()`). A read that lands in the wrong memory, or at the wrong offset, returns the wrong bytes.
- `check_write()` inspects the memories directly after a write, without going through the bus: the target must hold the data, and every other memory must still hold its tags.

`finish()`, called at the end of a cocotb test, fails the test on any protocol violation any checker has seen.

### Protocol checkers

`AxiChecker` in `harness/axichecker.py` samples one port on every rising edge of its clock, in both directions, so it checks the DUT's outputs and the test bench's own stimulus alike:
- a VALID that wasn't accepted stays high, with its payload unchanged;
- W bursts have AWLEN+1 beats, with WLAST on the last (AXI4);
- R bursts have ARLEN+1 beats, with RLAST on the last, per ID (AXI4);
- every B and R response has an outstanding request with its ID.

Its state is cleared while the port's reset is asserted. The first 20 violations of a port are kept, with their simulation time, for `finish()` to report.

`AhbChecker` in `harness/ahbchecker.py` samples one AHB manager port on every rising edge of its clock. It checks the DUT's address phase and the responses it gets:
- an address aligned to HSIZE, with the transfer within the data bus;
- an address phase that stays unchanged while HREADY is low (an ERROR response may cancel it);
- SEQ and BUSY only inside a burst, at the address the burst continues with;
- HBURST, HSIZE and HWRITE constant inside a burst, and INCR bursts not crossing a 1KB boundary;
- fixed-length bursts completed (unless an ERROR cancelled them), and no burst ending with BUSY;
- no transfer after the second cycle of an ERROR response.

It also records the accepted NONSEQ and SEQ address phases (`xfers`) and the BUSY cycles (`busy`), for tests that look at how a burst was split. Its state is cleared while the port's reset is asserted. The first 20 violations of a port are kept, with their simulation time, for `finish()` to report.

## Tiers

:::{list-table}
* - **cocotb test**
  - **What it does**
* - `tier0_build.port_widths`
  - every modeled port exists, with the specification's data width and address width
* - `tier0_build.reset_idle`
  - no VALID driven by the DUT rises during reset or in the 100 cycles after it
* - `tier1_smoke.rw_every_window`
  - from every manager, the first, middle and last word of every window it may access
* - `tier1_smoke.address_bit_walk`
  - from every manager, `base + 2**k` for every address bit inside each window: catches decoding and aliasing bugs
* - `tier1_smoke.byte_lanes`
  - narrow writes of every size below the bus width, on every byte lane, change only their bytes
* - `tier1_smoke.shared_visibility`
  - what one manager writes to a window, every other manager allowed there reads back; returns right away with a single manager
:::

Each Tier 1 access is checked three ways: the response code, the data read back, and, through `prime()` and `check_write()`, that it landed in the right memory at the right address.

## Known failures and guards

Two tables in `test_sim.py` keep the suite honest:
- **`EXPECTED_MODULES`** lists the modules a specification's generated RTL must contain, e.g. `axi_cdc_wrapper` for `cdc`. `test_build` fails if one is missing, so a specification can't silently stop exercising the component it's in the corpus for.
- **`XFAIL`** lists known failures by (specification, tier) or (specification, `"build"`), with the reason. They're marked `xfail(strict=True)`: pytest reports them as `XFAIL` without failing the run, and if one starts passing it's reported as `XPASS(strict)` and fails, so the entry gets removed together with the fix.

Expected failures and skipped tests don't fail the run, but `pytest -rxXs` lists them in its summary.
An expected failure accepts any failure of its test, not only the one its reason describes.

## Working with the suite

### Adding a specification

Add a `.yml` to `tests/sim/specs/`; `pytest` picks it up. If it's there to exercise a specific component, add the component's module name to `EXPECTED_MODULES`.

### Adding a cocotb test or a tier

A new cocotb test is a `@cocotb.test()` function in the tier module it belongs to.
It typically starts with `env = IcEnv(dut)` and `await env.start()`, uses `env.managers`, `env.memories` and `env.model`, and ends with `env.finish()`.

A new tier is a module in `tiers/`, plus its name in `TIERS` in `harness/__init__.py`, which also gives it a pytest marker.

### Debugging a failure

- **Logs.** The pytest failure names the log: `run/<tier>/sim.log` in the specification's build directory. Build problems are in `generate.log` (generation) and `build.log` (Verilator).
- **Narrowing down.** Select one specification and tier with `-k "<spec> and <tier>"`, and one cocotb test with `COCOTB_TEST_FILTER=<test name>`.
- **Reproducing random data.** `sim.log` starts with `Seeding Python random module with <seed>`; `COCOTB_RANDOM_SEED=<seed>` repeats that run. The bridge tests take one seed per pytest run: it is printed in the pytest header (`sim seed: <seed>`), stored as the `seed` property of every test in the JUnit report and repeated in the message of a failure, and `--sim-seed <seed>` reuses it.
- **Waveforms.** `--sim-waves` builds a separate simulator with tracing (a `-waves` build directory) and writes `run/<tier>/dump.fst`.
- **Generation by hand.** The commands in `generate.log` can be re-run in the build directory.

## Notes for reviewers

- **Topwrap branch.** Generating the top level needs Topwrap from the `102039-interface-generation-include-width` branch. The two workarounds in `generate.build()` (#102866, #102867) mirror `tests/generate.sh`.
- **Deprecation warnings.** cocotbext-axi uses APIs that cocotb 2.0 deprecates; the `py.warnings` lines in `sim.log` come from there.
- **Known issue: builds with and without `--sim-waves` evict each other.** Removing a specification's older builds also removes its build of the other kind, so alternating between the two rebuilds every time.
- **Not covered yet.** Error responses, bursts, concurrent traffic and performance, planned as further tiers.

## Converter tests

`test_bridges.py` tests single converter modules without an interconnect around them: the module under `omnibus/modules` is the Verilator top level, and `bridges/<name>.py` holds its cocotb tests.
Currently that is `axi_prconv_axi_ahb`, built for 32 and 64 bit data and for `FifoDepth` 1 to 4 (the FIFO depth parameter):

```
pytest tests/sim/test_bridges.py
pytest tests/sim/test_bridges.py -k "64-3"      # 64 bit data, FifoDepth 3
```

The AXI side is driven with cocotbext-axi channel sources and sinks, and the AHB side is answered by an `AhbRam`.
A Python model of the AXI address rules says which bytes each beat of a burst carries, and the memory is compared with a byte-for-byte model after every write.
The tests cover:
- full-width, narrow and unaligned transfers, INCR, WRAP and FIXED bursts, sparse and empty `WSTRB`, IDs, read/write arbitration, and random traffic with backpressure;
- which AHB bursts an AXI burst becomes (`ahb_bursts`): HBURST=INCR restarted at every 1KB, WRAP4/8/16 for reads, single transfers for FIXED, WRAP2, WRAP writes and beats that have to be split;
- BUSY while the R channel is blocked (`busy`), and the cycle counts of 16-beat bursts with no wait states (`throughput`; reads need `FifoDepth` 3 for one beat per cycle);
- AHB errors (`ahb_error`): no further AHB transfers after the error, SLVERR on the remaining read beats and on the B of a write.

The AHB side is watched by an `AhbChecker` (see [Protocol checkers](#protocol-checkers)). `ahb_bursts` and `busy` also look at the address phases and BUSY cycles it records, and `Bench.finish()` fails a test on its violations.
