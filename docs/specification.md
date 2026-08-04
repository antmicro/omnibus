# Omnibus

## Use cases

### Manual interconnect generation

You write the description by hand, run Omnibus and receive a stand-alone interconnect core.

### Automatic interconnect generation (eg. via `topwrap`)

Basing on the project description, `topwrap` generates the interconnect YAML file.
It runs Omnibus internally and integrates its products with the design.

## Concepts

 - Clock domains are defined explicitly
 - Ports are defined explicitly
 - Port roles (manager / subordinate) are defined from the interconnect perspective
 - Crossbars can be defined explicitly
   - If no crossbar is defined, a single one spanning all ports is assumed
 - Connections between all entities can also defined explicitly
   - If a single crossbar is assumed, it is connected to top-level ports automatically
 - Crossbar operating clocks can be either explicit or inferred
 - CDCs are inferred and placed on connections between different clock domains
 - Address map is explicit and is used to infer how switchboxes should work internally
 - All components inside the interconnect operate using the same "native" bus protocol (eg. AXI)

## Abstract interconnect components

These components are intended to be used by Omnibus to build the interconnect according to your description.
You only provide high-level parameters of crossbars in the description.

### Crossbar

 - `N` inputs
 - `M` outputs
 - Adress decoding & routing

### CDC

 - Single port CDC

### Register

 - A 1-deep skid buffer to cut critical paths

### Width upsizer

 - Single port bus width upsizer

### Width downsizer

 - Single port bus width downsizer

### Protocol converter (bridge)

 - AXI -> AHB
 - AXI -> APB (multiple APBs)
 - AHB -> AXI
 - TL-UL
 - Wishbone
 - Avalon
 - etc.

## Interconnect specification

### YAML schema

```
desc_version: {version}          # Version of the specification format used

name: {interconnect_name}        # Optional name of the interconnect
version: {interconnect_version}  # Optional interconnect version

global:
    addr_width: {width}          # Global address width

clocks:                          # Clock domains. If omitted, a single `clk` clock domain is assumed. Each clock domain is also a reset domain
  {clock_name}:                  # Clock name
    frequency: {value}           # Optional. Clock frequency in MHz
    {attribute}: {value}         # Generic clock attribute
    ...

ports:                           # Interconnect ports (interfaces)
  {port_name}:                   # Port name
    type:  {port_type}           # Mandatory. Port (bus) type. Like: "AXI", "AHB", "APB" and so on
    role:  {port_role}           # Mandatory. "manager" or "subordinate"
    clock: {clock_name}          # Mandatory. Clock domain name
    data_width: {width}          # Optional. Bus data width
    group: {group name}          # Port group name for muxed buses like AHB/APB
    {attribute}: {value}         # Generic port/bus attribute
    ...

crossbars:
  {crossbar_name}:               # Name
    clock: {clock_name}          # Optional. Clock domain the crossbar operates in. To be inferred by Omnibus if not provided
    ports:                       # Crossbar ports
      {port_name}:               # Port name
        {attribute}: {value}     # Generic port attribute
        ...
    {attribute}: {value}         # Generic attribute
    ...

connections:
  "{port_spec} -> {port_spec}:   # `port_spec` is either a top-level port name or a crossbar port: `{crossbar_name}.{port_name}`
    "registers": {count}         # Optional. Number of skid buffers on the connection. Default 0
    "cdc": {value}               # Optional. If True treats the connection as a barrier for clock propagation
    "data_width": {value}        # Optional. Force data width of this connection
    {attribute}: {value}         # Generic connection attribute
  ...

address_map:
  {entry_name}:
    from: {port_name(s)}         # Optional. Traffic source port(s). Can be a single port name or a list of port names. When omitted, the dest. port can be accessed from all subordinate ports.
    to:   {port_name}            # Traffic destination port
    base: {base_addr}            # Base address
    size: {window_size}          # Address window size
  ...
```

### Example

For more examples see `examples/`

This is an example of an interconnect for a system comprised of a CPU, memory, UART and I2C.
CPU runs at 1GHz, memory at 100MHz, peripherals at 25MHz.

There are 2 switchboxes.
The first one encapsulates CPU to memory traffic.

