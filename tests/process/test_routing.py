# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestCorrect


# These tests check whether routing properly finds paths for each crossbars
class TestRouting(TestCorrect):
    directory = "routing"

    def _process(self, ic):
        ic.find_routing_paths()
        ic._print_address_maps()

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

    def test_two_windows(self):
        self._test("two_windows", "tests/spec/two_windows.yml")
