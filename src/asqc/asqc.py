#!/usr/bin/env python

"""
ASQC - A SPARQL query client - command parser and dispatcher
"""

import sys
import os
import os.path
import re
import codecs
import optparse
import logging

log = logging.getLogger(__name__)

class asqc_settings(object):
    VERSION = "v0.1"

# Make sure MiscLib can be found on path
if __name__ == "__main__":
    sys.path.append(os.path.join(sys.path[0],".."))

def run(configbase, options, args):
    status   = 0
    progname = os.path.basename(args[0])
    ### Execeute SPARQL command
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
                usage="%prog [options] [query]",
                version="%prog "+asqc_settings.VERSION)
    # version option
    parser.add_option("-q", "--query",
                      dest="query", 
                      help="URI or filename> of resource containing query to execute")
    parser.add_option("-p", "--prefix",
                      dest="prefix",
                      default="~/.asqc-prefixes",
                      help="URI or filename of resource containing query prefixes "+
                           "(default ~/.asqc-prefixes)")
    parser.add_option("-b", "--bindings",
                      dest="bindings",
                      default=None,
                      help="URI or filename of resource containing query variable bindings "+
                           "(default stdin or none)."+
                           "Specify '-'to use stdin.")
    parser.add_option("-r", "--rdf-input",
                      dest="bindings",
                      default=None,
                      help="URI or filename of RDF resource to query "+
                           "(default stdin or none)."+
                           "Specify '-'to use stdin.")
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
                      dest="output_type",
                      default=None,
                      help="Type of output: SELECT (variable bindings, CONSTRUCT (RDF) or ASK (status)")
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
    configbase = os.path.expanduser("~")
    status = runCommand(configbase, sys.argv)
    sys.exit(status)

#--------+---------+---------+---------+---------+---------+---------+---------+
