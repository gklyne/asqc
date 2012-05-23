# This module provides an XML serializer for SPARQL results that are
# supplied as a SPARQL results structure suitable for output as JSON 

import StringIO

from xml.etree.ElementTree import Element, SubElement, ElementTree, _namespace_map

SPARQL_RESULT_NS = "http://www.w3.org/2005/sparql-results#"
XML_SCHEMA_NS    = "http://www.w3.org/2001/XMLSchema#"

def sparql_name(tag):
    return "{%s}%s" % (SPARQL_RESULT_NS, tag)

def xml_name(tag):
    return "{%s}%s" % (XML_SCHEMA_NS, tag)

def addHeader(head, root):
    headerElem = SubElement(root, sparql_name("head"))
    for var in head["vars"]:
        varElem = SubElement(headerElem, sparql_name("variable"))
        varElem.attrib["name"] = var
    return

def addBinding(var, val, result):
    bindingElem = SubElement(result, sparql_name("binding"), name=var)
    if val["type"] == "uri":
        varElem = SubElement(bindingElem, sparql_name("uri"))
    elif val["type"] == "bnode":
        varElem = SubElement(bindingElem, sparql_name("bnode"))
    elif val["type"] in ["literal","typed-literal"]:
        varElem = SubElement(bindingElem, sparql_name(u'literal'))
        if "xml:lang" in val:
            varElem.attrib[xml_name("lang")] = val["xml:lang"]
        if val["type"] == "typed-literal" and "datatype" in val:
            varElem.attrib[sparql_name("datatype")] = val["datatype"]
    varElem.text = val["value"]
    return

def addResults(results, root):
    resultsElem = SubElement(root, sparql_name("results"))
    for resultbindings in results["bindings"]:
        resultElem = SubElement(resultsElem, sparql_name("result"))
        for (var, val) in resultbindings.iteritems():
            addBinding(var, val, resultElem)
    return

# See http://effbot.org/zone/element-lib.htm#prettyprint
def indentTree(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indentTree(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def writeResultsXML(outstr, results):
    """
    Serialize query results per http://www.w3.org/TR/rdf-sparql-XMLres/
    """
    root = Element(sparql_name("sparql"))
    addHeader(results["head"], root)
    addResults(results["results"], root)
    resulttree = ElementTree(root)
    indentTree(root)
    _namespace_map[SPARQL_RESULT_NS] = ''
    outstr.write('<?xml version="1.0" encoding="utf-8"?>\n')
    outstr.write('<?xml-stylesheet type="text/xsl" href="/static/sparql-xml-to-html.xsl"?>\n')
    resulttree.write(outstr, encoding="utf-8")
    return

# End.
