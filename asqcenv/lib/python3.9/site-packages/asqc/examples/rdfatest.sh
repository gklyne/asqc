RDFAFILE=http://examples.tobyinkster.co.uk/hcard
asq -r "$RDFAFILE" -f rdfa,xml "CONSTRUCT {?s ?p ?o} WHERE { ?s ?p ?o }"
