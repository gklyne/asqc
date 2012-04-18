"""
Simple SPARQL HTTP protocol client
"""

import os, os.path
import sys

import re
import logging
import httplib
import urllib
import urlparse
try:
    import json
except ImportError:
    # Running Python 2.5 with simplejson?
    import simplejson as json

logger = logging.getLogger(__name__)

class SparqlHttpClient(object):
    """
    Class implements simple SPARQL HTTP protocol client
    """
    def __init__(self, endpointhost="localhost:3030", endpointpath="/ds", endpointuri=None):
        # Default SPARQL endpoint details based on Fuseki defaults
        self._endpointhost = None
        self._endpointpath = None
        self._endpointuri  = None
        self.setQueryEndpoint(endpointhost, endpointpath, endpointuri)
        return

    def setQueryEndpoint(self, endpointhost=None, endpointpath=None, endpointuri=None):
        if endpointuri:
            # assume scheme is http, no query, no fragment
            up = urlparse.urlsplit(endpointuri)
            endpointhost = up.netloc
            endpointpath = up.path
        if endpointhost: self._endpointhost = endpointhost
        if endpointpath: self._endpointpath = endpointpath
        logger.debug("setQueryEndPoint: endpointhost %s: " % self._endpointhost)
        logger.debug("setQueryEndPoint: endpointpath %s: " % self._endpointpath)

    def doQueryGET(self, query, accept="application/JSON", JSON=True):
        """
        Issue SPARQL query as HTTP GET request.
        """
        ###print "---- query "+query
        reqheaders   = {
            "Accept":       accept
            }
        hc = httplib.HTTPConnection(self._endpointhost)
        encodequery  = urllib.urlencode({"query": query})
        hc.request("GET", self._endpointpath+"?"+encodequery, None, reqheaders)
        response = hc.getresponse()
        status = response.status
        reason = response.reason
        responsedata = response.read()
        hc.close()
        ###print "---- responsedata "+responsedata
        if JSON:
            responsedata = json.loads(responsedata)
        return ((status, reason), responsedata)

    def doQueryPOST(self, query, accept="application/JSON", JSON=True):
        """
        Issue SPARQL query as HTTP POST request.
        """
        ###print "---- query "+query
        reqheaders   = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept":       accept
            }
        hc = httplib.HTTPConnection(self._endpointhost)
        encodequery  = urllib.urlencode({"query": query})
        hc.request("POST", self._endpointpath, encodequery, reqheaders)
        response = hc.getresponse()
        status = response.status
        reason = response.reason
        responsedata = response.read()
        hc.close()
        ###print "---- responsedata "+responsedata
        if JSON:
            responsedata = json.loads(responsedata)
        return ((status, reason), responsedata)

# End.
