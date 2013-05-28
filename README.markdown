ASQC provides a simple command-line SPARQL query client.

The intent is that this client can be used in Unix-style pipeline operations to perform sequences of query operations that pass information as RDF (from CONSTRUCT queries) or variable bindings (from SELECT queries).

# Installation

Assumes Python 2.7 installed; not yet tested with other versions.

Installation is from Python Package Index (PyPI).

## MacOS / Linux

### Temporary installation

This option assumes that the virtualenv package (http://pypi.python.org/pypi/virtualenv) has been installed.

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

# Documentation

Right now, this is pretty much it.  For a usage summary:

    asq --help

See also the examples described below.

Currently, RDF data is supported as RDF/XML only, and SPARQL SELECT query results as JSON.  Support for other formats is on the TODO list.

## Usage

This information is displayed by "asq --help":

    Usage: 
      asq [options] [query]
      asq --help      for an options summary
      asq --examples  to display the path containing example queries

    A sparql query client, designed to be used as a filter in a command pipeline.
    Pipelined data can be RDF or query variable binding sets, depending on the
    options used.

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      --examples            display path of examples directory and exit
      -b BINDINGS, --bindings=BINDINGS
                            URI or filename of resource containing incoming query
                            variable bindings (default none). Specify '-' to use
                            stdin. This option works for SELECT queries only when
                            accessing a SPARQL endpoint.
      -e ENDPOINT, --endpoint=ENDPOINT
                            URI of SPARQL endpoint to query.
      -f FORMAT, --format=FORMAT
                            Format for input and/or output:
                            RDFXML/N3/NT/TURTLE/JSONLD/RDFA/JSON/CSV/template.
                            XML, N3, NT, TURTLE, JSONLD, RDFA apply to RDF data,
                            others apply to query variable bindings.  Multiple
                            comma-separated values may be specified; they are
                            applied to RDF or variable bindings as appropriate.
                            'template' is a python formatting template with
                            '%(var)s' for query variable 'var'.  If two values are
                            given for RDF or variable binding data, they are
                            applied to input and output respectively.  Thus:
                            RDFXML,JSON = RDF/XML and JSON result bindings;
                            RDFXML,N3 = RDF/XML input and Turtle output; etc.
      -o OUTPUT, --output=OUTPUT
                            URI or filename of RDF resource for output (default
                            stdout).Specify '-'to use stdout.
      -p PREFIX, --prefix=PREFIX
                            URI or filename of resource containing query prefixes
                            (default ~/.asqc-prefixes)
      -q QUERY, --query=QUERY
                            URI or filename of resource containing query to
                            execute. If not present, query must be supplied as
                            command line argument.
      -r RDF_DATA, --rdf-input=RDF_DATA
                            URI or filename of RDF resource to query (default
                            stdin or none). May be repeated to merge multiple
                            input resources. Specify '-' to use stdin.
      -v, --verbose         display verbose output
      --query-type=QUERY_TYPE
                            Type of query output: SELECT (variable bindings,
                            CONSTRUCT (RDF) or ASK (status).  May be used when
                            system cannot tell the kind of result by analyzing the
                            query itself.  (Currently not used)
      --format-rdf-in=FORMAT_RDF_IN
                            Format for RDF input data:
                            RDFXML/N3/NT/TURTLE/JSONLD/RDFA.
      --format-rdf-out=FORMAT_RDF_OUT
                            Format for RDF output data:
                            RDFXML/N3/NT/TURTLE/JSONLD.
      --format-var-in=FORMAT_VAR_IN
                            Format for query variable binding input data:
                            JSON/CSV.
      --format-var-out=FORMAT_VAR_OUT
                            Format for query variable binding output data:
                            JSON/CSV/template.


# Example queries

The directory "examples" contains some sample files containing queries and prefix declarations that can be used with the following commands.

To obtain the full path name of the examples directory, enter:

    asq --examples

Commands below for running the examples assume this is the current working directory.

## Query DBpedia endpoint

This example comes from the DBpedia front page.  It returns a list of musicians born in Berlin, by sending a SPARQL query to the DBpedia SPARQL endpoint.

    asq -e http://dbpedia.org/sparql -p dbpedia.prefixes -q dbpedia-musicians.sparql

Where `dbpedia-musicians.sparql` contains:

    SELECT ?name ?birth ?description ?person WHERE {
         ?person dbo:birthPlace :Berlin .
         ?person <http://purl.org/dc/terms/subject> <http://dbpedia.org/resource/Category:German_musicians> .
         ?person dbo:birthDate ?birth .
         ?person foaf:name ?name .
         ?person rdfs:comment ?description .
         FILTER (LANG(?description) = 'en') .
         }

And `dbpedia.prefixes` contains:

    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX dbpedia2: <http://dbpedia.org/property/>
    PREFIX dbpedia: <http://dbpedia.org/>
    PREFIX dbo: <http://dbpedia.org/ontology/>
    PREFIX dbc: <http://dbpedia.org/resource/Category:>
    PREFIX : <http://dbpedia.org/resource/>

## Query SKOS ontology

This example retrieves the SKOS ontology RDF file and runs the SPARQL query locally.  It returns a list of classes defined by the ontology.

    asq -r http://www.w3.org/2009/08/skos-reference/skos.rdf -p skos.prefixes \
      "SELECT DISTINCT ?c WHERE { ?c rdf:type owl:Class }"

A similar query using CONSTRUCT returns the information as an RDF graph:

    asq -r http://www.w3.org/2009/08/skos-reference/skos.rdf -p skos.prefixes \
      "CONSTRUCT { ?c rdf:type owl:Class } WHERE { ?c rdf:type owl:Class }"

## Composition of queries to different data sources

This example shows how ASQ can be used to fetch results from different sources and combine the results.  SELECT query results from one query can be used to constrain the results returned by a second query.

This example uses DBpedia and BBC Backstage SPARQL endpoints to create a list of actors from Japan who appear in BBC television programmes:

    asq -e http://dbpedia.org/sparql -p dbpedia.prefixes \
      -q dbpedia-people-from-japan.sparql \
      >dbpedia-people-from-japan.json
    asq -e http://api.talis.com/stores/bbc-backstage/services/sparql -p dbpedia.prefixes \
      -b dbpedia-people-from-japan.json \
      -q bbc-people-starring-in-television-shows.sparql

or, equivalently, piping bindings from one asq command straight to the next:

    asq -e http://dbpedia.org/sparql -p dbpedia.prefixes \
      -q dbpedia-people-from-japan.sparql | \
    asq -e http://api.talis.com/stores/bbc-backstage/services/sparql -p dbpedia.prefixes \
      -b - \
      -q bbc-people-starring-in-television-shows.sparql

Notes:

* The query to the BBC backstage endpoint can take a little time to complete (about 30 seconds)
* These queries work in part because BBC backstage makes extensive use of the DBpedia ontologies
* It is possible that this particular result could have ben obtained from BBC backstage alone, as it replicates information from DBpedia, but the example has been constructed to use information from the different endpoints.
* Joining queries in this way when sending queries to different endpoints is *not* scalable in the current implementation of ASQ: all available results are retrieved from both services, then joined in the ASQ client.  (I am thinking about possible ways to use the results from one query to limit what comes from the next.  When querying RDF resources, results from one query are used directly to constrain the results of the next query.)


