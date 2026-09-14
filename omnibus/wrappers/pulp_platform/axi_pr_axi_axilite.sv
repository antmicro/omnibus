// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

module axi_prconv_axi_axilite #(
      /// AXI bus parameters
      parameter int unsigned AxiAddrWidth    = 32,
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


      output wire [AxiAddrWidth - 1 :0]         o_dst_awaddr,
      output wire  [2:0]                        o_dst_awprot,
      output wire  [2:0]                        o_dst_arprot,
      output wire                               o_dst_awvalid,
      input  wire                               i_dst_awready,
      output wire [AxiAddrWidth-1:0]            o_dst_araddr,
      input  wire                               i_dst_arready,
      output wire [AxiDataWidth - 1:0]          o_dst_wdata,
      output wire [AxiDataWidth/8 - 1:0]        o_dst_wstrb,
      output wire                               o_dst_wvalid,
      input  wire                               i_dst_wready,
      input  wire  [1:0]                        i_dst_bresp,
      input  wire                               i_dst_bvalid,
      output wire                               o_dst_bready,
      input  wire [AxiDataWidth - 1:0]          i_dst_rdata,
      input  wire  [1:0]                        i_dst_rresp,
      input  wire                               i_dst_rvalid,
      output wire                               o_dst_arvalid,
      output wire                               o_dst_rready
    );

    typedef logic [AxiIdWidth-1:0]        id_t;
    typedef logic [AxiAddrWidth-1:0]      addr_t;
    typedef logic [AxiDataWidth-1:0]      data_t;
    typedef logic [AxiDataWidth/8 -1:0]   strb_t;

    // full channels typedefs
    `AXI_TYPEDEF_AW_CHAN_T(full_aw_chan_t, addr_t, id_t, logic[0:0])
    `AXI_TYPEDEF_W_CHAN_T(full_w_chan_t, data_t, strb_t, logic[0:0])
    `AXI_TYPEDEF_B_CHAN_T(full_b_chan_t, id_t, logic[0:0])
    `AXI_TYPEDEF_AR_CHAN_T(full_ar_chan_t, addr_t, id_t, logic[0:0])
    `AXI_TYPEDEF_R_CHAN_T(full_r_chan_t, data_t, id_t, logic[0:0])
    `AXI_TYPEDEF_REQ_T(full_req_t, full_aw_chan_t, full_w_chan_t, full_ar_chan_t)
    `AXI_TYPEDEF_RESP_T(full_resp_t, full_b_chan_t, full_r_chan_t)

    // LITE channels typedef
    `AXI_LITE_TYPEDEF_AW_CHAN_T(lite_aw_chan_t, addr_t)
    `AXI_LITE_TYPEDEF_W_CHAN_T(lite_w_chan_t, data_t, strb_t)
    `AXI_LITE_TYPEDEF_B_CHAN_T(lite_b_chan_t)
    `AXI_LITE_TYPEDEF_AR_CHAN_T(lite_ar_chan_t, addr_t)
    `AXI_LITE_TYPEDEF_R_CHAN_T (lite_r_chan_t, data_t)
    `AXI_LITE_TYPEDEF_REQ_T(lite_req_t, lite_aw_chan_t, lite_w_chan_t, lite_ar_chan_t)
    `AXI_LITE_TYPEDEF_RESP_T(lite_resp_t, lite_b_chan_t, lite_r_chan_t)
  
    full_req_t  src_req;
    full_resp_t src_resp;
    lite_req_t  dst_req;
    lite_resp_t dst_resp;

    axi_to_axi_lite #(
       .AxiAddrWidth       (AxiAddrWidth   ),
       .AxiDataWidth       (AxiDataWidth   ),
       .AxiIdWidth         (AxiIdWidth     ),
       .AxiMaxWriteTxns    (AxiMaxWriteTxns),
       .AxiMaxReadTxns     (AxiMaxReadTxns ),
       .FallThrough        (FallThrough    ),
       .FullBW             (FullBW         ),
       .AxiUserWidth       (1              ),
       .full_req_t         (full_req_t     ),
       .full_resp_t        (full_resp_t    ),
       .lite_req_t         (lite_req_t     ),
       .lite_resp_t        (lite_resp_t    )
     ) i_axi_to_axi_lite (
       .clk_i     (clk_i     ),
       .rst_ni    (rst_ni    ),

       .slv_req_i (src_req ),
       .slv_resp_o(src_resp),

       .mst_req_o (dst_req ),
       .mst_resp_i(dst_resp)
     );

    assign src_req.aw.id = i_src_awid;
    assign src_req.aw.addr = i_src_awaddr;
    assign src_req.aw.len = i_src_awlen;
    assign src_req.aw.size = i_src_awsize;
    assign src_req.aw.burst = i_src_awburst;
    assign src_req.aw.lock = i_src_awlock;
    assign src_req.aw.cache = i_src_awcache;
    assign src_req.aw.prot = i_src_awprot;
    assign src_req.aw.region = i_src_awregion;
    assign src_req.aw.qos = i_src_awqos;
    assign src_req.aw.atop = 6'd0;
    assign src_req.aw_valid = i_src_awvalid;
    assign o_src_awready = src_resp.aw_ready;
    assign src_req.ar.id = i_src_arid;
    assign src_req.ar.addr = i_src_araddr;
    assign src_req.ar.len = i_src_arlen;
    assign src_req.ar.size = i_src_arsize;
    assign src_req.ar.burst = i_src_arburst;
    assign src_req.ar.lock = i_src_arlock;
    assign src_req.ar.cache = i_src_arcache;
    assign src_req.ar.prot = i_src_arprot;
    assign src_req.ar.region = i_src_arregion;
    assign src_req.ar.qos = i_src_arqos;
    assign src_req.ar_valid = i_src_arvalid;
    assign o_src_arready = src_resp.ar_ready;
    assign src_req.w.data = i_src_wdata;
    assign src_req.w.strb = i_src_wstrb;
    assign src_req.w.last = i_src_wlast;
    assign src_req.w_valid = i_src_wvalid;
    assign o_src_wready = src_resp.w_ready;
    assign o_src_bid = src_resp.b.id;
    assign o_src_bresp = src_resp.b.resp;
    assign o_src_bvalid = src_resp.b_valid;
    assign src_req.b_ready = i_src_bready;
    assign o_src_rid = src_resp.r.id;
    assign o_src_rdata = src_resp.r.data;
    assign o_src_rresp = src_resp.r.resp;
    assign o_src_rlast = src_resp.r.last;
    assign o_src_rvalid = src_resp.r_valid;
    assign src_req.r_ready = i_src_rready;

    assign o_dst_awaddr = dst_req.aw.addr;
    assign o_dst_awprot = dst_req.aw.prot;
    assign o_dst_awvalid = dst_req.aw_valid;
    assign dst_resp.aw_ready = i_dst_awready;
    assign o_dst_araddr = dst_req.ar.addr;
    assign o_dst_arprot = dst_req.ar.prot;
    assign o_dst_arvalid = dst_req.ar_valid;
    assign dst_resp.ar_ready = i_dst_arready;
    assign o_dst_wdata = dst_req.w.data;
    assign o_dst_wstrb = dst_req.w.strb;
    assign o_dst_wvalid = dst_req.w_valid;
    assign dst_resp.w_ready = i_dst_wready;
    assign dst_resp.b.resp = i_dst_bresp;
    assign dst_resp.b_valid = i_dst_bvalid;
    assign o_dst_bready = dst_req.b_ready;
    assign dst_resp.r.data = i_dst_rdata;
    assign dst_resp.r.resp = i_dst_rresp;
    assign dst_resp.r_valid = i_dst_rvalid;
    assign o_dst_rready = dst_req.r_ready;


endmodule
