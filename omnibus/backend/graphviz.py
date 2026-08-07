import graphviz


class Backend:
    """
    Graphviz backend

    This generates graphviz file from existing representation 
    It is fully self contained and does not require any external commands

    The `generate` method can be used to set filename, set whether to display the graph, and to set whether to color it according to some parameter
    """
    def generate(self, filename='interconnect.gv', view=False, color_by=""):
        """Generate graphviz graph, optionally color it by some parameter, and optionally display it"""
        g = graphviz.Digraph(self.name, filename=filename, node_attr={'style': 'filled', 'colorscheme': 'paired12'})
        g.attr(rankdir='LR')
    
        #max color id determined by paired12 colorscheme
        param_to_color_id = {}
        color_nxt_id = 1
        color_max_id = 11
    
        subgraphs = {}
    
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
    
            sg = subgraphs.get(params.parent)
            if not sg:
                #"cluster" is necessary to generate  grouping
                subgraphs[params.parent] = graphviz.Digraph(name='cluster ' + params.parent)
                sg = subgraphs[params.parent]
                sg.attr(label=params.parent)
                sg.attr(style='dashed', color='lightgrey')
    
            sg.node(port, fillcolor=color)
    
            for edge in params.edges:
                dest = edge.dest
                #crossbar might have outgoing connection
                #to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    sg.edge(port, dest)
                
    
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
            g.edge(next(iter(self.ports.keys())), "none", style="invis")
    
            g.subgraph(legend)
    
        for sg in subgraphs.values():
            g.subgraph(sg)
    
        if view:
            g.view()
        else:
            g.save()
