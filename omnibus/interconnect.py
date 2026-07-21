import yaml
import graphviz
import copy
import sys
import importlib.resources
import tempfile


class Path:
    def __init__(self, start):
        self.curport   = start
        self.startport = start
        self.crossbars = dict() 


class Edge:
    def __init__(self, dest, attributes):
        self.dest       = dest
        self.attributes = attributes

class Port:
    def __init__(self, parent, attributes):
        self.parent     = parent
        self.attributes = attributes
        self.edges      = list()
        self.backedges  = list()


class AddressMapEntry:
    def __init__(self, src, dest, base, size):
        self.src  = src
        self.dest = dest
        self.base = base
        self.size = size

class Component:
    def __init__(self, kind, attributes):
        self.kind       = kind
        self.attributes = attributes
        self.ports      = list()

        self.address_map = list()


class Interconnect:


    def __init__(self, filename):
        stream = open(filename, 'r')
        self.spec = yaml.load(stream, yaml.Loader)

        # check for mandatory top level fields before any processing
        err = False
        if not self.spec.get('ports'):
            print("ERROR: lack of 'ports' field")
            err = True
        if bool(self.spec.get('crossbars')) ^ bool(self.spec.get('connections')):
            print("ERROR: 'crossbar' and 'connections' must be both either defined or left for inference")
            err = True
        if not self.spec.get('address_map'):
            print("ERROR: lack of 'address_map' field")
            err = True
        if err:
            return

        # process optional top level fields
        if self.spec.get('name'):
            self.name = self.spec['name']
        else:
            self.name = 'interconnect'

        if self.spec.get('version'):
            self.version = self.spec['version']
        else:
            self.version = '0'
        
        if self.spec.get('clocks'):
            self.clocks = self.spec['clocks']
        else:
            self.clocks = dict([('clk', dict([('frequency', 'n/a')]))])

        # process mandatory top level fields
        self.ports      = dict()
        self.components = dict()

        # collects start points for later
        # also will be used for address map generation
        self.path_start_points = list()

        for k, v in self.spec['ports'].items():
            self.ports[k] = Port(None, v)

            if v['role'] == 'subordinate':
                self.path_start_points.append(k)
            elif v['role'] == 'manager':
                pass
            else:
                print(f"ERROR: entry '{k}' in ports has wrong role, should be either 'manager' or 'subordinate'")
                return

        #if not present, generate all to all
        if not self.spec.get('crossbars'):
            self.spec['crossbars'] = {'main': {'clock': None, 'ports': dict()}}
            self.spec['connections'] = dict()

            xb_ports = self.spec['crossbars']['main']['ports']
            
            for portname, port in self.ports.items():
                role = port.attributes['role']
                xb_ports[portname] = {'role': role}

                if role == 'subordinate':
                    self.spec['connections'][f"{portname} -> main.{portname}"] = {}
                else:
                    self.spec['connections'][f"main.{portname} -> {portname}"] = {}
                        
        for crossbar, cpars in self.spec['crossbars'].items():
            #store which ports are subs and which are managers, later use this info to create edges
            subs     = list()
            managers = list()

            if not cpars.get('ports'):
                print(f"ERROR: crossbar '{crossbar}' does not have 'ports' field")
                return 

            self.components[crossbar] = Component('crossbar', cpars)

            clock = cpars.get('clock')

            for k, v in cpars['ports'].items():
                name = crossbar + '_' + k
                self.ports[name] = Port(crossbar, v)
                self.ports[name].attributes['clock'] = clock

                self.components[crossbar].ports.append(name)

                if not v.get('role'):
                    print(f"ERROR: crossbar '{crossbar}'s port '{k}' lacks field 'role'")
                    return

                if v['role'] == "subordinate":
                    subs.append(name)
                elif v['role'] == "manager":
                    managers.append(name)
                else:
                    print(f"ERROR: crossbar '{crossbar}'s port '{k}'s field 'role' should be set either to 'master' or to 'subordinate', was instead set to '{v['role']}'")
           
            for sub in subs: 
                subport = self.ports[sub]

                for manager in managers:
                    subport.edges.append(Edge(manager, dict()))
                    self.ports[manager].backedges.append(Edge(sub, dict()))

        for conn, params in self.spec['connections'].items():
            parts = conn.split(' ')

            if len(parts) != 3 or parts[1] != '->':
                print("ERROR: entry in 'connections' '{conn}' invalid: expected format 'a -> b'")
                return

            parts[0] = parts[0].replace('.','_')
            parts[2] = parts[2].replace('.','_')

            port1 = self.ports.get(parts[0])
            port2 = self.ports.get(parts[2])

            if not port1:
                print(f"ERROR: entry in 'connections' '{conn}' invalid: first port does not exist")
                return
            if not port2:
                print(f"ERROR: entry in 'connections' '{conn}' invalid: second port does not exist")
                return

            
            if params is None:
                params = dict()

            #by default, protocol should not be propagated from subordinates 
            if not params.get('protocol') and port2.parent is None:
                params['protocol'] = True

            port1.edges.append(Edge(parts[2], params))
            port2.backedges.append(Edge(parts[0], params))

        self.address_map = self.spec['address_map']

    def find_routing_paths(self):
        self.paths_to_search = list()
        self.paths_complete  = dict()
        for port in self.path_start_points:
            self.paths_to_search.append(Path(port))

        while len(self.paths_to_search) > 0:
            curpath = self.paths_to_search[0]
            self.paths_to_search.pop(0)

            curport = self.ports[curpath.curport]

            if curport.attributes['role'] == 'manager':
                #on toplevel, search is complete
                #on crossbar, expand address map
                if curport.parent is None:
                    #curport used above is Port object, while endport should be string identifier
                    self.paths_complete[curpath.startport + ' -> ' + curpath.curport] = curpath.crossbars
                    continue
                
                #again, we need string not object 
                curpath.crossbars[curport.parent] = curpath.curport 

            # for each outgoing node create new path
            for destport in curport.edges:
                newpath = copy.deepcopy(curpath)
                newpath.curport = destport.dest
                self.paths_to_search.append(newpath)
        
        # generate address maps here
        for k, v in self.address_map.items():
            sources = v.get('from')
            if sources is None:
                sources = self.path_start_points

            #fix the case where single port is provided which is parsed as string and not array of strings
            if type(sources) is str:
                sources = [sources]

            dest = v['to']
            base = v['base']
            size = v['size']

            for source in sources:
                for crossbar, port in self.paths_complete[source + ' -> ' + dest].items():
                    self.components[crossbar].address_map.append(AddressMapEntry(source, port, base, size))

        #now sort each address map by (source, dest port, base) in that order
        #after that, check whether one entry is followed directly by another
        #if so, merge them 
        for comp, params in self.components.items():
            if params.kind != 'crossbar':
                continue

            params.address_map = sorted(params.address_map, key=lambda x: (x.src, x.dest, x.base))

            ii = 0
            while ii < len(params.address_map) - 1:
                cur = params.address_map[ii]
                nxt = params.address_map[ii + 1]
                
                if( 
                    cur.src  == nxt.src  and 
                    cur.dest == nxt.dest and 
                    nxt.base == cur.base + cur.size
                  ):
                    cur.size = cur.size + nxt.size
                    params.address_map.pop(ii + 1)
                    continue

                ii = ii + 1

            #for now, it is not possible to have address map entries with different source IDs 
            #if two rules match in all but first name, merge them, otherwise throw an error
            #there should be check to ensure address map has indeed entries for each source->dest pair, but assume this is the case for now 
            params.address_map = sorted(params.address_map, key=lambda x: (x.dest, x.src))

            ii = 0
            while ii < len(params.address_map) - 1:
                cur = params.address_map[ii]
                nxt = params.address_map[ii + 1]
                
                if cur.dest == nxt.dest:

                    if cur.base == nxt.base and cur.size == nxt.size:
                        params.address_map.pop(ii + 1)
                    else:
                        print(f"ERROR: it is not possible yet to have address map rules that are different based on source id, rule to {cur.dest} has different paths from {cur.src} and {nxt.src}")
                        params.address_map.pop(ii + 1)

                    continue

                ii = ii + 1

            for entry in params.address_map:
                entry.src = '_'


    def propagate_parameters(self):
        #data width is a bit special in that it can be forced on connections
        #to deal with this:
        # 1. find all connections that have it forced 
        # 2. assign it to connected ports
        # 3. if this process leads to conflict, there exists no valid configuration

        for portname, port in self.ports.items():
            for edge in port.edges:
                destname = edge.dest
                dest = self.ports[destname]

                data_width = edge.attributes.get('data_width')

                if data_width is None:
                    continue
                
                port_width = port.attributes.get('data_width')
                dest_width = dest.attributes.get('data_width')

                if port_width != data_width:
                    print(f"ERROR: no valid configuration exists for data width, port {portname} has assigned data width that is different than its outgoing connection to {destname}")

                    continue
                if dest_width != data_width:
                    print(f"ERROR: no valid configuration exists for data width, port {destname} has assigned data width that is different than its incoming connection from {portname}")

                    continue

                port.attributes['data_width'] = data_width
                dest.attributes['data_width'] = data_width

        ports_to_process = list()

        for attr, barrier in {('clock', 'cdc'), ('type', 'protocol'), ('data_width', None)}:

            for portname, port in self.ports.items():
                if port.attributes.get(attr):
                    ports_to_process.append(portname)


            if len(ports_to_process) == 0:
                print(f"WARNING: parameter {attr} is never specified, propagation not possible")
                continue

            while len(ports_to_process) > 0:
                portname = ports_to_process[0]
                ports_to_process.pop(0)

                port = self.ports[portname]

                for edge in port.edges + port.backedges: 
                    destname = edge.dest 
                    dest = self.ports[destname]

                    if dest.attributes.get(attr):
                        continue

                    if edge.attributes.get(barrier):
                        continue

                    if dest.parent is None:
                        dest.attributes[attr] = port.attributes[attr]
                        ports_to_process.append(destname)
                        continue

                    #all ports in crossbars must share the same parameter type
                    #NOTE: this probably should be done smarter, include some metric for picking best attribute for crossbar
                    #      metrics can include: majority, throughput, latency, etc
                    parent = dest.parent
                    for childportname, childport in self.ports.items():
                        if childport.parent == parent:
                            childport.attributes[attr] = port.attributes[attr]
                            ports_to_process.append(childportname)

            #if by this point attribute is not populated, then this must be an error and proper propagation is impossible
            #this might happen eg when a region is fully surrounded by CDC and no clock is provided inside
            for portname, port in self.ports.items():
                if not port.attributes.get(attr):
                    print(f"ERROR: could not propagate attribute '{attr}' to port '{portname}', it is likely surrounded by barriers that stop propagation")


        return

    def insert_new_components(self):
        #insert components from manager to subordinate components (left to right on graph view)
        #start with highest priority, AKA the ones that should be placed first in case of any conflict
        #current prioretization is: data width > clock > protocol

        #insertion algorithm is:
        # 1. go thru each connection, find connections between ports of different parameters
        # 2. insert two new ports under new component, the kind of component depends on the parameter
        #    also, note if new component kind was inserted, this info will be used during ip generation
        # 3. 
        #   a. for the parameter under consideration, get first's port param from source node, get second's port param from dest 
        #   b. for all the rest parameters, get both ports' params from source port 
        #note: source/dest are regarding edge direction, on graph view, source is on the left 
        for param, kind in {('data_width', 'dw_conv'), ('clock', 'cdc')}:
            newports = dict()

            for portname, port in self.ports.items():
                for edge in port.edges: 
                    destname = edge.dest 
                    dest = self.ports[destname]

                    portattr = port.attributes[param]
                    destattr = dest.attributes[param]

                    if portattr == destattr:
                        continue

                    name_comp = f"{kind}_{portname}_{portattr}_to_{destname}_{destattr}"
                    name1 = f"{kind}_{portname}_{portattr}"
                    name2 = f"{kind}_{destname}_{destattr}"

                    self.components[name_comp] = Component(kind, dict())
                    self.components[name_comp].ports = [name1, name2]

                    newports[name1] = Port(name_comp, copy.deepcopy(port.attributes))
                    newports[name2] = Port(name_comp, copy.deepcopy(port.attributes))

                    newports[name2].attributes[param] = destattr

                    edge.dest = name1
                    newports[name1].edges.append(Edge(name2, dict()))
                    newports[name2].edges.append(Edge(destname, dict()))


                    #fix manager-subordinate port organization as they are copied from left port, which is not correct
                    #notice that the only case when both 
                    #  1. port.parent is None
                    #  2. outgoing edges are not empty 
                    # is when port.role = 'subordinate' 
                    # therefore fix is always done by swapping the port name2
                    if port.parent is None:
                        newports[name2].attributes['role'] = 'manager'
                    # when port.parent is not none, then notice that outgoing connection from port name2 is correct
                    #  as it was correct when similar connection was outgoing from src port
                    # but, srcport is always master
                    # therefore the fix is done by swapping port name1
                    else:
                        newports[name1].attributes['role'] = 'subordinate'



            self.ports = self.ports | newports

        #some fixup 
        for compname, comp in self.components.items():
            
            if comp.kind == 'dw_conv':
                comp.attributes['clock'] = self.ports[comp.ports[0]].attributes['clock']

        return

    def map_components(self):
        self.generate_dw_conv = False
        self.generate_cdc     = False
        
        for name, component in self.components.items():
            
            #this is mostly a placeholder for now
            #in the future when proper mapping is implemented, this should include actual choice 
            match component.kind:
                case "crossbar":
                    pass
                case "pr_conv":
                    pass
                case "dw_conv":
                    self.generate_dw_conv = True
                case "cdc":
                    self.generate_cdc     = True
                case _:
                    print("ERROR: invalid kind of component, currently accepted ones are: 'crossbar', 'pr_conv', 'dw_conv', 'cdc'")
                    return

    def generate_ip(self, outdir):
        #for now, assume that all crossbars map to AXI from pulp-platform
        #this will be changed as soon as some way of choosing objects is chosen 
        #for now, each crossbar is generated as its own IP, though this can be later reduced to generating separate IP for each n x m crossbar

        #other IPs are generated manually below

        #it appears that the slave/master used in script generation describes connected device role, rather than crossbar port role 
        #therefore swap them internally
        plugin_path = importlib.resources.files("omnibus")
        sys.path.append(str(plugin_path / "third_party" / "axi" / "scripts"))
        import axi_intercon_gen
 
        for name, component in self.components.items():
            if component.kind   == 'dw_conv':
                pass
            elif component.kind   == 'cdc':
                pass
            elif component.kind == 'crossbar':
                slaves      = dict()
                slave_names = list()
                masters     = dict()
     
                for port in component.ports:
                    if self.ports[port].attributes['role'] == 'subordinate':
                        #TODO: find proper id_width instead of using placeholder, requires parameter propagation
                        masters[port] = {"id_width": 2, "slaves": slave_names}
                    else:
                        offset = 0
                        size   = 0

                        for entry in component.address_map:
                            if entry.dest == port:
                                offset = entry.base
                                size   = entry.size
                                break

                        if size == 0:
                            print(f"WARNING: rule of size 0 or lack of rule in crossbar {name} leading to port {port}")
                                
                        slaves[port] = {"offset": offset, "size": size}
                        slave_names.append(port)
                
                with tempfile.NamedTemporaryFile("w") as file:
                    config = {
                        "parameters": {
                            "output_file": f"{outdir}/src/axi_crossbar_{name}.sv",
                            "slaves": slaves,
                            "masters": masters,
                            "atop": 0,
                        },
                        "vlnv": f"vendor:library:axi_crossbar_{name}:1.0",
                    }
     
                    yaml.dump(config, file)
     
                    axi_intercon_gen.AxiIntercon(name, file.name).write()
            else:
                print(f"ERROR: cannot generate IP for component '{name}' of type '{component.kind}'")


        # data width converter is always the same
        if self.generate_dw_conv:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            content = """
module axi_dw_conv_wrapper #(
    parameter int unsigned AxiMaxReads         = 1    , // Number of outstanding reads
    parameter int unsigned AxiSrcPortDataWidth = 8    , // Data width of the slv port
    parameter int unsigned AxiOutPortDataWidth = 8    , // Data width of the mst port
    parameter int unsigned AxiAddrWidth        = 1    , // Address width
    parameter int unsigned AxiIdWidth          = 1      // ID width
    ) (
    input  logic          clk_i,
    input  logic          rst_ni,

          input  wire [AxiIdWidth   - 1 :0]         i_src_awid,
          input  wire [AxiAddrWidth - 1 :0]         i_src_awaddr,
          input  wire  [7:0]                        i_src_awlen,
          input  wire  [2:0]                        i_src_awsize,
          input  wire  [1:0]                        i_src_awburst,
          input  wire                               i_src_awlock,
          input  wire  [3:0]                        i_src_awcache,
          input  wire  [2:0]                        i_src_awprot,
          input  wire  [3:0]                        i_src_awregion,
          input  wire  [3:0]                        i_src_awqos,
          input  wire                               i_src_awvalid,
          output wire                               o_src_awready,
          input  wire [AxiIdWidth - 1   :0]         i_src_arid,
          input  wire [AxiAddrWidth - 1 :0]         i_src_araddr,
          input  wire  [7:0]                        i_src_arlen,
          input  wire  [2:0]                        i_src_arsize,
          input  wire  [1:0]                        i_src_arburst,
          input  wire                               i_src_arlock,
          input  wire  [3:0]                        i_src_arcache,
          input  wire  [2:0]                        i_src_arprot,
          input  wire  [3:0]                        i_src_arregion,
          input  wire  [3:0]                        i_src_arqos,
          input  wire                               i_src_arvalid,
          output wire                               o_src_arready,
          input  wire [AxiSrcPortDataWidth - 1:0]   i_src_wdata,
          input  wire [AxiSrcPortDataWidth/8 - 1:0] i_src_wstrb,
          input  wire                               i_src_wlast,
          input  wire                               i_src_wvalid,
          output wire                               o_src_wready,
          output wire [AxiIdWidth - 1 :0]           o_src_bid,
          output wire  [1:0]                        o_src_bresp,
          output wire                               o_src_bvalid,
          input  wire                               i_src_bready,
          output wire [AxiIdWidth - 1 :0]           o_src_rid,
          output wire [AxiSrcPortDataWidth - 1:0]   o_src_rdata,
          output wire  [1:0]                        o_src_rresp,
          output wire                               o_src_rlast,
          output wire                               o_src_rvalid,
          input  wire                               i_src_rready,

          output wire [AxiIdWidth - 1 :0]           o_dst_awid,
          output wire [AxiAddrWidth - 1 :0]         o_dst_awaddr,
          output wire  [7:0]                        o_dst_awlen,
          output wire  [2:0]                        o_dst_awsize,
          output wire  [1:0]                        o_dst_awburst,
          output wire                               o_dst_awlock,
          output wire  [3:0]                        o_dst_awcache,
          output wire  [2:0]                        o_dst_awprot,
          output wire  [3:0]                        o_dst_awregion,
          output wire  [3:0]                        o_dst_awqos,
          output wire                               o_dst_awvalid,
          input  wire                               i_dst_awready,
          output wire [AxiIdWidth-1:0]              o_dst_arid,
          output wire [AxiAddrWidth-1:0]            o_dst_araddr,
          output wire  [7:0]                        o_dst_arlen,
          output wire  [2:0]                        o_dst_arsize,
          output wire  [1:0]                        o_dst_arburst,
          output wire                               o_dst_arlock,
          output wire  [3:0]                        o_dst_arcache,
          output wire  [2:0]                        o_dst_arprot,
          output wire  [3:0]                        o_dst_arregion,
          output wire  [3:0]                        o_dst_arqos,
          output wire                               o_dst_arvalid,
          input  wire                               i_dst_arready,
          output wire [AxiOutPortDataWidth - 1:0]   o_dst_wdata,
          output wire [AxiOutPortDataWidth/8 - 1:0] o_dst_wstrb,
          output wire                               o_dst_wlast,
          output wire                               o_dst_wvalid,
          input  wire                               i_dst_wready,
          input  wire [AxiIdWidth - 1:0]            i_dst_bid,
          input  wire  [1:0]                        i_dst_bresp,
          input  wire                               i_dst_bvalid,
          output wire                               o_dst_bready,
          input  wire [AxiIdWidth - 1:0]            i_dst_rid,
          input  wire [AxiOutPortDataWidth - 1:0]   i_dst_rdata,
          input  wire  [1:0]                        i_dst_rresp,
          input  wire                               i_dst_rlast,
          input  wire                               i_dst_rvalid,
          output wire                               o_dst_rready
    );

    typedef logic [AxiIdWidth-1:0]            id_t;
    typedef logic [AxiAddrWidth-1:0]          addr_t;
    typedef logic [AxiOutPortDataWidth-1:0]   mst_data_t;
    typedef logic [AxiSrcPortDataWidth-1:0]   slv_data_t;


    typedef logic [AxiStrbWidth-1:0]          strb_t;
    typedef logic [AxiUserWidth-1:0]          user_t;
    
    `AXI_TYPEDEF_AW_CHAN_T(aw_chan_mst_t, addr_t, id_mst_t, user_t)
    `AXI_TYPEDEF_AW_CHAN_T(aw_chan_slv_t, addr_t, id_slv_t, user_t)
    `AXI_TYPEDEF_W_CHAN_T(mst_w_chan_t, mst_data_t, strb_t, user_t)
    `AXI_TYPEDEF_W_CHAN_T(slv_w_chan_t, slv_data_t, strb_t, user_t)
    `AXI_TYPEDEF_B_CHAN_T(b_chan_t, id_t, user_t)
    
    `AXI_TYPEDEF_AR_CHAN_T(ar_chan_t, addr_t, id_t, user_t)
    `AXI_TYPEDEF_R_CHAN_T(r_chan_mst_t, data_t, id_mst_t, user_t)
    `AXI_TYPEDEF_R_CHAN_T(r_chan_slv_t, data_t, id_slv_t, user_t)
    
    `AXI_TYPEDEF_REQ_T(slv_req_t, aw_chan_mst_t, w_chan_t, ar_chan_mst_t)
    `AXI_TYPEDEF_RESP_T(slv_resp_t, b_chan_mst_t, r_chan_mst_t)
    `AXI_TYPEDEF_REQ_T(mst_req_t, aw_chan_slv_t, w_chan_t, ar_chan_slv_t)
    `AXI_TYPEDEF_RESP_T(mst_resp_t, b_chan_slv_t, r_chan_slv_t)
         
    slv_req_t  dst_req;
    slv_resp_t dst_resp;
    mst_req_t  src_req;
    mst_resp_t src_resp;

    axi_dw_converter #(
       .AxiMaxReads        (AxiMaxReads        ),
       .AxiSrcPortDataWidth(AxiSrcPortDataWidth),
       .AxiOutPortDataWidth(AxiOutPortDataWidth),
       .AxiAddrWidth       (AxiAddrWidth       ),
       .AxiIdWidth         (AxiIdWidth         ),
       .aw_chan_t          (aw_chan_t          ),
       .mst_w_chan_t       (mst_w_chan_t       ),
       .slv_w_chan_t       (slv_w_chan_t       ),
       .b_chan_t           (b_chan_t           ),
       .ar_chan_t          (ar_chan_t          ),
       .mst_r_chan_t       (r_chan_mst_t       ),
       .slv_r_chan_t       (r_chan_slv_t       ),
       .axi_mst_req_t      (mst_req_t          ),
       .axi_mst_resp_t     (mst_resp_t         ),
       .axi_slv_req_t      (slv_req_t          ),
       .axi_slv_resp_t     (slv_resp_t         )
     ) i_axi_dw_converter (
       .clk_i     (clk_i     ),
       .rst_ni    (rst_ni    ),

       // Slave interface
       .slv_req_i (slv_req ),
       .slv_resp_o(slv_resp),
       // Master interface
       .mst_req_o (mst_req ),
       .mst_resp_i(mst_resp)
     );


    assign dst_req.aw.id = i_dst_awid;
    assign dst_req.aw.addr = i_dst_awaddr;
    assign dst_req.aw.len = i_dst_awlen;
    assign dst_req.aw.size = i_dst_awsize;
    assign dst_req.aw.burst = i_dst_awburst;
    assign dst_req.aw.lock = i_dst_awlock;
    assign dst_req.aw.cache = i_dst_awcache;
    assign dst_req.aw.prot = i_dst_awprot;
    assign dst_req.aw.region = i_dst_awregion;
    assign dst_req.aw.qos = i_dst_awqos;
    assign dst_req.aw.atop = 6'd0;
    assign dst_req.aw_valid = i_dst_awvalid;
    assign o_dst_awready = dst_resp.aw_ready;
    assign dst_req.ar.id = i_dst_arid;
    assign dst_req.ar.addr = i_dst_araddr;
    assign dst_req.ar.len = i_dst_arlen;
    assign dst_req.ar.size = i_dst_arsize;
    assign dst_req.ar.burst = i_dst_arburst;
    assign dst_req.ar.lock = i_dst_arlock;
    assign dst_req.ar.cache = i_dst_arcache;
    assign dst_req.ar.prot = i_dst_arprot;
    assign dst_req.ar.region = i_dst_arregion;
    assign dst_req.ar.qos = i_dst_arqos;
    assign dst_req.ar_valid = i_dst_arvalid;
    assign o_dst_arready = dst_resp.ar_ready;
    assign dst_req.w.data = i_dst_wdata;
    assign dst_req.w.strb = i_dst_wstrb;
    assign dst_req.w.last = i_dst_wlast;
    assign dst_req.w_valid = i_dst_wvalid;
    assign o_dst_wready = dst_resp.w_ready;
    assign o_dst_bid = dst_resp.b.id;
    assign o_dst_bresp = dst_resp.b.resp;
    assign o_dst_bvalid = dst_resp.b_valid;
    assign dst_req.b_ready = i_dst_bready;
    assign o_dst_rid = dst_resp.r.id;
    assign o_dst_rdata = dst_resp.r.data;
    assign o_dst_rresp = dst_resp.r.resp;
    assign o_dst_rlast = dst_resp.r.last;
    assign o_dst_rvalid = dst_resp.r_valid;
    assign dst_req.r_ready = i_dst_rready;

    assign o_src_awid = src_req.aw.id;
    assign o_src_awaddr = src_req.aw.addr;
    assign o_src_awlen = src_req.aw.len;
    assign o_src_awsize = src_req.aw.size;
    assign o_src_awburst = src_req.aw.burst;
    assign o_src_awlock = src_req.aw.lock;
    assign o_src_awcache = src_req.aw.cache;
    assign o_src_awprot = src_req.aw.prot;
    assign o_src_awregion = src_req.aw.region;
    assign o_src_awqos = src_req.aw.qos;
    assign o_src_awvalid = src_req.aw_valid;
    assign src_resp.aw_ready = i_src_awready;
    assign o_src_arid = src_req.ar.id;
    assign o_src_araddr = src_req.ar.addr;
    assign o_src_arlen = src_req.ar.len;
    assign o_src_arsize = src_req.ar.size;
    assign o_src_arburst = src_req.ar.burst;
    assign o_src_arlock = src_req.ar.lock;
    assign o_src_arcache = src_req.ar.cache;
    assign o_src_arprot = src_req.ar.prot;
    assign o_src_arregion = src_req.ar.region;
    assign o_src_arqos = src_req.ar.qos;
    assign o_src_arvalid = src_req.ar_valid;
    assign src_resp.ar_ready = i_src_arready;
    assign o_src_wdata = src_req.w.data;
    assign o_src_wstrb = src_req.w.strb;
    assign o_src_wlast = src_req.w.last;
    assign o_src_wvalid = src_req.w_valid;
    assign src_resp.w_ready = i_src_wready;
    assign src_resp.b.id = i_src_bid;
    assign src_resp.b.resp = i_src_bresp;
    assign src_resp.b_valid = i_src_bvalid;
    assign o_src_bready = src_req.b_ready;
    assign src_resp.r.id = i_src_rid;
    assign src_resp.r.data = i_src_rdata;
    assign src_resp.r.resp = i_src_rresp;
    assign src_resp.r.last = i_src_rlast;
    assign src_resp.r_valid = i_src_rvalid;
    assign o_src_rready = src_req.r_ready;

endmodule
        """
            with open(f"{outdir}/src/axi_dw_converter.sv", "w") as file:
                file.write(content)

        if self.generate_cdc:
            #NOTE: this file is currently not verified 
            #      it seems like it is correct up to idea but topwrap prints many warnings
            #      also it was not yet verified in whole design
            content = """
module axi_cdc_wrapper #(
    parameter int unsigned AxiMaxReads         = 1    , // Number of outstanding reads
    parameter int unsigned AxiDataWidth        = 8    , // Data width of the ports
    parameter int unsigned AxiAddrWidth        = 1    , // Address width
    parameter int unsigned AxiIdWidth          = 1      // ID width
    ) (
    input  logic          src_clk_i,
    input  logic          src_rst_ni,
    input  logic          dst_clk_i,
    input  logic          dst_rst_ni,

          input  wire [AxiIdWidth   - 1 :0]       i_src_awid,
          input  wire [AxiAddrWidth - 1 :0]       i_src_awaddr,
          input  wire  [7:0]                      i_src_awlen,
          input  wire  [2:0]                      i_src_awsize,
          input  wire  [1:0]                      i_src_awburst,
          input  wire                             i_src_awlock,
          input  wire  [3:0]                      i_src_awcache,
          input  wire  [2:0]                      i_src_awprot,
          input  wire  [3:0]                      i_src_awregion,
          input  wire  [3:0]                      i_src_awqos,
          input  wire                             i_src_awvalid,
          output wire                             o_src_awready,
          input  wire [AxiIdWidth - 1   :0]       i_src_arid,
          input  wire [AxiAddrWidth - 1 :0]       i_src_araddr,
          input  wire  [7:0]                      i_src_arlen,
          input  wire  [2:0]                      i_src_arsize,
          input  wire  [1:0]                      i_src_arburst,
          input  wire                             i_src_arlock,
          input  wire  [3:0]                      i_src_arcache,
          input  wire  [2:0]                      i_src_arprot,
          input  wire  [3:0]                      i_src_arregion,
          input  wire  [3:0]                      i_src_arqos,
          input  wire                             i_src_arvalid,
          output wire                             o_src_arready,
          input  wire [AxiDataWidth - 1:0]        i_src_wdata,
          input  wire [AxiDataWidth/8 - 1:0]      i_src_wstrb,
          input  wire                             i_src_wlast,
          input  wire                             i_src_wvalid,
          output wire                             o_src_wready,
          output wire [AxiIdWidth - 1 :0]         o_src_bid,
          output wire  [1:0]                      o_src_bresp,
          output wire                             o_src_bvalid,
          input  wire                             i_src_bready,
          output wire [AxiIdWidth - 1 :0]         o_src_rid,
          output wire [AxiDataWidth - 1:0]        o_src_rdata,
          output wire  [1:0]                      o_src_rresp,
          output wire                             o_src_rlast,
          output wire                             o_src_rvalid,
          input  wire                             i_src_rready,

          output wire [AxiIdWidth - 1 :0]         o_dst_awid,
          output wire [AxiAddrWidth - 1 :0]       o_dst_awaddr,
          output wire  [7:0]                      o_dst_awlen,
          output wire  [2:0]                      o_dst_awsize,
          output wire  [1:0]                      o_dst_awburst,
          output wire                             o_dst_awlock,
          output wire  [3:0]                      o_dst_awcache,
          output wire  [2:0]                      o_dst_awprot,
          output wire  [3:0]                      o_dst_awregion,
          output wire  [3:0]                      o_dst_awqos,
          output wire                             o_dst_awvalid,
          input  wire                             i_dst_awready,
          output wire [AxiIdWidth-1:0]            o_dst_arid,
          output wire [AxiAddrWidth-1:0]          o_dst_araddr,
          output wire  [7:0]                      o_dst_arlen,
          output wire  [2:0]                      o_dst_arsize,
          output wire  [1:0]                      o_dst_arburst,
          output wire                             o_dst_arlock,
          output wire  [3:0]                      o_dst_arcache,
          output wire  [2:0]                      o_dst_arprot,
          output wire  [3:0]                      o_dst_arregion,
          output wire  [3:0]                      o_dst_arqos,
          output wire                             o_dst_arvalid,
          input  wire                             i_dst_arready,
          output wire [AxiDataWidth - 1:0]        o_dst_wdata,
          output wire [AxiDataWidth/8 - 1:0]      o_dst_wstrb,
          output wire                             o_dst_wlast,
          output wire                             o_dst_wvalid,
          input  wire                             i_dst_wready,
          input  wire [AxiIdWidth - 1:0]          i_dst_bid,
          input  wire  [1:0]                      i_dst_bresp,
          input  wire                             i_dst_bvalid,
          output wire                             o_dst_bready,
          input  wire [AxiIdWidth - 1:0]          i_dst_rid,
          input  wire [AxiDataWidth - 1:0]        i_dst_rdata,
          input  wire  [1:0]                      i_dst_rresp,
          input  wire                             i_dst_rlast,
          input  wire                             i_dst_rvalid,
          output wire                             o_dst_rready
    );

    typedef logic [AxiIdWidth-1:0]            id_t;
    typedef logic [AxiAddrWidth-1:0]          addr_t;
    typedef logic [AxiDataWidth-1:0]          data_t;

    typedef logic [AxiStrbWidth-1:0]          strb_t;
    typedef logic [AxiUserWidth-1:0]          user_t;
    
    `AXI_TYPEDEF_AW_CHAN_T(aw_chan_t, addr_t, id_t, user_t)
    `AXI_TYPEDEF_W_CHAN_T(w_chan_t, data_t, strb_t, user_t)
    `AXI_TYPEDEF_B_CHAN_T(b_chan_t, id_t, user_t)
    
    `AXI_TYPEDEF_AR_CHAN_T(ar_chan_t, addr_t, id_t, user_t)
    `AXI_TYPEDEF_R_CHAN_T(r_chan_t, data_t, id_t, user_t)
    
    `AXI_TYPEDEF_REQ_T(req_t, aw_chan_t, w_chan_t, ar_chan_t)
    `AXI_TYPEDEF_RESP_T(resp_t, b_chan_t, r_chan_t)

    req_t  dst_req;
    resp_t dst_resp;
    req_t  src_req;
    resp_t src_resp;

    axi_cdc #(
       .aw_chan_t      (aw_chan_t          ),
       .w_chan_t       (mst_w_chan_t       ),
       .b_chan_t       (b_chan_t           ),
       .ar_chan_t      (ar_chan_t          ),
       .r_chan_t       (r_chan_slv_t       ),
       .axi_req_t      (mst_req_t          ),
       .axi_resp_t     (mst_resp_t         ),
     ) i_axi_cdc_wrapper (
       .src_clk_i      (src_clk_i     ),
       .src_rst_ni     (src_rst_ni    ),

       .dst_clk_i      (dst_clk_i     ),
       .dst_rst_ni     (dst_rst_ni    ),

       // Slave interface
       .src_req_i (src_req ),
       .src_resp_o(src_resp),
       // Master interface
       .dst_req_o (dst_req ),
       .dst_resp_i(dst_resp)
     );


    assign dst_req.aw.id = i_dst_awid;
    assign dst_req.aw.addr = i_dst_awaddr;
    assign dst_req.aw.len = i_dst_awlen;
    assign dst_req.aw.size = i_dst_awsize;
    assign dst_req.aw.burst = i_dst_awburst;
    assign dst_req.aw.lock = i_dst_awlock;
    assign dst_req.aw.cache = i_dst_awcache;
    assign dst_req.aw.prot = i_dst_awprot;
    assign dst_req.aw.region = i_dst_awregion;
    assign dst_req.aw.qos = i_dst_awqos;
    assign dst_req.aw.atop = 6'd0;
    assign dst_req.aw_valid = i_dst_awvalid;
    assign o_dst_awready = dst_resp.aw_ready;
    assign dst_req.ar.id = i_dst_arid;
    assign dst_req.ar.addr = i_dst_araddr;
    assign dst_req.ar.len = i_dst_arlen;
    assign dst_req.ar.size = i_dst_arsize;
    assign dst_req.ar.burst = i_dst_arburst;
    assign dst_req.ar.lock = i_dst_arlock;
    assign dst_req.ar.cache = i_dst_arcache;
    assign dst_req.ar.prot = i_dst_arprot;
    assign dst_req.ar.region = i_dst_arregion;
    assign dst_req.ar.qos = i_dst_arqos;
    assign dst_req.ar_valid = i_dst_arvalid;
    assign o_dst_arready = dst_resp.ar_ready;
    assign dst_req.w.data = i_dst_wdata;
    assign dst_req.w.strb = i_dst_wstrb;
    assign dst_req.w.last = i_dst_wlast;
    assign dst_req.w_valid = i_dst_wvalid;
    assign o_dst_wready = dst_resp.w_ready;
    assign o_dst_bid = dst_resp.b.id;
    assign o_dst_bresp = dst_resp.b.resp;
    assign o_dst_bvalid = dst_resp.b_valid;
    assign dst_req.b_ready = i_dst_bready;
    assign o_dst_rid = dst_resp.r.id;
    assign o_dst_rdata = dst_resp.r.data;
    assign o_dst_rresp = dst_resp.r.resp;
    assign o_dst_rlast = dst_resp.r.last;
    assign o_dst_rvalid = dst_resp.r_valid;
    assign dst_req.r_ready = i_dst_rready;

    assign o_src_awid = src_req.aw.id;
    assign o_src_awaddr = src_req.aw.addr;
    assign o_src_awlen = src_req.aw.len;
    assign o_src_awsize = src_req.aw.size;
    assign o_src_awburst = src_req.aw.burst;
    assign o_src_awlock = src_req.aw.lock;
    assign o_src_awcache = src_req.aw.cache;
    assign o_src_awprot = src_req.aw.prot;
    assign o_src_awregion = src_req.aw.region;
    assign o_src_awqos = src_req.aw.qos;
    assign o_src_awvalid = src_req.aw_valid;
    assign src_resp.aw_ready = i_src_awready;
    assign o_src_arid = src_req.ar.id;
    assign o_src_araddr = src_req.ar.addr;
    assign o_src_arlen = src_req.ar.len;
    assign o_src_arsize = src_req.ar.size;
    assign o_src_arburst = src_req.ar.burst;
    assign o_src_arlock = src_req.ar.lock;
    assign o_src_arcache = src_req.ar.cache;
    assign o_src_arprot = src_req.ar.prot;
    assign o_src_arregion = src_req.ar.region;
    assign o_src_arqos = src_req.ar.qos;
    assign o_src_arvalid = src_req.ar_valid;
    assign src_resp.ar_ready = i_src_arready;
    assign o_src_wdata = src_req.w.data;
    assign o_src_wstrb = src_req.w.strb;
    assign o_src_wlast = src_req.w.last;
    assign o_src_wvalid = src_req.w_valid;
    assign src_resp.w_ready = i_src_wready;
    assign src_resp.b.id = i_src_bid;
    assign src_resp.b.resp = i_src_bresp;
    assign src_resp.b_valid = i_src_bvalid;
    assign o_src_bready = src_req.b_ready;
    assign src_resp.r.id = i_src_rid;
    assign src_resp.r.data = i_src_rdata;
    assign src_resp.r.resp = i_src_rresp;
    assign src_resp.r.last = i_src_rlast;
    assign src_resp.r_valid = i_src_rvalid;
    assign o_src_rready = src_req.r_ready;

endmodule
        """
            with open(f"{outdir}/src/axi_cdc.sv", "w") as file:
                file.write(content)


    def generate_hierarchy(self, outdir):
        tree = {
            'name': self.name,
            'ips': dict(), 
            'connections': {
                'ports': dict(), 
                'interfaces': dict()}, 
            'external': {
                'ports': {'in': []},
                'interfaces': {'in': [], 'out': []}
            }
        } 

        # external clocks
        tree_ports = tree['external']['ports']
        for clockname, clock in self.clocks.items():
            tree_ports['in'].append(clockname)    
            
            
        # external ports (actually interfaces)
        tree_interfaces  = tree['external']['interfaces']
        for name, port in self.ports.items():
            if port.parent is not None:
                continue

            if port.attributes['role'] == 'subordinate':
                tree_interfaces['in'].append(name)
            else:
                tree_interfaces['out'].append(name)

        #for now, assume that all components map to AXI from pulp-platform
        for name, component in self.components.items():
            if component.kind == 'crossbar':
                tree['ips'][name] = dict()

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/{name}/module.yaml"
                tree['connections']['interfaces'][name] = dict()
                
                tree['connections']['ports'][name] = {'clk_i': component.attributes['clock']}
            elif component.kind == 'dw_conv':
                tree['ips'][name] = dict()

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/axi_dw_conv_wrapper/module.yaml"
                tree['ips'][name]['parameters'] = dict()

                tree['connections']['interfaces'][name] = dict()
                
                tree['connections']['ports'][name] = {'clk_i': component.attributes['clock']}

                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                params = tree['ips'][name]['parameters']

                params['AxiMaxReads'] = 1
                params['AxiSrcPortDataWidth'] = srcport.attributes['data_width']
                params['AxiOutPortDataWidth'] = dstport.attributes['data_width']
                #NOTE: placeholder until addr width is properly propagated
                params['AxiAddrWidth']        = 2
                #NOTE: placeholder until id width is properly propagated
                params['AxiIdWidth']          = 2
            elif component.kind == 'cdc':
                tree['ips'][name] = dict()

                tree['ips'][name]['file'] = f"file:{outdir}/modules/cores/axi_cdc_wrapper/module.yaml"
                tree['ips'][name]['parameters'] = dict()

                tree['connections']['interfaces'][name] = dict()
                
                srcport = self.ports[component.ports[0]]
                dstport = self.ports[component.ports[1]]

                tree['connections']['ports'][name] = {'src_clk_i': srcport.attributes['clock'], 'dst_clk_i': dstport.attributes['clock']}

                params = tree['ips'][name]['parameters']

                params['AxiMaxReads'] = 1
                params['AxiDataWidth'] = srcport.attributes['data_width']
                #NOTE: placeholder until addr width is properly propagated
                params['AxiAddrWidth']        = 2
                #NOTE: placeholder until id width is properly propagated
                params['AxiIdWidth']          = 2
                

        for portname, port in self.ports.items():
            for dest in port.edges:
                destname = dest.dest
                destport = self.ports[destname]

                #connections are only added between components
                if port.parent == destport.parent:
                    continue

                portcomp = self.components.get(port.parent)
                destcomp = self.components.get(destport.parent)

                #interfaces can only be defined from IPs 
                #ensure we are not in external interface
                #TODO: this is a bit ugly, find some nicer way
                if port.parent is None:
                    ip = tree['connections']['interfaces'][destport.parent]

                    if destcomp.kind == 'crossbar':
                        ip[destname] = portname
                    else:
                        ip['src'] = portname
                elif destport.parent is None:
                    ip = tree['connections']['interfaces'][port.parent]

                    if portcomp.kind == 'crossbar':
                        ip[portname] = destname
                    else:
                        ip['dst'] = destname
                else:
                    ip = tree['connections']['interfaces'][port.parent]

                    if portcomp.kind == 'crossbar' and destcomp.kind == 'crossbar':
                        ip[portname] = [destport.parent, destname]
                    elif portcomp.kind == 'crossbar':
                        ip[portname] = [destport.parent, 'src']
                    else:
                        ip['dst'] = [destport.parent, destname]

        with open(f"{outdir}/interconnect.yml", 'w') as file:
            yaml.dump(tree, file)

    def print_spec(self):
        yaml.dump(self.spec, sys.stdout)

    def print_elements(self):
        print("### PORTS ###")
        for k, v in self.ports.items():
            print(f"== PORT {k} parent: {v.parent} ==")
            print(sorted(v.attributes.items()))

            for edge in v.edges:
                print(f"- edge to {edge.dest} -")
                print(sorted(edge.attributes.items()))

        print("### COMPONENTS ###")

        for k, v in self.components.items():
            print(f"== COMP {k} {v.kind}")
            yaml.dump(v.attributes, sys.stdout, sort_keys=True)

        print("### ADDR MAPS ###")
        print("== INTERCONNECT ==") 
        print(self.address_map)

        for comp, params in self.components.items():
            if params.kind != 'crossbar':
                continue

            print(f"== CROSSBAR {comp}==")

            for entry in params.address_map:
                print('--')
                print(entry.src + ' ' + entry.dest)
                print(hex(entry.base) + ' ' + hex(entry.size))

    def generate_graph(self, filename='interconnect.gv', view=False, color_by=""):
        g = graphviz.Digraph(self.name, filename=filename, node_attr={'style': 'filled', 'colorscheme': 'paired12'})
        g.attr(rankdir='LR')

        #max color id determined by paired12 colorscheme
        param_to_color_id = dict()
        color_nxt_id = 1
        color_max_id = 11

        crossbars = dict()

        for port, params in self.ports.items():
            
            color = "white"

            if color_by != "":
                color = None

                paramval = params.attributes.get(color_by)

                if paramval is not None:
                    if not param_to_color_id.get(paramval):
                        if color_nxt_id > color_max_id:
                            print("ERROR: too many different parameter's values to color by")
                            return

                        param_to_color_id[paramval] = str(color_nxt_id)
                        color_nxt_id += 1 

                    color = param_to_color_id[paramval]

                if color is None:
                    color = '12'
            
            if params.parent is None:
                g.node(port, fillcolor=color)

                for edge in params.edges:
                    g.edge(port, edge.dest)
                
                continue

            cb = crossbars.get(params.parent)
            if not cb:
                #"cluster" is necessary to generate  grouping
                crossbars[params.parent] = graphviz.Digraph(name='cluster ' + params.parent)
                cb = crossbars[params.parent]
                cb.attr(label=params.parent)
                cb.attr(style='dashed', color='lightgrey')

            cb.node(port, fillcolor=color)

            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    cb.edge(port, dest)
                

        # create a legend
        if color_by != "":
            legend = graphviz.Digraph(name="cluster legend")
            legend.attr(label="legend")
            legend.attr(color='lightgrey')
            legend.attr(rank="same")
            
            for name, color in param_to_color_id.items():
                name = str(name)
                legend.node(name, fillcolor=color)
                #force layout
                legend.edge(name, "none", style="invis")

            legend.node("none", fillcolor=str(color_max_id + 1))

            #force layout
            g.edge(list(self.ports.keys())[0], "none", style="invis")

            g.subgraph(legend)

            

        for k, v in crossbars.items():
            g.subgraph(v)
    
        if view:
            g.view()
        else:
            g.save()
