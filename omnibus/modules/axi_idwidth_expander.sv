module axi_idwidth_expander #(
    parameter int unsigned AxiMaxReads         = 1    , // Number of outstanding reads
    parameter int unsigned AxiDataWidth        = 8    , // Data width of the ports
    parameter int unsigned AxiAddrWidth        = 1    , // Address width
    parameter int unsigned AxiSrcIdWidth       = 1    , // ID width
    parameter int unsigned AxiDstIdWidth       = 3      // ID width
    ) (
    input  logic          clk_i,
    input  logic          rst_ni,

          input  wire [AxiSrcIdWidth   - 1 :0]    i_src_awid,
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
          input  wire [AxiSrcIdWidth - 1   :0]    i_src_arid,
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
          output wire [AxiSrcIdWidth - 1 :0]      o_src_bid,
          output wire  [1:0]                      o_src_bresp,
          output wire                             o_src_bvalid,
          input  wire                             i_src_bready,
          output wire [AxiSrcIdWidth - 1 :0]      o_src_rid,
          output wire [AxiDataWidth - 1:0]        o_src_rdata,
          output wire  [1:0]                      o_src_rresp,
          output wire                             o_src_rlast,
          output wire                             o_src_rvalid,
          input  wire                             i_src_rready,

          output wire [AxiDstIdWidth - 1 :0]      o_dst_awid,
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
          output wire [AxiDstIdWidth-1:0]         o_dst_arid,
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
          input  wire [AxiDstIdWidth - 1:0]       i_dst_bid,
          input  wire  [1:0]                      i_dst_bresp,
          input  wire                             i_dst_bvalid,
          output wire                             o_dst_bready,
          input  wire [AxiDstIdWidth - 1:0]       i_dst_rid,
          input  wire [AxiDataWidth - 1:0]        i_dst_rdata,
          input  wire  [1:0]                      i_dst_rresp,
          input  wire                             i_dst_rlast,
          input  wire                             i_dst_rvalid,
          output wire                             o_dst_rready
    );

    
    //source -> destination gains few zero bits
    //destination -> source uses only lowest bits, highest must be zero due to how they were expanded

    localparam int unsigned bits_to_add = AxiDstIdWidth - AxiSrcIdWidth;

    assign o_dst_araddr    = i_src_araddr;
    assign o_dst_arburst   = i_src_arburst;
    assign o_dst_arid      = {{bits_to_add{1'b0}}, i_src_arid};
    assign o_dst_arcache   = i_src_arcache;
    assign o_dst_arlen     = i_src_arlen;
    assign o_dst_arlock    = i_src_arlock;
    assign o_dst_arprot    = i_src_arprot;
    assign o_dst_arqos     = i_src_arqos;
    assign o_dst_arregion  = i_src_arregion;
    assign o_dst_arsize    = i_src_arsize;
    assign o_dst_arvalid   = i_src_arvalid;
    assign o_dst_awaddr    = i_src_awaddr;
    assign o_dst_awburst   = i_src_awburst;
    assign o_dst_awcache   = i_src_awcache;
    assign o_dst_awid      = {{bits_to_add{1'b0}}, i_src_awid};
    assign o_dst_awlen     = i_src_awlen;
    assign o_dst_awlock    = i_src_awlock;
    assign o_dst_awprot    = i_src_awprot;
    assign o_dst_awqos     = i_src_awqos;
    assign o_dst_awregion  = i_src_awregion;
    assign o_dst_awsize    = i_src_awsize;
    assign o_dst_awvalid   = i_src_awvalid;
    assign o_dst_bready    = i_src_bready;
    assign o_dst_rready    = i_src_rready;
    assign o_dst_wdata     = i_src_wdata;
    assign o_dst_wlast     = i_src_wlast;
    assign o_dst_wstrb     = i_src_wstrb;
    assign o_dst_wvalid    = i_src_wvalid;

    assign o_src_arready   = i_dst_arready;
    assign o_src_awready   = i_dst_awready;
    assign o_src_bid       = i_dst_bid[AxiSrcIdWidth - 1:0];
    assign o_src_bresp     = i_dst_bresp;
    assign o_src_bvalid    = i_dst_bvalid;
    assign o_src_rdata     = i_dst_rdata;
    assign o_src_rid       = i_dst_rid[AxiSrcIdWidth - 1:0];
    assign o_src_rlast     = i_dst_rlast;
    assign o_src_rresp     = i_dst_rresp;
    assign o_src_rvalid    = i_dst_rvalid;
    assign o_src_wready    = i_dst_wready;

endmodule
