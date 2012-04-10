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
#import re
#import codecs
import optparse
import logging

from StdoutContext import SwitchStdout
from StdinContext  import SwitchStdin

if __name__ == "__main__":
    progdir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, progdir+"/../") # Insert at front of path to override pre-installed rdflib, if any

import rdflib

log = logging.getLogger(__name__)

class asqc_settings(object):
    VERSION = "v0.1"

# Make sure MiscLib can be found on path
if __name__ == "__main__":
    sys.path.append(os.path.join(sys.path[0],".."))

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
    assert retrieveUri("http://nohost.example.org/nosuchdata") == None, retrieveUri("http://nohost.example.org/nosuchdata")
    return

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
        PREFIX xml:        <http://www.w3.org/XML/1998/namespace>
        PREFIX dcterms:    <http://purl.org/dc/terms/>
        PREFIX foaf:       <http://xmlns.com/foaf/0.1/>
        """
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
        , "results": { "bindings": [] }
        })
    if options.bindings and options.bindings != "-":
        bndtext = retrieveUri(options.bindings)
    elif options.rdf_data or options.endpoint:
        bndtext = sys.stdin.read()
    else:
        return None
    if bndtext:
        try:
            bindings  = json.loads(bndtext)
        except Exception as e:
            bindings = None
    return bindings

def testGetBindings():
    class testOptions(object):
        rdf_data = None
        bindings = None
        endpoint = None
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
    defaultBindings = (
        { "head":    { "vars": [] }
        , "results": { "bindings": [] }
        })
    #
    options  = testOptions()
    inpstr   = StringIO.StringIO(testBindings)
    bindings = getBindings(options)
    assert bindings == None
    #
    options = testOptions()
    options.rdf_data = ["test.rdfdata"]
    inpstr   = StringIO.StringIO(testBindings)
    with SwitchStdin(inpstr):
        bindings = getBindings(options)
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
    options = testOptions()
    options.endpoint = "http://example.org/"
    inpstr   = StringIO.StringIO(testBindings)
    with SwitchStdin(inpstr):
        bindings = getBindings(options)
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
    options.bindings = "test.bindings"
    bindings = getBindings(options)
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
    Assemble RDF data files 
    """
    rdfgraph = getRdfData(options)
    if not rdfgraph:
        print "%s: Could not read RDF data (use -r <file> or supply RDF on stdin)"%progname
        return (2, None)
    return (status, result)

def run(configbase, options, args):
    status   = 0
    progname = os.path.basename(args[0])
    query    = getQuery(options, args)
    if not query:
        print "%s: Could not determine query string (need query argument or -q option)"%progname
        return 2
    prefixes = getPrefixes(options)
    if not prefixes:
        print "%s: Could not determine query prefixes"%progname
        return 2
    bindings = getBindings(options)
    if not bindings:
        print "%s: Could not determine incoming variable bindings"%progname
        return 2
    if option.endpoint:
        (status,result) = queryEndpoint(progname, options, prefixes, query, bindings)
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
                      help="URI or filename of resource containing query variable bindings "+
                           "(default stdin or none). "+
                           "Specify '-' to use stdin.")
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
    status = 1
    if options:
        status  = run(configbase, options, args)
    return status

if __name__ == "__main__":
    """
    Program invoked from the command line.
    """
    # tests...
    testResolveUri()
    testRetrieveUri()
    testGetQuery()
    testGetPrefixes()
    testGetBindings()
    testGetRdfData()
    # main program
    configbase = os.path.expanduser("~")
    status = runCommand(configbase, sys.argv)
    sys.exit(status)

#--------+---------+---------+---------+---------+---------+---------+---------+
