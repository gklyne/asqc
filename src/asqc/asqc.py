#!/usr/bin/env python

"""
ASQC - A SPARQL query client
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
import traceback

from SparqlHttpClient import SparqlHttpClient
from SparqlXmlResults import writeResultsXML

from StdoutContext import SwitchStdout
from StdinContext  import SwitchStdin

import rdflib

# Set up to use SPARQL
# rdflib.plugin.register(
#     'sparql', rdflib.query.Processor,
#     'rdfextras.sparql.processor', 'Processor')
# rdflib.plugin.register(
#     'sparql', rdflib.query.Result,
#     'rdfextras.sparql.query', 'SPARQLQueryResult')

# Register serializers (needed?)
#rdflib.plugin.register('n3', Serializer,
#         'rdflib.plugins.serializers.n3','N3Serializer')
#rdflib.plugin.register('turtle', Serializer,
#         'rdflib.plugins.serializers.turtle', 'TurtleSerializer')
#rdflib.plugin.register('nt', Serializer,
#         'rdflib.plugins.serializers.nt', 'NTSerializer')
#rdflib.plugin.register('xml', Serializer,
#         'rdflib.plugins.serializers.rdfxml', 'XMLSerializer')
#rdflib.plugin.register('pretty-xml', Serializer,
#         'rdflib.plugins.serializers.rdfxml', 'PrettyXMLSerializer')
#rdflib.plugin.register('json-ld', Serializer,
#         'rdflib.plugins.serializers.rdfxml', 'XMLSerializer')
#plugin.register('json-ld', Serializer,
#         'rdfextras.serializers.jsonld', 'JsonLDSerializer')

# Type codes and mapping for RDF and query variable p[arsing and serializing

RDFTYP = ["RDFXML","N3","TURTLE","NT","JSONLD","RDFA","HTML5"]
VARTYP = ["JSON","CSV","XML"]

RDFTYPPARSERMAP = (
    { "RDFXML": "xml"
    , "N3":     "n3"
    , "TURTLE": "n3"
    , "NT":     "nt"
    , "JSONLD": "jsonld"
    , "RDFA":   "rdfa"
    , "HTML5":  "rdfa+html"
    })

RDFTYPSERIALIZERMAP = (
    { "RDFXML": "pretty-xml"
    , "N3":     "n3"
    , "TURTLE": "turtle"
    , "NT":     "nt"
    , "JSONLD": "jsonld"
    })

# Logging object
log = logging.getLogger(__name__)

import __init__
class asqc_settings(object):
    VERSION = __init__.__version__

# Helper function for templated SPARQL results formatting and parsing

def formatBindings(template, bindings):
    """
    Return bindings formatted with supplied template
    """
    formatdict = {}
    for (var, val) in bindings.iteritems():
        formatdict[var]         = val["value"]
        if val["type"] == "bnode":
            vf = "_:%(value)s"
        elif val["type"] == "uri":
            vf = "<%(value)s>"
        elif val["type"] == "literal":
            vf = '"%(value)s"'
        elif val["type"] == "typed-literal":
            vf = '"%(value)s"^^<%(datatype)s>'
        formatdict[var+"_repr"] = vf%val
    return template.decode(encoding='string_escape')%formatdict

# Helper function for CSV formatting query result from JSON

def char_escape(c):
    if c == '"': return '""'
    if ord(c) >= 128: return r"\u" + "%04x"%ord(c)
    return c

def termToCSV(result): 
    if result == None: 
        return None
    resval = result['value']
    restyp = result['type']
    if restyp == "uri":
        return "<" + resval + ">"
    if restyp == "bnode":
        return "_:" + resval
    # strval  = '"' + resval.replace('"', '""') + '"'
    strval  = '"' + "".join([char_escape(c) for c in resval]) + '"'
    strlang = result.get('xml:lang', None)
    if restyp == "literal":
        if strlang:
            return strval + '@' + strlang
        else:
            return strval
    if restyp == "typed-literal":
        return strval + '^^' + result['datatype']
    raise rdflib.query.ResultException('Unknown term type: %s (%s)'%(term, type(term)))

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
        if t != None: res[str(var)] = t
    return res

def parseJsonTerm(d):
    """rdflib object (Literal, URIRef, BNode) for the given json-format dict.
    
    input is like:
      { 'type': 'uri', 'value': 'http://famegame.com/2006/01/username' }
      { 'type': 'bnode', 'value': '123abc456' }
      { 'type': 'literal', 'value': 'drewp' }
      { 'type': 'literal', 'value': 'drewp', xml:lang="en" }
      { 'type': 'typed-literal', 'value': '123', datatype="http://(xsd)#int" }
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

