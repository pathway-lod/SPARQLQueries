#!/usr/bin/env python3
"""One-off migration: turn the PlantMetWiki .rq example queries into .ttl example files.

Adapted from wikipathways/SPARQLQueries scripts/migrate_rq_to_ttl.py (commit fed6a2d).
Kept for the record of how the .ttl files were made; after the migration the .ttl files
are edited by hand (see AUTHORING.md) and this script is not run again.

For every .rq file it writes a .ttl file next to it, in the format checked by
Snorql-UI's tools/examples/snorql_examples.py:

- identifiers PMWQ001, PMWQ002, ... in folder order, then file name order;
- title: from the TITLES table below (the .rq files have no title line, except one);
- description: the first paragraph of the comment header; the rest of the header
  (named graphs used, implementation notes, ...) stays as comments in the query;
- a {{param}} placeholder becomes a query variable bound to the default in a VALUES
  block, and the parameter a sh:Parameter;
- PREFIX lines that Virtuoso does not need but other SPARQL engines do are added;
- created, creator and contributors from the git history of the .rq file;
- prov:wasDerivedFrom the .rq file at the commit it was migrated from, and
  snorql:alias the old path, so old ?example=<path>.rq links still work.

Usage, from the repository root:

    python scripts/migrate_rq_to_ttl.py --prefixes <prefixes.ttl> [--check]

with the prefixes.ttl of BiGCAT-UM/sparql-examples (examples/WikiPathways/prefixes.ttl).
"""

import argparse
import importlib.util
import pathlib
import re
import sys
import urllib.parse

from rdflib import Graph, Namespace

REPO = pathlib.Path(__file__).resolve().parent.parent
TARGET = "https://plantmetwiki.bioinformatics.nl/sparql"
LICENSE = "https://www.gnu.org/licenses/gpl-3.0.html"
SOURCE_BASE = "https://github.com/pathway-lod/SPARQLQueries/blob/"
WPQ = "https://sparql.wikipathways.org/.well-known/sparql-examples/"

SH = Namespace("http://www.w3.org/ns/shacl#")

# Git author names to the ORCID IRIs of the people (their names are in contributors.ttl).
# "De" is Denise Slenter, in the commits made through the GitHub web interface.
ELENA = "https://orcid.org/0000-0002-9472-918X"
DENISE = "https://orcid.org/0000-0001-8449-1318"
AUTHORS = {
    "De": DENISE, "DeniseSl22": DENISE, "Denise Slenter": DENISE,
    "Elena Del Pup": ELENA, "Del Pup": ELENA,
}
BOTS = {"GitHub Action", "github-actions[bot]"}

FOLDER_CATEGORY = {
    "1.(Meta)Data": "Metadata",
    "2.PlantMetWiki": "PlantMetWiki",
    "3.Biosynthetic gene cluster (BGC) Crosslinks": "BGC",
    "4.Federated": "Federated",
}
FOLDER_KEYWORDS = {
    "1.(Meta)Data": ["metadata"],
    "2.PlantMetWiki": [],
    "3.Biosynthetic gene cluster (BGC) Crosslinks": ["biosynthetic gene cluster", "MIBiG", "plantiSMASH"],
    "4.Federated": ["federated"],
}

