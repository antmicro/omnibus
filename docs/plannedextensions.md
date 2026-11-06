# Planned Extensions

This page is accurate as of: 2026-08-18.  
It might become out of date, especially regarding WIP features.
It will be periodically updated.
Always reference the main documentation for up-to-date information.

## General

### Muxed Buses
Status: Not started  

Buses like AHB and APB are muxed, they do not necessarily need a dedicated crossbar.
Right now, this is not supported; individual protocol converters are inserted at each such port.

## Frontend 

### Python API
Status: Planning  

This frontend will make the usage of the Python interface more convenient and user-friendly.
Omnibus will be importable from Python.
Through methods like `add_port()` or `verify()`, it will provide a way to construct an interconnect.
The primary purpose of this interface is to act as one of Topwrap's interconnect backends.

### KPM Frontend
Status: Planning  

This frontend will allow the GUI to specify the interconnect structure in similar way to Topwrap.

### YAML Verification
Status: Partially implemented  

Not all cases are properly verified; Omnibus does not always abort on erroneous input, but it does check for most problems.  

## Backend

### Verilog backend
Status: Not started  

This backend will allow Omnibus to be fully standalone without relying on Topwrap. 

### Pulp Platform 
Status: WIP  

The backend is mostly complete - however, it does rely on certain AXI scripts, which limit capabilities of the address map.
Eventually, these scripts will be replaced.

## Analysis

### Latency Analysis
Status: Planning  

This feature will allow to estimate the latency between ports in an interconnect.

### Throughput analysis
Status: Planning  

This feature will allow to estimate the throughput of an interconnect.
