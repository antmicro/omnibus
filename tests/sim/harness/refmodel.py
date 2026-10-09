# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

"""
What an Omnibus spec says the generated interconnect must do.

Port attributes (role, protocol, data width, clock) and clock frequencies are
*inputs* to the generator, so they are read through Omnibus's own frontend.
The address map is read from the spec file directly and decoded here, without
Omnibus's routing code -- expected results must not inherit its bugs.
"""

from dataclasses import dataclass, field
from pathlib import Path

import ruamel.yaml

from omnibus import InterconnectBuilder

DEFAULT_FREQUENCY = 100_000_000
# protocols the harness has memory models for; ports with others are left undriven
SUPPORTED_MANAGER_PROTOCOLS = ("axi4", "axi4lite", "apb3")


@dataclass(frozen=True)
class Port:
    name: str
    role: str  # Omnibus role: "subordinate" (an external manager drives it) or "manager"
    protocol: str
    data_width: int
    clock: str


@dataclass(frozen=True)
class Window:
    name: str
    target: str
    base: int
    size: int
    sources: tuple[str, ...]

    @property
    def end(self) -> int:
        """Exclusive end address."""
        return self.base + self.size


@dataclass
class SpecModel:
    name: str
    ports: dict[str, Port]
    clocks: dict[str, int]  # clock name -> frequency in Hz
    windows: list[Window]
    addr_width: int = 32
    unsupported: set[str] = field(default_factory=set)

    @property
    def managers(self) -> list[Port]:
        """Ports the test bench drives as an AXI manager (Omnibus role 'subordinate')."""
        return [p for p in self.ports.values() if p.role == "subordinate"]

    @property
    def memories(self) -> list[Port]:
        """Ports the test bench serves with a memory model (Omnibus role 'manager')."""
        return [
            p
            for p in self.ports.values()
            if p.role == "manager" and p.protocol in SUPPORTED_MANAGER_PROTOCOLS
        ]

    def decode(self, source: str, address: int) -> Window | None:
        """The window `source` reaches at `address`, or None where the spec maps nothing."""
        for window in self.windows:
            if window.base <= address < window.end and source in window.sources:
                return window
        return None

    def testable_windows(self, source: str) -> list[Window]:
        """Windows `source` may access whose target the harness has a model for."""
        return [
            w
            for w in self.windows
            if source in w.sources and w.target not in self.unsupported
        ]


def load(spec_path: Path) -> SpecModel:
    ic = InterconnectBuilder()
    if ic.read_yaml(str(spec_path)) != 0:
        raise ValueError(f"invalid spec {spec_path}:\n" + "\n".join(ic.errors))

    ports = {
        name: Port(
            name=name,
            role=port.attributes["role"],
            protocol=port.attributes["protocol"],
            data_width=port.attributes["data_width"],
            clock=port.attributes["clock"],
        )
        for name, port in ic.ports.items()
        if port.parent is None
    }
    clocks = {
        name: int(f)
        if isinstance(f := clk["frequency"], (int, float))
        else DEFAULT_FREQUENCY
        for name, clk in ic.clocks.items()
    }

    raw = ruamel.yaml.YAML(typ="safe").load(spec_path)
    all_sources = tuple(p.name for p in ports.values() if p.role == "subordinate")
    windows = []
    for name, entry in raw["address_map"].items():
        sources = entry.get("from", all_sources)
        windows.append(
            Window(
                name=name,
                target=entry["to"],
                base=entry["base"],
                size=entry["size"],
                sources=(sources,) if isinstance(sources, str) else tuple(sources),
            )
        )

    unsupported = {
        p.name
        for p in ports.values()
        if p.role == "manager" and p.protocol not in SUPPORTED_MANAGER_PROTOCOLS
    }
    return SpecModel(
        name=ic.name,
        ports=ports,
        clocks=clocks,
        windows=windows,
        addr_width=ic.globals.get("addr_width", 32),
        unsupported=unsupported,
    )
