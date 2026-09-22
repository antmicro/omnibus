// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

module axi_prconv_axi_ahb #(
      /// AXI bus parameters
      parameter int unsigned AxiAddrWidth    = 0,
      parameter int unsigned AxiDataWidth    = 0,
      parameter int unsigned AxiIdWidth      = 0,
      /// Maximum number of outstanding writes.
      parameter int unsigned AxiMaxWriteTxns = 1,
      /// Maximum number of outstanding reads.
      parameter int unsigned AxiMaxReadTxns  = 1,
      parameter bit          FallThrough     = 1,
      parameter bit          FullBW          = 0
    ) (
      input logic     clk_i,
      input logic     rst_ni,
      input logic     testmode_i,

      input  wire [AxiIdWidth   - 1 :0]         i_src_awid,
      input  wire [AxiAddrWidth - 1 :0]         i_src_awaddr,
      input  wire  [7:0]                        i_src_awlen,
      input  wire  [2:0]                        i_src_awsize,
      input  wire  [1:0]                        i_src_awburst,
      input  wire                               i_src_awlock,
      input  wire  [3:0]                        i_src_awcache,
      input  wire  [2:0]                        i_src_awprot,
      input  wire  [3:0]                        i_src_awregion,
      input  wire  [3:0]                        i_src_awqos,
      input  wire                               i_src_awvalid,
      output wire                               o_src_awready,
      input  wire [AxiIdWidth - 1   :0]         i_src_arid,
      input  wire [AxiAddrWidth - 1 :0]         i_src_araddr,
      input  wire  [7:0]                        i_src_arlen,
      input  wire  [2:0]                        i_src_arsize,
      input  wire  [1:0]                        i_src_arburst,
      input  wire                               i_src_arlock,
      input  wire  [3:0]                        i_src_arcache,
      input  wire  [2:0]                        i_src_arprot,
      input  wire  [3:0]                        i_src_arregion,
      input  wire  [3:0]                        i_src_arqos,
      input  wire                               i_src_arvalid,
      output wire                               o_src_arready,
      input  wire [AxiDataWidth - 1:0]          i_src_wdata,
      input  wire [AxiDataWidth/8 - 1:0]        i_src_wstrb,
      input  wire                               i_src_wlast,
      input  wire                               i_src_wvalid,
      output wire                               o_src_wready,
      output wire [AxiIdWidth - 1 :0]           o_src_bid,
      output wire  [1:0]                        o_src_bresp,
      output wire                               o_src_bvalid,
      input  wire                               i_src_bready,
      output wire [AxiIdWidth - 1 :0]           o_src_rid,
      output wire [AxiDataWidth - 1:0]          o_src_rdata,
      output wire  [1:0]                        o_src_rresp,
      output wire                               o_src_rlast,
      output wire                               o_src_rvalid,
      input  wire                               i_src_rready,


      output wire [AxiAddrWidth - 1 :0]         o_dst_addr,
      output wire [2:0]                         o_dst_burst,
      output wire                               o_dst_mastlock,
      output wire [3:0]                         o_dst_prot,
      output wire [2:0]                         o_dst_size,
      output wire [1:0]                         o_dst_trans,
      output wire [AxiDataWidth - 1 :0]         o_dst_wdata,
      output wire [AxiDataWidth/8 - 1 :0]       o_dst_wstrb,
      output wire                               o_dst_write,
      input  wire [AxiDataWidth - 1 :0]         i_dst_rdata,
      input  wire                               i_dst_ready,
      input  wire                               i_dst_resp
    );

endmodule
