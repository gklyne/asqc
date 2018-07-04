QUERYFILE=${1-showtypes.sparql}

asq -e http://dbpedia.org/sparql -q ${QUERYFILE} -f CSV


