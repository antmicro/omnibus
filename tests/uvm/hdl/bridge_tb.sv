// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

// UVM test bench top of axi_prconv_axi_ahb: the AXI4 AVIP master BFM drives the bridge, and the
// AHB AVIP slave BFM answers it. The data widths are set by the macros AXI4_DATA_WIDTH and
// AHB_DATA_WIDTH, which must be equal.

module bridge_tb #(
    parameter int unsigned FifoDepth = 3
);
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import bridge_pkg::*;

  localparam int unsigned AddrWidth = ADDR_W;
  localparam int unsigned DataWidth = DATA_W;

  bit clk;
  bit rst_n;

  initial begin
    clk = 0;
    forever #(CLK_PERIOD_NS / 2.0) clk = ~clk;
  end

  // the BFMs wait for the falling edge of the reset
  initial begin
    rst_n = 1;
    #1;
    rst_n = 0;
    repeat (5) @(posedge clk);
    rst_n = 1;
  end

  axi4_if axi_if (
      .aclk   (clk),
      .aresetn(rst_n)
  );
  AhbInterface ahb_if (
      .hclk   (clk),
      .hresetn(rst_n)
  );

  axi4_master_agent_bfm #(.MASTER_ID(0)) axi_master_bfm (axi_if);
  AhbSlaveAgentBFM ahb_slave_bfm (ahb_if);

  // signals of the AHB interface the bridge has no counterpart of
  assign ahb_if.hselx = 1'b1;
  assign ahb_if.hnonsec = 1'b0;
  assign ahb_if.hexcl = 1'b0;
  assign ahb_if.hmaster = '0;
  assign ahb_if.hwstrb = '1;

  assign axi_if.buser = '0;
  assign axi_if.ruser = '0;

  axi_prconv_axi_ahb #(
      .AxiAddrWidth(AddrWidth),
      .AxiDataWidth(DataWidth),
      .AxiIdWidth  (4),
      .FifoDepth   (FifoDepth)
  ) dut (
      .clk_i       (clk),
      .rst_ni      (rst_n),
      .src_awid    (axi_if.awid),
      .src_awaddr  (axi_if.awaddr),
      .src_awlen   (axi_if.awlen),
      .src_awsize  (axi_if.awsize),
      .src_awburst (axi_if.awburst),
      .src_awlock  (axi_if.awlock[0]),
      .src_awcache (axi_if.awcache),
      .src_awprot  (axi_if.awprot),
      .src_awqos   (axi_if.awqos),
      .src_awregion(axi_if.awregion),
      .src_awvalid (axi_if.awvalid),
      .src_awready (axi_if.awready),
      .src_wdata   (axi_if.wdata),
      .src_wstrb   (axi_if.wstrb),
      .src_wlast   (axi_if.wlast),
      .src_wvalid  (axi_if.wvalid),
      .src_wready  (axi_if.wready),
      .src_bid     (axi_if.bid),
      .src_bresp   (axi_if.bresp),
      .src_bvalid  (axi_if.bvalid),
      .src_bready  (axi_if.bready),
      .src_arid    (axi_if.arid),
      .src_araddr  (axi_if.araddr),
      .src_arlen   (axi_if.arlen),
      .src_arsize  (axi_if.arsize),
      .src_arburst (axi_if.arburst),
      .src_arlock  (axi_if.arlock[0]),
      .src_arcache (axi_if.arcache),
      .src_arprot  (axi_if.arprot),
      .src_arqos   (axi_if.arqos),
      .src_arregion(axi_if.arregion),
      .src_arvalid (axi_if.arvalid),
      .src_arready (axi_if.arready),
      .src_rid     (axi_if.rid),
      .src_rdata   (axi_if.rdata),
      .src_rresp   (axi_if.rresp),
      .src_rlast   (axi_if.rlast),
      .src_rvalid  (axi_if.rvalid),
      .src_rready  (axi_if.rready),
      .dst_haddr   (ahb_if.haddr),
      .dst_hburst  (ahb_if.hburst),
      .dst_hmastlock(ahb_if.hmastlock),
      .dst_hprot   (ahb_if.hprot),
      .dst_hsize   (ahb_if.hsize),
      .dst_htrans  (ahb_if.htrans),
      .dst_hwdata  (ahb_if.hwdata),
      .dst_hwrite  (ahb_if.hwrite),
      .dst_hrdata  (ahb_if.hrdata),
      .dst_hready  (ahb_if.hready),
      .dst_hresp   (ahb_if.hresp)
  );

  bridge_ahb_checker #(
      .AddrWidth(AddrWidth),
      .DataWidth(DataWidth)
  ) ahb_checker (
      .clk   (clk),
      .rst_n (rst_n),
      .haddr (ahb_if.haddr),
      .hburst(ahb_if.hburst),
      .hsize (ahb_if.hsize),
      .htrans(ahb_if.htrans),
      .hwrite(ahb_if.hwrite),
      .hready(ahb_if.hready),
      .hresp (ahb_if.hresp)
  );

  // +WAVES=<file> writes the waves of the run, in a build with tracing
  string waves_file;
  initial begin
    if ($value$plusargs("WAVES=%s", waves_file)) begin
      $dumpfile(waves_file);
      $dumpvars(0, bridge_tb);
    end
    run_test();
  end
endmodule
