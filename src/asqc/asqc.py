#!/usr/bin/env python

"""
ASQC - A SPARQL query client - command parser and dispatcher
"""

import sys
import os
import os.path
import urlparse
import urllib
import urllib2
import StringIO
import json
import re
import optparse
import logging

from SparqlHttpClient import SparqlHttpClient

from StdoutContext import SwitchStdout
from StdinContext  import SwitchStdin

import rdflib

# Set up to use SPARQL
rdflib.plugin.register(
    'sparql', rdflib.query.Processor,
    'rdfextras.sparql.processor', 'Processor')
rdflib.plugin.register(
    'sparql', rdflib.query.Result,
    'rdfextras.sparql.query', 'SPARQLQueryResult')

# Logging object
log = logging.getLogger(__name__)

class asqc_settings(object):
    VERSION = "v0.1"

# Helper functions for JSON formatting and parsing
# Mostly copied from rdflib SPARQL code (rdfextras/sparql/results/jsonresults)

def termToJSON(term): 
    if isinstance(term, rdflib.URIRef): 
        return { 'type': 'uri', 'value': str(term) }
    elif isinstance(term, rdflib.Literal):
        if term.datatype!=None:
            return { 'type': 'typed-literal', 
                     'value': unicode(term), 
                     'datatype': str(term.datatype) }
        else:
            r={'type': 'literal',
               'value': unicode(term) }
            if term.language!=None:
                r['xml:lang']=term.language
            return r
    elif isinstance(term, rdflib.BNode):
        return { 'type': 'bnode', 'value': str(term) }
    elif term==None: 
        return None
    else: 
        raise rdflib.query.ResultException('Unknown term type: %s (%s)'%(term, type(term)))

def bindingToJSON(binding):
    res={}
    for var in binding: 
        t = termToJSON(binding[var])
        if t != None: res[var] = t
    return res

def parseJsonTerm(d):
    """rdflib object (Literal, URIRef, BNode) for the given json-format dict.
    
    input is like:
      { 'type': 'uri', 'value': 'http://famegame.com/2006/01/username' }
      { 'type': 'literal', 'value': 'drewp' }
    """
    
    t = d['type']
    if t == 'uri':
        return rdflib.URIRef(d['value'])
    elif t == 'literal':
        if 'xml:lang' in d: 
            return rdflib.Literal(d['value'], lang=d['xml:lang'])
        return rdflib.Literal(d['value'])
    elif t == 'typed-literal':
        return rdflib.Literal(d['value'], datatype=rdflib.URIRef(d['datatype']))
    elif t == 'bnode': 
        return rdflib.BNode(d['value'])
    else:
        raise NotImplementedError("json term type %r" % t)

def parseJsonBindings(bindings):
    newbindings = []
    for row in bindings:
        outRow = {}
        for k, v in row.items():
            outRow[k] = parseJsonTerm(v)
        newbindings.append(outRow)
    return newbindings

# Helper functions to form join(?) of mutiple binding sets

def joinBinding(result_binding, constraint_binding):
    for k in result_binding:
        if k in constraint_binding:
            if result_binding[k] != constraint_binding[k]:
                return None
    joined_binding = result_binding.copy()
    joined_binding.update(constraint_binding)
    return joined_binding

def joinBindings(result_bindings, constraint_bindings):
    return [ bj 
             for bj in [ joinBinding(b1, b2) for b1 in result_bindings for b2 in constraint_bindings ]
             if bj ]

def joinBindingsToJSON(result_bindings, constraint_bindings):
    return [ bindingToJSON(bj) 
             for bj in [ joinBinding(b1, b2) for b1 in result_bindings for b2 in constraint_bindings ]
             if bj ]

# Helper functions for accessing data at URI reference, which may be a path relative to current directory

def resolveUri(uriref, base, path=""):
    """
    Resolve a URI reference against a supplied basae URI and path.
    (The path is a local file system path, and may need convertting to use URI conventions)
    """
    upath = urllib.pathname2url(path)
    if os.path.isdir(path) and not upath.endswith('/'):
        upath = upath + '/'
    return urlparse.urljoin(urlparse.urljoin(base, upath), uriref)

def testResolveUri():
    assert resolveUri("http://example.org/path", "http://base.example.org/base") == "http://example.org/path"
    assert resolveUri("path", "http://base.example.org/base") == "http://base.example.org/path"
    assert resolveUri("path", "file://", os.getcwd() ) == "file://"+urllib.pathname2url(os.getcwd())+"/path"
    return

