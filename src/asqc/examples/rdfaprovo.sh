RDFAFILE=http://dvcs.w3.org/hg/prov/raw-file/d53b5b7c1a32/ontology/Overview.html
asq -r "$RDFAFILE" -f rdfa,xml "CONSTRUCT {?s ?p ?o} WHERE { ?s ?p ?o }"
