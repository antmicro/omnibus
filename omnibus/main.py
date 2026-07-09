import argparse

from .interconnect import Interconnect


def main():
    argsparser = argparse.ArgumentParser(prog='omnibus')
    argsparser.add_argument('file') 
    argsparser.add_argument('--debug', nargs=1, help="specify at what stage to stop execution and output debug info: {'parse', 'elements', 'graph'}") 
    argsparser.add_argument('--graph', nargs='?', const='interconnect.gv', default=None, help="show graph, takes optional filename as argument, otherwise assumes 'interconnect.gv'") 

    args = argsparser.parse_args()

    ic = Interconnect(args.file)
    ic.find_routing_paths()

    if args.debug:
        if args.debug[0] == "parse":
            ic.print_spec()
            return 0
        if args.debug[0] == "elements":
            ic.print_elements()
            return 0
        if args.debug[0] == "graph":
            ic.generate_graph(filename='interconnect.gv', view=False)
            return 0

    if args.graph:
        ic.generate_graph(filename=args.graph, view=True)
        return 0

    return 0

