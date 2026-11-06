# Tool Organization

This page describes the general high level overview of the design structure.
You'll find low level details in the comments and the source code.
 
## Overview

Omnibus has a simple CLI interface specified in `main.py`.  

The main file is `interconnect.py`, which provides `InterconnectBuilder` that takes optional frontend and backend as arguments.
To provide illusion of a single `Interconnect` object with swappable frontend and backend, these arguments specify parents of `Interconnect`, which in turn make the class inherit all their methods.  
This design provides an easy way to add a new frontend or backend - add a new file with a proper interface and specify it as an argument to `InterconnectBuilder`.  

Internal processing is implemented directly in the `Interconnect` class, as there is never a reason to swap it.  

## Frontends
All frontends are put in `frontends/` and must have `Frontend` the class.
They must populate the internal list of components.
They may add new members to `Interconnect`.
In particular, they are allowed, and even expected, to add new methods.

### YAML
Argument name: "yaml".  

This fronted reads the specification from a YAML file specified as an argument and populates the internal representation with error checking.  
It is done with a single `read_yaml(filename)` call.
No other methods are exposed.  

## Internal Processing
The `process()` method is implemented as shorthand for all the steps described below.  

1. All paths from sources to destinations are found and encoded as crossbar configuration.
2. These paths are then picked depending on the address map needs; the rest are discarded.
3. Paths are coalesced into minimal representations for each crossbar - consecutive addresses are grouped together.
4. Parameters are propagated from each port that has them to all neighbors, but not over barriers. This process is repeated until there is nothing more to propagate.
5. ID widths are found, increasing width on each crossbar.
6. New components are inserted on each connection that has two different parameters on its end ports.

## Backends
All backends are put in `backends/` and must have the `Backend` class.
They read the internal list of components and create an appropriate output.  

Generally, they should expose a simple `generate(outdir)` interface, but they are allowed to use different one.  

A backend can accept specification parameters of its own, in `default` and in connections.
It declares them in three places:
- `parse_default` and `parse_connections`: parameter name to parse function, set in its `__init__`.
  `Interconnect` adds the common parameters to them, and frontends warn about parameters found in neither.
- `SCHEMA_EXTENSION`: file name of a JSON Schema fragment next to the backend, or `None`.
  Properties under its `$defs/default` extend `default`, those under `$defs/connection` extend connection parameters.
  The YAML frontend validates specifications against `frontend/spec.schema.yml` with the fragment of the selected backend.
- `port_connection_params`: connection parameters that internal processing copies onto the port each connection starts at, for components that read them from ports.

See `topwrap_pulpplatform` and its `topwrap_pulpplatform.schema.yml` for an example.

### Graphviz
Argument name: "graphviz".  

This backend converts an internal representation into a graphviz graph.
It generates a single `.gv` file and can be configured to display it in browser.
It allows for coloring according to some parameters.

This backend's primary purpose is debugging and visualization.

### Topwrap Pulp Platform
Argument name: "topwrap_pulpplatform".  

This backend converts an internal representation into a Topwrap file and SystemVerilog wrappers.
It expects Pulp Platform modules for operation.   
It requires external commands to be executed to produce a proper output.  
Verilator files are also provided to the set list of files and remove unnecessary warnings.  

New components can be added to it by:
1. creating a new component class deriving from `MappedComponent`, which:
- forwards constructor arguments to `MappedComponents` and specifies the `ip` name,
- creates the `generate_verilog(self, outdir)` method which creates verilog wrappers/modules,
- creates `generate_hierarchy(self, ports, params)`, which populates Topwrap's hierarchy - ports and parameters.
2. populating the registry in `map_components`.
3. possibly adjusting the choice procedure in `map_components`.

In short:
1. It goes through all components that were generated in the internal processing stage, and using some choice function, they are mapped to Verilog components with the help of `registry`.
2. Verilog files are generated.
3. Verilator filelist and waivers are generated.
4. Topwrap hierarchy is generated.
