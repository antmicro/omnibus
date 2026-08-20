# Interconnect Specification
The input depends on frontend used, below are specifications for available frontends.

## Yaml Syntax Specification

Full examples are provided at the bottom of this file and in [examples](examples.md).

Current version of the specification is `1.0`. 

### Top Level Fields
:::{list-table}
:Top Level Fields:
* - **Field Name**
  - **Required**
  - **Description**
  - **Default**
* - `desc_version`
  - yes
  - version of specification used
  - \-
* - `name`
  - no
  - interconnect name
  - `interconnect`
* - `version`
  - no
  - interconnect version
  - `0`
:::

### Top Level Sections
These sections are explained in detail in their own subsections of this document.

:::{list-table}
:Top Level Sections:
* - **Field Name**
  - **Required**
  - **Description**
* - `global`
  - no
  - interconnect configuration options
* - `default`
  - no
  - default options for parameters
* - `clocks`
  - no
  - clocks used in the interconnect
* - `ports`
  - yes
  - interconnect ports
* - `crossbars`
  - no\*
  - crossbars used 
* - `connections`
  - no\*
  - connections between ports and crossbars
* - `address_map`
  - yes
  - determines which addresses lead to what port
:::
\*`crossbars` and `connections` must either both be defined or both be left for inference

### Global
Global parameters for configuring global interconnect behavior.

None of the fields are required, if they are unspecified then they are set to default value.   
If the `global` field would be empty, it is valid to omit it completely.

:::{list-table}
* - **Field Name**
  - **Description**
  - **Allowed Values**
  - **Default**
* - `addr_width`
  - address width, used in address map and by the components
  - any positive integer
  - `32`
:::

### Default 
Default parameters specify default value for various fields used throughout the specification.  

None of the fields are required, if they are unspecified then they are unset.  
If the `default` field would be empty, it is valid to omit it completely.
For allowed set of values see corresponding fields in other sections.

:::{list-table}
* - **Field Name**
  - **Description**
* - `data_width`
  - data width of interconnect ports
* - `clock`
  - clock name to be used by components and ports
* - `frequency`
  - frequency to be used by clocks
* - `protocol`
  - bus protocol of interconnect ports
:::

#### Backend Specific
##### Pulp Platform Axi
:::{list-table}
* - **Field Name**
  - **Description**
* - `axi_max_reads`
  - max number of reads in axi
:::

### Clocks
Specifies clocks and their frequencies, each clock implies reset domain. 

Each clock is defined as:
```yaml
name:
    frequency: ...
```
where `name` has to be unique clock identifier.
`frequency` can be omitted, in which case it is taken from [Defaults](#Defaults), or set to `n/a` if not available.
Valid values for `frequency` are any positive floating point numbers, they can include suffix `Hz`, `KHz,`, `K`, `MHz`, `M`, `GHz`, or `G`, which scales the value accordingly.

When omitted, one clock with name `clk` and default frequency is created.

### Ports
Interconnect ports, each port has to have unique name.  

:::{list-table}
:Port parameters:
* - **Field Name**
  - **Optional**
  - **Allowed Values**
  - **Description**
* - `role`
  - no
  - 'subordinate' or 'manager'
  - determines port role from the perspective of interconnect
* - `data_width`
  - yes\*
  - any positive integer
  - \-
* - `clock`
  - yes\*
  - any valid clock name, see [Clocks](#Clocks)
  - clock domain of the port
* - `protocol`
  - yes\*
  - one of `axi`, `axilite`, `apb`, `ahb`
  - bus protocol to be used
* - `group`
  - yes
  - any valid name
  - group for muxed buses, NOT SUPPORTED YET
:::
\* optional only if default exists, see [Defaults](#Defaults)

### Crossbars
Interconnect crossbars, each crossbar has to have unique name. 
If crossbar's clock is not specified and no default exists, then the clock will be inferred from the design.

:::{list-table}
:Crossbar parameters:
* - **Field Name**
  - **Optional**
  - **Allowed Values**
  - **Description**
* - `clock`
  - yes
  - any valid clock name, see [Clocks](#Clocks)
  - clock domain of the crossbar
* - `ports`
  - no
  - see below
  - ports of the crossbar
:::

Each port is defined as 
```yaml
name:
    role: ...
```
where `name` has to be unique to the crossbar, while `role` takes either `subordinate` or `manager` as arguments, they specify whether port is subordinate or manager with respect to crossbar.

Crossbars field can be omitted, in such case:
- `connections` field must also be omitted
- one all to all crossbar is generated

### Connections
Interconnect connections between ports and crossbars.  
If `crossbars` field is omitted, this field must be omitted too, otherwise it must be specified.

Each connection is specified as `porta -> portb` in the direction of interconnect subordinate ports to interconnect manager ports (device manager to device subordinate).
If port is top level port (from `ports` field) then its name is taken as is, e.g. `cpu`.
If port is crossbar port then its name is "crossbar.port", e.g. `main.cpu`.  

:::{list-table}
:Connection Parameters:
* - **Field Name**
  - **Optional**
  - **Allowed Values**
  - **Default**
  - **Description**
* - `registers`
  - yes
  - any nonnegative integer
  - `0`
  - number of skid buffers NOT SUPPORTED YET
* - `cdc`
  - yes
  - `True` or `False`
  - `False`
  - whether to treat this connection as clock barier 
* - `data_width`
  - yes
  - any positive integer
  - `False`
  - sets data width of this connection
* - `protocol`
  - yes
  - `True` or `False`
  - `True` on connections to interconnect manager ports, otherwise `False`
  - whether to treat this connection as protocol propagation barrier
:::

#### Backend specific parameters
##### Pulp Platform Axi
:::{list-table}
* - **Field Name**
  - **Optional**
  - **Allowed Values**
  - **Default**
  - **Description**
* - `axi_max_reads`
  - yes
  - any positive integer
  - value from [Defaults](#Defaults) if exists, otherwise `1`
  - number of maximum axi reads
:::

### Address Map
Address map inside interconnect. 
It is specified as a set of entries, each entry is identified by unique name.

:::{list-table}
:Address Map Entry Parameters:
* - **Field Name**
  - **Optional**
  - **Allowed Values**
  - **Default**
  - **Description**
* - `from`
  - yes
  - single port or list of ports
  - all ports
  - source ports for which address map applies NOT SUPPORTED YET
* - `to`
  - no
  - single port
  - \-
  - destination port for which address map applies
* - `base`
  - no
  - any valid nonnegative integer
  - \-
  - base address of address map
* - `size`
  - no
  - any valid nonnegative integer
  - \-
  - size of address map entry
:::

### Full File

```yaml
desc_version: 1.0

name: Interconnect
version: 0.1

#addr width defaults to 32

default:
    data_width: 64
    clock: clka
    frequency: 10MHz
    protocol: AXI4
    axi_max_reads: 1

clocks:
    clka:
        frequency: 10GHz
    clkb:
        frequency: 10e6
    clkc:
        #frequency taken from default

ports:
    porta:
        role: "subordinate"
        #other parameters are taken from their default value
    portb:
        protocol: AXI4Lite
        role: "manager"
        clock: clkb
        data_width: 32

crossbars:
    main:
        #clock taken from default
        porta:
            role: "subordinate"
        portb:
            role: "manager"

connections:
    "porta -> main.porta":
        registers: 1
        axi_max_reads: 2 #overwrites default
        #does NOT have "protocol: True"
    "main.portb -> portb":
        cdc: True 
        #also has "protocol: True", can be overwritten with "protocol: False"


address_map:
    "portb":
        to: portb
        base: 0x0000
        size: 0xFFFF
```
