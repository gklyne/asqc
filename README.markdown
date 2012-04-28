This project is for a simple command-line SPARQL query client.

The plan is that the client can be used in Unix-style pipeline operations to perform sequences of query operations that pass information as RDF (from CONSTRUCT queries) or variable bindings (from SELECT queries).

# Installation

Assumes Python 2.7 installed; not yet tested with other versions.

Installation is from Python Package Index (PyPI).

## MacOS / Linux

### Temporary installation

Select working directory, then:

  virtualenv testenv
  source testenv/bin/activate
  pip install asqc

When finished, from the same directory:

  deactivate
  rm -rf testenv

### System-wide installation (needs root privileges)

  sudo pip install asqc

If older versions of rdflib and/or other utilities are installed, it may be necessary to force an upgrade, thus:

  sudo pip install --upgrade asqc
