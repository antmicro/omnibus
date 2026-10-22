# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import sys

from omnibus import InterconnectBuilder

class TestTopwrapBackendIncorrect():
    def _test(self, name, icname=None, err=[]):
        subprocess.call("rm -fr tests/out/src/* tests/out/modules/*", shell=True)
        subprocess.call("rm -f tests/out/*yml tests/out/*core tests/out/*f", shell=True)

        ic = InterconnectBuilder(frontend="yaml", backend="topwrap_pulpplatform")
        ic.read_yaml(f"tests/interconnectinvalid/{name}.yml")
        ic.process()
        ic.generate("tests/out/")
        assert ic.errors == err


    def test_unsupported_protocol(self):
        self._test(
            "component_unsupported_protocol",
            err=[
                "ERROR: component 'main' generated with port 'main_pin' of protocol 'apb3', currently protocol must be of type 'axi4'"
            ],
        )
        self._test(
            "component_unsupported_protocol2",
            err=[
                "ERROR: protocol converter 'pr_conv_pin_apb3_to_main_pin_axi4' generated with source port protocol 'apb3', currently source protocol must be of type 'axi4'",
            ],
        )
