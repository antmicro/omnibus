# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import graphviz


class Backend:
    """
    Graphviz backend

    This generates graphviz file from existing representation
    It is fully self contained and does not require any external commands

    The `generate` method can be used to set filename, set whether to display the graph, set whether to color it according to some parameter, set colorscheme, and whether to shorten the names used in the graph
    """

    def __init__(self):
        self.parse_global = {}
        self.parse_default = {}
        self.parse_connections = {}

    def generate(
        self,
        outdir,
        view=False,
        color_by="",
        color_scheme="paired12",
        display_full_name=False,
    ):
        """Generate graphviz graph, optionally display it and optionally color it by some parameter according to chosen colorscheme"""
        g = graphviz.Digraph(
            self.name,
            filename=f"{outdir}/{self.name}.gv",
            node_attr={"style": "filled", "colorscheme": color_scheme},
        )
        g.attr(rankdir="LR")
        g.attr(splines="line")

        # max color id determined by colorscheme
        # colorschemes are defined in https://graphviz.org/doc/info/colors.html#brewer
        param_to_color_id = {}

        # each colorscheme ends in a number that defines how many colors are available
        # unfortunately some colorscheme names include number (eg dark2)
        # fortunately there are at most 12 colors in single colorscheme (paired12), and the lowest invalid numbers go is 13 (pastel13)
        # and so, proper colornames scheme can be found by
        # 1. if there are 3 digits, ignore first one
        # 2. if there are 2 digits, ignore first one if last digit is above 2
        if len(color_scheme) < 4 or color_scheme[-1] < "0" or color_scheme[-1] > "9":
            self.errors.append(
                "ERROR: invalid colorscheme provided; check https://graphviz.org/doc/info/colors.html#brewer for list of allowed ones"
            )
            return

        color_max_id = 0
        if "0" <= color_scheme[-3] <= "9":
            color_max_id = int(color_scheme[-2:])
        elif "0" <= color_scheme[-2] <= "9":
            if color_scheme[-1] > "2":
                color_max_id = int(color_scheme[-1])
            else:
                color_max_id = int(color_scheme[-2:])
        else:
            color_max_id = int(color_scheme[-1])
        color_nxt_id = 1

        # collect all parameters, sort them, assign colors in order
        if color_by != "":
            param_set = set()

            for params in self.ports.values():
                if params.attributes.get(color_by):
                    param_set.add(params.attributes.get(color_by))

            for param in sorted(param_set):
                if color_nxt_id > color_max_id:
                    self.errors.append(
                        "ERROR: too many different parameter's values to color by"
                    )
                    return

                param_to_color_id[param] = str(color_nxt_id)
                color_nxt_id += 1

        subgraphs = {}

        for port, params in self.ports.items():
            color = param_to_color_id.get(params.attributes.get(color_by), "white")

            if params.parent is None:
                g.node(port, fillcolor=color)

                for edge in params.edges:
                    g.edge(port, edge.dest)

                continue

            sg = subgraphs.get(params.parent)
            kind = self.components[params.parent].kind
            if not sg:
                # "cluster" is necessary to generate grouping
                subgraphs[params.parent] = graphviz.Digraph(
                    name="cluster " + params.parent
                )
                sg = subgraphs[params.parent]

                if display_full_name or kind == "crossbar":
                    sg.attr(label=f"{kind}\n{params.parent}")
                else:
                    sg.attr(label=f"{kind}")

                sg.attr(style="dashed", color="lightgrey")

            if display_full_name or kind == "crossbar":
                sg.node(port, fillcolor=color)
            elif kind == "cdc":
                sg.node(port, fillcolor=color, label=str(params.attributes["clock"]))
            elif kind == "pr_conv":
                sg.node(port, fillcolor=color, label=str(params.attributes["protocol"]))
            elif kind == "iw_conv":
                sg.node(port, fillcolor=color, label=str(params.attributes["id_width"]))
            elif kind == "dw_conv":
                sg.node(
                    port, fillcolor=color, label=str(params.attributes["data_width"])
                )
            elif kind == "register":
                sg.node(port, fillcolor=color, label=port[-3:])

            for edge in params.edges:
                dest = edge.dest
                # crossbar might have outgoing connection
                # to properly generate stuff with graphviz such connection has to be placed out of the cluster
                if self.ports[dest].parent != self.ports[port].parent:
                    g.edge(port, dest)
                else:
                    sg.edge(port, dest)

        # create a legend
        if color_by != "":
            legend = graphviz.Digraph(name="cluster legend")
            legend.attr(label=f"legend - {color_by}")
            legend.attr(color="lightgrey")
            legend.attr(rank="same")

            params = list(param_to_color_id.items())
            for ii in range(len(params) - 1):
                name = str(params[ii][0])
                legend.node(name, fillcolor=params[ii][1])
                # force layout
                legend.edge(name, str(params[ii + 1][0]), style="invis")

            name = str(params[-1][0])
            legend.node(name, fillcolor=params[-1][1])
            legend.edge(name, "none", style="invis")
            legend.node("none", fillcolor="white")

            g.subgraph(legend)

        for sg in subgraphs.values():
            g.subgraph(sg)

        if view:
            g.view()
        else:
            g.save()
