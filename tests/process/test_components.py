# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether parameters are properly propagated and components properly inserted
class TestComponents:
    def _test(self, name, directory="examples"):
        ic = InterconnectBuilder(frontend="yaml") 

        ic.read_yaml(f"{directory}/{name}.yml")
        ic.propagate_parameters()
        ic.insert_new_components()
        ic._print_set_output("tests/output.txt")
        ic._print_ports()
        ic._print_components()
        
        assert 0 == subprocess.call(f"diff -y tests/output.txt tests/ideal/process/components/{name}.txt", shell=True)
        
    def test_simple(self):
        self._test("simple")

    def test_spec(self):
        self._test("spec")

    def test_butterfly(self):
        self._test("butterfly")
        
    def test_asoca(self):
        self._test("asoca")

    def test_idwidth(self):
        self._test("idwidth_butterflyish", "tests/spec/")
