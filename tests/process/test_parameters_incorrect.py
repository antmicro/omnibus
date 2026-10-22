# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from base import TestIncorrect


class TestParametersIncorrect(TestIncorrect):
    def _process(self, ic):
        ic.propagate_parameters()

    def test_blocked(self):
        self._test(
            "parameter_blocked",
            err=[
                "ERROR: could not propagate attribute 'clock' to port 'xb_in', it is likely surrounded by barriers that stop propagation",
                "ERROR: could not propagate attribute 'clock' to port 'xb_out', it is likely surrounded by barriers that stop propagation",
            ],
        )

    def test_datawidth_conflict(self):
        self._test(
            "parameter_datawidth_conflict",
            err=[
                "ERROR: no valid configuration exists for data_width, port pin has assigned value that is different than its outgoing connection to xb_in",
                "ERROR: no valid configuration exists for data_width, port xb_out has assigned value that is different than its outgoing connection to pout",
            ],
        )