def retrieveUri(uriref):
    uri = resolveUri(uriref, "file://", os.getcwd())
    request  = urllib2.Request(uri)
    try:
        response = urllib2.urlopen(request)
        result   = response.read()
    except:
        result = None
    return result

def testRetrieveUri():
    assert retrieveUri("test.txt") == "Test data\n"
    assert retrieveUri("file://"+urllib.pathname2url(os.getcwd())+"/test.txt") == "Test data\n"
    assert "<title>IANA &mdash; Example domains</title>" in retrieveUri("http://example.org/nosuchdata"), \
           retrieveUri("http://example.org/nosuchdata")
    assert retrieveUri("http://nohost.example.org/nosuchdata") == None, \
           retrieveUri("http://nohost.example.org/nosuchdata")
    return

# Helper function for determining type of query

def queryType(query):
    """
    Returns "ASK", "SELECT", "CONSTRUCT", "DESCRIBE" or None
    """
    iriregex    = "<[^>]*>"
    baseregex   = ".*base.*"+iriregex
    prefixregex = ".*prefix.*"+iriregex
    queryregex  = "^("+baseregex+")?("+prefixregex+")*.*(ask|select|construct|describe).*$"
    match = re.match(queryregex, query, flags=re.IGNORECASE|re.DOTALL)
    if match:
        return match.group(3).upper()
    return None

def testQueryType():
    q1 = """
        prefix foo: <http://example.org/foo#>
        ask { ?s ?p ?o }
        """
    assert queryType(q1) == "ASK"
    q2 = """
        base <http://example.org/base#>
        prefix foo: <http://example.org/foo#>
        SELECT * WHERE { ?s ?p ?o }
        """
    assert queryType(q2) == "SELECT"
    q3 = """
        prefix foo: <http://example.org/foo#>
        prefix bar: <http://example.org/bar#>
        construct { ?s ?p ?o }
        """
    assert queryType(q3) == "CONSTRUCT"
    q4 = """
        prefix foo: <http://example.org/foo#>
        prefix ask: <http://example.org/ask#>
        DeScRiBe ?s where { ?s ?p ?o }
        """
    assert queryType(q4) == "DESCRIBE"
    q5 = """
        prefix foo: <http://example.org/foo#>
        prefix bar: <http://example.org/bar#>
        noquery { ?s ?p ?o }
        """
    assert queryType(q5) == None
    return

# Main program functions

def getQuery(options, args):
    """
    Get query string from command line option or argument.
    """
    if options.query:
        return retrieveUri(options.query)
    elif len(args) >= 2:
        return args[1]
    return None

def testGetQuery():
    class testOptions(object):
        query = None
    options = testOptions()
    options.query = "test.sparql"
    assert getQuery(options, ["test"]) == "SELECT * WHERE { ?s ?p ?o }\n"
    options.query = None
    assert getQuery(options, ["test", "SELECT * WHERE { ?s ?p ?o }"]) == "SELECT * WHERE { ?s ?p ?o }"
    options.query = None
    assert getQuery(options, ["test"]) == None
    return

def getPrefixes(options):
    """
    Get prefix string from command line option.
    """
    defaultPrefixes = """
        PREFIX rdf:        <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs:       <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:        <http://www.w3.org/2002/07/owl#>
        PREFIX xsd:        <http://www.w3.org/2001/XMLSchema#>
        PREFIX dcterms:    <http://purl.org/dc/terms/>
        PREFIX foaf:       <http://xmlns.com/foaf/0.1/>
        """
    #    PREFIX xml:        <http://www.w3.org/XML/1998/namespace>
    configbase = os.path.expanduser("~")
    prefixUri  = options.prefix or resolveUri(".asqc-prefixes", "file://", configbase)
    prefixes   = retrieveUri(prefixUri)
    return prefixes or defaultPrefixes

def testGetPrefixes():
    class testOptions(object):
        prefix = None
    options = testOptions()
    # named file or resource
    f = open("test.prefixes", "r")
    p = f.read()
    f.close()
    options.prefix = "test.prefixes"
    assert getPrefixes(options) == p, getPrefixes(options)
    # configured defaults
    configprefixfile = os.path.join(os.path.expanduser("~"), ".asqc-prefixes")
    f = open(configprefixfile, "r")
    p = f.read()
    f.close()
    options.prefix = None
    assert getPrefixes(options) == p, getPrefixes(options)
    return

