# SPARQL examples for PlantMetWiki

Example SPARQL queries for the [PlantMetWiki SPARQL Explorer](https://plantmetwiki.bioinformatics.nl/).

Each example is a Turtle file with the query and its metadata (title, description, version,
creators, category, parameters), in the format of
[SIB's sparql-examples](https://github.com/sib-swiss/sparql-examples). Every example has a
permanent identifier and IRI, for example
[`PMWQ012`](https://plantmetwiki.bioinformatics.nl/?example=PMWQ012) is
`https://plantmetwiki.bioinformatics.nl/.well-known/sparql-examples/PMWQ012`. Files can be moved
and renamed without breaking links.

- [AUTHORING.md](AUTHORING.md): how to write or change an example, and how versions work.
- `categories.ttl`: the categories that make up the editor's tree.
- `contributors.ttl`: names of creators and contributors.
- `collection.ttl`: the collection itself.

On every push to `master`, CI publishes the `examples-index` branch, which the editor reads; it
also holds every past version of every example, the examples in one Turtle file, and plain `.rq`
copies. The `.rq` files next to the `.ttl` files are the originals the examples were converted
from (`scripts/migrate_rq_to_ttl.py`); edit the `.ttl` files.

Relevant prefixes from this knowledge graph:
```SPARQL
PREFIX biopax:      <http://www.biopax.org/release/biopax-level3.owl#>
PREFIX cito:        <http://purl.org/spar/cito/>
PREFIX dc:          <http://purl.org/dc/elements/1.1/>
PREFIX dcterms:     <http://purl.org/dc/terms/>
PREFIX foaf:        <http://xmlns.com/foaf/0.1/>
PREFIX freq:        <http://purl.org/cld/freq/>
PREFIX gpml:        <http://vocabularies.wikipathways.org/gpml#>
PREFIX owl:         <http://www.w3.org/2002/07/owl#>
PREFIX pav:         <http://purl.org/pav/>
PREFIX prov:        <http://www.w3.org/ns/prov#>
PREFIX rdf:         <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:        <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos:        <http://www.w3.org/2004/02/skos/core#>
PREFIX void:        <http://rdfs.org/ns/void#>
PREFIX wp:          <http://vocabularies.wikipathways.org/wp#>
PREFIX wprdf:       <http://rdf.wikipathways.org/>
PREFIX xsd:         <http://www.w3.org/2001/XMLSchema#>
PREFIX pmw:         <http://rdf-plantmetwiki.bioinformatics.nl/pathways/>
PREFIX ncbi:        <http://purl.obolibrary.org/obo/NCBITaxon_>
PREFIX ro:          <http://purl.obolibrary.org/obo/RO_>
PREFIX bioregistry: <https://bioregistry.io/mibig:>
```

Commonly used prefixes for federated queries:
- Wikidata
```SPARQL
PREFIX wd:          <http://www.wikidata.org/entity/>
PREFIX wdt:         <http://www.wikidata.org/prop/direct/>
PREFIX p:           <http://www.wikidata.org/prop/>
PREFIX pq:          <http://www.wikidata.org/prop/qualifier/>
PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/> 
```
- Lotus
```SPARQL
#tba
```

## License 

[ GNU GENERAL PUBLIC LICENSE](LICENSE)
