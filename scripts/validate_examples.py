#!/usr/bin/env python3
"""Run every .ttl example query against the live endpoint and flag problems:
Virtuoso/HTTP errors, queries returning 0 rows, and queries slower than
--slow-after seconds.

.github/workflows/live-test.yml already runs a weekly live check through
wikipathways/Snorql-UI's tools/examples/snorql_examples.py, but that tool
only fails an example that declares snorql:expect and then doesn't meet it -
by design, an example with no snorql:expect (because it is known to return
nothing today, see migrate_rq_to_ttl.py's NO_ROWS_TODAY) stays silently
green even at 0 rows. This script reports every example's actual row count
and any HTTP/Virtuoso error regardless of whether snorql:expect is set, so
it surfaces those silently-empty queries too, with the live error text
inline. Matches the house style of scripts/compare_live.py (same ENDPOINT,
argparse shape, and per-identifier print-and-exit-code convention).

Usage, from the repository root:

    python scripts/validate_examples.py [--only PMWQ032 PMWQ040] [--workers 4] [--timeout 180]
"""

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import concurrent.futures

from rdflib import Graph, Namespace
from rdflib.namespace import DCTERMS, RDFS

SH = Namespace("http://www.w3.org/ns/shacl#")
SCHEMA = Namespace("https://schema.org/")
SNORQL = Namespace("https://w3id.org/snorql/ns#")
REPO = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://plantmetwiki.bioinformatics.nl/sparql"
SUPPORT_FILES = {"collection.ttl", "categories.ttl", "contributors.ttl"}

QUERY_PREDICATES = [SH.select, SH.ask, SH.construct,
                     Namespace("https://purl.expasy.org/sparql-examples/ontology#").describe]


def load(ttl):
    g = Graph().parse(ttl, format="turtle")
    s = next(g.subjects(DCTERMS.identifier, None))
    ident = str(g.value(s, DCTERMS.identifier))
    label = str(g.value(s, RDFS.label))
    target = str(g.value(s, SCHEMA.target))
    query = None
    for p in QUERY_PREDICATES:
        query = query or g.value(s, p)
    expect = g.value(s, SNORQL.expect)
    min_results = int(g.value(expect, SNORQL.minResults)) if expect is not None else None
    return ident, label, target, str(query), min_results


def run(endpoint, query, timeout):
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(endpoint, data=data, headers={
        "Accept": "application/sparql-results+json", "User-Agent": "sparqlqueries-validation"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        doc = json.loads(r.read().decode("utf-8"))
    secs = time.time() - start
    n = len(doc.get("results", {}).get("bindings", []))
    return n, secs


def check(ttl, timeout, endpoint, slow_after):
    ident, label, target, query, min_results = load(ttl)
    rel = ttl.relative_to(REPO).as_posix()
    if target != endpoint:
        return ident, "SKIP", f"{label} | schema:target {target} is not {endpoint}", rel
    try:
        n, secs = run(target, query, timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        first_line = next((ln for ln in body.splitlines() if ln.strip()), body[:200])
        return ident, "ERROR", f"{label} | HTTP {e.code}: {first_line[:200]}", rel
    except Exception as e:
        return ident, "ERROR", f"{label} | {type(e).__name__}: {str(e)[:200]}", rel
    if n == 0:
        why = " (snorql:expect says >=1)" if min_results else " (no snorql:expect set)"
        return ident, "ZERO_ROWS", f"{label} | 0 rows in {secs:.1f}s{why}", rel
    if secs > slow_after:
        return ident, "SLOW", f"{label} | {n} rows but took {secs:.1f}s", rel
    return ident, "OK", f"{label} | {n} rows in {secs:.1f}s", rel


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="identifiers to check")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--slow-after", type=float, default=20.0, help="seconds to flag as SLOW")
    ap.add_argument("--endpoint", default=ENDPOINT)
    args = ap.parse_args()

    files = sorted(p for p in REPO.rglob("*.ttl")
                    if p.relative_to(REPO).as_posix() not in SUPPORT_FILES and ".git" not in p.parts)
    if args.only:
        files = [p for p in files if any(f'"{i}"' in p.read_text(encoding="utf-8") for i in args.only)]

    results = []
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(check, p, args.timeout, args.endpoint, args.slow_after) for p in files]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda r: r[0])
    counts = {}
    for ident, status, detail, rel in results:
        counts[status] = counts.get(status, 0) + 1
        print(f"{ident} | {status:9s} | {rel} | {detail}")

    print(f"\n{len(results)} checked: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())),
          file=sys.stderr)
    bad = sum(v for k, v in counts.items() if k in ("ERROR", "ZERO_ROWS"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
