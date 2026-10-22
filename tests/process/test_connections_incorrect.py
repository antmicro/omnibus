# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestIncorrect


class TestConnectionsIncorrect(TestIncorrect):
    def _process(self, ic):
        ic.verify()

    def test_in_crossbar(self):
        self._test(
            "conn_in_crossbar",
            err="ERROR: connection in crossbar defined in 'connections', between xb_in and xb_out",
        )

    def test_between_crossbar(self):
        self._test(
            "conn_between_crossbar",
            err="ERROR: connection defined between different crossbars' internal ports, 'xa_in' of 'xa' and 'xb_out' of 'xb'",
        )

    def test_top_level_ports(self):
        self._test(
            "conn_ports",
            err=[
                "ERROR: cannot connect top level ports, found connection between 'pin' and 'pout'",
                "ERROR: exactly one connection must lead to crossbar port 'xb_in', instead found 0",
                "ERROR: connection in crossbar defined in 'connections', between xb_in and xb_out",
                "ERROR: exactly one connection must lead out of crossbar port 'xb_out', instead found 0",
            ],
        )

    def test_tlp_too_many(self):
        self._test(
            "conn_too_many",
            err=[
                "ERROR: top level subordinate port must have exactly one outgoing connection, pin has 2",
                "ERROR: top level manager port must have exactly one incoming connection, pout has 2",
            ],
        )

    def test_subordinate_unconnected(self):
        self._test(
            "conn_subordinate_unconnected",
            err=[
                "ERROR: top level subordinate port must have exactly one outgoing connection, pin has 2",
                "ERROR: top level subordinate port must have exactly one outgoing connection, pin2 has 0",
                "ERROR: top level manager port must have exactly one incoming connection, pout has 2",
            ],
        )

    def test_manager_unconnected(self):
        self._test(
            "conn_manager_unconnected",
            err=[
                "ERROR: top level manager port must have exactly one incoming connection, pout has 2",
                "ERROR: top level manager port must have exactly one incoming connection, pout2 has 0",
            ],
        )

    def test_direction(self):
        self._test(
            "conn_dir",
            err=[
                "ERROR: top level subordinate port cannot have incoming connections, pin has 1",
                "ERROR: cannot connect top level ports, found connection between 'pin' and 'pout'",
                "ERROR: top level manager port cannot have outgoing connections, pout has 1",
                "ERROR: exactly one connection must lead to crossbar port 'xb_in', instead found 0",
                "ERROR: exactly one connection must lead out of crossbar port 'xb_out', instead found 0",
            ],
        )

    def test_missing(self):
        self._test(
            "conn_missing",
            err="ERROR: exactly one connection must lead to crossbar port 'xb_in2', instead found 0",
        )
