# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

class TestTopwarpIntegration:
    def test_asoca(self):
        #cleanup any existing files
        subprocess.call("rm -fr topwrap.yaml ASoCaInt.yml out/", shell=True)

        #uses this file instead of 'example/asoca.yml' as temporary workaround for #100959
        assert 0 == subprocess.call(
            "omnibus tests/asoca2.yml", shell=True)

        assert 0 == subprocess.call(
            "topwrap repo parse repo out/src --inference-interface AXI4 --inference-interface APB3 --inference-interface AHB3 --inference-interface AXI4Lite --log-level error",
            shell=True)

        subprocess.call("rm -fr out/modules/cores/axi_prconv_axi_ahb out/modules/interfaces/vendor*", shell=True);

        assert 0 == subprocess.call(
            "topwrap repo parse repo out/src/axi_pr_axi_ahb.sv --inference-interface AXI4 --inference-interface AHB3 --log-level error",
            shell=True)

        subprocess.call("rm -f out/modules/interfaces/vendor*", shell=True)

        subprocess.call("cp -f out/ASoCaInt.yml ./", shell=True)

        assert 0 == subprocess.call(
            "topwrap build --design ASoCaInt.yml --log-level error", 
            shell=True)

        assert 0 == subprocess.call(
            "diff <(grep -v build/ASoCaInt.sv -e 'Automatically generated') <(grep -v ./tests/ideal/topwrap/asoca.sv -e 'Automatically generated')",
            shell=True, executable='/bin/bash')

        #this warning must be removed in place, it cannot be turned off in lint
        subprocess.call('sed -i "s/\\$warning.*//g" common_cells/src/deprecated/cf_math_pkg.sv', shell=True)

        assert 0 == subprocess.call(
            "verilator --lint-only -Wall tests/verilator/general_config.vlt tests/verilator/pulp_platform_config.vlt -f tests/verilator/pulp_platform_filelist.f -F out/ASoCaInt.f build/ASoCaInt.sv --top-module ASoCaInt", 
            shell=True)
