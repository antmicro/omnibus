# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder

from tests.filediff import filediff


# These tests check whether routing properly finds paths for each crossbars
class TestRouting:
    def _test(self, name):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"examples/{name}.yml")
        ic.find_routing_paths()
        ic._print_set_output("tests/output.txt")
        ic._print_address_maps()

        assert not filediff(
            "tests/output.txt", f"tests/ideal/process/routing/{name}.txt"
        )

    def test_simple(self):
        self._test("simple")

    #    NOTE: requires ability to configure crossbars differently for each subordinate port for full operation
    def test_spec(self):
        self._test("spec")

    #    NOTE: requires ability to find path in multipath interconnects
    #    def test_butterfly(self):
    #        self._test("butterfly")

    def test_asoca(self):
        self._test("asoca")
