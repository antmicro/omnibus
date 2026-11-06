# Installation
## System Dependencies

Omnibus always depends on `python` and [uv](https://docs.astral.sh/uv/).  
The Graphviz (graph visualization) backend also uses `graphviz`.  

### Debian based systems
```
apt install python3 graphviz
```

## Package

Omnibus is installed with uv, either as a command line tool or into a virtual environment.

### Command line tool
```
git clone --recursive https://github.com/antmicro/omnibus
uv tool install ./omnibus/
```

### Virtual environment
```
git clone --recursive https://github.com/antmicro/omnibus
uv venv
uv pip install ./omnibus/
```

