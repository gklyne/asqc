ENDPOINT=${1-http://dbpedia.org/sparql}

cp prefixes.sparql query.tmp

cat >>query.tmp <<ENDQUERY
SELECT DISTINCT ?class 
WHERE
{ ?s rdf:type ?class }
LIMIT 10

ENDQUERY

asq -e ${ENDPOINT} -q query.tmp -f CSV

