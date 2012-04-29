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

# Example queries

The directory Examples contains some sample files containing queriues and prefix declarations that can be used with the following commands.

## Query Dbpedia endpoint

This example comes from the Dbpedia front page.  It returns a list of musicians born in Berlin, by sending a SPARQL query to the Dbpedia SPARQL emndpoint.

    asq -e http://dbpedia.org/sparql -p dbpedia.prefixes -q dbpedia-musicians.sparql 

## Query SKOS ontology

This example retrieves the SKOS ontology RDF file and runs the SPARQL query locally.  It returns a list of classes defined by the ontology.

    asq -r http://www.w3.org/2009/08/skos-reference/skos.rdf -p skos.prefixes \
      "SELECT DISTINCT ?c WHERE { ?c rdf:type owl:Class }"

A similar query using CONSTRUCT returns the information as an RDF graph:

    asq -r http://www.w3.org/2009/08/skos-reference/skos.rdf -p skos.prefixes \
      "CONSTRUCT { ?c rdf:type owl:Class } WHERE { ?c rdf:type owl:Class }"

## Composition of queries to different data sources

This example shows how ASQ can be used to fetch results from different sources and combine the results.  SELECT query results from one query can be used to constrain the results returned by a second query.

This example uses Dbpedia and BBC Backstage SPARQL endpoints to create a list of Actors from Japan who appear in BBC television programmes:

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
* These queries work in part because BC backstage makes extensive use of the Dbpedia ontologies
* It is possible that this particular result could have ben obtained from BBC backstage alone, as it replicates information from Dbpedia, but the example has been constructed to use information from the different endpoints.
* Joining queries in this way when sending queries to different endpoints is *not* scalable n the current implementation of ASQ: all available results are retrieved from both services, then joined inthe ASQ client.  (I am thinking about possible ways to use the results from one query to limit what comes from the next.  When querying RDF resources, results from one query are used directly to constrain the results of the next query.)






