ASQC provides a simple command-line SPARQL query client.

The intent is that this client can be used in Unix-style pipeline operations to perform sequences of query operations that pass information as RDF (from CONSTRUCT queries) or variable bindings (from SELECT queries).


== Installation ==

Assumes Python 2.7 installed; not yet tested with other versions.  Also not yet tested on systems other than Linux or MacOS.

Installation is from the Python Package Index (PyPI - http://pypi.python.org/pypi):

    pip install asqc

See the project page at github for more details (https://github.com/gklyne/asqc).


== Documentation ==

Right now, there's not much.  After installation, type:

    asq --help

for a usage summary, or see the example queries.


== Examples ==

The package includes a small number of sample queries.  See the project page at github for more details.


== Update history ==

* 0.1.1: Initial packaging
* 0.1.2: Add examples and extended README
* 0.1.3: Add support for alternative input and output formats
* 0.1.4: Add support for CSV output format for query result bindings
* 0.1.5: Add support for --debug option and diagnostics for query syntax error
* 0.1.6: Update to work with rdflib 4.0.1 and neew SPARQL 1.1 library
* 0.1.7: Support parsing of RDFa from HTML5
