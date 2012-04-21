#!/usr/bin/env python

import sys
import os
import os.path
import urlparse
import urllib
import urllib2
import StringIO
import json
import re

#Use local copy of rdflib/rdfextras for testing
#if __name__ == "__main__":
#    progdir = os.path.dirname(os.path.abspath(__file__))
#    sys.path.insert(0, progdir+"/../") # Insert at front of path to override pre-installed rdflib, if any

import rdflib

# Set up to use SPARQL
rdflib.plugin.register(
    'sparql', rdflib.query.Processor,
    'rdfextras.sparql.processor', 'Processor')
rdflib.plugin.register(
    'sparql', rdflib.query.Result,
    'rdfextras.sparql.query', 'SPARQLQueryResult')

def queryRdfData(progname, options, prefixes, query, bindings):
    """
    Submit query against RDF data.
    Result is tuple of status and dictionary/list structure suitable for JSON encoding.
    """
    rdftext  = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF
          xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
          xmlns:rdfs='http://www.w3.org/2000/01/rdf-schema#'
          xmlns:ex='http://example.org/test#'
        >
          <rdf:Description rdf:about="http://example.org/test#s1">
            <ex:p1 rdf:resource="http://example.org/test#o1" />
            <ex:p2 rdf:resource="http://example.org/test#o2" />
          </rdf:Description>
          <rdf:Description rdf:about="http://example.org/test#s2">
            <ex:p3 rdf:resource="http://example.org/test#o3" />
            <ex:p4 rdf:resource="http://example.org/test#o4" />
          </rdf:Description>
        </rdf:RDF>
        """
    rdfgraph = rdflib.Graph()
    rdfgraph.parse(data=rdftext)
    query = prefixes + query
    ###print "---- Query\n"+query+"\n----"
    resp = rdfgraph.query(query)
    retrieveresponsetypenoinitbindings = resp.type
    ###print "---- retrieveresponsetypenoinitbindings: "+retrieveresponsetypenoinitbindings
    resp = rdfgraph.query(query, initBindings=bindings['results']['bindings'][0])
    retrieveresponsetypeonequery = resp.type
    ###print "---- retrieveresponsetypeonequery: "+retrieveresponsetypeonequery
    resps = [rdfgraph.query(query, initBindings=b) for b in bindings['results']['bindings']]
    retrieveresponsetype = resps[0].type
    ###print "---- retrieveresponsetype: "+retrieveresponsetype
    return (2, None)

def testQueryRdfDataSelect():
    class testOptions(object):
        rdf_data = ["test1.rdf", "test2.rdf"]
        prefix   = None
    options  = testOptions()
    prefixes = """
        PREFIX rdf:        <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs:       <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:        <http://www.w3.org/2002/07/owl#>
        PREFIX xsd:        <http://www.w3.org/2001/XMLSchema#>
        PREFIX dcterms:    <http://purl.org/dc/terms/>
        PREFIX foaf:       <http://xmlns.com/foaf/0.1/>
        PREFIX ex: <http://example.org/test#>
        """
    bindings = (
            { "head":    { "vars": ["s", "p", "o"] }
            , "results": 
              { "bindings": 
                [ { 's': rdflib.URIRef("http://example.org/test#s1")
                  }
                , { 's': rdflib.URIRef("http://example.org/test#s2")
                  , 'o': rdflib.URIRef("http://example.org/test#o4")
                  }
                , { 's': rdflib.URIRef("http://example.org/test#s3")
                  , 'p': rdflib.URIRef("http://example.org/test#p5")
                  }
                ]
              }
            })
    query = "SELECT * WHERE { ?s ?p ?o }"
    (status,result) = queryRdfData("test", options, prefixes, query, bindings)
    return

if __name__ == "__main__":
    print "testQueryRdfDataSelect.."
    testQueryRdfDataSelect()
    print "Done."

#--------+---------+---------+---------+---------+---------+---------+---------+