# Titles, written from the file names (only the IDSM .rq has a title line).
TITLES = {
    "1.(Meta)Data/CountPWsPerSpecies.rq": "Number of pathways per species",
    "1.(Meta)Data/Entity_Counts.rq": "Number of entities per type",
    "1.(Meta)Data/GraphIsLoaded.rq": "Triples per named graph",
    "1.(Meta)Data/ListAllSpecies.rq": "All species with annotated data nodes",
    "1.(Meta)Data/ListEntities.rq": "All entity types",
    "1.(Meta)Data/ListNamedGraphs.rq": "All named graphs with their triple counts",
    "1.(Meta)Data/PlantCyc_PWY_ID_Lookup.rq": "PlantCyc accession of a pathway",
    "1.(Meta)Data/Taxa_Missing_from_NCBITaxon.rq": "Taxa missing from NCBITaxon",
    "1.(Meta)Data/VoIDHeader.rq": "VoID metadata of the datasets",
    "2.PlantMetWiki/BridgeDb_Coverage_Summary.rq": "BridgeDb cross-references per database",
    "2.PlantMetWiki/BridgeDb_Metabolite_CrossReferences.rq": "Metabolite cross-references from BridgeDb",
    "2.PlantMetWiki/Count_PWs_for_SpeciesName.rq": "Pathways of a species, with data node counts",
    "2.PlantMetWiki/CrossSpecies_ReactionCoverage.rq": "Species with an enzyme for each reaction of a pathway",
    "2.PlantMetWiki/Genes_and_Enzymes_per_Species.rq": "Genes and enzymes per species",
    "2.PlantMetWiki/Interaction_Types_Distribution.rq": "Number of interactions per type",
    "2.PlantMetWiki/Metabolite_by_PubChem_ID.rq": "Metabolite by PubChem ID, with its pathways and species",
    "2.PlantMetWiki/Metabolites_in_Pathway_for_SpeciesName.rq": "Metabolites in pathways of a species",
    "2.PlantMetWiki/Pathway_Content_Summary.rq": "Content of a pathway",
    "2.PlantMetWiki/Proteins_Names_andReference_forPathwayID.rq": "Proteins of a pathway, with references",
    "2.PlantMetWiki/Proteins_in_Pathway_for_TaxonID.rq": "Proteins in pathways of a taxon",
    "2.PlantMetWiki/Show_Species_and_TaxonID_Per_PW.rq": "Species in a pathway",
    "2.PlantMetWiki/TopPathways_by_GeneCount.rq": "Pathways with the most genes",
    "2.PlantMetWiki/nReferences_per_Pathway.rq": "Number of references per pathway",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/All_BGC_Gene_Links.rq": "Genes of all biosynthetic gene clusters",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/BGC_Pathway_Gene_Crosslinks.rq": "Genes shared by gene clusters and pathways",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/BGCs_Without_Pathway_Connection.rq": "Gene clusters without a pathway",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/Check_BGCs_Loaded.rq": "Gene cluster data per source",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/Connect_BGC_to_Pathway.rq": "Pathways of a gene cluster",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/Provenance_BGCs_and_Genes.rq": "Source of each gene cluster",
    "3.Biosynthetic gene cluster (BGC) Crosslinks/Top_Pathways_by_BGC_Genes.rq": "Pathways with the most gene cluster genes",
    "4.Federated/Extend_PWs_with_little_Refs_with_Title_and_DOI.rq": "Title and DOI of the references of pathways with few references",
    "4.Federated/IDSM_similaritySearch.rq": "IDSM chemical similarity search",
    "4.Federated/InChIKey_to_Wikidata_for_ChEBI_and_HMDB.rq": "Wikidata, ChEBI and PubChem for metabolites, by InChIKey",
    "4.Federated/Metabolites_by_InChIKey_with_Involved_Species.rq": "Pathways and species of metabolites, by InChIKey",
    "4.Federated/Metabolites_by_Name_with_Involved_Species.rq": "Pathways and species of metabolites, by name",
    "4.Federated/SMILES_from_Wikidata.rq": "SMILES from Wikidata for metabolites of a species",
}

# Descriptions written here: the first two queries have no comment header.
DESCRIPTIONS = {
    "1.(Meta)Data/ListEntities.rq":
        "Lists every entity type (rdf:type) used in PlantMetWiki, to help build your own queries.",
    "4.Federated/Extend_PWs_with_little_Refs_with_Title_and_DOI.rq":
        "Pathways with at most two references, with the title and DOI of each reference from "
        "Wikidata (through QLever). Returns 10 pathways at a time (LIMIT and OFFSET).",
    # The header continues its list on an indented line.
    "2.PlantMetWiki/Interaction_Types_Distribution.rq":
        "Count the number of interactions of each wp:Interaction subtype across the whole knowledge "
        "base: Catalysis, Conversion, TranscriptionTranslation, Inhibition, Stimulation, Binding and "
        "ComplexBinding.",
    # The header is a list; this sums it up.
    "2.PlantMetWiki/Genes_and_Enzymes_per_Species.rq":
        "For every species annotated in PlantMetWiki, the number of gene products, proteins and "
        "pathways, sorted by the number of genes and proteins.",
}

# New parameter defaults. WP4225 (copied from WikiPathways) is not a PlantMetWiki pathway.
# PC302 has conversions with sources and targets, but the query needs
# wp:bdbChEBI links, which the live endpoint does not have (2026-11-11), so no default
# returns rows today.
DEFAULTS = {("4.Federated/IDSM_similaritySearch.rq", "pathwayId"): "PC302"}

