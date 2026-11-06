# Simulation tests

Generates interconnects from the specs in `specs/`, simulates them with Verilator
and [cocotb](https://www.cocotb.org/) 2.0, and checks them with
[cocotbext-axi](https://github.com/alexforencich/cocotbext-axi) managers and memories.

```
pip install ".[sim]"              # plus Verilator on PATH
git submodule update --init       # pulp sources in omnibus/third_party
pytest tests/sim                  # everything
pytest tests/sim -k "dw_mix and tier1_smoke"
```

How the suite is organized, what it generates, how a test runs and how to debug
one: see [docs/simulationtests.md](../../docs/simulationtests.md).