def getBindings(options):
    bndtext  = None
    bindings = (
        { "head":    { "vars": [] }
        , "results": { "bindings": [{}] }
        })
    if options.bindings and options.bindings != "-":
        bndtext = retrieveUri(options.bindings)
    elif options.bindings == "-":
        if options.rdf_data or options.endpoint:
            bndtext = sys.stdin.read()
        else:
            # Can't read bindings from stdin if trying to read RDF from stdin
            return None
    else:
        bndtext = None
    if bndtext:
        try:
            bindings = json.loads(bndtext)
            bindings['results']['bindings'] = parseJsonBindings(bindings['results']['bindings'])
        except Exception as e:
            bindings = None
    return bindings

def testGetBindings():
    class testOptions(object):
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
    bindings = getBindings(options)
    assert bindings == defaultBindings, repr(bindings)
    #
    options = testOptions()
    options.bindings = "-"
    options.rdf_data = ["test.rdfdata"]
    inpstr   = StringIO.StringIO(testBindings)
    with SwitchStdin(inpstr):
        bindings = getBindings(options)
        checkBindings(bindings)
    #
    options = testOptions()
    options.bindings = "-"
    options.endpoint = "http://example.org/"
    inpstr   = StringIO.StringIO(testBindings)
    with SwitchStdin(inpstr):
        bindings = getBindings(options)
        checkBindings(bindings)
    #
    options.bindings = "test.bindings"
    bindings = getBindings(options)
    checkBindings(bindings)
    return

def getRdfData(options):
    """
    Reads RDF data from files specified using -r or from stdin
    """
    if not options.rdf_data:
        options.rdf_data = ['-']
    rdfgraph = rdflib.Graph()
    for r in options.rdf_data:
        if r == "-":
            rdftext = sys.stdin.read()
        else:
            rdftext = retrieveUri(r)
        try:
            rdfgraph.parse(data=rdftext)
        except Exception, e:
            return None
    return rdfgraph

def testGetRdfData():
    class testOptions(object):
        rdf_data = None
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
        rdfgraph = getRdfData(options)
        assert len(rdfgraph) == 2
    #
    options = testOptions()
    options.rdf_data = ["test.rdf"]
    rdfgraph = getRdfData(options)
    assert len(rdfgraph) == 2
    #
    options = testOptions()
    options.rdf_data = ["nosuchfile.rdf"]
    rdfgraph = getRdfData(options)
    assert rdfgraph == None
    #
    return

def queryRdfData(progname, options, prefixes, query, bindings):
    """
    Submit query against RDF data.
    Result is tuple of status and dictionary/list structure suitable for JSON encoding.
    """
    rdfgraph = getRdfData(options)
    if not rdfgraph:
        print "%s: Could not read RDF data (use -r <file> or supply RDF on stdin)"%progname
        return (2, None)
    query = prefixes + query
    resps = [rdfgraph.query(query, initBindings=b) for b in bindings['results']['bindings']]
    #for b in bindings['results']['bindings']:
    #    resp = rdfgraph.query(query, initBindings=b)
    #    resps.append(resp)
    res = { "head": {} }
    if resps[0].type == 'ASK':
        res["boolean"] = any([ r.askAnswer for r in resps ])
        return (0 if res["boolean"] else 1, res)
    elif resps[0].type == 'SELECT':
        res["head"]["vars"] = resps[0].vars
        res["results"] = {}
        res["results"]["bindings"] = [ bindingToJSON(b) for r in resps for b in r.bindings ]
        return (0 if len(res["results"]["bindings"]) > 0 else 1, res)
    elif resps[0].type == 'CONSTRUCT':
        res = rdflib.graph.ReadOnlyGraphAggregate( [r.graph for r in resps] )
        return (0 if len(res) > 0 else 1, res)
    else:
        assert False, "Unexpected query response type %s"%resp.type
    return (2, None)

