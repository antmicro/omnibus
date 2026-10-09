// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

// AHB rules the bridge must keep, checked on every cycle just before the rising edge:
//  - transfers are aligned to HSIZE and inside one bus word,
//  - the address phase does not change while HREADY is low (an ERROR may cancel it),
//  - no transfer follows the second cycle of an ERROR response,
//  - SEQ and BUSY only occur inside a burst, at the address it continues with, with the HBURST,
//    HSIZE and HWRITE of the burst,
//  - an undefined length INCR burst stays inside 1KB,
//  - a fixed length burst is completed (unless an ERROR cancelled it), and no burst ends with BUSY,
//  - HBURST is SINGLE, INCR, WRAP4, WRAP8 or WRAP16, which are the bursts the bridge uses.
module bridge_ahb_checker #(
    parameter int unsigned AddrWidth = 32,
    parameter int unsigned DataWidth = 64
) (
    input logic                 clk,
    input logic                 rst_n,
    input logic [AddrWidth-1:0] haddr,
    input logic [          2:0] hburst,
    input logic [          2:0] hsize,
    input logic [          1:0] htrans,
    input logic                 hwrite,
    input logic                 hready,
    input logic                 hresp
);
  import uvm_pkg::*;
  `include "uvm_macros.svh"

  localparam int unsigned Lanes = DataWidth / 8;
  localparam logic [1:0] Idle = 2'b00, Busy = 2'b01, Nonseq = 2'b10, Seq = 2'b11;

  // beats of a fixed length burst, 0 for INCR of undefined length
  function automatic int beats(logic [2:0] burst);
    case (burst)
      3'b000:  return 1;
      3'b010, 3'b011: return 4;
      3'b100, 3'b101: return 8;
      3'b110, 3'b111: return 16;
      default: return 0;
    endcase
  endfunction

  // the transfer presented in the previous cycle
  bit prev_valid;
  logic [1:0] prev_trans;
  logic [AddrWidth-1:0] prev_addr;
  logic [2:0] prev_size, prev_burst;
  logic prev_write, prev_ready;

  // the running burst
  bit run_valid;
  logic [2:0] run_burst, run_size;
  logic run_write;
  longint unsigned run_next;
  longint unsigned run_first;
  int run_left;  // beats still to come, -1 for undefined length
  bit run_cancelled, run_busy_last;

  longint unsigned nbytes;
  longint unsigned wrap_bytes;
  longint unsigned wrap_low;

  always @(negedge clk) begin
    if (!rst_n) begin
      prev_valid = 0;
      run_valid = 0;
    end
    else begin
      nbytes = 1 << hsize;
      if (hresp && hready && htrans != Idle)
        `uvm_error("AHB_CHK", "a transfer follows the second cycle of an ERROR response")
      if (htrans >= Nonseq) begin
        if (haddr % nbytes != 0)
          `uvm_error("AHB_CHK", $sformatf("address %h is not aligned to HSIZE %0d", haddr, hsize))
        if ((haddr % Lanes) + nbytes > Lanes)
          `uvm_error("AHB_CHK", $sformatf("transfer at %h of %0d bytes leaves the bus word", haddr, nbytes))
        if (!(hburst inside {3'b000, 3'b001, 3'b010, 3'b100, 3'b110}))
          `uvm_error("AHB_CHK", $sformatf("HBURST %0d is not one the bridge uses", hburst))
      end
      if (prev_valid && prev_trans >= Nonseq && !prev_ready && !hresp &&
          {htrans, haddr, hsize, hburst, hwrite} != {prev_trans, prev_addr, prev_size, prev_burst, prev_write})
        `uvm_error("AHB_CHK", "the address phase changed while HREADY was low")
      prev_valid = 1;
      prev_trans = htrans;
      prev_addr = haddr;
      prev_size = hsize;
      prev_burst = hburst;
      prev_write = hwrite;
      prev_ready = hready;

      if (hresp && run_valid) run_cancelled = 1;

      if (hready) begin
        if (run_valid && (htrans == Busy || htrans == Seq)) begin
          if ({run_burst, run_size, run_write} != {hburst, hsize, hwrite})
            `uvm_error("AHB_CHK", "HBURST, HSIZE or HWRITE changed inside a burst")
          if (haddr != run_next)
            `uvm_error("AHB_CHK", $sformatf("%s at %h, the burst continues at %h", htrans == Busy ? "BUSY" : "SEQ", haddr, run_next))
        end
        if (htrans == Busy) begin
          if (!run_valid) `uvm_error("AHB_CHK", "BUSY outside a burst")
          run_busy_last = 1;
        end
        else begin
          if (htrans == Seq) begin
            if (!run_valid) `uvm_error("AHB_CHK", "SEQ outside a burst")
            else begin
              if (run_left == 0) `uvm_error("AHB_CHK", "SEQ after the last beat of a fixed length burst")
              if (beats(hburst) == 0 && haddr >> 10 != run_first >> 10)
                `uvm_error("AHB_CHK", $sformatf("INCR burst crosses 1KB at %h", haddr))
            end
          end
          else begin
            // IDLE or NONSEQ end the running burst
            if (run_valid && !run_cancelled) begin
              if (run_busy_last) `uvm_error("AHB_CHK", "a burst ends with BUSY")
              if (run_left > 0)
                `uvm_error("AHB_CHK", $sformatf("a fixed length burst ended with %0d beats left", run_left))
            end
            run_valid = 0;
          end

          if (htrans >= Nonseq) begin
            if (!run_valid) begin
              run_valid = 1;
              run_burst = hburst;
              run_size = hsize;
              run_write = hwrite;
              run_first = haddr;
              run_left = beats(hburst) == 0 ? -1 : beats(hburst) - 1;
              run_cancelled = 0;
            end
            else if (run_left > 0) run_left--;
            run_busy_last = 0;
            run_next = haddr + nbytes;
            if (hburst inside {3'b010, 3'b100, 3'b110}) begin
              wrap_bytes = nbytes * beats(hburst);
              wrap_low = haddr / wrap_bytes * wrap_bytes;
              if (run_next == wrap_low + wrap_bytes) run_next = wrap_low;
            end
          end
        end
      end
    end
  end
endmodule
