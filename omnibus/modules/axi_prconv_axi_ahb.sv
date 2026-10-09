// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

// AXI4 -> AHB3 bridge, one AXI transaction in flight at a time.
//
// The next AHB address phase is issued while the previous data phase is running.
//  - A beat that is a single aligned transfer (for writes: all bytes of the beat enabled by
//    WSTRB) can be part of an AHB burst: INCR bursts run as HBURST=INCR (restarted with NONSEQ
//    at every 1KB), reads with WRAP of 4, 8 and 16 beats as WRAP4/8/16.
//  - Everything else is issued as NONSEQ SINGLE transfers: FIXED, WRAP2, writes with WRAP,
//    and beats that must be split into several transfers (narrow or unaligned beats, and
//    WSTRB that is not a whole aligned chunk).
// Reads go through a FIFO of FifoDepth beats and are issued only while it has room, a running
// AHB burst waits with BUSY. FifoDepth 3 (the default) lets reads run at one beat per cycle.
// Writes take W beats into a FIFO of FifoDepth beats first, since the transfers a beat needs
// depend on its WSTRB.
// After an AHB error no more AHB transfers are issued: the remaining beats of a read return
// SLVERR, the remaining W beats of a write are dropped and its B is SLVERR.
// Exclusive accesses, QOS and REGION are ignored. AxiDataWidth must be a power of two in
// 16..256.

