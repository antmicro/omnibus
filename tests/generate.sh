#!/bin/bash
# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

#helper script to fully generate interconnect verilog
#argument 1: interconnect name
#argument 2: file where to take the specification from

if [ $# -ne 2 ]
then 
	echo "Usage: $0 <interconnect_name> <specification_path>"
	exit
fi

set -ex

#cleanup
rm -fr topwrap.yaml $1.yml out/ build/

#generate
omnibus $2

#parse verilog files
topwrap repo parse repo out/src -I --log-level error

#cleanup vendor files, workaround for #102866
rm -f out/modules/interfaces/vendor*

#move topwrap spec, workaround for #102867
cp -f out/$1.yml ./

#build verilog
topwrap build --design $1.yml --log-level error

#code check, removing lines with time and commit 
diff <(grep -v build/$1.sv -e 'Automatically generated') <(grep -v ./tests/ideal/topwrap/$1.sv -e 'Automatically generated')

#this warning must be removed in place, it cannot be turned off in lint
sed -i "s/\\$warning.*//g" common_cells/src/deprecated/cf_math_pkg.sv

#linter
verilator --lint-only -Wall tests/verilator/general_config.vlt tests/verilator/pulp_platform_config.vlt -f tests/verilator/pulp_platform_filelist.f -F out/$1.f build/$1.sv --top-module $1
