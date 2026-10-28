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
rm -fr topwrap.yaml out/ build/

#generate
omnibus $2

#parse verilog files
topwrap repo parse repo out/src -I --log-level error

#build verilog
topwrap generate out/$1.yml --verilog --log-level error --flatten-interfaces

mkdir -p artifacts/$1/
cp -r build out artifacts/$1/

#code check, removing lines with time and commit
diff <(grep -v -e 'Automatically generated' ./build/src/$1.sv) <(grep -v -e 'Automatically generated' ./tests/ideal/topwrap/$1.sv)

#pulp_platform_filelist.f defines COMMON_CELLS_NO_DEPRECATED_WARNINGS, silencing the
#deprecation $warning in common_cells' cf_math_pkg.sv that -Wall would fail on

#linter
verilator --lint-only -Wall tests/verilator/general_config.vlt tests/verilator/pulp_platform_config.vlt -f tests/verilator/pulp_platform_filelist.f -F out/$1.f build/src/$1.sv --top-module $1
