"""What ``enrich_claim`` may and may not assert about a slot."""

from __future__ import annotations

import pytest

from indicium_adapters_agentic_ai import AgenticAIAdapter


@pytest.fixture
def adapter() -> AgenticAIAdapter:
    return AgenticAIAdapter()


def test_a_curated_concept_resolves_and_names_its_source(adapter):
    out = adapter.enrich_claim({"subject": "Multi-agent systems"})
    assert out["ontology_terms"]["subject"].startswith("CCS:")
    assert out["ontology_term_sources"]["subject"] == "ACM CCS 2012"


def test_a_term_coined_after_ccs_froze_resolves_against_wikidata(adapter):
    """The whole reason the index carries two vocabularies: CCS 2012 has no
    entry for anything named after 2012."""
    out = adapter.enrich_claim({"subject": "large language model"})
    assert out["ontology_terms"]["subject"] == "WD:Q115305900"
    assert out["ontology_term_sources"]["subject"] == "Wikidata"


def test_an_unknown_term_is_reported_not_silently_dropped(adapter):
    """"Not in either vocabulary" must stay distinguishable from "not attempted"
    -- in this domain the first case is common and is the input to the next
    release."""
    out = adapter.enrich_claim({"subject": "agent harness"})
    assert "ontology_terms" not in out
    assert out["ontology_terms_unmatched"]["subject"] == "agent harness"


def test_number_disagreement_between_the_two_sources_still_resolves(adapter):
    """CCS writes "Multi-agent systems", Wikidata writes "multi-agent system".
    A query phrased either way must not miss for a reason unrelated to meaning."""
    singular = adapter.enrich_claim({"subject": "multi-agent system"})
    plural = adapter.enrich_claim({"subject": "multi-agent systems"})
    assert singular["ontology_terms"]["subject"]
    assert plural["ontology_terms"]["subject"]


def test_number_agreement_never_invents_a_curie(adapter):
    """A variant resolves only when the variant is itself a published label."""
    out = adapter.enrich_claim({"subject": "hallucinated agentic widgets"})
    assert "ontology_terms" not in out


def test_a_slot_another_adapter_resolved_is_left_alone(adapter):
    claim = {"subject": "large language model", "ontology_terms": {"subject": "OTHER:1"}}
    out = adapter.enrich_claim(claim)
    assert out["ontology_terms"]["subject"] == "OTHER:1"


def test_a_generic_branch_is_flagged_so_a_match_can_be_discounted(adapter):
    """CCS is the whole of computing, so it genuinely contains statistics and
    theory vocabulary. A match there is a true mapping of the label and weak
    evidence that this domain's sense was meant."""
    from indicium_adapters_agentic_ai import _concepts

    generic = [
        curie
        for curie in _concepts._index()["concepts"]
        if _concepts.is_generic(curie)
    ]
    assert generic, "no concept sits under a generic branch -- the flag is dead"


def test_empty_and_non_string_slots_are_skipped(adapter):
    out = adapter.enrich_claim({"subject": "", "object": None, "qualifier": 7})
    assert "ontology_terms" not in out
    assert "ontology_terms_unmatched" not in out
