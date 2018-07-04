PATTERN="${1-?s ?p ?o}"
ENDPOINT=${2-http://dbpedia.org/sparql}

cp prefixes.sparql query.tmp

cat >>query.tmp <<ENDQUERY
SELECT DISTINCT * 
WHERE
{
${PATTERN}
}
LIMIT 100

ENDQUERY

asq -e ${ENDPOINT} -q query.tmp -f CSV

