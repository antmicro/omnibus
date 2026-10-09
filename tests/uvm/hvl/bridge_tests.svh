// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

localparam bit [ADDR_W-1:0] AHB_BASE = 'h2000_0000;
localparam int unsigned AHB_SIZE = 'h4000;
localparam int unsigned MAX_SIZE = $clog2(LANES);  // log2 of the bus width in bytes

localparam int FIXED = axi4_globals_pkg::WRITE_FIXED;
localparam int INCR = axi4_globals_pkg::WRITE_INCR;
localparam int WRAP = axi4_globals_pkg::WRITE_WRAP;

function bit [DATA_W-1:0] rand_data();
  bit [DATA_W-1:0] data;
  for (int i = 0; i < DATA_W; i += 32) data[i+:32] = $urandom();
  return data;
endfunction

// What the AHB subordinate answers every transfer with: random read data and wait states.
class bridge_ahb_slave_seq extends uvm_sequence #(AhbSlaveTransaction);
  `uvm_object_utils(bridge_ahb_slave_seq)

  int unsigned max_wait_states = 3;

  function new(string name = "bridge_ahb_slave_seq");
    super.new(name);
  endfunction

  task body();
    forever begin
      req = AhbSlaveTransaction::type_id::create("req");
      start_item(req);
      req.choosePacketData = 0;
      req.hrdata = {rand_data()};
      req.noOfWaitStates = $urandom_range(max_wait_states);
      req.hresp = AhbGlobalPackage::OKAY;
      finish_item(req);
    end
  endtask
endclass

// One AXI transaction. The result has the read data or the write response.
class bridge_axi_op_seq extends uvm_sequence #(axi4_master_tx);
  `uvm_object_utils(bridge_axi_op_seq)

  bit write;
  bit [ADDR_W-1:0] addr;
  int unsigned len;  // beats - 1
  int unsigned size;
  int unsigned burst;
  int unsigned id;
  int unsigned prot;
  int unsigned cache;  // the VIP knows 0 to 3
  int unsigned waits;  // cycles of the master before it accepts B or R
  bit [DATA_W-1:0] wdata[$];
  bit [LANES-1:0] wstrb[$];

  function new(string name = "bridge_axi_op_seq");
    super.new(name);
  endfunction

  task body();
    axi4_master_tx tx = axi4_master_tx::type_id::create("tx");
    axi4_master_tx rsp;
    start_item(tx);
    tx.no_of_wait_states = waits;
    if (write) begin
      tx.tx_type = axi4_globals_pkg::WRITE;
      tx.transfer_type = axi4_globals_pkg::NON_OUTSTANDING_WRITE;
      tx.awid = axi4_globals_pkg::awid_e'(id);
      tx.awaddr = addr;
      tx.awlen = len;
      tx.awsize = axi4_globals_pkg::awsize_e'(size);
      tx.awburst = axi4_globals_pkg::awburst_e'(burst);
      tx.awlock = axi4_globals_pkg::WRITE_NORMAL_ACCESS;
      tx.awprot = axi4_globals_pkg::awprot_e'(prot);
      tx.awcache = axi4_globals_pkg::awcache_e'(cache);
      tx.wdata = wdata;
      tx.wstrb = wstrb;
    end
    else begin
      tx.tx_type = axi4_globals_pkg::READ;
      tx.transfer_type = axi4_globals_pkg::NON_OUTSTANDING_READ;
      tx.arid = axi4_globals_pkg::arid_e'(id);
      tx.araddr = addr;
      tx.arlen = len;
      tx.arsize = axi4_globals_pkg::arsize_e'(size);
      tx.arburst = axi4_globals_pkg::arburst_e'(burst);
      tx.arlock = axi4_globals_pkg::READ_NORMAL_ACCESS;
      tx.arprot = axi4_globals_pkg::arprot_e'(prot);
      tx.arcache = axi4_globals_pkg::arcache_e'(cache);
    end
    finish_item(tx);
    get_response(rsp, tx.get_transaction_id());
  endtask