module axi_prconv_axi_ahb #(
    parameter int unsigned AxiAddrWidth = 32,
    parameter int unsigned AxiDataWidth = 64,
    parameter int unsigned AxiIdWidth   = 1,
    parameter int unsigned FifoDepth    = 3
) (
    input logic clk_i,
    input logic rst_ni,

    input  logic [  AxiIdWidth-1:0] src_awid,
    input  logic [AxiAddrWidth-1:0] src_awaddr,
    input  logic [           7:0]   src_awlen,
    input  logic [           2:0]   src_awsize,
    input  logic [           1:0]   src_awburst,
    input  logic                    src_awlock,
    input  logic [           3:0]   src_awcache,
    input  logic [           2:0]   src_awprot,
    input  logic [           3:0]   src_awqos,
    input  logic [           3:0]   src_awregion,
    input  logic                    src_awvalid,
    output logic                    src_awready,

    input  logic [AxiDataWidth-1:0]   src_wdata,
    input  logic [AxiDataWidth/8-1:0] src_wstrb,
    input  logic                      src_wlast,
    input  logic                      src_wvalid,
    output logic                      src_wready,

    output logic [AxiIdWidth-1:0] src_bid,
    output logic [         1:0]   src_bresp,
    output logic                  src_bvalid,
    input  logic                  src_bready,

    input  logic [  AxiIdWidth-1:0] src_arid,
    input  logic [AxiAddrWidth-1:0] src_araddr,
    input  logic [           7:0]   src_arlen,
    input  logic [           2:0]   src_arsize,
    input  logic [           1:0]   src_arburst,
    input  logic                    src_arlock,
    input  logic [           3:0]   src_arcache,
    input  logic [           2:0]   src_arprot,
    input  logic [           3:0]   src_arqos,
    input  logic [           3:0]   src_arregion,
    input  logic                    src_arvalid,
    output logic                    src_arready,

    output logic [  AxiIdWidth-1:0] src_rid,
    output logic [AxiDataWidth-1:0] src_rdata,
    output logic [           1:0]   src_rresp,
    output logic                    src_rlast,
    output logic                    src_rvalid,
    input  logic                    src_rready,

    output logic [AxiAddrWidth-1:0] dst_haddr,
    output logic [           2:0]   dst_hburst,
    output logic                    dst_hmastlock,
    output logic [           3:0]   dst_hprot,
    output logic [           2:0]   dst_hsize,
    output logic [           1:0]   dst_htrans,
    output logic [AxiDataWidth-1:0] dst_hwdata,
    output logic                    dst_hwrite,
    input  logic [AxiDataWidth-1:0] dst_hrdata,
    input  logic                    dst_hready,
    input  logic                    dst_hresp
);

  localparam int unsigned Lanes = AxiDataWidth / 8;
  localparam int unsigned LaneBits = $clog2(Lanes);

  localparam logic [1:0] BurstFixed = 2'b00, BurstIncr = 2'b01, BurstWrap = 2'b10;
  localparam logic [1:0] TransIdle = 2'b00, TransBusy = 2'b01;
  localparam logic [1:0] TransNonseq = 2'b10, TransSeq = 2'b11;

  typedef enum logic [1:0] {
    IDLE,  // waiting for AW or AR
    RUN,   // issuing the AHB transfers, moving the data
    RESP   // B of a write
  } state_t;

  state_t state;

  logic                    write;
  logic [  AxiIdWidth-1:0] id;
  logic [AxiAddrWidth-1:0] addr;  // address of the beat being issued
  logic [             7:0] len;
  logic [             2:0] size;
  logic [             1:0] burst;
  logic [             3:0] hprot;
  logic [             8:0] beat;  // beats issued (read) or taken from the W FIFO (write)
  logic [             8:0] rpush;  // R beats put into the FIFO
  logic [             8:0] rdel;  // R beats delivered
  logic [      LaneBits:0] ptr;  // first byte lane of the beat not yet issued
  logic                    seq_ok;  // the transfer issued last can be continued by a SEQ
  logic                    aborted;  // an AHB error was seen
  logic                    w_done;  // WLAST taken
  logic                    prefer_read;

  // data phase of the AHB transfer accepted last
  logic                    dp_valid;
  logic                    dp_last;  // it finishes its beat
  logic [      LaneBits:0] dp_start;
  logic [  LaneBits-1:0]   dp_log;
  logic [AxiDataWidth-1:0] dp_wdata;
  logic [AxiDataWidth-1:0] asm;  // read beat being assembled

  logic take_write, take_read;
  logic [AxiAddrWidth-1:0] ax_addr;

  // AW and AR are served in turn when both are valid: after a write (prefer_read) the read
  // goes first, after a read the write does, so neither can starve the other.
  assign take_write = src_awvalid && (!src_arvalid || !prefer_read);
  assign take_read  = src_arvalid && !take_write;
  assign ax_addr    = take_write ? src_awaddr : src_araddr;

  // FIFOs
  logic wf_push, wf_pop, wf_full, wf_empty;
  logic rf_push, rf_pop, rf_full, rf_empty;
  logic [Lanes-1:0] wf_strb;
  logic [AxiDataWidth-1:0] wf_data, asm_n, rf_data;
  logic rf_err;

  axi_prconv_fifo #(
      .Width(Lanes + AxiDataWidth),
      .Depth(FifoDepth)
  ) w_fifo (
      .clk_i,
      .rst_ni,
      .push  (wf_push),
      .data_i({src_wstrb, src_wdata}),
      .full  (wf_full),
      .pop   (wf_pop),
      .data_o({wf_strb, wf_data}),
      .empty (wf_empty)
  );

  axi_prconv_fifo #(
      .Width(1 + AxiDataWidth),
      .Depth(FifoDepth)
  ) r_fifo (
      .clk_i,
      .rst_ni,
      .push  (rf_push),
      .data_i({aborted || dst_hresp, asm_n}),
      .full  (rf_full),
      .pop   (rf_pop),
      .data_o({rf_err, rf_data}),
      .empty (rf_empty)
  );

  // Byte lanes [ptr, hi) of the bus word are still to be issued; the next transfer is the
  // largest naturally aligned chunk that starts at the first of them that is enabled.
  logic [Lanes-1:0] lane_en;
  logic [LaneBits:0] lo, hi, start, ptr_next;
  logic [LaneBits-1:0] chunk_log;
  logic chunk_valid, more_after, simple;

  assign lane_en = write ? wf_strb : '1;
  assign lo = {1'b0, addr[LaneBits-1:0]};
  assign hi = (lo | (LaneBits + 1)'((1 << size) - 1)) + 1;
  assign ptr_next = start + (LaneBits + 1)'(1 << chunk_log);
  // the whole beat is one transfer
  assign simple = chunk_valid && start == lo && int'(chunk_log) == int'(size);

  always_comb begin
    start = ptr;
    for (int i = Lanes - 1; i >= 0; i--) if (i >= ptr && lane_en[i]) start = (LaneBits + 1)'(i);
    chunk_valid = start < hi && lane_en[start[LaneBits-1:0]];
    chunk_log   = '0;
    for (int s = 1; s <= LaneBits; s++) begin
      if ((start & ((1 << s) - 1)) == 0 && start + (1 << s) <= hi &&
          &(lane_en | ~(Lanes'((64'd1 << (1 << s)) - 1) << start))) chunk_log = LaneBits'(s);
    end
    more_after = 1'b0;
    for (int i = 0; i < Lanes; i++) if (i >= ptr_next && i < hi && lane_en[i]) more_after = 1'b1;
  end

  // Address of the next beat
  logic [AxiAddrWidth-1:0] beat_bytes, aligned, wrap_mask, next_addr;

  assign beat_bytes = AxiAddrWidth'(1) << size;
  assign aligned    = addr & ~(beat_bytes - 1);
  assign wrap_mask  = (AxiAddrWidth'(len) << size) | (beat_bytes - 1);

  always_comb begin
    case (burst)
      BurstFixed: next_addr = addr;
      BurstWrap:  next_addr = (aligned & ~wrap_mask) | ((aligned + beat_bytes) & wrap_mask);
      default:    next_addr = aligned + beat_bytes;
    endcase
  end

  // HBURST of the beats of this transaction that are a single transfer each
  logic [2:0] burst_type;
  logic burstable;

  always_comb begin
    burst_type = 3'b000;
    if (burst == BurstIncr && len != 0) burst_type = 3'b001;
    else if (burst == BurstWrap && !write) begin
      case (len)
        8'd3:    burst_type = 3'b010;
        8'd7:    burst_type = 3'b100;
        8'd15:   burst_type = 3'b110;
        default: burst_type = 3'b000;
      endcase
    end
  end

  assign burstable = simple && burst_type != 3'b000;

  // Issuing
  logic all_issued, can_issue, xfer, acc, skip, drain, last_beat;

  assign all_issued = beat == {1'b0, len} + 9'd1;
  assign last_beat = beat == {1'b0, len};
  assign can_issue = state == RUN && !aborted && !all_issued &&
                     (write ? !wf_empty : 9'(beat - rdel) < 9'(FifoDepth));
  assign xfer = can_issue && chunk_valid;
  assign acc = dst_htrans[1] && dst_hready;
  assign skip = can_issue && write && !chunk_valid;  // WSTRB enables nothing: no transfer
  assign drain = state == RUN && write && aborted && !all_issued && !wf_empty;

  always_comb begin
    if (xfer) dst_htrans = burstable && seq_ok ? TransSeq : TransNonseq;
    else if (state == RUN && !aborted && !write && seq_ok) dst_htrans = TransBusy;
    else dst_htrans = TransIdle;
  end

  assign dst_haddr = {addr[AxiAddrWidth-1:LaneBits], start[LaneBits-1:0]};
  assign dst_hsize = simple ? size : 3'(chunk_log);
  assign dst_hburst = simple ? burst_type : 3'b000;
  assign dst_hmastlock = 1'b0;
  assign dst_hprot = hprot;
  assign dst_hwrite = write;
  assign dst_hwdata = dp_wdata;

  // Data phase of the read transfers, byte lanes [dp_start, dp_start + 2**dp_log)
  logic [AxiDataWidth-1:0] dp_bits;

  always_comb begin
    dp_bits = '0;
    for (int i = 0; i < Lanes; i++) begin
      if (i >= int'(dp_start) && i < int'(dp_start) + (1 << dp_log)) dp_bits[8*i+:8] = '1;
    end
  end

  assign asm_n = (asm & ~dp_bits) | (dst_hrdata & dp_bits);

  // Transfers finished in the data phase before an error are ignored, the beats they
  // would have finished are answered with SLVERR instead.
  logic completed;

  assign completed = dp_valid && dst_hready && !aborted;
  assign rf_push = state == RUN && !write && !rf_full && (completed && dp_last ||
                                                          aborted && rpush != {1'b0, len} + 9'd1);
  assign rf_pop = src_rvalid && src_rready;
  assign wf_push = src_wvalid && src_wready;
  assign wf_pop = acc && write && !more_after || skip || drain;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state       <= IDLE;
      prefer_read <= 1'b0;
      dp_valid    <= 1'b0;
      aborted     <= 1'b0;
      asm         <= '0;
    end else begin
      case (state)
        IDLE:
        if ((take_write || take_read) && !dp_valid) begin
          {id, addr, len, size, burst, hprot} <= take_write ?
              {src_awid, src_awaddr, src_awlen, src_awsize, src_awburst,
               src_awcache[1:0], src_awprot[0], ~src_awprot[2]} :
              {src_arid, src_araddr, src_arlen, src_arsize, src_arburst,
               src_arcache[1:0], src_arprot[0], ~src_arprot[2]};
          write       <= take_write;
          prefer_read <= take_write;
          beat        <= '0;
          rpush       <= '0;
          rdel        <= '0;
          ptr         <= {1'b0, ax_addr[LaneBits-1:0]};
          seq_ok      <= 1'b0;
          aborted     <= 1'b0;
          w_done      <= 1'b0;
          state       <= RUN;
        end
        RUN:
        if (write ? all_issued && !dp_valid : rf_pop && src_rlast) state <= write ? RESP : IDLE;
        RESP: if (src_bready) state <= IDLE;
        default: state <= IDLE;
      endcase

      if (state == RUN) begin
        if (acc) begin
          ptr <= ptr_next;
          seq_ok <= 1'b0;
          if (!more_after) begin
            beat <= beat + 1'b1;
            addr <= next_addr;
            ptr <= {1'b0, next_addr[LaneBits-1:0]};
            seq_ok <= burstable && !last_beat && !(burst == BurstIncr && next_addr[9:0] == '0);
          end
        end else if (skip) begin
          beat   <= beat + 1'b1;
          addr   <= next_addr;
          ptr    <= {1'b0, next_addr[LaneBits-1:0]};
          seq_ok <= 1'b0;
        end else if (drain) beat <= beat + 1'b1;
        else if (write && !dst_htrans[1]) seq_ok <= 1'b0;

        if (dp_valid && dst_hresp) aborted <= 1'b1;
        if (completed) asm <= asm_n;
        if (rf_push) rpush <= rpush + 1'b1;
        if (rf_pop) rdel <= rdel + 1'b1;
        if (wf_push && src_wlast) w_done <= 1'b1;
      end

      if (dst_hready) dp_valid <= dst_htrans[1];
      if (acc) begin
        dp_start <= start;
        dp_log   <= chunk_log;
        dp_last  <= !more_after;
        dp_wdata <= wf_data;
      end
    end
  end

  assign src_awready = state == IDLE && !dp_valid && take_write;
  assign src_arready = state == IDLE && !dp_valid && take_read;
  assign src_wready = state == RUN && write && !w_done && !wf_full;

  assign src_bvalid = state == RESP;
  assign src_bid = id;
  assign src_bresp = aborted ? 2'b10 : 2'b00;

  assign src_rvalid = state == RUN && !write && !rf_empty;
  assign src_rid = id;
  assign src_rdata = rf_data;
  assign src_rresp = rf_err ? 2'b10 : 2'b00;
  assign src_rlast = rdel[7:0] == len;

endmodule