def testQueryRdfDataSelect():
    class testOptions(object):
        rdf_data = ["test1.rdf", "test2.rdf"]
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
    assert status == 0, "queryRdfData SELECT with data status"
    assert len(result["results"]["bindings"]) == 4, "queryRdfData result count"
    assert { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
           , 'p': { 'type': "uri", 'value': "http://example.org/test#p1" }
           , 'o': { 'type': "uri", 'value': "http://example.org/test#o1" }
           } in result["results"]["bindings"], "queryRdfData result 1"
    assert { 's': { 'type': "uri", 'value': "http://example.org/test#s1" }
           , 'p': { 'type': "uri", 'value': "http://example.org/test#p2" }
           , 'o': { 'type': "uri", 'value': "http://example.org/test#o2" }
           } in result["results"]["bindings"], "queryRdfData result 2"
    assert { 's': { 'type': "uri", 'value': "http://example.org/test#s2" }
           , 'p': { 'type': "uri", 'value': "http://example.org/test#p4" }
           , 'o': { 'type': "uri", 'value': "http://example.org/test#o4" }
           } in result["results"]["bindings"], "queryRdfData result 3"
    assert { 's': { 'type': "uri", 'value': "http://example.org/test#s3" }
           , 'p': { 'type': "uri", 'value': "http://example.org/test#p5" }
           , 'o': { 'type': "uri", 'value': "http://example.org/test#o5" }
           } in result["results"]["bindings"], "queryRdfData result 4"
    query = "SELECT * WHERE { <http://example.org/nonesuch> ?p ?o }"
    (status,result) = queryRdfData("test", options, prefixes, query, bindings)
    assert status == 1, "queryRdfData SELECT with no data status"
    assert len(result["results"]["bindings"]) == 0, "queryRdfData result count"
    return

def testQueryRdfDataAsk():
    class testOptions(object):
        rdf_data = ["test1.rdf", "test2.rdf"]
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
    (status,result) = queryRdfData("test", options, prefixes, query, bindings)
    assert status == 0, "queryRdfData ASK with data status"
    assert result == {'head': {}, 'boolean': True}
    query = "ASK { ex:nonesuch ?p ?o }"
    (status,result) = queryRdfData("test", options, prefixes, query, bindings)
    assert status == 1, "queryRdfData ASK with no data status"
    assert result == {'head': {}, 'boolean': False}
    return

def testQueryRdfDataConstruct():
    class testOptions(object):
        rdf_data = ["test1.rdf", "test2.rdf"]
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
    (status,result)   = queryRdfData("test", options, prefixes, query, bindings)
    assert status == 0, "queryRdfData CONSTRUCT with data status"
    assert len(result) == 4, "queryRdfData triple count"
    assert ( rdflib.URIRef("http://example.org/test#s1"),
             rdflib.URIRef("http://example.org/test#p1"),
             rdflib.URIRef("http://example.org/test#o1") ) in result
    query    = "CONSTRUCT { <http://example.org/nonesuch> ?p ?o } WHERE { <http://example.org/nonesuch> ?p ?o }"
    (status,result)   = queryRdfData("test", options, prefixes, query, bindings)
    assert status == 1, "queryRdfData CONSTRUCT with no data status"
    assert len(result) == 0, "queryRdfData triple count"
    return

def querySparqlEndpoint(progname, options, prefixes, query, bindings):
    """
    Issue SPARQL query to SPARQL HTTP endpoint.
    Requests either JSON or RDF/XML depending on query type.
    Returns JSON-like dictionary/list structure or RDF graph, depending on query type.
    These are used as basis for result formatting by outputResult function
    """
    query = prefixes + query
    resulttype = "application/RDF+XML"
    resultjson = False
    querytype  = queryType(query) 
    if querytype in ["ASK", "SELECT"]:
        # NOTE application/json doesn't work with Fuseki
        # See: http://gearon.blogspot.co.uk/2011/09/sparql-json-after-commenting-other-day.html
        resulttype = "application/sparql-results+json"
        resultjson = True
    sc = SparqlHttpClient(endpointuri=options.endpoint)
    ((status, reason), result) = sc.doQueryPOST(query, accept=resulttype, JSON=resultjson)
    if status != 200:
        assert False, "Error from SPARQL query request: %i %s"%(status, reason)
    status = 1
    if querytype == "SELECT":
        result['results']['bindings'] = parseJsonBindings(result['results']['bindings'])
        result['results']['bindings'] = joinBindingsToJSON(
                                            result['results']['bindings'], 
                                            bindings['results']['bindings'])
        if result['results']['bindings']: status = 0
    elif bindings:
        assert False, "Can't use supplied bindings with endpoint query other than SELECT"
    elif querytype == "ASK":
        # Just return JSON from Sparql query
        if result['boolean']: status = 0
    else:
        # return RDF
        rdfgraph = rdflib.Graph()
        try:
            # Note: declaring xml prefix in SPAQL query can result in invalid XML from Fuseki (v2.1)
            # See: https://issues.apache.org/jira/browse/JENA-24
            rdfgraph.parse(data=result)
            result = rdfgraph   # Return parsed RDF graph
            if len(result) > 0: status = 0
        except Exception, e:
            assert False, "Error parsing RDF from SPARQL endpoint query: "+str(e)
    return (status, result)

