# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestCorrect


# These tests check whether data is properly passed to the internal represntation
class TestBasic(TestCorrect):
    directory = "basic"

    def _process(self, ic):
        ic._print_elements("tests/output.txt")

    def test_simple(self):
        self._test("simple")

    def test_spec(self):
        self._test("spec")

    def test_butterfly(self):
        self._test("butterfly")

    def test_asoca(self):
        self._test("asoca")
