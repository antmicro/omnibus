// Copyright (c) 2026 Antmicro
// SPDX-License-Identifier: Apache-2.0

// The AXI4 AVIP master drives the bridge, the AHB AVIP slave answers it, and the scoreboard
// checks what both monitors saw.
class bridge_env extends uvm_env;
  `uvm_component_utils(bridge_env)

  axi4_master_agent axi_agent;
  AhbSlaveAgent ahb_agent;
  axi4_master_agent_config axi_cfg;
  AhbSlaveAgentConfig ahb_cfg;
  bridge_scoreboard sb;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(axi4_master_agent_config)::get(this, "", "axi_cfg", axi_cfg))
      `uvm_fatal("CFG", "no axi_cfg")
    if (!uvm_config_db#(AhbSlaveAgentConfig)::get(this, "", "ahb_cfg", ahb_cfg))
      `uvm_fatal("CFG", "no ahb_cfg")
    axi_agent = axi4_master_agent::type_id::create("axi_agent", this);
    axi_agent.axi4_master_agent_cfg_h = axi_cfg;
    ahb_agent = AhbSlaveAgent::type_id::create("ahb_agent", this);
    ahb_agent.ahbSlaveAgentConfig = ahb_cfg;
    sb = bridge_scoreboard::type_id::create("sb", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    axi4_master_monitor_proxy mon;
    super.connect_phase(phase);
    mon = axi_agent.axi4_master_mon_proxy_h;
    mon.axi4_master_write_address_analysis_port.connect(sb.aw_imp);
    mon.axi4_master_write_data_analysis_port.connect(sb.w_imp);
    mon.axi4_master_write_response_analysis_port.connect(sb.b_imp);
    mon.axi4_master_read_address_analysis_port.connect(sb.ar_imp);
    mon.axi4_master_read_data_analysis_port.connect(sb.r_imp);
    ahb_agent.ahbSlaveMonitorProxy.ahbSlaveAnalysisPort.connect(sb.ahb_imp);
  endfunction
endclass
