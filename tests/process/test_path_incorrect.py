# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder

from tests.filediff import filediff

from base import TestIncorrect


class TestPathIncorrect(TestIncorrect):
    def _process(self, ic):
        ic.find_routing_paths()

    # ordering of ports can change the exact error message, hence this test is specialized
    def test_multi(self):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"tests/interconnectinvalid/path_multi.yml")

        assert len(ic.errors) == 0
        assert len(ic.warns) == 0

        ic.find_routing_paths()

        assert len(ic.errors) == 1
        assert len(ic.warns) == 0

        assert ic.errors[0] in [
            "ERROR: path i0 -> o0 defined more than once, only one path between two ports can exist",
            "ERROR: path i0 -> o1 defined more than once, only one path between two ports can exist",
            "ERROR: path i1 -> o0 defined more than once, only one path between two ports can exist",
            "ERROR: path i1 -> o1 defined more than once, only one path between two ports can exist",
        ]

    def test_missing(self):
        self._test(
            "path_missing",
            err="ERROR: no path from 'pbin' to 'paout', required by address map entry 'paout'",
        )
