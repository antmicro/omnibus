# Planned Extensions

This page is accurate as of: 2026-08-18.  
It might get *slightly* out of date, especially regarding WIP features.
It will be periodically updated but always reference main part of documentation.

## General

### Muxed Buses
Status: Not started  

Buses like AHB and APB are muxed, they do not necessarily need dedicated crossbar.
Unfortunately right now this is not supported and individual protocol converters are inserted at each such port.

## Frontend 

### Python API
Status: Planning  

This frontend will provide convenient to use python interface.
Omnibus will be importable from python and via methods like `add_port()` or `verify()` will provide a way to construct an interconnect.
Primary purpose of this interface is to act as one of Topwrap's interconnect backends.

### KPM Frontend
Status: Planning  

This frontend will allow GUI to specify interconnect structure.
In similar way to Topwrap.

### YAML Verification
Status: Partially implemented  

Not all cases are properly verified, Omnibus does not always abort on erroneous input, but it does check for most problems.  

## Backend

### Verilog backend
Status: Not started  

This backend will allow Omnibus to be fully standalone without relying on Topwrap. 

### Pulp Platform 
Status: WIP  

The backend is mostly done but it does rely on some axi scripts, they do limit capabilities of address map.
Eventually they will be replaced.

## Analysis

### Latency Analysis
Status: Planning  

This feature would allow to estimate latency between ports in interconnect.

### Throughput analysis
Status: Planning  

This feature would allow to estimate throughput of interconnect.
