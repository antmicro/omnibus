# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestCorrect


# These tests check whether parameters are properly propagated and components properly inserted
class TestComponents(TestCorrect):
    directory = "components"

    def _process(self, ic):
        ic.propagate_parameters()
        ic.insert_new_components()
        ic._print_ports()
        ic._print_components()

    def test_simple(self):
        self._test("simple")

    def test_spec(self):
        self._test("spec")

    def test_butterfly(self):
        self._test("butterfly")

    def test_asoca(self):
        self._test("asoca")

    def test_idwidth(self):
        self._test("idwidth_butterflyish", "tests/spec/idwidth_butterflyish.yml")
