// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

// Small synchronous FIFO for axi_prconv_axi_ahb. Callers push only when not full
// and pop only when not empty. Depth is at least 1.

module axi_prconv_fifo #(
    parameter int unsigned Width = 8,
    parameter int unsigned Depth = 2
) (
    input logic clk_i,
    input logic rst_ni,

    input  logic             push,
    input  logic [Width-1:0] data_i,
    output logic             full,

    input  logic             pop,
    output logic [Width-1:0] data_o,
    output logic             empty
);

  if (Depth < 1) begin : g_depth
    $fatal(1, "axi_prconv_fifo: Depth must be at least 1, it is %0d", Depth);
  end

  localparam int unsigned PtrBits = Depth > 1 ? $clog2(Depth) : 1;

  logic [Width-1:0] mem[Depth];
  logic [PtrBits-1:0] rd, wr;
  logic [$clog2(Depth+1)-1:0] count;

  assign full   = count == $bits(count)'(Depth);
  assign empty  = count == 0;
  assign data_o = mem[rd];

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rd    <= '0;
      wr    <= '0;
      count <= '0;
    end else begin
      if (push) begin
        mem[wr] <= data_i;
        wr      <= wr == PtrBits'(Depth - 1) ? '0 : wr + 1'b1;
      end
      if (pop) rd <= rd == PtrBits'(Depth - 1) ? '0 : rd + 1'b1;
      count <= count + $bits(count)'(push) - $bits(count)'(pop);
    end
  end

endmodule