def testQuerySparqlEndpointSelect():
    # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
    # containing the contents of files test1.rdf and test2.rdf.
    # (I use Jena Fuseki with default settings for testing.)
    class testOptions(object):
        endpoint = "http://localhost:3030/ds/query"
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
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
    (status,result)   = querySparqlEndpoint("test", options, prefixes, query, bindings)
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

def testQuerySparqlEndpointAsk():
    # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
    # containing the contents of files test1.rdf and test2.rdf.
    # (I use Jena Fuseki with default settings for testing.)
    class testOptions(object):
        endpoint = "http://localhost:3030/ds/query"
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
    query    = "ASK { ex:s1 ?p ?o }"
    (status,result)   = querySparqlEndpoint("test", options, prefixes, query, None)
    assert status == 0, "Ask success status"
    assert result == {'head': {}, 'boolean': True}
    query    = "ASK { ex:notfound ?p ?o }"
    (status,result)   = querySparqlEndpoint("test", options, prefixes, query, None)
    assert status == 1, "Ask not found status"
    assert result == {'head': {}, 'boolean': False}
    return

def testQuerySparqlEndpointConstruct():
    # This test assumes a SPARQL endpoint running at http://localhost:3030/ds/query 
    # containing the contents of files test1.rdf and test2.rdf.
    # (I use Jena Fuseki with default settings for testing.)
    class testOptions(object):
        endpoint = "http://localhost:3030/ds/query"
        prefix   = None
    options  = testOptions()
    prefixes = getPrefixes(options)+"PREFIX ex: <http://example.org/test#>\n"
    query    = "CONSTRUCT { ex:s1 ?p ?o } WHERE { ex:s1 ?p ?o }"
    (status,result)   = querySparqlEndpoint("test", options, prefixes, query, None)
    assert status == 0, "Construct success status"
    assert len(result) == 2
    assert ( rdflib.URIRef("http://example.org/test#s1"),
             rdflib.URIRef("http://example.org/test#p1"),
             rdflib.URIRef("http://example.org/test#o1") ) in result
    query    = "CONSTRUCT { ex:notfound ?p ?o } WHERE { ex:notfound ?p ?o }"
    (status,result)   = querySparqlEndpoint("test", options, prefixes, query, None)
    assert status == 1, "Construct not found status"
    return

def outputResult(progname, options, result):
    outstr = sys.stdout
    if options.output and options.output != "-":
        print "Output to other than stdout not implemented"
    if isinstance(result, rdflib.Graph):
        result.serialize(destination=outstr, format="pretty-xml", base=None)
    elif isinstance(result, str):
        outstr.write(result)
    else:
        outstr.write(json.dumps(result))
        outstr.write("\n")
    return

def testOutputResultJSON():
    class testOptions(object):
        output = None
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
        outputResult("asqc", options, result)
        testtxt = teststr.getvalue()
    assert """"s": {"type": "uri", "value": "http://example.org/test#s1"}""" in testtxt
    assert """"p": {"type": "uri", "value": "http://example.org/test#p1"}""" in testtxt
    assert """"s": {"type": "uri", "value": "http://example.org/test#s1"}""" in testtxt
    return

def testOutputResultRDFXML():
    class testOptions(object):
        output = None
    options  = testOptions()
    result = rdflib.Graph()
    result.add(
        ( rdflib.URIRef("http://example.org/test#s1")
        , rdflib.URIRef("http://example.org/test#p1")
        , rdflib.URIRef("http://example.org/test#o1")
        ) )
    teststr = StringIO.StringIO()
    with SwitchStdout(teststr):
        outputResult("asqc", options, result)
        testtxt = teststr.getvalue()
    assert """<rdf:Description rdf:about="http://example.org/test#s1">""" in testtxt
    return

