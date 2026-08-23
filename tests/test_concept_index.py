"""The generated index must stay faithful to its sources and to the loader."""

from __future__ import annotations

import json
from pathlib import Path

from indicium_adapters_agentic_ai import _concepts

_ROOT = Path(__file__).resolve().parents[1]


def test_provenance_names_both_sources_and_how_they_rank():
    prov = _concepts.provenance()
    names = {source["name"] for source in prov["sources"]}
    assert names == {"ACM Computing Classification System (CCS) 2012", "Wikidata"}
    assert "CCS wins" in prov["precedence"]


def test_rejected_anchors_carry_their_reason():
    """An anchor refused without a recorded reason is an anchor the next person
    re-adds. Wikidata's "tool use" is animal behaviour, not tool calling."""
    wikidata = next(s for s in _concepts.provenance()["sources"] if s["name"] == "Wikidata")
    assert wikidata["rejected_anchors"]
    for qid, reason in wikidata["rejected_anchors"].items():
        assert qid.startswith("Q") and len(reason) > 20


def test_normalise_agrees_with_the_generator():
    """If the two diverge every lookup silently misses."""
    source = (_ROOT / "scripts" / "generate_concept_index.py").read_text(encoding="utf-8")
    namespace: dict = {}
    start = source.index("def normalise(")
    end = source.index("def _get(")
    exec(source[start:end], namespace)  # noqa: S102 -- pinning the generator's own function
    for probe in ("  Multi-Agent   Systems ", "LARGE Language Model", "chain-of-thought"):
        assert namespace["normalise"](probe) == _concepts._normalise(probe)


def test_curies_expand_to_real_iris():
    for curie in list(_concepts._index()["concepts"])[:200]:
        assert (_concepts.expand(curie) or "").startswith("http"), curie


def test_every_label_points_at_a_known_concept():
    concepts = _concepts._index()["concepts"]
    orphans = [c for c in _concepts._index()["labels"].values() if c not in concepts]
    assert not orphans, orphans[:5]


def test_subdomains_and_techniques_do_not_overlap():
    assert not set(_concepts.subdomains()) & set(_concepts.techniques())


def test_the_measured_coverage_is_shipped_with_the_package():
    """The adapter claims a number for how much of the field it reaches; the
    evidence for that number travels with it."""
    report = json.loads((_ROOT / "coverage.json").read_text())
    assert report["papers"] >= 400
    assert 0.0 < report["resolved_fraction"] < 1.0
    assert report["top_unresolved"], "the gap list is the input to the next release"
