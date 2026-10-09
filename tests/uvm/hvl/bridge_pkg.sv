// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

package bridge_pkg;
  `include "uvm_macros.svh"
  import uvm_pkg::*;
  import axi4_master_pkg::*;
  import AhbSlavePackage::*;

  localparam int unsigned CLK_PERIOD_NS = 20;
  localparam int unsigned DATA_W = axi4_globals_pkg::DATA_WIDTH;
  localparam int unsigned ADDR_W = axi4_globals_pkg::ADDRESS_WIDTH;
  localparam int unsigned LANES = DATA_W / 8;

  `include "bridge_scoreboard.svh"
  `include "bridge_env.svh"
  `include "bridge_tests.svh"
endpackage
