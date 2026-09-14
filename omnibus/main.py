# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import argparse
import os

from .interconnect import InterconnectBuilder


def print_lines(l):
    for line in l:
        print(line)

def main():
    argsparser = argparse.ArgumentParser(prog='omnibus')
    argsparser.add_argument('file') 
    argsparser.add_argument('-o', '--output', default="./out", help="specifies output directory") 
    argsparser.add_argument('--graph', action='store_true', help="produce graph as an output in output directory with name of the interconnect") 
    argsparser.add_argument('-g', '--graphview', action='store_true', help="like --graph but automatically displays the result in browser") 
    argsparser.add_argument('-d', '--debug', help="specify at what stage to stop execution and output debug info", choices=['parse', 'elements', 'graph']) 
    argsparser.add_argument('-c', '--colorby', default="", help="specify what parameter to color by in a graph", choices=['clock','protocol','role','data_width', 'id_width']) 
    argsparser.add_argument('--colorscheme', default="paired12", help="specify graphviz colorscheme") 
    argsparser.add_argument('--fulldisplay', action='store_true', help="if specified, provides full port names in the graph output, otherwise shortens them for readability") 

    args = argsparser.parse_args()

    os.makedirs(f"{args.output}/src", exist_ok=True)
    os.makedirs(f"{args.output}/modules", exist_ok=True)

    if args.debug == "graph":
        ic = InterconnectBuilder(backend="graphviz")
        if 0 != ic.read_yaml(args.file):
            print_lines(ic.warns)
            print_lines(ic.errors)
            return 1

        ic.generate(outdir=args.output, view=False, display_full_name=True)
        return 0

    if args.graphview:
        args.graph = args.graphview

    if args.graph:
        ic = InterconnectBuilder(backend="graphviz")
        if 0 != ic.read_yaml(args.file):
            print_lines(ic.warns)
            print_lines(ic.errors)
            return 1

        ic.process()
        ic.generate(outdir=args.output, view=bool(args.graphview), color_by=args.colorby, color_scheme=args.colorscheme, display_full_name=args.fulldisplay)
        return 0
        
    ic = InterconnectBuilder()
    if 0 != ic.read_yaml(args.file):
        print_lines(ic.warns)
        print_lines(ic.errors)
        return 1

    if args.debug:
        if args.debug == "parse":
            ic._print_spec()
            return 0

        ic.find_routing_paths()
        ic.propagate_parameters()

        if args.debug == "elements":
            ic._print_elements()
            return 0

        return 0

    ic.process()
    ic.generate(args.output)

    return 0