endclass

// Writes the master issues back to back, without waiting for the response of one to send the next
class bridge_axi_queued_writes_seq extends uvm_sequence #(axi4_master_tx);
  `uvm_object_utils(bridge_axi_queued_writes_seq)

  bit [ADDR_W-1:0] addr;
  int unsigned count;

  function new(string name = "bridge_axi_queued_writes_seq");
    super.new(name);
  endfunction

  task body();
    axi4_master_tx txs[$];
    // nobody asks for the responses: the scoreboard sees every B
    set_response_queue_error_report_enabled(0);
    repeat (count) begin
      axi4_master_tx tx = axi4_master_tx::type_id::create("tx");
      start_item(tx);
      tx.no_of_wait_states = 0;
      tx.tx_type = axi4_globals_pkg::WRITE;
      tx.transfer_type = axi4_globals_pkg::OUTSTANDING_WRITE;
      tx.awid = axi4_globals_pkg::awid_e'(txs.size());
      tx.awaddr = addr;
      tx.awlen = 0;
      tx.awsize = axi4_globals_pkg::awsize_e'(2);
      tx.awburst = axi4_globals_pkg::WRITE_INCR;
      tx.awlock = axi4_globals_pkg::WRITE_NORMAL_ACCESS;
      tx.wdata = {rand_data()};
      tx.wstrb = {'1 & ((1 << 4) - 1)};
      finish_item(tx);
      txs.push_back(tx);
    end
  endtask
endclass

class bridge_base_test extends uvm_test;
  `uvm_component_utils(bridge_base_test)

  bridge_env env;
  axi4_master_agent_config axi_cfg;
  AhbSlaveAgentConfig ahb_cfg;
  bridge_ahb_slave_seq ahb_seq;
  int fifo_depth = 3;  // of the build, for the tests that depend on it

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    void'($value$plusargs("FIFO_DEPTH=%d", fifo_depth));
    // the longest test takes about 130us, a bridge that deadlocks must fail early
    uvm_root::get().set_timeout(2ms, 1);
    axi_cfg = axi4_master_agent_config::type_id::create("axi_cfg");
    axi_cfg.is_active = UVM_ACTIVE;
    axi_cfg.has_coverage = 1;
    ahb_cfg = AhbSlaveAgentConfig::type_id::create("ahb_cfg");
    ahb_cfg.is_active = UVM_ACTIVE;
    ahb_cfg.hasCoverage = 1;
    // the AHB subordinate answers ERROR outside of this window
    ahb_cfg.minimumAddress = AHB_BASE;
    ahb_cfg.maximumAddress = AHB_BASE + AHB_SIZE - 1;
    uvm_config_db#(axi4_master_agent_config)::set(this, "env", "axi_cfg", axi_cfg);
    uvm_config_db#(AhbSlaveAgentConfig)::set(this, "env", "ahb_cfg", ahb_cfg);
    env = bridge_env::type_id::create("env", this);
    ahb_seq = bridge_ahb_slave_seq::type_id::create("ahb_seq");
    configure();
  endfunction

  // for the tests to change the defaults
  virtual function void configure();
  endfunction

  task run_phase(uvm_phase phase);
    phase.raise_objection(this);
    phase.get_objection().set_drain_time(this, 30 * CLK_PERIOD_NS * 1ns);
    fork
      ahb_seq.start(env.ahb_agent.ahbSlaveSequencer);
    join_none
    #(10 * CLK_PERIOD_NS * 1ns);
    test_body();
    phase.drop_objection(this);
  endtask

  virtual task test_body();
  endtask

  //--------------------------------------------------------------------------------------------
  // Stimulus
  //--------------------------------------------------------------------------------------------

  // WSTRB of a beat: the lanes the beat covers
  function bit [LANES-1:0] beat_strobe(bit [ADDR_W-1:0] addr, int len, int size, int burst, int idx);
    int lo;
    int hi;
    bit [LANES-1:0] strobe = '0;
    env.sb.beat_lanes(env.sb.beat_addr(addr, len, size, burst, idx), size, lo, hi);
    for (int i = lo; i < hi; i++) strobe[i] = 1;
    return strobe;
  endfunction

  task write(bit [ADDR_W-1:0] addr, int size, int burst, int n, int id = 0, int waits = 0,
             int prot = 0, bit random_strobe = 0, bit [LANES-1:0] strobe = '0, bit use_strobe = 0,
             int cache = 0);
    bridge_axi_op_seq seq = bridge_axi_op_seq::type_id::create("wr");
    seq.write = 1;
    seq.addr = addr;
    seq.len = n - 1;
    seq.size = size;
    seq.burst = burst;
    seq.id = id;
    seq.waits = waits;
    seq.prot = prot;
    seq.cache = cache;
    for (int i = 0; i < n; i++) begin
      bit [LANES-1:0] window = beat_strobe(addr, n - 1, size, burst, i);
      seq.wdata.push_back(rand_data());
      if (use_strobe) seq.wstrb.push_back(strobe & window);
      else if (random_strobe) seq.wstrb.push_back($urandom() & window);
      else seq.wstrb.push_back(window);
    end
    seq.start(env.axi_agent.axi4_master_write_seqr_h);
  endtask

  task read(bit [ADDR_W-1:0] addr, int size, int burst, int n, int id = 0, int waits = 0,
            int prot = 0, int cache = 0);
    bridge_axi_op_seq seq = bridge_axi_op_seq::type_id::create("rd");
    seq.write = 0;
    seq.addr = addr;
    seq.len = n - 1;
    seq.size = size;
    seq.burst = burst;
    seq.id = id;
    seq.waits = waits;
    seq.prot = prot;
    seq.cache = cache;
    seq.start(env.axi_agent.axi4_master_read_seqr_h);
  endtask

  task write_read(bit [ADDR_W-1:0] addr, int size, int burst, int n);
    write(addr, size, burst, n);
    read(addr, size, burst, n);
  endtask

  // A legal burst inside [base, base + span)
  function void random_burst(bit [ADDR_W-1:0] base, int span, output bit [ADDR_W-1:0] addr,
                             output int n, output int size, output int burst);
    int nbytes;
    int kind = $urandom_range(4);
    size = $urandom_range(MAX_SIZE);
    nbytes = 1 << size;
    addr = base + $urandom_range(span - 4096);
    case (kind)
      0, 1, 2: burst = INCR;
      3: burst = WRAP;
      default: burst = FIXED;
    endcase
    if (burst == WRAP) begin
      int lens[4] = '{2, 4, 8, 16};
      n = lens[$urandom_range(3)];
      addr = addr / nbytes * nbytes;
    end
    else begin
      n = $urandom_range(1, 16);
      if (burst == INCR) begin
        int left = (4096 - addr % 4096 + nbytes - 1) / nbytes;  // beats before the 4KB boundary
        if (n > left) n = left;
      end
    end
  endfunction

  function int counted_transactions();
    return env.sb.writes_checked + env.sb.reads_checked;
  endfunction
