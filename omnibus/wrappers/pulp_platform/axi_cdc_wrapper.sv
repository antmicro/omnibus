// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

module axi_cdc_wrapper #(
    parameter int unsigned AxiDataWidth        = 8    , // Data width of the ports
    parameter int unsigned AxiAddrWidth        = 32   , // Address width
    parameter int unsigned AxiIdWidth          = 1      // ID width
    ) (
    input  logic          src_clk_i,
    input  logic          src_rst_ni,
    input  logic          dst_clk_i,
    input  logic          dst_rst_ni,

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

    axi_cdc #(
       .aw_chan_t      (aw_chan_t  ),
       .w_chan_t       (w_chan_t   ),
       .b_chan_t       (b_chan_t   ),
       .ar_chan_t      (ar_chan_t  ),
       .r_chan_t       (r_chan_t   ),
       .axi_req_t      (req_t      ),
       .axi_resp_t     (resp_t     )
     ) i_axi_cdc_wrapper (
       .src_clk_i      (src_clk_i  ),
       .src_rst_ni     (src_rst_ni ),

       .dst_clk_i      (dst_clk_i  ),
       .dst_rst_ni     (dst_rst_ni ),

       // Slave interface
       .src_req_i (src_req ),
       .src_resp_o(src_resp),
       // Master interface
       .dst_req_o (dst_req ),
       .dst_resp_i(dst_resp)
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
    assign o_dst_awvalid = dst_req.aw_valid;
    assign dst_resp.aw_ready = i_dst_awready;
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
    assign o_dst_arvalid = dst_req.ar_valid;
    assign dst_resp.ar_ready = i_dst_arready;
    assign o_dst_wdata = dst_req.w.data;
    assign o_dst_wstrb = dst_req.w.strb;
    assign o_dst_wlast = dst_req.w.last;
    assign o_dst_wvalid = dst_req.w_valid;
    assign dst_resp.w_ready = i_dst_wready;
    assign dst_resp.b.id = i_dst_bid;
    assign dst_resp.b.resp = i_dst_bresp;
    assign dst_resp.b_valid = i_dst_bvalid;
    assign o_dst_bready = dst_req.b_ready;
    assign dst_resp.r.id = i_dst_rid;
    assign dst_resp.r.data = i_dst_rdata;
    assign dst_resp.r.resp = i_dst_rresp;
    assign dst_resp.r.last = i_dst_rlast;
    assign dst_resp.r_valid = i_dst_rvalid;
    assign o_dst_rready = dst_req.r_ready;

endmodule
