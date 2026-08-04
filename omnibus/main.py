import argparse
import os

from .interconnect import Interconnect


def main():
    argsparser = argparse.ArgumentParser(prog='omnibus')
    argsparser.add_argument('file') 
    argsparser.add_argument('-o', '--output', nargs=1, default="./out", help="specifies output directory") 
    argsparser.add_argument('-d', '--debug', help="specify at what stage to stop execution and output debug info: {'parse', 'elements', 'graph'}") 
    argsparser.add_argument('-g', '--graph', nargs='?', const='interconnect.gv', default=None, help="show graph, takes optional filename as argument, otherwise assumes 'interconnect.gv'") 
    argsparser.add_argument('-c', '--colorby', default="", help="specify what parameter to color by in a graph", choices=['clock','type','role','data_width', 'id_width']) 

    args = argsparser.parse_args()

    outdir = str(args.output)
    os.makedirs(f"{outdir}/src", exist_ok=True)
    os.makedirs(f"{outdir}/modules", exist_ok=True)

    ic = Interconnect(args.file)

    if args.debug:
        if args.debug == "parse":
            ic.print_spec()
            return 0

        ic.find_routing_paths()
        ic.propagate_parameters()

        if args.debug == "elements":
            ic.print_elements()
            return 0
        if args.debug == "graph":
            ic.generate_graph(filename=f'{outdir}/interconnect.gv', view=False)
            return 0

    ic.process()

    if args.graph:
        ic.generate_graph(filename=args.graph, view=True, color_by = args.colorby)
        return 0

    ic.map_components()
    ic.generate_ip(outdir)
    ic.generate_hierarchy(outdir)

    return 0