# Queries that return no rows on the live endpoint (2026-11-11), so they get no
# snorql:expect: the BridgeDb links (wp:bdb*) are not loaded there, "Content of a
# pathway" exceeds Virtuoso's 400 s estimate, and QLever answers the SMILES query
# with 429 Too Many Requests. The original .rq files behave the same.
NO_ROWS_TODAY = {
    "2.PlantMetWiki/BridgeDb_Coverage_Summary.rq",
    "2.PlantMetWiki/BridgeDb_Metabolite_CrossReferences.rq",
    "2.PlantMetWiki/Metabolite_by_PubChem_ID.rq",
    "2.PlantMetWiki/Pathway_Content_Summary.rq",
    "4.Federated/IDSM_similaritySearch.rq",
    "4.Federated/SMILES_from_Wikidata.rq",
}

# Fixes to the query text, so that SPARQL engines other than Virtuoso accept it.
# PMWQ035 uses GROUP_CONCAT without GROUP BY; Virtuoso groups by the other selected
# variables on its own, Jena and RDF4J reject the query. The GROUP BY makes that explicit.
QUERY_FIXES = {
    "4.Federated/Metabolites_by_Name_with_Involved_Species.rq":
        ("}\nORDER BY ?name", "}\nGROUP BY ?pwID ?name ?wd ?ingredientLabel\nORDER BY ?name"),
}

# Parameters that get autocomplete by their name.
AUTOCOMPLETE = {"pathwayId": "pathway"}

# Where a query was copied from a WikiPathways example.
DERIVED_FROM_WPQ = {"4.Federated/IDSM_similaritySearch.rq": "WPQ055"}

# A line of the comment header that starts the notes kept in the query, not the description.
NOTES_START = re.compile(
    r"^(Named graphs|Editable|Note|Implementation|Federat|Replace|Change|Example CID|Enabled by|"
    r"Uses VALUES|Expected|Strategy|Added by|Edit the|Columns|Results for|Look up|Even with|"
    r"Browse|Mirrors|ro:|BGC data|Join|PC\*|RC\*)")

