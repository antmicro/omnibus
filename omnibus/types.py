# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0


class Path:
    def __init__(self, start):
        self.curport   = start
        self.startport = start
        self.crossbars = {} 


class Edge:
    def __init__(self, dest, attributes):
        self.dest       = dest
        self.attributes = attributes

class Port:
    def __init__(self, parent, attributes):
        self.parent     = parent
        self.attributes = attributes
        self.edges      = []
        self.backedges  = []


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
        self.sub_log2   = 0
        self.ports      = []

        self.address_map = []
