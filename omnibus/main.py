import argparse
import os

from .interconnect import InterconnectBuilder


def main():
    argsparser = argparse.ArgumentParser(prog='omnibus')
    argsparser.add_argument('file') 
    argsparser.add_argument('-o', '--output', default="./out", help="specifies output directory") 
    argsparser.add_argument('--graph', nargs='?', const='interconnect.gv', default=None, help="show graph, takes optional filename as argument, otherwise assumes 'interconnect.gv'") 
    argsparser.add_argument('-g', '--graphview', nargs='?', const='interconnect.gv', default=None, help="like --graph but automatically displays the result in browser") 
    argsparser.add_argument('-d', '--debug', help="specify at what stage to stop execution and output debug info", choices=['parse', 'elements', 'graph']) 
    argsparser.add_argument('-c', '--colorby', default="", help="specify what parameter to color by in a graph", choices=['clock','type','role','data_width', 'id_width']) 

    args = argsparser.parse_args()

    os.makedirs(f"{args.output}/src", exist_ok=True)
    os.makedirs(f"{args.output}/modules", exist_ok=True)

    if args.debug == "graph":
        ic = InterconnectBuilder(backend="graphviz")
        ic.read_yaml(args.file)
        ic.generate(filename=f'{args.output}/interconnect.gv', view=False)
        return 0

    if args.graphview:
        args.graph = args.graphview

    if args.graph:
        ic = InterconnectBuilder(backend="graphviz")
        ic.read_yaml(args.file)
        ic.process()
        ic.generate(filename=args.graph, view=bool(args.graphview), color_by = args.colorby)
        return 0
        
    ic = InterconnectBuilder()
    ic.read_yaml(args.file)

    if args.debug:
        if args.debug == "parse":
            ic.print_spec()
            return 0

        ic.find_routing_paths()
        ic.propagate_parameters()

        if args.debug == "elements":
            ic.print_elements()
            return 0

        return 0

    ic.process()
    ic.generate(args.output)

    return 0

