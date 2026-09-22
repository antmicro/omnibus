# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether yaml frontend behaves as expected
class TestYaml:
    def _test(self, name, corrname=None):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"examples/{name}.yml")
        ic._print_spec("tests/out/output.txt")

        if corrname is None:
            assert 0 == subprocess.call(
                f"diff -y tests/out/output.txt tests/ideal/frontend/{name}.txt",
                shell=True,
            )
        else:
            assert 0 == subprocess.call(
                f"diff -y tests/out/output.txt tests/ideal/frontend/{corrname}.txt",
                shell=True,
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
