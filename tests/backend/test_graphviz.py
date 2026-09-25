# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder

from tests.filediff import filediff


# These tests check whether graphviz backend operates properly with all examples and some options
class TestGraphviz:
    def _test(self, file, graph, ideal, **kwargs):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz")

        ic.read_yaml(file)

        ic.process()

        ic.generate("tests/out/", **kwargs)

        assert not filediff(
            f"tests/out/{graph}.gv",
            f"tests/ideal/backend/graphviz/{ideal}.gv",
        )

    def test_simple(self):
        self._test(
            "examples/simple.yml",
            "simple",
            "simple",
            color_by="protocol",
            color_scheme="paired12",
            display_full_name=False,
        )

    def test_spec(self):
        self._test(
            "examples/spec.yml",
            "MyInterconnect",
            "spec",
            color_by="clock",
            color_scheme="brbg10",
            display_full_name=True,
        )

    def test_butterfly(self):
        self._test("examples/butterfly.yml", "butterfly", "butterfly")

    def test_asoca(self):
        self._test(
            "examples/asoca.yml",
            "ASoCaInt",
            "asoca",
            color_by="data_width",
            color_scheme="reds3",
        )

    def test_idwidth(self):
        self._test(
            "tests/spec/idwidth_butterflyish.yml",
            "butterflyish",
            "idwidth_butterflyish",
            color_by="id_width",
        )