```yaml
desc_version: 1.0

name: MyInterconnect
version: 0.85a

clocks:
  clk_bus:
    frequency: 100e6
  clk_cpu:
    frequency: 1GHz
  clk_lpp:
    frequency: 25M

ports:
  axi_cpu:
    type:  AXI4
    clock: clk_cpu
    role:  "subordinate"
  axi_dbg:
    type:  AXI4
    clock: clk_bus
    role:  "subordinate"
  axi_mem:
    type:  AXI4
    clock: clk_bus
    role:  "manager"
  apb_uart:
    type:  APB
    clock: clk_lpp
    role:  "manager"
  apb_i2c:
    type:  APB
    clock: clk_lpp
    role:  "manager"

crossbars:
  sb_cpu:
    clock: clk_bus
    ports:
      cpu:
        role: "subordinate"
      dbg:
        role: "subordinate"
      mem:
        role: "manager"
      lpp:
        role: "manager"
  sb_lpp:    
    clock: clk_lpp
    ports:
      up:
        role: "subordinate"
      uart:
        role: "manager"
      i2c:
        role: "manager"

connections:
  "axi_cpu -> sb_cpu.cpu":
  "axi_dbg -> sb_cpu.dbg":
  "sb_cpu.mem -> axi_mem":
    "registers": 1 # Insert a skid buffer to help timing closure
  "sb_cpu.lpp -> sb_lpp.up":
  "sb_lpp.uart -> apb_uart":
  "sb_lpp.i2c -> apb_i2c":

address_map:
  "memory": # All ports can access axi_mem
    to:    axi_mem
    base:  0x00000000
    size:  0x20000000
  "uart":  # Only CPU can access UART
    from:  axi_cpu
    to:    apb_uart
    base:  0x40000000
    size:  0x00001000
  "i2c":   # Explicitly axi_cpu and axi_dbg can access apb_i2c
    from:  ["axi_cpu", "axi_dbg"]
    to:    apb_i2c
    base:  0x40001000
    size:  0x00001000
```

## Omnibus architecture

 - Main components:

   - Internal representation
     This part will keep the abstract interconnect representation and will
     allow it to be modified during the flow.

   - Frontend(s)
     Responsible for loading interconnect specification. Will parse and
     interpret the YAML spec.

   - Backend(s)
     Serves actual RTL generation. A backend will contain a collection of
     compatible cores (eg. PULP) that can constitute the interconnect. Each core will
     be associated with capabilities description.

## Omnibus flow

 - Sanitize internal interconnect representation. Report warnings, stop on errors.

 - Determine minimal ID width for each manager port.
   - Each N:1 junction on subordinate to manager route adds log2(N) bits
   - Final ID width for a port is max among all routes leading to it

 - Insert AXI to AHB/APB protocol converters
   - Collect AHB/APB master ports belonging to the same group
   - For each group:
     - Check if all of them are connected to a single crossbar. If not, throw an error
     - Throw an error if there are multiple clock domains within the group
     - Insert AXI to AHB/APB conversion component in place of the fanout

 - Propagate clocks
   - Repeat until all ports and components have their clocks assigned:
     - Repeat for each connections until there are none with clock assigned only on one side
       - If a connection has a clock assigned only on one side, propagate it to the other
       - If a connection has both or no clocks assigned, skip it.
     - For each component determine and assign its operating clock from its port clocks (majority voting?)
 - Insert CDCs on all connections which have different clocks on their ends

 - Propagate bus widths (same algorithm as for clock domains)
 - Insert bus width converters on all connections which have different

 - Insert skid buffers (registers) on connections which specify them
 - TODO: What to do with a connection with both CDC, width conv. and skid buffers? How to determine their relative order?
   - Idea: width conversion always on faster clock side

 - Find routes from subordinate to manager ports using address map
   - Construct graph where nodes are ports and edges are connections between them
   - Run breadth-first search for each route from the address map
   - Once a route is found, store it in each component it passes through
   - TODO: Handle multi-path routes in complex systems
 - Assemble address decoder configuration for each crossbar (also in AHB/APB protocol converter)
   - Use ID bits as well for connections carrying traffic from multiple subordinate ports if address maps for the ports differ.

 - Choose and configure IP blocks for components (backend)
 - Write Topwrap project file for the interconnect

## Analyses

With the complete interconnect internal representation Omnibus will be able to provide useful information:

 - Port to port latency
   - With each component having its min/max latency specified it will be possible to calculate top-level port to port latency

 - Throughput bottlenecks
   - Given:
     - Max capacity of each connection in MB/s.
     - A traffic scenario as required throughput in MB/s for each top-level subordinate to manager pair.
   - It will be possible to calculate required throughput at each internal connection and identify bottlenecks.

## Visualization

Omnibus should be able to provide interconnect microarchitecture vizualization showing the following features (not necessarily at the same time):

 - Bus protocols
 - Bus data width
 - Bus ID width
 - Clock domains
 - Traffic congestion (analysis)

## Testbench generation

TODO: Requires choosing bus VIPs

 - Input data:
   - Traffic intensity per each manager port including which addresses to target. Can be multiple entries per one port

 - Output artifacts:
   - Top-level testbench with clock & reset generations and VIP agents connected
     - Should connect monitors on all intermediate internal buses
   - UVM environment
   - UVM sequence for each manager port
   - UVM virtual sequence to orchestrate the test
