#!/usr/bin/env python3
"""Regenerate ``_concept_index.json`` from two published vocabularies.

    python scripts/generate_concept_index.py

The adapter never invents a concept identifier: every CURIE it emits comes from
this generated index, and the index comes from sources that publish, version and
license their vocabulary.

**Why two sources, when the astronomy adapter needs only one.** Astronomy has a
living curated thesaurus (the UAT) that covers its own subject matter. This
domain has no counterpart. Its curated thesaurus -- the ACM Computing
Classification System -- was frozen in 2012, which is before the subject matter
existed: measured against 35 terms drawn from representative papers of the wave,
CCS 2012 matches 15. Every miss is a term coined after it froze (large language
model, chain-of-thought prompting, retrieval-augmented generation, in-context
learning, tool calling). Shipping CCS alone would return "no concept" for exactly
the vocabulary the domain is about.

Wikidata supplies the second layer. It is not a thesaurus and its coverage is
uneven, but it is published, versioned by retrieval date, carries stable IRIs,
and it does hold the modern terms. Concepts come from the transitive
``subclass of`` closure of the anchors in ``ANCHORS`` -- the anchors are chosen,
everything under them is Wikidata's own structure, not an editor's list.

**Anchors are verified by their description before use.** An exact label match
against a published vocabulary can still be the wrong sense: Wikidata's "tool
use" (Q12333059) is a facet of animal behaviour, and rooting a closure there
would pull primatology into an agent adapter under a confident-looking CURIE.
``REJECTED_ANCHORS`` records the ones checked and refused, so the next person to
reach for them finds the reason rather than repeating the mistake.

Network access is required. Nothing else in the package touches the network.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Final

_CCS_URL: Final[str] = "https://dl.acm.org/pb-assets/dl_ccs/acm_ccs2012-1626988337597.xml"
_WD_SPARQL: Final[str] = "https://query.wikidata.org/sparql"
_AGENT: Final[str] = "indicium-adapters-agentic-ai/0.1 (https://github.com/HolobiomicsLab)"

_NS: Final[dict[str, str]] = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}

_OUT: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "indicium_adapters_agentic_ai"
    / "_concept_index.json"
)

#: Wikidata items whose transitive ``subclass of`` closure is taken as domain
#: vocabulary. Each was read at its Wikidata description before being admitted.
ANCHORS: Final[dict[str, str]] = {
    "Q11660": "artificial intelligence",
    "Q2539": "machine learning",
    "Q30642": "natural language processing",
    "Q529909": "multi-agent system",
    "Q115305900": "large language model",
    "Q121362277": "retrieval-augmented generation",
    "Q108941486": "prompt engineering",
    "Q132451509": "AI agent",
    "Q2297769": "software agent",
    "Q1142726": "intelligent agent",
    "Q112702082": "foundation model",
    "Q117322965": "in-context learning",
    "Q115570683": "reinforcement learning from human feedback",
    "Q117286419": "fine-tuning",
    "Q4117718": "program synthesis",
}

#: Checked and refused, with the reason. A label that reads right in this domain
#: is not evidence the item means what the domain means by it.
REJECTED_ANCHORS: Final[dict[str, str]] = {
    "Q12333059": "'tool use' is a facet of animal behaviour and human sociology, not tool calling",
    "Q109359963": (
        "'transformer' -- the English sense is not stated in the item, "
        "so it may be the electrical device"
    ),
}

#: CCS branches whose leaves are vocabulary shared with every other computing
#: field rather than this domain's subject matter. A match under one of these is
#: a true mapping of the label and weak evidence about the domain.
GENERIC_CCS_BRANCHES: Final[tuple[str, ...]] = (
    "General and reference",
    "Mathematics of computing",
    "Theory of computation",
    "Social and professional topics",
)


def normalise(label: str) -> str:
    """Lookup key: case-folded, whitespace-collapsed.

    Must stay identical to ``_concepts._normalise`` -- if the two diverge every
    lookup silently misses, so a test pins them together.
    """
    return " ".join(str(label).lower().split())


def _get(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


#: Wikidata's public endpoint drops long queries under load. Retrying is worth
#: it because the alternative -- an anchor silently contributing nothing -- is
#: indistinguishable from an anchor whose subtree is genuinely empty.
_SPARQL_ATTEMPTS: Final[int] = 4
_SPARQL_BACKOFF: Final[int] = 20


def _sparql(query: str, timeout: int = 180) -> list[dict]:
    """Run `query`, retrying a timeout rather than reporting an empty subtree."""
    url = f"{_WD_SPARQL}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
    request = urllib.request.Request(
        url, headers={"User-Agent": _AGENT, "Accept": "application/sparql-results+json"}
    )
    for attempt in range(1, _SPARQL_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())["results"]["bindings"]
        except Exception as exc:  # noqa: BLE001 -- retried below, re-raised on the last
            if attempt == _SPARQL_ATTEMPTS:
                raise
            print(f"    retry {attempt}/{_SPARQL_ATTEMPTS - 1} after {type(exc).__name__}",
                  flush=True)
            time.sleep(_SPARQL_BACKOFF * attempt)
    raise AssertionError("unreachable")


# ---- ACM CCS 2012 -----------------------------------------------------------


def fetch_ccs() -> dict:
    """Concepts, labels and hierarchy from the ACM's SKOS release.

    CCS identifiers are dotted paths, so a concept's top-level branch is the
    first segment of its own id -- no tree walk is needed.
    """
    root = ET.fromstring(_get(_CCS_URL))
    labels: dict[str, str] = {}
    narrower: dict[str, list[str]] = {}
    for concept in root.findall("skos:Concept", _NS):
        cid = concept.get(f"{{{_NS['rdf']}}}about")
        pref = concept.find("skos:prefLabel", _NS)
        if not cid or pref is None or not pref.text:
            continue
        labels[cid] = pref.text
        narrower[cid] = [
            child.get(f"{{{_NS['rdf']}}}resource")
            for child in concept.findall("skos:narrower", _NS)
        ]
    return {"labels": labels, "narrower": narrower}


def _descendants(root_id: str, narrower: dict[str, list[str]]) -> list[str]:
    """Every concept below `root_id`, breadth-first, root excluded."""
    seen: list[str] = []
    queue = list(narrower.get(root_id) or [])
    while queue:
        cid = queue.pop(0)
        if cid in seen:
            continue
        seen.append(cid)
        queue.extend(narrower.get(cid) or [])
    return seen


def _by_label(labels: dict[str, str], wanted: str) -> str | None:
    return next((cid for cid, name in labels.items() if name == wanted), None)


# ---- Wikidata ---------------------------------------------------------------


def fetch_wikidata() -> dict:
    """Preferred labels and aliases for the subclass closure of every anchor.

    One request per anchor: a single query unioning all of them exceeds the
    endpoint's time limit, and a partial answer would be indistinguishable from a
    small subtree.
    """
    cache_path = Path(__file__).with_name("_wikidata_cache.json")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    concepts: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    anchor_of: dict[str, str] = {}
    for qid in ANCHORS:
        if qid not in cache:
            query = (
                f"SELECT ?item ?label ?alt WHERE {{ ?item wdt:P279* wd:{qid} ; rdfs:label ?label . "
                'OPTIONAL { ?item skos:altLabel ?alt . FILTER(lang(?alt)="en") } '
                'FILTER(lang(?label)="en") }'
            )
            cache[qid] = [
                {
                    "qid": row["item"]["value"].rsplit("/", 1)[-1],
                    "label": row["label"]["value"],
                    "alt": row.get("alt", {}).get("value"),
                }
                for row in _sparql(query)
            ]
            cache_path.write_text(json.dumps(cache))
        for row in cache[qid]:
            concepts.setdefault(row["qid"], row["label"])
            anchor_of.setdefault(row["qid"], qid)
            if row.get("alt"):
                aliases.setdefault(row["qid"], []).append(row["alt"])
        print(f"  {qid} ({ANCHORS[qid]}): {len(concepts)} cumulative", flush=True)
    return {"concepts": concepts, "aliases": aliases, "anchor_of": anchor_of}


# ---- index ------------------------------------------------------------------


def build() -> dict:
    print("ACM CCS 2012 ...", flush=True)
    ccs = fetch_ccs()
    print(f"  {len(ccs['labels'])} concepts", flush=True)
    print("Wikidata ...", flush=True)
    wd = fetch_wikidata()

    concepts: dict[str, str] = {}
    labels: dict[str, str] = {}
    branch_of: dict[str, str] = {}

    # CCS first: it is the field's own curated thesaurus, so where both sources
    # carry a label ("machine learning") the curated identifier is the one kept.
    for cid, name in ccs["labels"].items():
        curie = f"CCS:{cid}"
        concepts[curie] = name
        labels[normalise(name)] = curie
        branch_of[curie] = ccs["labels"].get(cid.split(".", 1)[0], "")

    for qid, name in wd["concepts"].items():
        curie = f"WD:{qid}"
        concepts[curie] = name
        branch_of[curie] = ANCHORS[wd["anchor_of"][qid]]
        labels.setdefault(normalise(name), curie)
        for alt in wd["aliases"].get(qid) or []:
            labels.setdefault(normalise(alt), curie)

    ai_root = _by_label(ccs["labels"], "Artificial intelligence")
    ml_root = _by_label(ccs["labels"], "Machine learning")
    if not ai_root or not ml_root:
        raise SystemExit("CCS release did not expose the expected AI/ML branches")

    # The domain's own decomposition, read from the ACM tree rather than listed:
    # the immediate children of "Artificial intelligence" and "Machine learning".
    subdomains = {
        ccs["labels"][cid]: f"CCS:{cid}"
        for root in (ai_root, ml_root)
        for cid in (ccs["narrower"].get(root) or [])
        if cid in ccs["labels"]
    }
    # Techniques: everything deeper than those children, again from the tree.
    techniques = {
        ccs["labels"][cid]: f"CCS:{cid}"
        for root in (ai_root, ml_root)
        for cid in _descendants(root, ccs["narrower"])
        if cid in ccs["labels"] and ccs["labels"][cid] not in subdomains
    }

    return {
        "_provenance": {
            "sources": [
                {
                    "name": "ACM Computing Classification System (CCS) 2012",
                    "role": "curated concept spine; frozen 2012",
                    "url": _CCS_URL,
                    "homepage": "https://dl.acm.org/ccs",
                    "concepts": len(ccs["labels"]),
                },
                {
                    "name": "Wikidata",
                    "role": "current layer for vocabulary coined after CCS froze",
                    "url": _WD_SPARQL,
                    "licence": "CC0 1.0",
                    "anchors": ANCHORS,
                    "rejected_anchors": REJECTED_ANCHORS,
                    "concepts": len(wd["concepts"]),
                },
            ],
            "precedence": "CCS wins a label collision; Wikidata fills what CCS lacks",
            "retrieved": date.today().isoformat(),
            "generator": "scripts/generate_concept_index.py",
            "note": "GENERATED FILE -- do not hand-edit. Rerun the generator instead.",
        },
        "generic_branches": list(GENERIC_CCS_BRANCHES),
        "subdomains": subdomains,
        "techniques": techniques,
        "branch_of": branch_of,
        "labels": labels,
        "concepts": concepts,
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    index = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote {_OUT} -- {len(index['concepts'])} concepts, "
        f"{len(index['labels'])} lookup labels, {len(index['subdomains'])} subdomains, "
        f"{len(index['techniques'])} techniques"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