PREFIXES = """@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix param: <https://w3id.org/snorql/param#> .
@prefix pmwcat: <https://plantmetwiki.bioinformatics.nl/.well-known/sparql-examples/category/> .
@prefix pmwq: <https://plantmetwiki.bioinformatics.nl/.well-known/sparql-examples/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix snorql: <https://w3id.org/snorql/ns#> .
@prefix spex: <https://purl.expasy.org/sparql-examples/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""

EXTRA_NAMESPACES = {
    "cito": "http://purl.org/spar/cito/",
    "ncbi": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "pmw": "http://rdf-plantmetwiki.bioinformatics.nl/pathways/",
    "ro": "http://purl.obolibrary.org/obo/RO_",
    "v": "http://rdf-plantmetwiki.bioinformatics.nl/vocab/",
    "p": "http://www.wikidata.org/prop/",
    "pq": "http://www.wikidata.org/prop/qualifier/",
    "wdt": "http://www.wikidata.org/prop/direct/",
    "wdtn": "http://www.wikidata.org/prop/direct-normalized/",
    "wd": "http://www.wikidata.org/entity/",
}


def load_wp_helpers():
    """The query-text helpers of the WikiPathways migration (mask, VALUES rewrite, ...)."""
    path = pathlib.Path(__file__).with_name("_wp_migrate_helpers.py")
    spec = importlib.util.spec_from_file_location("wp_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wp = load_wp_helpers()


def split_header(rel):
    """(title, description lines, notes lines, params, body) of an .rq file."""
    text = (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = text.split("\n")
    n = 0
    while n < len(lines) and (lines[n].startswith("#") or not lines[n].strip()):
        if not lines[n].strip() and n + 1 < len(lines) and not lines[n + 1].startswith("#"):
            break
        n += 1
    header, body = lines[:n], "\n".join(lines[n:]).strip("\n")
    if any(re.match(r"^#\s*(title|description|param):", h) for h in header):
        title, desc, params = "", [], []
        field = None
        for h in header:
            m = wp.HEADER_FIELD.match(h)
            if m:
                field, value = m.group(1), m.group(2).strip()
                if field == "title":
                    title = value
                elif field == "description":
                    desc.append(value)
                elif field == "param":
                    parts = [p.strip() for p in value.split("|")] + [""] * 4
                    params.append(tuple(parts[:4]))
            elif field == "description" and h.startswith("#"):
                desc.append(h.lstrip("#").strip())
        return title, desc, [], params, body
    desc, notes, in_notes = [], [], False
    for h in header:
        text = h.lstrip("#").rstrip()
        bare = text.strip()
        if not in_notes:
            if not bare and desc:
                in_notes = True
            elif bare and desc and (NOTES_START.match(bare) or text.startswith("   ") or bare.endswith(":")):
                in_notes = True
            elif bare:
                desc.append(bare)
                continue
            else:
                continue
        notes.append(h.rstrip())
    while notes and not notes[0].lstrip("#").strip():
        notes.pop(0)
    while notes and not notes[-1].lstrip("#").strip():
        notes.pop()
    return "", desc, notes, [], body


def normalise_prologue(body):
    """One PREFIX declaration per line (two queries declare several on one line)."""
    return re.sub(r">[ \t]+(?=PREFIX\s)", ">\n", body)


def from_rq(ident, rel, namespaces):
    title, desc, notes, params, body = split_header(rel)
    folder = str(pathlib.PurePosixPath(rel).parent)
    body = normalise_prologue(body)
    if rel in QUERY_FIXES:
        old, new = QUERY_FIXES[rel]
        if body.count(old) != 1:
            raise wp.MigrationError(f"{rel}: the query fix does not apply")
        body = body.replace(old, new)
    params = [(n, t, DEFAULTS.get((rel, n), d), lab) for n, t, d, lab in params]
    kinds = {}
    if params:
        body, kinds = wp.turn_into_values(body, params, namespaces, rel)
    query = wp.add_prefixes(body, namespaces, rel)
    if notes:
        query = "\n".join(notes) + "\n\n" + query
    created, authors = wp_history(rel)
    persons = []
    for a in authors:
        if a not in AUTHORS:
            raise wp.MigrationError(f"no IRI for git author {a!r}; add it to AUTHORS")
        if AUTHORS[a] not in persons:
            persons.append(AUTHORS[a])
    sha = wp.git(REPO, "log", "-1", "--format=%H", "--", rel).strip()
    comment = DESCRIPTIONS.get(rel) or " ".join(desc)
    if not comment:
        raise wp.MigrationError(f"{rel}: no description")
    plist = []
    for name, ptype, default, label in params:
        kind, template, variable = kinds[name]
        plist.append({"name": name, "label": label, "default": default, "kind": kind,
                      "template": template, "variable": variable,
                      "autocomplete": AUTOCOMPLETE.get(name)})
    derived = [SOURCE_BASE + sha + "/" + urllib.parse.quote(rel)]
    if rel in DERIVED_FROM_WPQ:
        derived.append(WPQ + DERIVED_FROM_WPQ[rel])
    keywords = []
    for k in [FOLDER_CATEGORY[folder].lower() if folder != "3.Biosynthetic gene cluster (BGC) Crosslinks" else ""] + \
            FOLDER_KEYWORDS[folder]:
        if k and k.lower() not in (x.lower() for x in keywords):
            keywords.append(k)
    return {
        "id": ident, "path": re.sub(r"\.rq$", ".ttl", rel), "label": TITLES[rel], "comment": comment,
        "created": created, "creators": persons[:1], "contributors": persons[1:],
        "category": FOLDER_CATEGORY[folder], "keywords": keywords, "aliases": [rel],
        "derived": derived, "params": plist, "query": query, "expect": rel not in NO_ROWS_TODAY,
    }


def wp_history(rel):
    # No --follow: git links some of these files to unrelated 2020 WikiPathways files
    # through a 2025 reorganisation commit; their own history starts there.
    out = wp.git(REPO, "log", "--format=%cs\t%an", "--", rel)
    log = sorted(tuple(line.split("\t", 1)) for line in out.splitlines() if line)
    authors = []
    for _, a in log:
        if a not in BOTS and a not in authors:
            authors.append(a)
    return (log[0][0] if log else None), authors


def render(ex):
    cls, prop = wp.FORMS[wp.query_form(ex["query"])]
    L = [PREFIXES, f"pmwq:{ex['id']} a sh:SPARQLExecutable, {cls} ;"]
    add = L.append
    add(f'    dcterms:identifier "{ex["id"]}" ;')
    add(f"    rdfs:label {wp.turtle_string(ex['label'])}@en ;")
    add(f"    rdfs:comment {wp.turtle_string(ex['comment'])}@en ;")
    add('    schema:version "1.0.0" ;')
    add(f'    dcterms:created "{ex["created"]}"^^xsd:date ;')
    add("    dcterms:creator " + ", ".join(f"<{c}>" for c in ex["creators"]) + " ;")
    if ex["contributors"]:
        add("    dcterms:contributor " + ", ".join(f"<{c}>" for c in ex["contributors"]) + " ;")
    add(f"    dcterms:license <{LICENSE}> ;")
    add(f"    dcterms:subject pmwcat:{ex['category']} ;")
    if ex["keywords"]:
        add("    schema:keywords " + ", ".join(wp.turtle_string(k) for k in ex["keywords"]) + " ;")
    add(f"    schema:target <{TARGET}> ;")
    for s in wp.services(ex["query"]):
        add(f"    spex:federatesWith <{s}> ;")
    for a in ex["aliases"]:
        add(f"    snorql:alias {wp.turtle_string(a)} ;")
    for d in ex["derived"]:
        add(f"    prov:wasDerivedFrom <{d}> ;")
    if ex["expect"]:
        add("    snorql:expect [ snorql:minResults 1 ] ;")
    for order, p in enumerate(ex["params"], 1):
        add("    sh:parameter [")
        add("        a sh:Parameter ;")
        add(f"        sh:path param:{p['name']} ;")
        add(f"        sh:name {wp.turtle_string(p['label'])} ;")
        add(f"        sh:defaultValue {wp.turtle_string(p['default'])} ;")
        if p.get("variable"):
            add(f"        snorql:variable {wp.turtle_string(p['variable'])} ;")
        if p["kind"] == "iri":
            add("        sh:nodeKind sh:IRI ;")
            add(f"        snorql:valueTemplate {wp.turtle_string(p['template'])} ;")
        else:
            add("        sh:datatype xsd:string ;")
        if p.get("autocomplete"):
            add(f"        snorql:autocomplete {wp.turtle_string(p['autocomplete'])} ;")
        add(f"        sh:order {order}")
        add("    ] ;")
    add(f"    {prop} {wp.turtle_long_string(ex['query'].rstrip())} .")
    ttl = "\n".join(L) + "\n"
    g = Graph()
    g.parse(data=ttl, format="turtle")
    found = [str(o) for _, p, o in g if str(p).endswith(("#select", "#ask", "#construct", "#describe"))]
    if found != [ex["query"].rstrip()]:
        raise wp.MigrationError(f"{ex['id']}: the query does not survive the Turtle round trip")
    return ttl


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prefixes", required=True, type=pathlib.Path,
                    help="prefixes.ttl of BiGCAT-UM/sparql-examples (examples/WikiPathways/)")
    ap.add_argument("--check", action="store_true", help="write nothing")
    args = ap.parse_args()
    g = Graph().parse(args.prefixes, format="turtle")
    namespaces = {str(p): str(n) for _, d in g.subject_objects(SH.declare)
                  for p in g.objects(d, SH.prefix) for n in g.objects(d, SH.namespace)}
    namespaces.update(EXTRA_NAMESPACES)

    def order(rel):
        return (list(FOLDER_CATEGORY).index(str(pathlib.PurePosixPath(rel).parent)), rel.casefold())
    rq_files = sorted((p.relative_to(REPO).as_posix() for p in REPO.rglob("*.rq")
                       if p.relative_to(REPO).parts[0] not in {".git", "scripts"}), key=order)
    missing = set(rq_files) ^ set(TITLES)
    if missing:
        sys.exit(f"TITLES does not match the .rq files: {sorted(missing)}")
    examples, errors = [], []
    for n, rel in enumerate(rq_files, 1):
        try:
            examples.append(from_rq(f"PMWQ{n:03d}", rel, namespaces))
        except wp.MigrationError as e:
            errors.append(str(e))
    if errors:
        for e in errors:
            print("ERROR: " + e, file=sys.stderr)
        sys.exit(1)
    for ex in examples:
        ttl = render(ex)
        if not args.check:
            (REPO / ex["path"]).write_text(ttl, encoding="utf-8")
    print(f"{len(examples)} examples, {sum(1 for e in examples if e['params'])} with parameters")


if __name__ == "__main__":
    main()
