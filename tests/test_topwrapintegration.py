# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess


class TestTopwarpIntegration:
    def test_asoca(self):
        assert 0 == subprocess.call(
            "tests/generate.sh ASoCaInt examples/asoca.yml",
            shell=True,
            executable="/bin/bash",
        )

    def test_spec(self):
        assert 0 == subprocess.call(
            "tests/generate.sh MyInterconnect examples/spec.yml",
            shell=True,
            executable="/bin/bash",
        )
