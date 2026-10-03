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

    typedef struct packed {
        logic [AxiIdWidth   - 1 :0] id;
        logic [AxiAddrWidth - 1 :0] addr;
        logic  [7:0]                len;
        logic  [2:0]                size;
        logic  [1:0]                burst;
        logic                       lock;
        logic  [3:0]                cache;
        logic  [2:0]                prot;
        logic  [3:0]                region;
        logic  [3:0]                qos;
    } aw_chan_t;

    typedef struct packed {
        logic [AxiDataWidth - 1:0]   data;
        logic [AxiDataWidth/8 - 1:0] strb;
        logic                        last;
    } w_chan_t;

    typedef struct packed {
        logic [AxiIdWidth - 1   :0] id;
        logic [AxiAddrWidth - 1 :0] addr;
        logic  [7:0]                len;
        logic  [2:0]                size;
        logic  [1:0]                burst;
        logic                       lock;
        logic  [3:0]                cache;
        logic  [2:0]                prot;
        logic  [3:0]                region;
        logic  [3:0]                qos;
    } ar_chan_t;

    typedef struct packed {
        logic [AxiIdWidth - 1 :0]  id;
        logic [AxiDataWidth - 1:0] data;
        logic  [1:0]               resp;
        logic                      last;
    } r_chan_t;

    typedef struct packed {
        logic [AxiIdWidth - 1:0] id;
        logic  [1:0]             resp;
    } b_chan_t;

	aw_chan_t awsrc, awdst;
	w_chan_t   wsrc,  wdst;
	ar_chan_t arsrc, ardst;
	r_chan_t   rsrc,  rdst;
	b_chan_t   bsrc,  bdst;

    cc_spill_register #(
        .data_t (aw_chan_t),
        .Bypass (0) 
    ) i_aw_spill_reg (
        .clk_i (clk_i),
        .rst_ni (rst_ni), 
        .clr_i (1'b0),

        .data_i(awsrc),
        .ready_o(o_src_awready),
        .valid_i(i_src_awvalid),
        
        .data_o(awdst),
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

        .data_i(wsrc),
        .ready_o(o_src_wready),
        .valid_i(i_src_wvalid),
        
        .data_o(wdst),
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

        .data_i(arsrc),
        .ready_o(o_src_arready),
        .valid_i(i_src_arvalid),
        
        .data_o(ardst),
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

        .data_i(rdst),
        .ready_o(o_dst_rready),
        .valid_i(i_dst_rvalid),

        .data_o(rsrc),
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

        .data_i(bdst),
        .ready_o(o_dst_bready),
        .valid_i(i_dst_bvalid),

        .data_o(bsrc),
        .ready_i(i_src_bready),
        .valid_o(o_src_bvalid)
    );

    assign awsrc.id = i_src_awid;
    assign awsrc.addr = i_src_awaddr;
    assign awsrc.len = i_src_awlen;
    assign awsrc.size = i_src_awsize;
    assign awsrc.burst = i_src_awburst;
    assign awsrc.lock = i_src_awlock;
    assign awsrc.cache = i_src_awcache;
    assign awsrc.prot = i_src_awprot;
    assign awsrc.region = i_src_awregion;
    assign awsrc.qos = i_src_awqos;

    assign arsrc.id = i_src_arid;
    assign arsrc.addr = i_src_araddr;
    assign arsrc.len = i_src_arlen;
    assign arsrc.size = i_src_arsize;
    assign arsrc.burst = i_src_arburst;
    assign arsrc.lock = i_src_arlock;
    assign arsrc.cache = i_src_arcache;
    assign arsrc.prot = i_src_arprot;
    assign arsrc.region = i_src_arregion;
    assign arsrc.qos = i_src_arqos;

    assign wsrc.data = i_src_wdata;
    assign wsrc.strb = i_src_wstrb;
    assign wsrc.last = i_src_wlast;

    assign o_src_bid = bsrc.id;
    assign o_src_bresp = bsrc.resp;

    assign o_src_rid = rsrc.id;
    assign o_src_rdata = rsrc.data;
    assign o_src_rresp = rsrc.resp;
    assign o_src_rlast = rsrc.last;

    assign o_dst_awid = awdst.id;
    assign o_dst_awaddr = awdst.addr;
    assign o_dst_awlen = awdst.len;
    assign o_dst_awsize = awdst.size;
    assign o_dst_awburst = awdst.burst;
    assign o_dst_awlock = awdst.lock;
    assign o_dst_awcache = awdst.cache;
    assign o_dst_awprot = awdst.prot;
    assign o_dst_awregion = awdst.region;
    assign o_dst_awqos = awdst.qos;

    assign o_dst_arid = ardst.id;
    assign o_dst_araddr = ardst.addr;
    assign o_dst_arlen = ardst.len;
    assign o_dst_arsize = ardst.size;
    assign o_dst_arburst = ardst.burst;
    assign o_dst_arlock = ardst.lock;
    assign o_dst_arcache = ardst.cache;
    assign o_dst_arprot = ardst.prot;
    assign o_dst_arregion = ardst.region;
    assign o_dst_arqos = ardst.qos;

    assign o_dst_wdata = wdst.data;
    assign o_dst_wstrb = wdst.strb;
    assign o_dst_wlast = wdst.last;

    assign bdst.id = i_dst_bid;
    assign bdst.resp = i_dst_bresp;

    assign rdst.id = i_dst_rid;
    assign rdst.data = i_dst_rdata;
    assign rdst.resp = i_dst_rresp;
    assign rdst.last = i_dst_rlast;

endmodule
