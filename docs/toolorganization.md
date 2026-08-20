# Tool Organization

This page describes general high level overview of design structure.
You'll find low level details in the comments and the source code.
 
## Overview

Omnibus has simple CLI interface specified in `main.py`.  

The main file is `interconnect.py` which provides `InterconnectBuilder` that takes optional frontend and backend as arguments.
To provide illusion of single `Interconnect` object with swappable frontend and backend, these arguments specify parents of `Interconnect`, which in turn make the class inherit all their methods.  
This design provides easy way to add new frontend or backend - add new file with proper interface and specify it as argument to `InterconnectBuilder`.  

Internal processing is implemented directly in `Interconnect` class as there is never a reason to swap it.  

## Frontends
All frontends are put in `frontends/` and must have class `Frontend`.
They must populate internal list of components.
They may add new members to `Interconnect`.
In particular they are allowed, and even expected, to add new methods.

### YAML
Argument name: "yaml".  

This fronted reads specification from yaml file specified as argument and populates internal representation with error checking.  
It is done with single `read_yaml(filename)` call, no other methods are exposed.  

## Internal Processing
Method `process()` is implemented as shorthand for all steps described below.  

1. All paths from sources to destinations are found and encoded as crossbar configuration
2. These paths are then picked depending on address map needs, the rest are discarded  
3. Paths are coalesced into minimal representation for each crossbar - consecutive addresses are grouped together
4. Parameters are propagated from each port that has them to all neighbors but not over barriers, this process is repeated until there is nothing more to propagate
5. ID widths are found, increasing width on each crossbar 
6. New components are inserted on each connection that has two different parameters on its end ports 

## Backends
All backends are put in `backends/` and must have class `Backend`.
They read internal list of components and create appropriate output.  

Generally, they should expose simple `generate(outdir)` interface, but they are allowed to use different one.  

### Graphviz
Argument name: "graphviz".  

This backend converts internal representation into graphviz graph, it generates single `.gv` file and can be configured to display it in browser.
It allows for coloring according to some parameters.  

This backend primary purpose is debugging and visualization.  

### Topwrap Pulp Platform
Argument name: "topwrap_pulpplatform".  

This backend converts internal representation into Topwrap's file and systemverilog wrappers, it expects Pulp Platform modules for operation.   
It requires external commands to be executed to produce proper output.  
Verilator files are also provided to set list of files and remove unnecessary warnings.  

New components can be added to it by 
1. creating new component class deriving from `MappedComponent` which 
- forwards constructor arguments to `MappedComponents` and specifies `ip` name 
- creates `generate_verilog(self, outdir)` method which creates verilog wrappers/modules
- creates `generate_hierarchy(self, ports, params)` which populates Topwrap's hierarchy - ports and parameters
2. populating registry in `map_components`
3. possibly adjusting choice procedure in `map_components`

In short
1. It goes through all components that were generated in internal processing stage, and using some choice function, they are mapped to verilog components with the help of `registry`
2. Verilog files are generated
3. Verilator filelist and waivers are generated
4. Topwrap hierarchy is generated
