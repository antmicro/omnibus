# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestIncorrect


class TestRoutingIncorrect(TestIncorrect):
    def _process(self, ic):
        ic.verify()
        ic.find_routing_paths()

    def test_different_sources(self):
        self._test(
            "address_map_different_sources",
            err="ERROR: it is not yet possible to have address map rules that are different based on source",
        )

    def test_size_zero(self):
        self._test(
            "address_map_size_zero", "ERROR: address map entry 'pout' has size of 0"
        )

    def test_overlap(self):
        self._test(
            "address_map_overlap",
            err="ERROR: overlapping address map entries pout1 and pout2 for ports {'pin1'}",
        )
