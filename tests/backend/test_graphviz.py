# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether graphviz backend operates properly with all examples and some options
class TestGraphviz:
    def test_simple(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml("examples/simple.yml")
        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)

        ic.process()
        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)

        ic.generate(
            "tests/out/",
            color_by="protocol",
            color_scheme="paired12",
            display_full_name=False,
        )

        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)
        assert 0 == subprocess.call(
            "diff -y tests/out/simple.gv tests/ideal/backend/graphviz/simple.gv",
            shell=True,
        )

    def test_spec(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml("examples/spec.yml")
        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)

        ic.process()
        # NOTE: forced by pulp platform backend
        assert [
            "ERROR: it is not possible yet to have address map rules that are different based on source id, rule to sb_cpu_lpp has different paths from axi_cpu and axi_dbg"
        ] == ic.errors
        ic.errors = []
        assert 0 == len(ic.warns)

        ic.generate(
            "tests/out/",
            color_by="clock",
            color_scheme="brbg10",
            display_full_name=True,
        )

        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)
        assert 0 == subprocess.call(
            "diff -y tests/out/MyInterconnect.gv tests/ideal/backend/graphviz/spec.gv",
            shell=True,
        )

    def test_butterfly(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml("examples/butterfly.yml")
        assert 0 == len(ic.errors)
        assert [
            "WARNING: clock 'clk' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable"
        ] == ic.warns
        ic.warns = []

        ic.process()
        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)

        ic.generate("tests/out/")

        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)
        assert 0 == subprocess.call(
            "diff -y tests/out/butterfly.gv tests/ideal/backend/graphviz/butterfly.gv",
            shell=True,
        )

    def test_asoca(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml("examples/asoca.yml")
        assert 0 == len(ic.errors)
        # NOTE: will be the case becasue graphviz backend doesnt support it
        assert [
            "WARNING: 'axi_max_reads' not in the list of known defaults"
        ] == ic.warns
        ic.warns = []

        ic.process()
        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)

        ic.generate("tests/out/", color_by="data_width", color_scheme="reds3")

        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)
        assert 0 == subprocess.call(
            "diff -y tests/out/ASoCaInt.gv tests/ideal/backend/graphviz/asoca.gv",
            shell=True,
        )

    def test_idwidth(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml("tests/spec/idwidth_butterflyish.yml")
        assert 0 == len(ic.errors)
        assert [
            "WARNING: clock 'clk' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable"
        ] == ic.warns
        ic.warns = []

        ic.process()
        # NOTE: connection errors expected in this example
        ic.errors = []
        assert 0 == len(ic.warns)

        ic.generate("tests/out/", color_by="id_width")

        assert 0 == len(ic.errors)
        assert 0 == len(ic.warns)
        assert 0 == subprocess.call(
            "diff -y tests/out/butterflyish.gv tests/ideal/backend/graphviz/idwidth_butterflyish.gv",
            shell=True,
        )
