#!/usr/bin/env python

"""
Module to test asqc functions

See: https://github.com/gklyne/asqc
"""

import os, os.path
import sys
import unittest
import logging
try:
    # Running Python 2.5 with simplejson?
    import simplejson as json
except ImportError:
    import json
import StringIO
import urllib
import rdflib

if __name__ == "__main__":
    # Add main project directory and ro manager directories at start of python path
    sys.path.insert(0, "../..")
    sys.path.insert(0, "..")
from MiscLib       import TestUtils
from StdoutContext import SwitchStdout
from StdinContext  import SwitchStdin
import asqc

# Logging object
log = logging.getLogger(__name__)

# Base directory for file access tests in this module
testbase = os.path.dirname(__file__)

class TestAsqc(unittest.TestCase):

    def setUp(self):
        super(TestAsqc, self).setUp()
        return

    def tearDown(self):
        super(TestAsqc, self).tearDown()
        return

    # Actual tests follow

    def testResolveUri(self):
        assert asqc.resolveUri("http://example.org/path", "http://base.example.org/base") == "http://example.org/path"
        assert asqc.resolveUri("path", "http://base.example.org/base") == "http://base.example.org/path"
        assert asqc.resolveUri("path", "file://", os.getcwd() ) == "file://"+urllib.pathname2url(os.getcwd())+"/path"
        return

    def testRetrieveUri(self):
        assert asqc.retrieveUri("test.txt") == "Test data\n"
        assert asqc.retrieveUri("file://"+urllib.pathname2url(os.getcwd())+"/test.txt") == "Test data\n"
        assert "<title>Example Domain</title>" in asqc.retrieveUri("http://example.org/nosuchdata"), \
               asqc.retrieveUri("http://example.org/nosuchdata")
        assert asqc.retrieveUri("http://nohost.example.org/nosuchdata") == None, \
               asqc.retrieveUri("http://nohost.example.org/nosuchdata")
        return

    def testQueryType(self):
        q1 = """
            prefix foo: <http://example.org/foo#>
            ask { ?s ?p ?o }
            """
        assert asqc.queryType(q1) == "ASK"
        q2 = """
            base <http://example.org/base#>
            prefix foo: <http://example.org/foo#>
            SELECT * WHERE { ?s ?p ?o }
            """
        assert asqc.queryType(q2) == "SELECT"
        q3 = """
            prefix foo: <http://example.org/foo#>
            prefix bar: <http://example.org/bar#>
            construct { ?s ?p ?o }
            """
        assert asqc.queryType(q3) == "CONSTRUCT"
        q4 = """
            prefix foo: <http://example.org/foo#>
            prefix ask: <http://example.org/ask#>
            DeScRiBe ?s where { ?s ?p ?o }
            """
        assert asqc.queryType(q4) == "DESCRIBE"
        q5 = """
            prefix foo: <http://example.org/foo#>
            prefix bar: <http://example.org/bar#>
            noquery { ?s ?p ?o }
            """
        assert asqc.queryType(q5) == None
        return

    def testGetQuery(self):
        class testOptions(object):
            verbose = False
            query   = None
        options = testOptions()
        options.query = "test.sparql"
        assert asqc.getQuery(options, ["test"]) == "SELECT * WHERE { ?s ?p ?o }\n"
        options.query = None
        assert asqc.getQuery(options, ["test", "SELECT * WHERE { ?s ?p ?o }"]) == "SELECT * WHERE { ?s ?p ?o }"
        options.query = None
        assert asqc.getQuery(options, ["test"]) == None
        return

    def testGetPrefixes(self):
        class testOptions(object):
            verbose = False
            prefix  = None
        options = testOptions()
        # named file or resource
        f = open("test.prefixes", "r")
        p = f.read()
        f.close()
        options.prefix = "test.prefixes"
        assert asqc.getPrefixes(options) == p, asqc.getPrefixes(options)
        # configured defaults
        configprefixfile = os.path.join(os.path.expanduser("~"), ".asqc-prefixes")
        f = open(configprefixfile, "r")
        p = f.read()
        f.close()
        options.prefix = None
        assert asqc.getPrefixes(options) == p, asqc.getPrefixes(options)
        return

    def testGetBindings(self):
        class testOptions(object):
            verbose  = False
            rdf_data = None
            bindings = None
            endpoint = None
        defaultBindings = (
            { "head":    { "vars": [] }
            , "results": { "bindings": [{}] }
            })
        testBindings = """
            { "head": { "vars": [ "a", "b", "c", "d", "e" ] }
            , "results":
              { "bindings":
                [ { "a": { "type": "uri",           "value": "http://example.org/a1" }
                  , "b": { "type": "bnode",         "value": "b1" }
                  , "c": { "type": "literal",       "value": "lit-c1" }
                  , "d": { "type": "typed-literal", "value": "1", "datatype": "http://www.w3.org/2001/XMLSchema#integer" }
                  , "e": { "type": "literal",       "value": "lit-c1", "xml:lang": "en" }
                  }
                , { "a": { "type": "uri",           "value": "http://example.org/a2" }
                  , "b": { "type": "bnode",         "value": "b2" }
                  , "c": { "type": "literal",       "value": "lit-c2" }
                  }
                ]
              }
            }
            """
        def checkBindings(bindings):
            xsdint = "http://www.w3.org/2001/XMLSchema#integer"
            assert bindings['head']['vars']                == [ 'a', 'b', 'c', 'd', 'e' ]
            assert bindings['results']['bindings'][0]['a'] == rdflib.URIRef("http://example.org/a1")
            assert bindings['results']['bindings'][0]['b'] == rdflib.BNode("b1")
            assert bindings['results']['bindings'][0]['c'] == rdflib.Literal("lit-c1")
            assert bindings['results']['bindings'][0]['d'] == rdflib.Literal("1", datatype=xsdint)
            assert bindings['results']['bindings'][0]['e'] == rdflib.Literal("lit-c1", lang="en")
            assert bindings['results']['bindings'][1]['a'] == rdflib.URIRef("http://example.org/a2")
            assert bindings['results']['bindings'][1]['b'] == rdflib.BNode("b2")
            assert bindings['results']['bindings'][1]['c'] == rdflib.Literal("lit-c2")
        def checkBindingsJSON(bindings):
            assert bindings['head']['vars']                == [ 'a', 'b', 'c', 'd', 'e' ]
            assert bindings['results']['bindings'][0]['a'] == { 'type': "uri",           'value': "http://example.org/a1" }
            assert bindings['results']['bindings'][0]['b'] == { 'type': "bnode",         'value': "b1" }
            assert bindings['results']['bindings'][0]['c'] == { 'type': "literal",       'value': "lit-c1" }
            assert bindings['results']['bindings'][0]['d'] == { 'type': "typed-literal", 'value': "1"
                                                              , 'datatype': "http://www.w3.org/2001/XMLSchema#integer" }
            assert bindings['results']['bindings'][0]['e'] == { 'type': "literal",       'value': "lit-c1", 'xml:lang': "en" }
            assert bindings['results']['bindings'][1]['a'] == { 'type': "uri",           'value': "http://example.org/a2" }
            assert bindings['results']['bindings'][1]['b'] == { 'type': "bnode",         'value': "b2" }
            assert bindings['results']['bindings'][1]['c'] == { 'type': "literal",       'value': "lit-c2" }
        #
        options  = testOptions()
        inpstr   = StringIO.StringIO(testBindings)
        bindings = asqc.getBindings(options)
        assert bindings == defaultBindings, repr(bindings)
        #
        options = testOptions()
        options.bindings = "-"
        options.rdf_data = ["test.rdfdata"]
        inpstr   = StringIO.StringIO(testBindings)
        with SwitchStdin(inpstr):
            bindings = asqc.getBindings(options)
            checkBindings(bindings)
        #
        options = testOptions()
        options.bindings = "-"
        options.endpoint = "http://example.org/"
        inpstr   = StringIO.StringIO(testBindings)
        with SwitchStdin(inpstr):
            bindings = asqc.getBindings(options)
            checkBindings(bindings)
        #
        options.bindings = "test.bindings"
        bindings = asqc.getBindings(options)
        checkBindings(bindings)
        return

    def testGetRdfXmlData(self):
        class testOptions(object):
            verbose        = False
            rdf_data       = None
            format_rdf_in  = None
        testRdfData = """<?xml version="1.0" encoding="UTF-8"?>
            <rdf:RDF
              xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
              xmlns:rdfs='http://www.w3.org/2000/01/rdf-schema#'
            >
              <rdf:Description>
                <rdfs:label>Example</rdfs:label>
                <rdfs:comment>This is really just an example.</rdfs:comment>
              </rdf:Description>
            </rdf:RDF>
            """
        #
        options = testOptions()
        inpstr   = StringIO.StringIO(testRdfData)
        with SwitchStdin(inpstr):
            rdfgraph = asqc.getRdfData(options)
            assert len(rdfgraph) == 2
        #
        options = testOptions()
        options.rdf_data = ["test.rdf"]
        rdfgraph = asqc.getRdfData(options)
        assert len(rdfgraph) == 2
        #
        options = testOptions()
        options.rdf_data = ["nosuchfile.rdf"]
        rdfgraph = asqc.getRdfData(options)
        assert rdfgraph == None
        #
        return

    def testGetRdfN3Data(self):
        class testOptions(object):
            verbose        = False
            rdf_data       = None
            format_rdf_in  = "N3"
        testRdfData = """
            @prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            _:s rdfs:label "Example" ;
                rdfs:comment "This is really just an example." .
            """
        #
        options = testOptions()
        inpstr   = StringIO.StringIO(testRdfData)
        with SwitchStdin(inpstr):
            rdfgraph = asqc.getRdfData(options)
            assert len(rdfgraph) == 2
        #
        options = testOptions()
        options.rdf_data = ["test.n3"]
        rdfgraph = asqc.getRdfData(options)
        assert len(rdfgraph) == 2
        #
        options = testOptions()
        options.rdf_data = ["nosuchfile.n3"]
        rdfgraph = asqc.getRdfData(options)
        assert rdfgraph == None
        #
        return

    def matchBinding(self, expect, found):
        for k in expect:
            if k not in found or expect[k] != found[k]: return False
        return True

    def assertInResult(self, binding, result, msg):
        for b in result["results"]["bindings"]:
            if self.matchBinding(binding, b): return
        assert False, "Expected binding not found: %s"%(msg)
        return

    def testQueryRdfDataSelect(self):
        class testOptions(object):
            verbose        = False
            rdf_data       = ["test1.rdf", "test2.rdf"]
            prefix         = None
            format_rdf_in  = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
        (status,result) = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 0, "queryRdfData SELECT with data status"
        log.debug("Query result: %s"%(repr(result["results"]["bindings"])))
        log.debug("- s: %s"%(result["results"]["bindings"][0]['s']))
        log.debug("- p: %s"%(result["results"]["bindings"][0]['p']))
        log.debug("- o: %s"%(result["results"]["bindings"][0]['o']))
        assert len(result["results"]["bindings"]) == 4, "queryRdfData result count"
        self.assertInResult(
                { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
                , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
                , 'o': { 'type': "uri", 'value': "http://example.org/test#o1" }
                },
                result, "queryRdfData result 1"
            )
        self.assertInResult(
                { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
                , 'p': { 'type': "uri", 'value': "http://example.org/test#p2" }
                , 'o': { 'type': "uri", 'value': "http://example.org/test#o2" }
                },
                result, "queryRdfData result 2"
            )
        self.assertInResult(
                { 's': { 'type': "uri", 'value': "http://example.org/test#s2" }
                , 'p': { 'type': "uri", 'value': "http://example.org/test#p4" }
                , 'o': { 'type': "uri", 'value': "http://example.org/test#o4" }
                },
                result, "queryRdfData result 3"
            )
        self.assertInResult(
                { 's': { 'type': "uri", 'value': "http://example.org/test#s3" }
                , 'p': { 'type': "uri", 'value': "http://example.org/test#p5" }
                , 'o': { 'type': "uri", 'value': "http://example.org/test#o5" }
                },
                result, "queryRdfData result 4"
            )
        query = "SELECT * WHERE { <http://example.org/nonesuch> ?p ?o }"
        (status,result) = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 1, "queryRdfData SELECT with no data status"
        assert len(result["results"]["bindings"]) == 0, "queryRdfData result count"
        return

    def testQueryRdfDataAsk(self):
        class testOptions(object):
            verbose        = False
            rdf_data       = ["test1.rdf", "test2.rdf"]
            prefix         = None
            format_rdf_in  = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
        query = "ASK { ?s ?p ?o }"
        (status,result) = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 0, "queryRdfData ASK with data status"
        assert result == {'head': {}, 'boolean': True}
        query = "ASK { ex:nonesuch ?p ?o }"
        (status,result) = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 1, "queryRdfData ASK with no data status"
        assert result == {'head': {}, 'boolean': False}
        return

    def testQueryRdfDataConstruct(self):
        class testOptions(object):
            verbose        = False
            rdf_data       = ["test1.rdf", "test2.rdf"]
            prefix         = None
            format_rdf_in  = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
        query    = "CONSTRUCT {?s ?p ?o } WHERE { ?s ?p ?o }"
        (status,result)   = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 0, "queryRdfData CONSTRUCT with data status"
        assert len(result) == 4, "queryRdfData triple count"
        assert ( rdflib.URIRef("http://example.org/test#s1"),
                 rdflib.URIRef("http://example.org/test#p1"),
                 rdflib.URIRef("http://example.org/test#o1") ) in result
        query    = "CONSTRUCT { <http://example.org/nonesuch> ?p ?o } WHERE { <http://example.org/nonesuch> ?p ?o }"
        (status,result)   = asqc.queryRdfData("test", options, prefixes, query, bindings)
        assert status == 1, "queryRdfData CONSTRUCT with no data status"
        assert len(result) == 0, "queryRdfData triple count"
        return

    def testQuerySparqlEndpointSelect(self):
        # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
        # containing the contents of files test1.rdf and test2.rdf.
        # (I use Jena Fuseki with default settings for testing.)
        class testOptions(object):
            verbose  = False
            endpoint = "http://localhost:3030/ds/query"
            prefix   = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
        query    = "SELECT * WHERE { ?s ?p ?o }"
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
        (status,result) = asqc.querySparqlEndpoint("test", options, prefixes, query, bindings)
        assert len(result["results"]["bindings"]) == 4, "querySparqlEndpoint result count"
        assert { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
               , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
               , 'o': { 'type': "uri", 'value': "http://example.org/test#o1" }
               } in result["results"]["bindings"], "querySparqlEndpoint result 1"
        assert { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
               , 'p': { 'type': "uri", 'value': "http://example.org/test#p2" }
               , 'o': { 'type': "uri", 'value': "http://example.org/test#o2" }
               } in result["results"]["bindings"], "querySparqlEndpoint result 2"
        assert { 's': { 'type': "uri", 'value': "http://example.org/test#s2" }
               , 'p': { 'type': "uri", 'value': "http://example.org/test#p4" }
               , 'o': { 'type': "uri", 'value': "http://example.org/test#o4" }
               } in result["results"]["bindings"], "querySparqlEndpoint result 3"
        assert { 's': { 'type': "uri", 'value': "http://example.org/test#s3" }
               , 'p': { 'type': "uri", 'value': "http://example.org/test#p5" }
               , 'o': { 'type': "uri", 'value': "http://example.org/test#o5" }
               } in result["results"]["bindings"], "querySparqlEndpoint result 4"
        return

    def testQuerySparqlEndpointAsk(self):
        # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
        # containing the contents of files test1.rdf and test2.rdf.
        # (I use Jena Fuseki with default settings for testing.)
        #   ./fuseki-server --update --mem /ds
        # Then browse to localhost:3030 to upload RDF files
        class testOptions(object):
            verbose  = False
            endpoint = "http://localhost:3030/ds/query"
            prefix   = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
        query    = "ASK { ex:s1 ?p ?o }"
        (status,result) = asqc.querySparqlEndpoint("test", options, prefixes, query, None)
        assert status == 0, "Ask success status"
        assert result == {'head': {}, 'boolean': True}
        query    = "ASK { ex:notfound ?p ?o }"
        (status,result) = asqc.querySparqlEndpoint("test", options, prefixes, query, None)
        assert status == 1, "Ask not found status"
        assert result == {'head': {}, 'boolean': False}
        return

    def testQuerySparqlEndpointConstruct(self):
        # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
        # containing the contents of files test1.rdf and test2.rdf.
        # (I use Jena Fuseki with default settings for testing.)
        #   ./fuseki-server --update --mem /ds
        # Then browse to localhost:3030 to upload RDF files
        class testOptions(object):
            verbose  = False
            endpoint = "http://localhost:3030/ds/query"
            prefix   = None
        options  = testOptions()
        prefixes = asqc.getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
        query    = "CONSTRUCT { ex:s1 ?p ?o } WHERE { ex:s1 ?p ?o }"
        (status,result) = asqc.querySparqlEndpoint("test", options, prefixes, query, None)
        assert status == 0, "Construct success status"
        assert len(result) == 2
        assert ( rdflib.URIRef("http://example.org/test#s1"),
                 rdflib.URIRef("http://example.org/test#p1"),
                 rdflib.URIRef("http://example.org/test#o1") ) in result
        query    = "CONSTRUCT { ex:notfound ?p ?o } WHERE { ex:notfound ?p ?o }"
        (status,result) = asqc.querySparqlEndpoint("test", options, prefixes, query, None)
        assert status == 1, "Construct not found status"
        return

    def testOutputResultJSON(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_var_out = None
        options  = testOptions()
        result = (
            { "head":    { "vars": ["s", "p", "o"] }
            , "results": 
              { "bindings": 
                [ { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
                  , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
                  , 'o': { 'type': "uri", 'value': "http://example.org/test#o1" }
                  }
                ]
              }
            })
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        assert """"s": {"type": "uri", "value": "http://example.org/test#s1"}""" in testtxt
        assert """"p": {"type": "uri", "value": "http://example.org/test#p1"}""" in testtxt
        assert """"s": {"type": "uri", "value": "http://example.org/test#s1"}""" in testtxt
        return

    def testOutputResultXML(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_var_out = "XML"
        options  = testOptions()
        result = (
            { "head":    { "vars": ["s", "p", "o"] }
            , "results": 
              { "bindings": 
                [ { 's': { 'type': "bnode", 'value': "nodeid" }
                  , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
                  , 'o': { 'type': "literal", 'value': "literal string" }
                  }
                ]
              }
            })
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        log.debug("testOutputResultXML \n"+testtxt)
        assert """<binding name="s">""" in testtxt
        assert """<bnode>nodeid</bnode>""" in testtxt
        assert """<binding name="p">""" in testtxt
        assert """<uri>http://example.org/test#p1</uri>""" in testtxt
        assert """<binding name="o">""" in testtxt
        assert """<literal>literal string</literal>""" in testtxt
        return

    def testOutputResultCSV(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_var_out = "CSV"
        options  = testOptions()
        result = (
            { "head":    { "vars": ["s", "p", "o"] }
            , "results": 
              { "bindings": 
                [ { 's': { 'type': "bnode", 'value': "nodeid" }
                  , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
                  , 'o': { 'type': "literal", 'value': """literal '"' '\u00e9' string""" }
                  }
                ]
              }
            })
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        log.debug("testOutputResultCSV \n"+testtxt)
        log.debug("testOutputResultCSV \n"+repr(testtxt))
        assert """s, p, o""" in testtxt
        assert r'''_:nodeid, <http://example.org/test#p1>, "literal '""' '\u00e9' string"''' in testtxt
        return

    def testOutputResultTemplate(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_var_out = "s: %(s_repr)s p: <%(p)s> o: %(o_repr)s ."
        options  = testOptions()
        result = (
            { "head":    { "vars": ["s", "p", "o"] }
            , "results": 
              { "bindings": 
                [ { 's': { 'type': "bnode", 'value': "nodeid" }
                  , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
                  , 'o': { 'type': "literal", 'value': "literal string" }
                  }
                ]
              }
            })
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        log.debug("testOutputResultTemplate \n"+testtxt)
        assert """s: _:nodeid p: <http://example.org/test#p1> o: "literal string" .""" in testtxt
        return

    def testOutputResultRDFXML(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_rdf_out = None
        options  = testOptions()
        result = rdflib.Graph()
        result.add(
            ( rdflib.URIRef("http://example.org/test#s1")
            , rdflib.URIRef("http://example.org/test#p1")
            , rdflib.URIRef("http://example.org/test#o1")
            ) )
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        assert """<rdf:Description rdf:about="http://example.org/test#s1">""" in testtxt
        return

    def testOutputResultRDFN3(self):
        class testOptions(object):
            verbose        = False
            output         = None
            format_rdf_out = "N3"
        options  = testOptions()
        result = rdflib.Graph()
        result.add(
            ( rdflib.URIRef("http://example.org/test#s1")
            , rdflib.URIRef("http://example.org/test#p1")
            , rdflib.URIRef("http://example.org/test#o1")
            ) )
        teststr = StringIO.StringIO()
        with SwitchStdout(teststr):
            asqc.outputResult("asqc", options, result)
            testtxt = teststr.getvalue()
        log.debug("testOutputResultRDFN3 \n"+testtxt)
        assert """ns1:s1 ns1:p1 ns1:o1 .""" in testtxt
        return

    # Sentinel/placeholder tests

    def testUnits(self):
        assert (True)

    def testComponents(self):
        assert (True)

    def testIntegration(self):
        assert (True)

    def testPending(self):
        assert (False), "Pending tests follow"

# Assemble test suite

def getTestSuite(select="unit"):
    """
    Get test suite

    select  is one of the following:
            "unit"      return suite of unit tests only
            "component" return suite of unit and component tests
            "all"       return suite of unit, component and integration tests
            "pending"   return suite of pending tests
            name        a single named test to be run
    """
    testdict = {
        "unit":
            [ "testUnits"
            , "testResolveUri"
            , "testQueryType"
            , "testGetQuery"
            , "testGetPrefixes"
            , "testGetBindings"
            , "testGetRdfXmlData"
            , "testGetRdfN3Data"
            , "testQueryRdfDataSelect"
            , "testQueryRdfDataAsk"
            , "testQueryRdfDataConstruct"
            , "testOutputResultJSON"
            , "testOutputResultXML"
            , "testOutputResultCSV"
            , "testOutputResultTemplate"
            , "testOutputResultRDFXML"
            , "testOutputResultRDFN3"
            ],
        "component":
            [ "testComponents"
            ],
        "integration":
            [ "testIntegration"
            , "testRetrieveUri"                     # Needs Internet access to example.org
            , "testQuerySparqlEndpointSelect"       # Needs fuseki running with test data
            , "testQuerySparqlEndpointAsk"          # Needs fuseki running with test data
            , "testQuerySparqlEndpointConstruct"    # Needs fuseki running with test data
            ],
        "pending":
            [ "testPending"
            ]
        }
    return TestUtils.getTestSuite(TestAsqc, testdict, select=select)

if __name__ == "__main__":
    TestUtils.runTests("TestAsqc.log", getTestSuite, sys.argv)

# End.
