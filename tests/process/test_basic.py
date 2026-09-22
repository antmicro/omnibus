# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether data is properly passed to the internal represntation
class TestBasic:
    def _test(self, name):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"examples/{name}.yml")
        ic._print_elements("tests/output.txt")

        assert 0 == subprocess.call(
            f"diff -y tests/output.txt tests/ideal/process/basic/{name}.txt", shell=True
        )

    def test_simple(self):
        self._test("simple")

    def test_spec(self):
        self._test("spec")

    def test_butterfly(self):
        self._test("butterfly")

    def test_asoca(self):
        self._test("asoca")
