// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

`uvm_analysis_imp_decl(_aw)
`uvm_analysis_imp_decl(_w)
`uvm_analysis_imp_decl(_b)
`uvm_analysis_imp_decl(_ar)
`uvm_analysis_imp_decl(_r)
`uvm_analysis_imp_decl(_ahb)

typedef struct {
  int start;  // first byte lane
  int log;  // log2 of the size in bytes
} chunk_t;

// What happened to one AXI transaction, for the tests that look at timing and shapes.
class txn_stat_t;
  bit write;
  int beats;
  longint addr_time;  // ns, address handshake
  longint first_ahb_time;  // ns, first transfer finished on AHB
  longint last_time;  // ns, last R beat or B
  int transfers;  // NONSEQ and SEQ transfers
  int busy;  // BUSY cycles
  bit error;  // an AHB ERROR ended the transaction
  AhbGlobalPackage::ahbTransferEnum trans[$];
  AhbGlobalPackage::ahbBurstEnum burst[$];
  bit [ADDR_W-1:0] addr[$];
endclass

// Checks the AXI transactions against what the AHB side saw, with a model of the conversion:
// - the AXI address rules say which byte lanes every beat covers,
// - each beat becomes naturally aligned AHB transfers, the largest chunk that starts at the
//   first lane the beat transfers (for writes: has WSTRB set) and fits, until none is left,
// - only beats that are a single transfer of the full beat size may be part of an AHB burst:
//   INCR beats of INCR bursts as HBURST=INCR, reads of WRAP of 4, 8 or 16 beats as WRAP4/8/16,
// - an AHB ERROR ends the AHB side of the transaction: the read beats from the failing one on
//   and the B are SLVERR, the transfers and write data after it do not happen.
// The bridge serves one transaction at a time in the order of the AW and AR handshakes.
class bridge_scoreboard extends uvm_component;
  `uvm_component_utils(bridge_scoreboard)

  uvm_analysis_imp_aw #(axi4_master_tx, bridge_scoreboard) aw_imp;
  uvm_analysis_imp_w #(axi4_master_tx, bridge_scoreboard) w_imp;
  uvm_analysis_imp_b #(axi4_master_tx, bridge_scoreboard) b_imp;
  uvm_analysis_imp_ar #(axi4_master_tx, bridge_scoreboard) ar_imp;
  uvm_analysis_imp_r #(axi4_master_tx, bridge_scoreboard) r_imp;
  uvm_analysis_imp_ahb #(AhbSlaveTransaction, bridge_scoreboard) ahb_imp;

  // what the monitors have seen and the checks have not used yet, with the time ($time, in ns:
  // the unit of the build is 1ns) the monitor reported it
  axi4_master_tx order_q[$];  // AW and AR handshakes in order
  bit order_write_q[$];
  longint order_time_q[$];
  axi4_master_tx w_q[$];
  axi4_master_tx b_q[$];
  longint b_time_q[$];
  axi4_master_tx r_q[$];
  longint r_time_q[$];
  AhbSlaveTransaction ahb_q[$];
  longint ahb_time_q[$];
  event new_item;

  txn_stat_t stats[$];
  int writes_checked;
  int reads_checked;
  int errors_seen;  // transactions ended by an AHB ERROR

  function new(string name, uvm_component parent);
    super.new(name, parent);
    aw_imp = new("aw_imp", this);
    w_imp = new("w_imp", this);
    b_imp = new("b_imp", this);
    ar_imp = new("ar_imp", this);
    r_imp = new("r_imp", this);
    ahb_imp = new("ahb_imp", this);
  endfunction

  function void write_aw(axi4_master_tx t);
    order_q.push_back(t);
    order_write_q.push_back(1);
    order_time_q.push_back($time);
    -> new_item;
  endfunction

  function void write_ar(axi4_master_tx t);
    order_q.push_back(t);
    order_write_q.push_back(0);
    order_time_q.push_back($time);
    -> new_item;
  endfunction

  function void write_w(axi4_master_tx t);
    w_q.push_back(t);
    -> new_item;
  endfunction

  function void write_b(axi4_master_tx t);
    b_q.push_back(t);
    b_time_q.push_back($time);
    -> new_item;
  endfunction

  function void write_r(axi4_master_tx t);
    r_q.push_back(t);
    r_time_q.push_back($time);
    -> new_item;
  endfunction

  function void write_ahb(AhbSlaveTransaction t);
    ahb_q.push_back(t);
    ahb_time_q.push_back($time);
    -> new_item;
  endfunction

  //----------------------------------------------------------------------------------------
  // Model of the conversion
  //----------------------------------------------------------------------------------------

  // Address of beat `idx` of an AXI burst
  function longint beat_addr(longint addr0, int len, int size, int burst, int idx);
    longint a = addr0;
    longint nbytes = 1 << size;
    longint total = nbytes * (len + 1);
    longint aligned;
    longint low;
    for (int k = 0; k < idx; k++) begin
      aligned = a / nbytes * nbytes;
      case (burst)
        axi4_globals_pkg::WRITE_FIXED: a = a;
        axi4_globals_pkg::WRITE_WRAP: begin
          low = a / total * total;
          a = aligned + nbytes;
          if (a == low + total) a = low;
        end
        default: a = aligned + nbytes;
      endcase
    end
    return a;
  endfunction

  // Byte lanes [lo, hi) of the bus word that beat `idx` covers
  function void beat_lanes(longint addr, int size, output int lo, output int hi);
    longint nbytes = 1 << size;
    lo = addr % LANES;
    hi = (lo / nbytes) * nbytes + nbytes;
  endfunction

  // The AHB transfers of a beat: the lanes [lo, hi) that are enabled in `en`
  function void split_beat(int lo, int hi, bit [LANES-1:0] en, ref chunk_t chunks[$]);
    int ptr = lo;
    int start;
    int best;
    bit all_enabled;
    chunks.delete();
    forever begin
      start = -1;
      for (int i = ptr; i < hi; i++) begin
        if (en[i]) begin
          start = i;
          break;
        end
      end
      if (start < 0) break;
      best = 0;
      for (int s = 1; (1 << s) <= LANES; s++) begin
        if (start % (1 << s) == 0 && start + (1 << s) <= hi) begin
          all_enabled = 1;
          for (int j = start; j < start + (1 << s); j++) if (!en[j]) all_enabled = 0;
          if (all_enabled) best = s;
        end
      end
      chunks.push_back('{start, best});
      ptr = start + (1 << best);
    end
  endfunction

  // Whether the chunks of a beat make it one transfer of the full beat size
  function bit single_transfer(chunk_t chunks[$], int lo, int size);
    return chunks.size() == 1 && chunks[0].start == lo && chunks[0].log == size;
  endfunction

  // Whether (htrans, hburst) is allowed for a transfer of an AXI burst
  function bit shape_allowed(bit write, int burst, int len, bit single, AhbSlaveTransaction t);
    AhbGlobalPackage::ahbBurstEnum wrap_burst = AhbGlobalPackage::SINGLE;
    if (t.htrans == AhbGlobalPackage::NONSEQ && t.hburst == AhbGlobalPackage::SINGLE) return 1;
    if (!single) return 0;
    if (burst == axi4_globals_pkg::WRITE_INCR && len > 0)
      return t.hburst == AhbGlobalPackage::INCR;
    if (burst == axi4_globals_pkg::WRITE_WRAP && !write) begin
      case (len)
        3: wrap_burst = AhbGlobalPackage::WRAP4;
        7: wrap_burst = AhbGlobalPackage::WRAP8;
        15: wrap_burst = AhbGlobalPackage::WRAP16;
        default: return 0;
      endcase
      return t.hburst == wrap_burst;
    end
    return 0;
  endfunction

  //----------------------------------------------------------------------------------------
  // Getting what the monitors saw
  //----------------------------------------------------------------------------------------
  task next_ahb(output AhbSlaveTransaction t, output longint time_ns);
    while (ahb_q.size() == 0) @(new_item);
    t = ahb_q.pop_front();
    time_ns = ahb_time_q.pop_front();
  endtask

  task next_w(output axi4_master_tx t);
    while (w_q.size() == 0) @(new_item);
    t = w_q.pop_front();
  endtask

  task next_b(output axi4_master_tx t, output longint time_ns);
    while (b_q.size() == 0) @(new_item);
    t = b_q.pop_front();
    time_ns = b_time_q.pop_front();
  endtask

  task next_r(output axi4_master_tx t, output longint time_ns);
    while (r_q.size() == 0) @(new_item);
    t = r_q.pop_front();
    time_ns = r_time_q.pop_front();
  endtask

  // The next NONSEQ or SEQ transfer, the BUSY cycles before it are counted
  task next_transfer(txn_stat_t st, output AhbSlaveTransaction t, output longint time_ns);
    forever begin
      next_ahb(t, time_ns);
      if (t.htrans != AhbGlobalPackage::BUSY) break;
      st.busy++;
    end
  endtask

  //----------------------------------------------------------------------------------------
  // Checks of one transaction
  //----------------------------------------------------------------------------------------
  function bit [3:0] expected_hprot(bit [3:0] cache, bit [2:0] prot);
    return {cache[1:0], prot[0], ~prot[2]};
  endfunction

  // Common checks of one AHB transfer against the expected chunk
  function void check_transfer(AhbSlaveTransaction t, bit write, longint word, chunk_t c,
                               bit [3:0] hprot, string what);
    longint addr = word + c.start;
    if (t.htrans != AhbGlobalPackage::NONSEQ && t.htrans != AhbGlobalPackage::SEQ)
      `uvm_error("SB", $sformatf("%s: htrans %s", what, t.htrans.name()))
    if ((t.hwrite == AhbGlobalPackage::WRITE) != write)
      `uvm_error("SB", $sformatf("%s: hwrite %s", what, t.hwrite.name()))
    if (t.haddr != addr)
      `uvm_error("SB", $sformatf("%s: haddr %h, expected %h", what, t.haddr, addr))
    if (t.hsize != AhbGlobalPackage::ahbHsizeEnum'(c.log))
      `uvm_error("SB", $sformatf("%s: hsize %s, expected %0d bytes", what, t.hsize.name(), 1 << c.log))
    if (t.hmastlock)
      `uvm_error("SB", $sformatf("%s: hmastlock set", what))
    if (t.hprot != AhbGlobalPackage::ahbProtectionEnum'(hprot))
      `uvm_error("SB", $sformatf("%s: hprot %h, expected %h", what, t.hprot, hprot))
  endfunction

  task check_write(axi4_master_tx aw, longint addr_time);
    int n = aw.awlen + 1;
    int size = aw.awsize;
    axi4_master_tx wb[$];
    axi4_master_tx w;
    axi4_master_tx b;
    AhbSlaveTransaction t;
    chunk_t chunks[$];
    txn_stat_t st = new();
    longint addr;
    longint word;
    longint time_ns;
    longint b_time;
    int lo;
    int hi;
    bit [3:0] hprot = expected_hprot(aw.awcache, aw.awprot);
    bit error = 0;
    bit single;
    string what;

    st.write = 1;
    st.beats = n;
    st.addr_time = addr_time;
    for (int i = 0; i < n; i++) begin
      next_w(w);
      wb.push_back(w);
      if (w.wlast != (i == n - 1))
        `uvm_error("SB", $sformatf("write %h: wlast %0b on beat %0d of %0d", aw.awaddr, w.wlast, i, n))
    end

    for (int i = 0; i < n && !error; i++) begin
      addr = beat_addr(aw.awaddr, aw.awlen, size, aw.awburst, i);
      beat_lanes(addr, size, lo, hi);
      word = addr - addr % LANES;
      split_beat(lo, hi, wb[i].wstrb[0], chunks);
      single = single_transfer(chunks, lo, size);
      foreach (chunks[c]) begin
        what = $sformatf("write %h beat %0d transfer %0d", aw.awaddr, i, c);
        next_transfer(st, t, time_ns);
        if (st.transfers == 0) st.first_ahb_time = time_ns;
        st.transfers++;
        st.trans.push_back(t.htrans);
        st.burst.push_back(t.hburst);
        st.addr.push_back(t.haddr);
        check_transfer(t, 1, word, chunks[c], hprot, what);
        if (!shape_allowed(1, aw.awburst, aw.awlen, single, t))
          `uvm_error("SB", $sformatf("%s: %s %s is not allowed here", what, t.htrans.name(), t.hburst.name()))
        for (int j = 0; j < (1 << chunks[c].log); j++) begin
          int lane = chunks[c].start + j;
          if (t.hwdata[0][8*lane+:8] != wb[i].wdata[0][8*lane+:8])
            `uvm_error("SB", $sformatf("%s: lane %0d is %h, AXI wrote %h", what, lane, t.hwdata[0][8*lane+:8], wb[i].wdata[0][8*lane+:8]))
        end
        if (t.hresp == AhbGlobalPackage::ERROR) begin
          error = 1;
          break;
        end
      end
    end

    next_b(b, b_time);
    if (st.busy != 0) `uvm_error("SB", $sformatf("write %h: %0d BUSY cycles", aw.awaddr, st.busy))
    if (int'(b.bid) != int'(aw.awid))
      `uvm_error("SB", $sformatf("write %h: bid %0d, expected %0d", aw.awaddr, b.bid, aw.awid))
    if (b.bresp != (error ? axi4_globals_pkg::WRITE_SLVERR : axi4_globals_pkg::WRITE_OKAY))
      `uvm_error("SB", $sformatf("write %h: bresp %s, AHB error %0b", aw.awaddr, b.bresp.name(), error))
    st.error = error;
    st.last_time = b_time;
    stats.push_back(st);
    errors_seen += error;
    writes_checked++;
  endtask

  task check_read(axi4_master_tx ar, longint addr_time);
    int n = ar.arlen + 1;
    int size = ar.arsize;
    axi4_master_tx r;
    AhbSlaveTransaction t;
    chunk_t chunks[$];
    txn_stat_t st = new();
    longint addr;
    longint word;
    longint time_ns;
    longint r_time;
    int lo[$];
    int hi[$];
    bit [DATA_W-1:0] data[$];
    int good = n;  // beats before the one an AHB ERROR hit
    bit [3:0] hprot = expected_hprot(ar.arcache, ar.arprot);
    bit single;
    bit [DATA_W-1:0] beat_data;
    string what;
    int l;
    int h;

    st.write = 0;
    st.beats = n;
    st.addr_time = addr_time;

    for (int i = 0; i < n && good == n; i++) begin
      addr = beat_addr(ar.araddr, ar.arlen, size, ar.arburst, i);
      beat_lanes(addr, size, l, h);
      lo.push_back(l);
      hi.push_back(h);
      word = addr - addr % LANES;
      split_beat(l, h, '1, chunks);
      single = single_transfer(chunks, l, size);
      beat_data = '0;
      foreach (chunks[c]) begin
        what = $sformatf("read %h beat %0d transfer %0d", ar.araddr, i, c);
        next_transfer(st, t, time_ns);
        if (st.transfers == 0) st.first_ahb_time = time_ns;
        st.transfers++;
        st.trans.push_back(t.htrans);
        st.burst.push_back(t.hburst);
        st.addr.push_back(t.haddr);
        check_transfer(t, 0, word, chunks[c], hprot, what);
        if (!shape_allowed(0, ar.arburst, ar.arlen, single, t))
          `uvm_error("SB", $sformatf("%s: %s %s is not allowed here", what, t.htrans.name(), t.hburst.name()))
        if (t.hresp == AhbGlobalPackage::ERROR) begin
          good = i;
          break;
        end
        for (int j = 0; j < (1 << chunks[c].log); j++) begin
          int lane = chunks[c].start + j;
          beat_data[8*lane+:8] = t.hrdata[0][8*lane+:8];
        end
      end
      data.push_back(beat_data);
    end

    // the beats from the failing one on have no AHB transfers, so their lanes are not known
    for (int i = lo.size(); i < n; i++) begin
      addr = beat_addr(ar.araddr, ar.arlen, size, ar.arburst, i);
      beat_lanes(addr, size, l, h);
      lo.push_back(l);
      hi.push_back(h);
    end

    for (int i = 0; i < n; i++) begin
      next_r(r, r_time);
      what = $sformatf("read %h beat %0d", ar.araddr, i);
      if (int'(r.rid) != int'(ar.arid)) `uvm_error("SB", $sformatf("%s: rid %0d, expected %0d", what, r.rid, ar.arid))
      if (r.rlast != (i == n - 1)) `uvm_error("SB", $sformatf("%s: rlast %0b", what, r.rlast))
      if (i >= good) begin
        if (r.rresp != axi4_globals_pkg::READ_SLVERR)
          `uvm_error("SB", $sformatf("%s: rresp %s after an AHB error", what, r.rresp.name()))
      end
      else begin
        if (r.rresp != axi4_globals_pkg::READ_OKAY)
          `uvm_error("SB", $sformatf("%s: rresp %s", what, r.rresp.name()))
        for (int lane = lo[i]; lane < hi[i]; lane++) begin
          if (r.rdata[0][8*lane+:8] != data[i][8*lane+:8])
            `uvm_error("SB", $sformatf("%s: lane %0d is %h, AHB returned %h", what, lane, r.rdata[0][8*lane+:8], data[i][8*lane+:8]))
        end
      end
    end

    st.error = good < n;
    st.last_time = r_time;
    stats.push_back(st);
    errors_seen += st.error;
    reads_checked++;
  endtask

  task run_phase(uvm_phase phase);
    axi4_master_tx tx;
    bit write;
    longint time_ns;
    forever begin
      while (order_q.size() == 0) @(new_item);
      tx = order_q.pop_front();
      write = order_write_q.pop_front();
      time_ns = order_time_q.pop_front();
      if (write) check_write(tx, time_ns);
      else check_read(tx, time_ns);
    end
  endtask

  function void check_phase(uvm_phase phase);
    super.check_phase(phase);
    if (order_q.size() != 0) `uvm_error("SB", $sformatf("%0d transactions were not checked", order_q.size()))
    if (ahb_q.size() != 0) `uvm_error("SB", $sformatf("%0d AHB items nobody expected", ahb_q.size()))
    if (w_q.size() != 0) `uvm_error("SB", $sformatf("%0d W beats nobody expected", w_q.size()))
    if (b_q.size() != 0) `uvm_error("SB", $sformatf("%0d B responses nobody expected", b_q.size()))
    if (r_q.size() != 0) `uvm_error("SB", $sformatf("%0d R beats nobody expected", r_q.size()))
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("SB", $sformatf("checked %0d writes and %0d reads, %0d ended by an AHB error", writes_checked, reads_checked, errors_seen), UVM_LOW)
  endfunction
endclass
