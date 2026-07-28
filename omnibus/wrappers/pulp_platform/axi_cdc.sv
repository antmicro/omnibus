module axi_cdc_wrapper #(
    parameter int unsigned AxiMaxReads         = 1    , // Number of outstanding reads
    parameter int unsigned AxiDataWidth        = 8    , // Data width of the ports
    parameter int unsigned AxiAddrWidth        = 1    , // Address width
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

    typedef logic [AxiStrbWidth-1:0]          strb_t;
    typedef logic [AxiUserWidth-1:0]          user_t;
    
    `AXI_TYPEDEF_AW_CHAN_T(aw_chan_t, addr_t, id_t, user_t)
    `AXI_TYPEDEF_W_CHAN_T(w_chan_t, data_t, strb_t, user_t)
    `AXI_TYPEDEF_B_CHAN_T(b_chan_t, id_t, user_t)
    
    `AXI_TYPEDEF_AR_CHAN_T(ar_chan_t, addr_t, id_t, user_t)
    `AXI_TYPEDEF_R_CHAN_T(r_chan_t, data_t, id_t, user_t)
    
    `AXI_TYPEDEF_REQ_T(req_t, aw_chan_t, w_chan_t, ar_chan_t)
    `AXI_TYPEDEF_RESP_T(resp_t, b_chan_t, r_chan_t)

    req_t  dst_req;
    resp_t dst_resp;
    req_t  src_req;
    resp_t src_resp;

    axi_cdc #(
       .aw_chan_t      (aw_chan_t          ),
       .w_chan_t       (mst_w_chan_t       ),
       .b_chan_t       (b_chan_t           ),
       .ar_chan_t      (ar_chan_t          ),
       .r_chan_t       (r_chan_slv_t       ),
       .axi_req_t      (mst_req_t          ),
       .axi_resp_t     (mst_resp_t         ),
     ) i_axi_cdc_wrapper (
       .src_clk_i      (src_clk_i     ),
       .src_rst_ni     (src_rst_ni    ),

       .dst_clk_i      (dst_clk_i     ),
       .dst_rst_ni     (dst_rst_ni    ),

       // Slave interface
       .src_req_i (src_req ),
       .src_resp_o(src_resp),
       // Master interface
       .dst_req_o (dst_req ),
       .dst_resp_i(dst_resp)
     );


    assign dst_req.aw.id = i_dst_awid;
    assign dst_req.aw.addr = i_dst_awaddr;
    assign dst_req.aw.len = i_dst_awlen;
    assign dst_req.aw.size = i_dst_awsize;
    assign dst_req.aw.burst = i_dst_awburst;
    assign dst_req.aw.lock = i_dst_awlock;
    assign dst_req.aw.cache = i_dst_awcache;
    assign dst_req.aw.prot = i_dst_awprot;
    assign dst_req.aw.region = i_dst_awregion;
    assign dst_req.aw.qos = i_dst_awqos;
    assign dst_req.aw.atop = 6'd0;
    assign dst_req.aw_valid = i_dst_awvalid;
    assign o_dst_awready = dst_resp.aw_ready;
    assign dst_req.ar.id = i_dst_arid;
    assign dst_req.ar.addr = i_dst_araddr;
    assign dst_req.ar.len = i_dst_arlen;
    assign dst_req.ar.size = i_dst_arsize;
    assign dst_req.ar.burst = i_dst_arburst;
    assign dst_req.ar.lock = i_dst_arlock;
    assign dst_req.ar.cache = i_dst_arcache;
    assign dst_req.ar.prot = i_dst_arprot;
    assign dst_req.ar.region = i_dst_arregion;
    assign dst_req.ar.qos = i_dst_arqos;
    assign dst_req.ar_valid = i_dst_arvalid;
    assign o_dst_arready = dst_resp.ar_ready;
    assign dst_req.w.data = i_dst_wdata;
    assign dst_req.w.strb = i_dst_wstrb;
    assign dst_req.w.last = i_dst_wlast;
    assign dst_req.w_valid = i_dst_wvalid;
    assign o_dst_wready = dst_resp.w_ready;
    assign o_dst_bid = dst_resp.b.id;
    assign o_dst_bresp = dst_resp.b.resp;
    assign o_dst_bvalid = dst_resp.b_valid;
    assign dst_req.b_ready = i_dst_bready;
    assign o_dst_rid = dst_resp.r.id;
    assign o_dst_rdata = dst_resp.r.data;
    assign o_dst_rresp = dst_resp.r.resp;
    assign o_dst_rlast = dst_resp.r.last;
    assign o_dst_rvalid = dst_resp.r_valid;
    assign dst_req.r_ready = i_dst_rready;

    assign o_src_awid = src_req.aw.id;
    assign o_src_awaddr = src_req.aw.addr;
    assign o_src_awlen = src_req.aw.len;
    assign o_src_awsize = src_req.aw.size;
    assign o_src_awburst = src_req.aw.burst;
    assign o_src_awlock = src_req.aw.lock;
    assign o_src_awcache = src_req.aw.cache;
    assign o_src_awprot = src_req.aw.prot;
    assign o_src_awregion = src_req.aw.region;
    assign o_src_awqos = src_req.aw.qos;
    assign o_src_awvalid = src_req.aw_valid;
    assign src_resp.aw_ready = i_src_awready;
    assign o_src_arid = src_req.ar.id;
    assign o_src_araddr = src_req.ar.addr;
    assign o_src_arlen = src_req.ar.len;
    assign o_src_arsize = src_req.ar.size;
    assign o_src_arburst = src_req.ar.burst;
    assign o_src_arlock = src_req.ar.lock;
    assign o_src_arcache = src_req.ar.cache;
    assign o_src_arprot = src_req.ar.prot;
    assign o_src_arregion = src_req.ar.region;
    assign o_src_arqos = src_req.ar.qos;
    assign o_src_arvalid = src_req.ar_valid;
    assign src_resp.ar_ready = i_src_arready;
    assign o_src_wdata = src_req.w.data;
    assign o_src_wstrb = src_req.w.strb;
    assign o_src_wlast = src_req.w.last;
    assign o_src_wvalid = src_req.w_valid;
    assign src_resp.w_ready = i_src_wready;
    assign src_resp.b.id = i_src_bid;
    assign src_resp.b.resp = i_src_bresp;
    assign src_resp.b_valid = i_src_bvalid;
    assign o_src_bready = src_req.b_ready;
    assign src_resp.r.id = i_src_rid;
    assign src_resp.r.data = i_src_rdata;
    assign src_resp.r.resp = i_src_rresp;
    assign src_resp.r.last = i_src_rlast;
    assign src_resp.r_valid = i_src_rvalid;
    assign o_src_rready = src_req.r_ready;

endmodule
