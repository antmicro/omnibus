# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess
import sys

from omnibus import InterconnectBuilder

from tests.filediff import filediff


# These tests check whether yaml frontend behaves as expected
class TestYaml:
    def _test(self, name, corrname=None):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"examples/{name}.yml")
        ic._print_spec("tests/out/output.txt")

        assert not filediff(
            "tests/out/output.txt",
            f"tests/ideal/frontend/{corrname if corrname else name}.txt",
        )

    def test_simple(self):
        self._test("simple")

    def test_spec(self):
        self._test("spec")

    def test_butterfly(self):
        self._test("butterfly")

    def test_asoca(self):
        self._test("asoca")

    def test_asoca_implicit_crossbar(self):
        self._test("asoca_implicit_crossbar", "asoca")
