# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import sys

from omnibus import InterconnectBuilder


# These tests check whether topwrap backend operates properly
class TestTopwrapBackend:
    def _test(self, name, icname=None):
        subprocess.call("rm -fr tests/out/src/* tests/out/modules/*", shell=True)
        subprocess.call("rm -f tests/out/*yml tests/out/*core tests/out/*f", shell=True)

        ic = InterconnectBuilder(frontend="yaml", backend="topwrap_pulpplatform")
        ic.read_yaml(f"examples/{name}.yml")
        ic.process()
        ic.generate("tests/out/")
        os.sync()

        if icname:
            assert 0 == subprocess.call(
                f"diff -y tests/out/{icname}.yml tests/ideal/backend/topwrap/{name}.yml",
                shell=True,
            )
        else:
            assert 0 == subprocess.call(
                f"diff -y tests/out/{name}.yml tests/ideal/backend/topwrap/{name}.yml",
                shell=True,
            )

    def test_simple(self):
        self._test("simple")

        assert os.path.isfile("tests/out/src/axi_crossbar_main.sv")
        assert os.path.isfile("tests/out/src/axi_prconv_axi_axilite.sv")

    # NOTE: this test is not full until address maps specific to source are implemented
    def test_spec(self):
        self._test("spec", "MyInterconnect")

        assert os.path.isfile("tests/out/src/axi_crossbar_sb_cpu.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_sb_lpp.sv")
        assert os.path.isfile("tests/out/src/axi_cdc_wrapper.sv")
        assert os.path.isfile("tests/out/src/axi_prconv_axi_apb.sv")
        assert os.path.isfile("tests/out/modules/interfaces/apb.yml")

    # NOTE: this test is not full until routing in multipath interconnects is implemented
    def test_butterfly(self):
        self._test("butterfly")

        assert os.path.isfile("tests/out/src/axi_crossbar_x00.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x01.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x02.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x03.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x10.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x11.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x12.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x13.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x20.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x21.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x22.sv")
        assert os.path.isfile("tests/out/src/axi_crossbar_x23.sv")

    def test_asoca(self):
        self._test("asoca", "ASoCaInt")

        assert os.path.isfile("tests/out/src/axi_crossbar_main.sv")
        assert os.path.isfile("tests/out/src/axi_cdc_wrapper.sv")
        assert os.path.isfile("tests/out/src/axi_dw_conv_wrapper.sv")
        assert os.path.isfile("tests/out/src/axi_prconv_axi_axilite.sv")
        assert os.path.isfile("tests/out/src/axi_prconv_axi_apb.sv")
        assert os.path.isfile("tests/out/src/axi_prconv_axi_ahb.sv")
        assert os.path.isfile("tests/out/src/beh_lib.sv")
        assert os.path.isfile("tests/out/modules/interfaces/apb.yml")
        assert os.path.isfile("tests/out/modules/interfaces/ahb.yml")
