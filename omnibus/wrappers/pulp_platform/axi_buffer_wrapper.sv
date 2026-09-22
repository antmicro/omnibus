// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

module axi_buffer_wrapper #(
    parameter int unsigned AxiDataWidth        = 8    , // Data width of the ports
    parameter int unsigned AxiAddrWidth        = 32   , // Address width
    parameter int unsigned AxiIdWidth          = 1      // ID width
    ) (
    input  logic          clk_i,
    input  logic          rst_ni,

          input  wire [AxiIdWidth   - 1 :0]       i_src_awid,
          input  wire [AxiAddrWidth - 1 :0]       i_src_awaddr,
          input  wire  [7:0]                      i_src_awlen,
          input  wire  [2:0]                      i_src_awsize,
          input  wire  [1:0]                      i_src_awburst,
          input  wire                             i_src_awlock,
          input  wire  [3:0]                      i_src_awcache,
          input  wire  [2:0]                      i_src_awprot,
          input  wire  [3:0]                      i_src_awregion,
          input  wire  [3:0]                      i_src_awqos,
          input  wire                             i_src_awvalid,
          output wire                             o_src_awready,
          input  wire [AxiIdWidth - 1   :0]       i_src_arid,
          input  wire [AxiAddrWidth - 1 :0]       i_src_araddr,
          input  wire  [7:0]                      i_src_arlen,
          input  wire  [2:0]                      i_src_arsize,
          input  wire  [1:0]                      i_src_arburst,
          input  wire                             i_src_arlock,
          input  wire  [3:0]                      i_src_arcache,
          input  wire  [2:0]                      i_src_arprot,
          input  wire  [3:0]                      i_src_arregion,
          input  wire  [3:0]                      i_src_arqos,
          input  wire                             i_src_arvalid,
          output wire                             o_src_arready,
          input  wire [AxiDataWidth - 1:0]        i_src_wdata,
          input  wire [AxiDataWidth/8 - 1:0]      i_src_wstrb,
          input  wire                             i_src_wlast,
          input  wire                             i_src_wvalid,
          output wire                             o_src_wready,
          output wire [AxiIdWidth - 1 :0]         o_src_bid,
          output wire  [1:0]                      o_src_bresp,
          output wire                             o_src_bvalid,
          input  wire                             i_src_bready,
          output wire [AxiIdWidth - 1 :0]         o_src_rid,
          output wire [AxiDataWidth - 1:0]        o_src_rdata,
          output wire  [1:0]                      o_src_rresp,
          output wire                             o_src_rlast,
          output wire                             o_src_rvalid,
          input  wire                             i_src_rready,

          output wire [AxiIdWidth - 1 :0]         o_dst_awid,
          output wire [AxiAddrWidth - 1 :0]       o_dst_awaddr,
          output wire  [7:0]                      o_dst_awlen,
          output wire  [2:0]                      o_dst_awsize,
          output wire  [1:0]                      o_dst_awburst,
          output wire                             o_dst_awlock,
          output wire  [3:0]                      o_dst_awcache,
          output wire  [2:0]                      o_dst_awprot,
          output wire  [3:0]                      o_dst_awregion,
          output wire  [3:0]                      o_dst_awqos,
          output wire                             o_dst_awvalid,
          input  wire                             i_dst_awready,
          output wire [AxiIdWidth-1:0]            o_dst_arid,
          output wire [AxiAddrWidth-1:0]          o_dst_araddr,
          output wire  [7:0]                      o_dst_arlen,
          output wire  [2:0]                      o_dst_arsize,
          output wire  [1:0]                      o_dst_arburst,
          output wire                             o_dst_arlock,
          output wire  [3:0]                      o_dst_arcache,
          output wire  [2:0]                      o_dst_arprot,
          output wire  [3:0]                      o_dst_arregion,
          output wire  [3:0]                      o_dst_arqos,
          output wire                             o_dst_arvalid,
          input  wire                             i_dst_arready,
          output wire [AxiDataWidth - 1:0]        o_dst_wdata,
          output wire [AxiDataWidth/8 - 1:0]      o_dst_wstrb,
          output wire                             o_dst_wlast,
          output wire                             o_dst_wvalid,
          input  wire                             i_dst_wready,
          input  wire [AxiIdWidth - 1:0]          i_dst_bid,
          input  wire  [1:0]                      i_dst_bresp,
          input  wire                             i_dst_bvalid,
          output wire                             o_dst_bready,
          input  wire [AxiIdWidth - 1:0]          i_dst_rid,
          input  wire [AxiDataWidth - 1:0]        i_dst_rdata,
          input  wire  [1:0]                      i_dst_rresp,
          input  wire                             i_dst_rlast,
          input  wire                             i_dst_rvalid,
          output wire                             o_dst_rready
    );

    typedef logic [AxiIdWidth-1:0]            id_t;
    typedef logic [AxiAddrWidth-1:0]          addr_t;
    typedef logic [AxiDataWidth-1:0]          data_t;

    typedef logic [AxiDataWidth/8-1:0]          strb_t;

    `AXI_TYPEDEF_AW_CHAN_T(aw_chan_t, addr_t, id_t, logic[0:0])
    `AXI_TYPEDEF_W_CHAN_T(w_chan_t, data_t, strb_t, logic[0:0])
    `AXI_TYPEDEF_B_CHAN_T(b_chan_t, id_t, logic[0:0])

    `AXI_TYPEDEF_AR_CHAN_T(ar_chan_t, addr_t, id_t, logic[0:0])
    `AXI_TYPEDEF_R_CHAN_T(r_chan_t, data_t, id_t, logic[0:0])

    `AXI_TYPEDEF_REQ_T(req_t, aw_chan_t, w_chan_t, ar_chan_t)
    `AXI_TYPEDEF_RESP_T(resp_t, b_chan_t, r_chan_t)

    req_t  dst_req;
    resp_t dst_resp;
    req_t  src_req;
    resp_t src_resp;

    cc_spill_register #(
		.data_t (aw_chan_t),
		.Bypass (0) 
	) i_aw_spill_reg (
		.clk_i (clk_i),
		.rst_ni (rst_ni), 
		.clr_i (1'b0),

		.data_i(src_req.aw),
		.ready_o(o_src_awready),
		.valid_i(i_src_awvalid),
		
		.data_o(dst_req.aw),
		.ready_i(i_dst_awready),
		.valid_o(o_dst_awvalid)
	);

    cc_spill_register #(
		.data_t (w_chan_t),
		.Bypass (0) 
	) i_w_spill_reg (
		.clk_i (clk_i),
		.rst_ni (rst_ni), 
		.clr_i (1'b0),

		.data_i(src_req.w),
		.ready_o(o_src_wready),
		.valid_i(i_src_wvalid),
		
		.data_o(dst_req.w),
		.ready_i(i_dst_wready),
		.valid_o(o_dst_wvalid)
	);

    cc_spill_register #(
		.data_t (ar_chan_t),
		.Bypass (0) 
	) i_ar_spill_reg (
		.clk_i (clk_i),
		.rst_ni (rst_ni), 
		.clr_i (1'b0),

		.data_i(src_req.ar),
		.ready_o(o_src_arready),
		.valid_i(i_src_arvalid),
		
		.data_o(dst_req.ar),
		.ready_i(i_dst_arready),
		.valid_o(o_dst_arvalid)
	);

    cc_spill_register #(
		.data_t (r_chan_t),
		.Bypass (0) 
	) i_r_spill_reg (
		.clk_i (clk_i),
		.rst_ni (rst_ni), 
		.clr_i (1'b0),

		.data_o(dst_resp.r),
		.ready_o(o_dst_rready),
		.valid_i(i_dst_rvalid),

		.data_i(src_resp.r),
		.ready_i(i_src_rready),
		.valid_o(o_src_rvalid)
	);

    cc_spill_register #(
		.data_t (b_chan_t),
		.Bypass (0) 
	) i_b_spill_reg (
		.clk_i (clk_i),
		.rst_ni (rst_ni), 
		.clr_i (1'b0),

		.data_o(dst_resp.b),
		.ready_o(o_dst_bready),
		.valid_i(i_dst_bvalid),

		.data_i(src_resp.b),
		.ready_i(i_src_bready),
		.valid_o(o_src_bvalid)
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
    assign src_req.w.data = i_src_wdata;
    assign src_req.w.strb = i_src_wstrb;
    assign src_req.w.last = i_src_wlast;
    assign o_src_bid = src_resp.b.id;
    assign o_src_bresp = src_resp.b.resp;
    assign o_src_rid = src_resp.r.id;
    assign o_src_rdata = src_resp.r.data;
    assign o_src_rresp = src_resp.r.resp;
    assign o_src_rlast = src_resp.r.last;

    assign o_dst_awid = dst_req.aw.id;
    assign o_dst_awaddr = dst_req.aw.addr;
    assign o_dst_awlen = dst_req.aw.len;
    assign o_dst_awsize = dst_req.aw.size;
    assign o_dst_awburst = dst_req.aw.burst;
    assign o_dst_awlock = dst_req.aw.lock;
    assign o_dst_awcache = dst_req.aw.cache;
    assign o_dst_awprot = dst_req.aw.prot;
    assign o_dst_awregion = dst_req.aw.region;
    assign o_dst_awqos = dst_req.aw.qos;
    assign o_dst_arid = dst_req.ar.id;
    assign o_dst_araddr = dst_req.ar.addr;
    assign o_dst_arlen = dst_req.ar.len;
    assign o_dst_arsize = dst_req.ar.size;
    assign o_dst_arburst = dst_req.ar.burst;
    assign o_dst_arlock = dst_req.ar.lock;
    assign o_dst_arcache = dst_req.ar.cache;
    assign o_dst_arprot = dst_req.ar.prot;
    assign o_dst_arregion = dst_req.ar.region;
    assign o_dst_arqos = dst_req.ar.qos;
    assign o_dst_wdata = dst_req.w.data;
    assign o_dst_wstrb = dst_req.w.strb;
    assign o_dst_wlast = dst_req.w.last;
endmodule