# Helper functions to form join of mutiple binding sets

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
    Resolve a URI reference against a supplied base URI and path.
    (The path is a local file system path, and may need converting to use URI conventions)
    """
    upath = urllib.pathname2url(path)
    if os.path.isdir(path) and not upath.endswith('/'):
        upath = upath + '/'
    return urlparse.urljoin(urlparse.urljoin(base, upath), uriref)

def retrieveUri(uriref):
    uri = resolveUri(uriref, "file://", os.getcwd())
    log.debug("retrievUri: %s"%(uri))
    request  = urllib2.Request(uri)
    try:
        response = urllib2.urlopen(request)
        result   = response.read()
    except:
        result = None
    return result

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
    prefixUri  = options.prefix or resolveUri(
        ".asqc-prefixes", "file://", configbase)
    if prefixUri.startswith("~"):
        prefixUri = configbase+prefixUri[1:]
    log.debug("Prefix URI %s"%(prefixUri))
    prefixes   = retrieveUri(prefixUri)
    return prefixes or defaultPrefixes

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

def getRdfData(options):
    """
    Reads RDF data from files specified using -r or from stdin
    """
    if not options.rdf_data:
        options.rdf_data = ['-']
    rdfgraph = rdflib.Graph()
    for r in options.rdf_data:
        base = ""
        if r == "-":
            rdftext = sys.stdin.read()
        else:
            log.debug("Reading RDF from %s"%(r))
            rdftext = retrieveUri(r)
            base    = r
        rdfformatdefault = RDFTYPPARSERMAP[RDFTYP[0]]
        rdfformatselect  = RDFTYPPARSERMAP.get(options.format_rdf_in, rdfformatdefault)
        try:
            log.debug("Parsing RDF format %s"%(rdfformatselect))
            if rdfformatselect == "rdfa+html":
                rdfgraph.parse(data=rdftext, format="rdfa", media_type="text/html", publicID=base)
            else:
                rdfgraph.parse(data=rdftext, format=rdfformatselect, publicID=base)
        except Exception, e:
            log.debug("RDF Parse failed: %s"%(repr(e)))
            log.debug("traceback:        %s"%(traceback.format_exc()))
            return None
    return rdfgraph

def queryRdfData(progname, options, prefixes, query, bindings):
    """
    Submit query against RDF data.
    Result is tuple of status and dictionary/list structure suitable for JSON encoding,
    or an rdflib.graph value.
    """
    rdfgraph = getRdfData(options)
    if not rdfgraph:
        print "%s: Could not read RDF data, or syntax error in input"%progname
        print "     Use -r <file> or supply RDF on stdin; specify input format if not RDF/XML"
        return (2, None)
    query = prefixes + query
    log.debug("queryRdfData query:\n%s\n"%(query))
    try:
        resps = [rdfgraph.query(query, initBindings=b) for b in bindings['results']['bindings']]
    except AssertionError, e:
        print "Query failed (query syntax problem?)"
        print "Submitted query:"
        print query
        return (2, None)
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
    if options.verbose:
        print "== Query to endpoint =="
        print query
        print "== resulttype: "+resulttype
        print "== resultjson: "+str(resultjson)
    sc = SparqlHttpClient(endpointuri=options.endpoint)
    ((status, reason), result) = sc.doQueryPOST(query, accept=resulttype, JSON=False)
    if status != 200:
        assert False, "Error from SPARQL query request: %i %s"%(status, reason)
    if options.verbose:
        print "== Query response =="
        print result
    if resultjson:
        result = json.loads(result)
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

def outputResult(progname, options, result):
    outstr = sys.stdout
    if options.output and options.output != "-":
        print "Output to other than stdout not implemented"
    if isinstance(result, rdflib.Graph):
        rdfformatdefault = RDFTYPSERIALIZERMAP[RDFTYP[0]]
        rdfformatselect  = RDFTYPSERIALIZERMAP.get(options.format_rdf_out, rdfformatdefault)
        result.serialize(destination=outstr, format=rdfformatselect, base=None)
    elif isinstance(result, str):
        outstr.write(result)
    else:
        if options.format_var_out == "JSON" or options.format_var_out == None:
            outstr.write(json.dumps(result))
            outstr.write("\n")
        elif options.format_var_out == "XML":
            writeResultsXML(outstr, result)
        elif options.format_var_out == "CSV":
            qvars = result["head"]["vars"]
            outstr.write(", ".join(qvars))
            outstr.write("\n")
            for bindings in result["results"]["bindings"]:
                vals = [ termToCSV(bindings[str(v)]) for v in qvars ]
                outstr.write(", ".join(vals))
                outstr.write("\n")
        else:
            for bindings in result["results"]["bindings"]:
                #log.debug("options.format_var_out '%s'"%(repr(options.format_var_out)))
                formattedrow = formatBindings(options.format_var_out, bindings)
                #log.debug("formattedrow '%s'"%(repr(formattedrow)))
                outstr.write(formattedrow)
    return

def run(configbase, options, args):
    status   = 0
    if options.examples:
        print "%s/examples"%(os.path.dirname(os.path.abspath(__file__)))
        return 0
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
    ## log.debug("Prefixes:\n%s\n"%(prefixes))
    bindings = getBindings(options)
    if not bindings:
        print "%s: Could not determine incoming variable bindings"%progname
        print "Run '%s --help' for more information"%progname
        return 2
    if options.verbose:
        print "== Options =="
        print repr(options)
        print "== Prefixes =="
        print prefixes
        print "== Query =="
        print query
        print "== Initial bindings =="
        print bindings
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
                usage=("\n"+
                       "  %prog [options] [query]\n"+
                       "  %prog --help      for an options summary\n"+
                       "  %prog --examples  to display the path containing example queries"),
                description="A sparql query client, designed to be used as a filter in a command pipeline. "+
                            "Pipelined data can be RDF or query variable binding sets, depending on the options used.",
                version="%prog "+asqc_settings.VERSION)
    parser.add_option("--examples",
                      action="store_true", 
                      dest="examples", 
                      default=False,
                      help="display path of examples directory and exit")
    parser.add_option("-b", "--bindings",
                      dest="bindings",
                      default=None,
                      help="URI or filename of resource containing incoming query variable bindings "+
                           "(default none). "+
                           "Specify '-' to use stdin. "+
                           "This option works for SELECT queries only when accessing a SPARQL endpoint.")
    parser.add_option("--debug",
                      action="store_true", 
                      dest="debug", 
                      default=False,
                      help="run with full debug output enabled")
    parser.add_option("-e", "--endpoint",
                      dest="endpoint",
                      default=None,
                      help="URI of SPARQL endpoint to query.")
    parser.add_option("-f", "--format",
                      dest="format",
                      default=None,
                      help="Format for input and/or output:  "+
                           "RDFXML, N3, NT, TURTLE, JSONLD, RDFA, HTML5, JSON, CSV or template.  "+
                           "XML, N3, NT, TURTLE, JSONLD, RDFA, HTML5 apply to RDF data, "+
                           "others apply to query variable bindings.  "+
                           "Multiple comma-separated values may be specified; "+
                           "they are applied to RDF or variable bindings as appropriate.  "+
                           "'template' is a python formatting template with '%(var)s' for query variable 'var'.  "+
                           "If two values are given for RDF or variable binding data, "+
                           "they are applied to input and output respectively.  "+
                           "Thus: RDFXML,JSON = RDF/XML and JSON result bindings; "+
                           "RDFXML,N3 = RDF/XML input and Turtle output; etc.")
    parser.add_option("-o", "--output",
                      dest="output",
                      default='-',
                      help="URI or filename of RDF resource for output "+
                           "(default stdout)."+
                           "Specify '-'to use stdout.")
    parser.add_option("-p", "--prefix",
                      dest="prefix",
                      default="~/.asqc-prefixes",
                      help="URI or filename of resource containing query prefixes "+
                           "(default %default)")
    parser.add_option("-q", "--query",
                      dest="query", 
                      help="URI or filename of resource containing query to execute. "+
                           "If not present, query must be supplied as command line argument.")
    parser.add_option("-r", "--rdf-input",
                      action="append",
                      dest="rdf_data",
                      default=None,
                      help="URI or filename of RDF resource to query "+
                           "(default stdin or none). "+
                           "May be repeated to merge multiple input resources. "+
                           "Specify '-' to use stdin.")
    parser.add_option("-v", "--verbose",
                      action="store_true", 
                      dest="verbose", 
                      default=False,
                      help="display verbose output")
    parser.add_option("--query-type",
                      dest="query_type",
                      default=None,
                      help="Type of query output: SELECT (variable bindings, CONSTRUCT (RDF) or ASK (status).  "+
                            "May be used when system cannot tell the kind of result by analyzing the query itself.  "+
                            "(Currently not used)")
    parser.add_option("--format-rdf-in",
                      dest="format_rdf_in",
                      default=None,
                      help="Format for RDF input data: RDFXML, N3, NT, TURTLE, JSONLD, RDFA or HTML5.  "+
                           "RDFA indicates RDFa embedded in XML (or XHTML);  "+
                           "HTML5 indicates RDFa embedded in HTML5.")
    parser.add_option("--format-rdf-out",
                      dest="format_rdf_out",
                      default=None,
                      help="Format for RDF output data: RDFXML, N3, NT, TURTLE or JSONLD.")
    parser.add_option("--format-var-in",
                      dest="format_var_in",
                      default=None,
                      help="Format for query variable binding input data: JSON or CSV.")
    parser.add_option("--format-var-out",
                      dest="format_var_out",
                      default=None,
                      help="Format for query variable binding output data: JSON, CSV or template.  "+
                           "The template option is a Python format string applied to a dictionary of query result variables.")
    # parse command line now
    (options, args) = parser.parse_args(argv)
    if len(args) < 1: parser.error("No command present")
    if len(args) > 2: parser.error("Too many arguments present: "+repr(args))
    def pick_next_format_option(s,kws):
        t = s
        for k in kws:
            if s.upper().startswith(k):
                s = s[len(k):]
                if s == "":           return (k, "")
                if s.startswith(','): return (k, s[1:])
                break
        return (t, "")
    if options.format:
        fs = options.format
        while fs:
            fn,fs = pick_next_format_option(fs, RDFTYP+VARTYP)
            if fn in RDFTYP:
                if not options.format_rdf_in:
                    options.format_rdf_in = fn
                if fn in RDFTYPSERIALIZERMAP:
                    options.format_rdf_out = fn
            else:
                if not options.format_var_in and fn in VARTYP:
                    options.format_var_in = fn
                options.format_var_out = fn
    if options.verbose:
        print "RDF graph input format:    "+repr(options.format_rdf_in)
        print "RDF graph output format:   "+repr(options.format_rdf_out)
        print "Var binding input format:  "+repr(options.format_var_in)
        print "Var binding output format: "+repr(options.format_var_out)
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
    if not options or options.debug:
        logging.basicConfig(level=logging.DEBUG)
    status = 2
    if options:
        status  = run(configbase, options, args)
    return status

def runMain():
    """
    Main program transfer function for setup.py console script
    """
    configbase = os.path.expanduser("~")
    return runCommand(configbase, sys.argv)

if __name__ == "__main__":
    """
    Program invoked from the command line.
    """
    # main program
    status = runMain()
    sys.exit(status)

#--------+---------+---------+---------+---------+---------+---------+---------+