def run(configbase, options, args):
    if options.runtests:
        runTests()
        return 0
    status   = 0
    progname = os.path.basename(args[0])
    query    = getQuery(options, args)
    if not query:
        print "%s: Could not determine query string (need query argument or -q option)"%progname
        print "Run '%s --help' for more information"%progname
        return 2
    prefixes = getPrefixes(options)
    if not prefixes:
        print "%s: Could not determine query prefixes"%progname
        print "Run '%s --help' for more information"%progname
        return 2
    bindings = getBindings(options)
    if not bindings:
        print "%s: Could not determine incoming variable bindings"%progname
        print "Run '%s --help' for more information"%progname
        return 2
    if options.endpoint:
        (status,result) = querySparqlEndpoint(progname, options, prefixes, query, bindings)
    else:
        (status,result) = queryRdfData(progname, options, prefixes, query, bindings)
    if result:
        outputResult(progname, options, result)
    return status

def parseCommandArgs(argv):
    """
    Parse command line arguments
    
    argv -- argument list from command line
    
    Returns a pair consisting of options specified as returned by
    OptionParser, and any remaining unparsed arguments.
    """
    # create a parser for the command line options
    parser = optparse.OptionParser(
                usage="%prog [options] [query]\n%prog --help  for option summary",
                description="A sparql query client, designed to be used as a filter in a command pieline. "+
                            "Pipelined data can be RDF or query variable binding sets, depending on the options used.",
                version="%prog "+asqc_settings.VERSION)
    parser.add_option("-q", "--query",
                      dest="query", 
                      help="URI or filename of resource containing query to execute. "+
                           "If not present, query must be supplied as command line argument.")
    parser.add_option("-p", "--prefix",
                      dest="prefix",
                      default="~/.asqc-prefixes",
                      help="URI or filename of resource containing query prefixes "+
                           "(default %default)")
    parser.add_option("-b", "--bindings",
                      dest="bindings",
                      default=None,
                      help="URI or filename of resource containing incoming query variable bindings "+
                           "(default none). "+
                           "Specify '-' to use stdin. "+
                           "This option works for SELECT queries only when accessing a SPARQL endpoint.")
    parser.add_option("-r", "--rdf-input",
                      action="append",
                      dest="rdf_data",
                      default=None,
                      help="URI or filename of RDF resource to query "+
                           "(default stdin or none). "+
                           "May be repeated to merge multiple input resources. "+
                           "Specify '-' to use stdin.")
    parser.add_option("-e", "--endpoint",
                      dest="endpoint",
                      default=None,
                      help="URI of SPARQL endpoint to query ")
    parser.add_option("-o", "--output",
                      dest="output",
                      default='-',
                      help="URI or filename of RDF resource for output "+
                           "(default stdout)."+
                           "Specify '-'to use stdout.")
    parser.add_option("-t", "--type",
                      dest="query_type",
                      default=None,
                      help="Type of query output: SELECT (variable bindings, CONSTRUCT (RDF) or ASK (status)")
    parser.add_option("-v", "--verbose",
                      action="store_true", 
                      dest="verbose", 
                      default=False,
                      help="display verbose output")
    parser.add_option("--test",
                      action="store_true", 
                      dest="runtests", 
                      default=False,
                      help="Run tests")
    # parse command line now
    (options, args) = parser.parse_args(argv)
    if len(args) < 1: parser.error("No command present")
    if len(args) > 2: parser.error("Too many arguments present: "+repr(args))
    return (options, args)

def runCommand(configbase, argv):
    """
    Run program with supplied configuration base directory, Base directory 
    from which to start looking for research objects, and arguments.
    
    This is called by main function (below), and also by test suite routines.
    
    Returns exit status.
    """
    log.debug("runCommand: configbase %s, argv %s"%(configbase, repr(argv)))
    (options, args) = parseCommandArgs(argv)
    status = 2
    if options:
        status  = run(configbase, options, args)
    return status

def runTests():
    print "Running tests..."
    testResolveUri()
    testRetrieveUri()                   # Needs Internet access to example.org
    testQueryType()
    testGetQuery()
    testGetPrefixes()
    testGetBindings()
    testGetRdfData()
    testQueryRdfDataSelect()
    testQueryRdfDataAsk()
    testQueryRdfDataConstruct()
    testQuerySparqlEndpointSelect()     # Needs fuseki running with test data
    testQuerySparqlEndpointAsk()        # Needs fuseki running with test data
    testQuerySparqlEndpointConstruct()  # Needs fuseki running with test data
    testOutputResultJSON()
    testOutputResultRDFXML()
    print "Done."
    return

if __name__ == "__main__":
    """
    Program invoked from the command line.
    """
    # main program
    configbase = os.path.expanduser("~")
    status = runCommand(configbase, sys.argv)
    sys.exit(status)

#--------+---------+---------+---------+---------+---------+---------+---------+
