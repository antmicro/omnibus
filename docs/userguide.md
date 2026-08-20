# User Guide

Before running any commands, check [installation](./installation.md).  

## Specification

You describe the interconnect to generate in a `yaml` file, according to the [specification](./specification.md).
There are no requirements on the file location or name.

A very simple specification of interconnect: 
```yaml
docs_version: 1.0

name: simple
version: 1.0

default:
  data_width: 64
  clock: clk
  frequency: 10MHz
  protocol: AXI4

ports:
  pin:
    role: "subordinate"
  pout1:
    role: "manager"
    protocol: AXI4Lite
  pout2:
    role: "manager"

address_map:
  pout1:  
    to: pout1
    base: 0x0000_0000
    size: 0x8000_0000
  pout2:  
    to: pout2
    base: 0x8000_0000
    size: 0x8000_0000
```
The file can also be found in [examples/simple.yml](https://github.com/antmicro/omnibus/blob/main/examples/simple.yml).  

Most of the fields are automatically inferred by Omnibus or are taken from the `default`, so you don't need to specify them explicitly. 
The file specifies interconnect with one input port and two output ports, where lower half of address leads to first output, and upper half to second output.  

The ports are described from the perspective of interconnect, so connect the manager device to the subordinate port.  

The interconnect has data width of 64, automatically generated clock `clk` with frequency of 10MHz assigned to all ports and components.
The interconnect mostly uses AXI4 protocol, but `pout1` uses AXI4Lite, Omnibus notices that and inserts protocol converters.  

Currently, you can use Omnibus in two ways - visualization and generation. 

## Visualization

By running
```
omnibus examples/simple.yml -g --colorby protocol
```
The window opens displaying the following interconnect graph:
![](./images/simple_graph.png)

The colors are assigned based on protocol assigned to each port. 
Notice that `pr_conv` (protocol converter) has two ports, each of them uses different protocol.
This visualization is very useful for debugging problems with interconnect structure as it abstracts implementation details.  

## Generation

While pretty to look at, the graph is not very useful. 
Generating final interconnect currently requires [Topwrap](https://github.com/antmicro/topwrap). 

First, run Omnibus:
```
omnibus examples/simple.yml
```
This generates necessary files in `out/`.  
Then, initialize the Topwrap project:
```
topwrap repo init repo out/modules/
topwrap repo parse repo out/src/*sv --log-level=error
```
Before generating with Topwrap, change the file structure slightly:  
```
mv out/simple.yml ./
```
And then
```
topwrap build --design simple.yml --log-level=error
```

You'll find the interconnect in `build/`. 
It contains instantiation of all used components, in this case that is just crossbar. 

## Compilation with Verilator
To fully use this file, clone its dependencies (these and only these dependencies are needed, regardless of interconnect complexity).  
```
git clone https://github.com/pulp-platform/axi
git clone https://github.com/pulp-platform/common_cells
git clone https://github.com/pulp-platform/tech_cells_generic
```
And then verify the output with `verilator`:
```
verilator --lint-only -Wall \
    -Iaxi/include/ -Icommon_cells/include/ \
    out/verilator/general_config.vlt \
    out/verilator/pulp_platform_config.vlt \
    -f out/verilator/pulp_platform_filelist.vc \
    out/src/*sv build/*sv  \
    --top-module simple
```