endclass

class bridge_smoke_test extends bridge_base_test;
  `uvm_component_utils(bridge_smoke_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    write_read(AHB_BASE + 'h100, MAX_SIZE, INCR, 1);
  endtask
endclass

// Full-width single beats and short bursts
class bridge_regular_test extends bridge_base_test;
  `uvm_component_utils(bridge_regular_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    repeat (50) begin
      bit [ADDR_W-1:0] addr = AHB_BASE + $urandom_range(AHB_SIZE / LANES - 20) * LANES;
      int n = $urandom_range(1, 8);
      int prot = $urandom_range(7);
      int cache = $urandom_range(3);
      write(addr, MAX_SIZE, INCR, n, .prot(prot), .cache(cache));
      read(addr, MAX_SIZE, INCR, n, .prot(prot), .cache(cache));
    end
  endtask
endclass

// Every size below the bus width on every naturally aligned lane
class bridge_narrow_test extends bridge_base_test;
  `uvm_component_utils(bridge_narrow_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    for (int size = 0; size < MAX_SIZE; size++) begin
      for (int lane = 0; lane < LANES; lane += 1 << size) begin
        write_read(AHB_BASE + 'h100 + lane, size, INCR, 1);
      end
    end
  endtask
endclass

// Start addresses that are not a multiple of the size: the first beat is partial
class bridge_unaligned_test extends bridge_base_test;
  `uvm_component_utils(bridge_unaligned_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    int counts[3] = '{1, 2, 5};
    for (int size = 1; size <= MAX_SIZE; size++) begin
      for (int offset = 1; offset < (1 << size); offset++) begin
        foreach (counts[c]) write_read(AHB_BASE + 'h200 + offset, size, INCR, counts[c]);
      end
    end
  endtask
endclass

// FIXED, WRAP and INCR bursts of every size
class bridge_burst_types_test extends bridge_base_test;
  `uvm_component_utils(bridge_burst_types_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    int kinds[6][2] = '{'{FIXED, 4}, '{INCR, 16}, '{WRAP, 2}, '{WRAP, 4}, '{WRAP, 8}, '{WRAP, 16}};
    for (int size = 0; size <= MAX_SIZE; size++) begin
      int nbytes = 1 << size;
      foreach (kinds[k]) begin
        repeat (3) begin
          int offset = $urandom_range(0, 'h40 / nbytes - 1) * nbytes;
          write_read(AHB_BASE + 'h400 + offset, size, kinds[k][0], kinds[k][1]);
        end
      end
    end
  endtask
endclass

// Sparse and empty WSTRB: only the enabled bytes of a beat are written
class bridge_strobes_test extends bridge_base_test;
  `uvm_component_utils(bridge_strobes_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    repeat (100) begin
      int size = $urandom_range(MAX_SIZE);
      bit [ADDR_W-1:0] addr = AHB_BASE + 'h800 + $urandom_range('h100);
      int n = $urandom_range(1, 4);
      write(addr, size, INCR, n, .random_strobe(1));
    end
    // all strobes empty, and a few that stand out
    write(AHB_BASE + 'h900, MAX_SIZE, INCR, 3, .use_strobe(1), .strobe('0));
    write(AHB_BASE + 'h900, MAX_SIZE, INCR, 2, .use_strobe(1), .strobe(1));
    write(AHB_BASE + 'h900, MAX_SIZE, INCR, 2, .use_strobe(1), .strobe('1 ^ 1));
  endtask
endclass

// IDs of B and R follow the request
class bridge_ids_test extends bridge_base_test;
  `uvm_component_utils(bridge_ids_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    for (int id = 0; id < 16; id++) begin
      write(AHB_BASE + 8 * id, 2, INCR, 1, id);
      read(AHB_BASE + 8 * id, 2, INCR, 1, id);
    end
  endtask
endclass

// Random legal bursts, a writer and a reader at once, backpressure on B and R, wait states on AHB
class bridge_random_test extends bridge_base_test;
  `uvm_component_utils(bridge_random_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void configure();
    ahb_seq.max_wait_states = 4;
  endfunction

  task test_body();
    fork
      repeat (100) begin
        bit [ADDR_W-1:0] addr;
        int n, size, burst;
        random_burst(AHB_BASE, AHB_SIZE, addr, n, size, burst);
        write(addr, size, burst, n, $urandom_range(15), $urandom_range(4), $urandom_range(7), $urandom_range(1), '0, 0, $urandom_range(3));
      end
      repeat (100) begin
        bit [ADDR_W-1:0] addr;
        int n, size, burst;
        random_burst(AHB_BASE, AHB_SIZE, addr, n, size, burst);
        read(addr, size, burst, n, $urandom_range(15), $urandom_range(4), $urandom_range(7), $urandom_range(3));
      end
    join
  endtask
endclass

// An AHB ERROR stops the AHB transfers of a burst: the beats before it complete, the read beats
// from it on and the B of a write are SLVERR, and the next transaction is not affected.
class bridge_error_test extends bridge_base_test;
  `uvm_component_utils(bridge_error_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    bit [ADDR_W-1:0] starts[3] = '{AHB_BASE + AHB_SIZE + 'h1000, AHB_BASE - 2 * LANES,
                                   AHB_BASE + AHB_SIZE - 3 * LANES};
    int counts[3] = '{3, 6, 8};
    foreach (starts[i]) begin
      write(starts[i], MAX_SIZE, INCR, counts[i]);
      read(starts[i], MAX_SIZE, INCR, counts[i]);
      write_read(AHB_BASE, 2, INCR, 1);
    end
    if (env.sb.errors_seen != 6)
      `uvm_error("TEST", $sformatf("%0d transactions ended by an AHB error, expected 6", env.sb.errors_seen))
  endtask
endclass

// A read that is ready while writes keep coming is served in between them
class bridge_arbitration_test extends bridge_base_test;
  `uvm_component_utils(bridge_arbitration_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task test_body();
    bridge_axi_queued_writes_seq writes = bridge_axi_queued_writes_seq::type_id::create("writes");
    int read_position = -1;
    string order = "";
    writes.addr = AHB_BASE + 'h1000;
    writes.count = 12;
    fork
      writes.start(env.axi_agent.axi4_master_write_seqr_h);
      begin
        #(25 * CLK_PERIOD_NS * 1ns);
        read(AHB_BASE + 'h2000, 2, INCR, 1);
      end
    join
    wait (env.sb.writes_checked == writes.count);
    #(5 * CLK_PERIOD_NS * 1ns);
    foreach (env.sb.stats[i]) begin
      order = {order, env.sb.stats[i].write ? "W" : "R"};
      if (!env.sb.stats[i].write) read_position = i;
    end
    `uvm_info("ARBITRATION", $sformatf("served in the order %s", order), UVM_LOW)
    if (read_position < 0 || read_position == env.sb.stats.size() - 1)
      `uvm_error("TEST", $sformatf("the read waited for all the queued writes: %s", order))
  endtask
endclass

// Which AHB bursts an AXI burst turns into
class bridge_shapes_test extends bridge_base_test;
  `uvm_component_utils(bridge_shapes_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void configure();
    ahb_seq.max_wait_states = 0;
  endfunction

  function void expect_shape(string what, int first, AhbGlobalPackage::ahbBurstEnum burst, int seqs);
    txn_stat_t st = env.sb.stats[$];
    if (st.trans.size() != seqs + 1) begin
      `uvm_error("TEST", $sformatf("%s: %0d transfers, expected %0d", what, st.trans.size(), seqs + 1))
      return;
    end
    for (int i = 0; i < st.trans.size(); i++) begin
      AhbGlobalPackage::ahbTransferEnum want = i == first ? AhbGlobalPackage::NONSEQ : AhbGlobalPackage::SEQ;
      if (burst == AhbGlobalPackage::SINGLE) want = AhbGlobalPackage::NONSEQ;
      if (st.trans[i] != want || st.burst[i] != burst)
        `uvm_error("TEST", $sformatf("%s: transfer %0d is %s %s, expected %s %s", what, i, st.trans[i].name(), st.burst[i].name(), want.name(), burst.name()))
    end
  endfunction

  task test_body();
    int wraps[3] = '{4, 8, 16};
    AhbGlobalPackage::ahbBurstEnum wrap_burst[3] = '{AhbGlobalPackage::WRAP4, AhbGlobalPackage::WRAP8,
                                                     AhbGlobalPackage::WRAP16};
    // INCR is one burst, WRAP4, WRAP8 and WRAP16 reads are bursts
    read(AHB_BASE + 'h100, MAX_SIZE, INCR, 8);
    #(5 * CLK_PERIOD_NS * 1ns);
    expect_shape("INCR read", 0, AhbGlobalPackage::INCR, 7);
    foreach (wraps[w]) begin
      read(AHB_BASE + 'h800 + 3 * LANES, MAX_SIZE, WRAP, wraps[w]);
      #(5 * CLK_PERIOD_NS * 1ns);
      expect_shape($sformatf("WRAP%0d read", wraps[w]), 0, wrap_burst[w], wraps[w] - 1);
    end
    // over a 1KB boundary a new burst starts
    read(AHB_BASE + 'h400 - 3 * LANES, MAX_SIZE, INCR, 8);
    #(5 * CLK_PERIOD_NS * 1ns);
    begin
      txn_stat_t st = env.sb.stats[$];
      if (st.trans.size() != 8 || st.trans[3] != AhbGlobalPackage::NONSEQ || st.addr[3] != AHB_BASE + 'h400)
        `uvm_error("TEST", "INCR read over 1KB: no new NONSEQ at the boundary")
    end
    // no AHB equivalent: FIXED, WRAP2
    read(AHB_BASE + 'h900, MAX_SIZE, FIXED, 4);
    #(5 * CLK_PERIOD_NS * 1ns);
    expect_shape("FIXED read", 0, AhbGlobalPackage::SINGLE, 3);
    read(AHB_BASE + 'h900, MAX_SIZE, WRAP, 2);
    #(5 * CLK_PERIOD_NS * 1ns);
    expect_shape("WRAP2 read", 0, AhbGlobalPackage::SINGLE, 1);
    // writes: INCR is a burst, WRAP is not
    write(AHB_BASE + 'hA00, MAX_SIZE, INCR, 8);
    #(5 * CLK_PERIOD_NS * 1ns);
    // a one beat W FIFO cannot hold the next beat in time
    if (fifo_depth >= 2) expect_shape("INCR write", 0, AhbGlobalPackage::INCR, 7);
    write(AHB_BASE + 'hA00, MAX_SIZE, WRAP, 4);
    #(5 * CLK_PERIOD_NS * 1ns);
    expect_shape("WRAP write", 0, AhbGlobalPackage::SINGLE, 3);
  endtask
endclass

// A running read burst waits with BUSY while the R channel is not accepted
class bridge_busy_test extends bridge_base_test;
  `uvm_component_utils(bridge_busy_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void configure();
    ahb_seq.max_wait_states = 0;
  endfunction

  task test_body();
    read(AHB_BASE + 'h100, MAX_SIZE, INCR, 16, .waits(60));
    #(5 * CLK_PERIOD_NS * 1ns);
    if (env.sb.stats[$].busy == 0) `uvm_error("TEST", "no BUSY while the R channel was blocked")
  endtask
endclass

// Aligned full-width INCR bursts with no wait states run at about one beat per cycle
class bridge_throughput_test extends bridge_base_test;
  `uvm_component_utils(bridge_throughput_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void configure();
    ahb_seq.max_wait_states = 0;
  endfunction

  function void report(string what, txn_stat_t st, int limit);
    int cycles = (st.last_time - st.addr_time) / CLK_PERIOD_NS;
    `uvm_info("THROUGHPUT", $sformatf("%s of %0d beats: %0d cycles", what, st.beats, cycles), UVM_LOW)
    if (cycles > limit) `uvm_error("TEST", $sformatf("%s of %0d beats took %0d cycles, the limit is %0d", what, st.beats, cycles, limit))
  endfunction

  task test_body();
    int n = 16;
    read(AHB_BASE, MAX_SIZE, INCR, n);
    #(5 * CLK_PERIOD_NS * 1ns);
    // a read beat is issued 3 cycles before it can be taken off the FIFO
    if (fifo_depth >= 3) report("read", env.sb.stats[$], n + 8);
    else if (fifo_depth == 2) report("read", env.sb.stats[$], 3 * n / 2 + 8);
    write(AHB_BASE, MAX_SIZE, INCR, n);
    #(5 * CLK_PERIOD_NS * 1ns);
    if (fifo_depth >= 2) report("write", env.sb.stats[$], n + 12);
  endtask
endclass
