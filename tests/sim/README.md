# Simulation tests

Generates interconnects from the specs in `specs/`, simulates them with Verilator
and [cocotb](https://www.cocotb.org/) 2.0, and checks them with
[cocotbext-axi](https://github.com/alexforencich/cocotbext-axi) managers and memories.

The RTL is generated the same way as `tests/generate.sh` does it: `omnibus`
generates the interconnect and a topwrap design for it, `topwrap repo parse` and
`topwrap build` turn that into the top-level module.

## Requirements

- Verilator on `PATH` (tested with 5.052 and 5.053).
- Topwrap (see [Installation](installation.md)).
- The Python packages in the `sim` extra: `pip install ".[sim]"`.
- The pulp submodules in `omnibus/third_party` (`axi`, `common_cells`,
  `tech_cells_generic`): `git submodule update --init`. The files used from them are
  listed in `tests/verilator/pulp_platform_filelist.f`.

The tests skip themselves when topwrap, cocotb or Verilator are missing.

## Running

```
pytest tests/sim                  # everything
pytest tests/sim -m tier1_smoke   # one tier
pytest tests/sim -k dw_mix        # one spec
pytest tests/sim --sim-waves      # also dump waveforms
```

Generated RTL, simulator builds and logs go to `.build/<spec>-<hash>/`; each tier's
cocotb log is `run/<tier>/sim.log` there. A build is reused until the spec, topwrap,
omnibus or `harness/generate.py` changes.

## Layout

- `specs/`: the curated corpus, one spec per feature under test.
- `harness/generate.py`: spec → SystemVerilog → Verilator build.
- `harness/refmodel.py`: what the spec says the interconnect must do. The address map
  is decoded here, independently of omnibus's routing code.
- `harness/env.py`: the test bench: clocks, resets, an `AxiMaster` on every port an
  external manager drives, a memory (`AxiRam`/`AxiLiteRam`) on every other port.
- `harness/checker.py`: passive AXI protocol checker attached to every port.
- `tiers/`: cocotb test modules, one per tier.
- `test_sim.py`: the pytest entry point, spec × tier.

## How routing is checked

A memory accepts any address, so writing and reading back over the same path can't
tell a misrouted access from a correct one. Before each access, the range is filled
in every memory with a pattern unique to that memory, so a read that lands in the
wrong memory returns the wrong bytes. After each write, the memories are inspected
directly to confirm that only the intended one changed.

## Tiers

- `tier0_build`: ports match the spec's widths; no VALID rises around reset.
- `tier1_smoke`: every manager reaches every window the spec gives it: first, middle
  and last word, a walk over every address bit, narrow writes on every byte lane,
  and writes by one manager visible to the others.

## Adding a spec

Drop a `.yml` into `specs/`. If it's there to exercise a particular component, add
the module name to `EXPECTED_MODULES` in `test_sim.py`, so the spec can't silently
stop generating it. Known failures go into `XFAIL` with the reason; they are strict,
so a fix turns them into a failure until the entry is removed.
