"""The adapter must satisfy the DomainAdapter protocol and its RDF-boundary rules."""

from __future__ import annotations

import re

import pytest

from indicium_adapters_agentic_ai import AgenticAIAdapter

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


@pytest.fixture
def adapter() -> AgenticAIAdapter:
    return AgenticAIAdapter()


def test_satisfies_the_structural_protocol(adapter):
    from indicium_adapters import CURRENT_API_VERSION, DomainAdapter

    assert isinstance(adapter, DomainAdapter)
    # An adapter whose api_version differs is skipped by discover_adapters() with
    # only a UserWarning -- it would vanish silently rather than fail loudly.
    assert adapter.api_version == CURRENT_API_VERSION


def test_every_qualifier_is_snake_case(adapter):
    """Perspicacite routes adapter qualifiers onto the open ``asb:domainQualifier``
    slot, whose SHACL shape enforces this pattern. A non-conforming value would be
    rejected at the RDF boundary rather than reported here."""
    bad = [q for q in adapter.qualifiers if not _SNAKE_CASE.match(q)]
    assert not bad, f"non-snake_case qualifiers: {bad}"


def test_ontology_prefixes_are_expandable_iris(adapter):
    for prefix, base in adapter.ontology_prefixes.items():
        assert _SNAKE_CASE.match(prefix.lower()), prefix
        assert base.startswith("http"), (prefix, base)


def test_extraction_context_names_the_domain_and_its_qualifiers(adapter):
    ctx = adapter.extraction_context()
    assert "agentic ai" in ctx.lower()
    # The prompt must actually carry the qualifiers, else the LLM cannot use them.
    for q in ("invokes_tool", "evolves_via", "evaluated_on"):
        assert q in ctx


def test_declares_primary_domain_so_asb_classification_picks_it_up(adapter):
    """ASB reads ``primary_domain`` in preference to ``domain_id`` and unions it
    into the controlled vocabulary; without it an agentic-AI paper stays "other"."""
    assert adapter.primary_domain == "agentic-ai"


def test_enrich_claim_is_pure(adapter):
    claim = {"subject": "ReAct", "qualifier": "invokes_tool", "object": "a search API"}
    snapshot = {k: v for k, v in claim.items()}
    adapter.enrich_claim(claim)
    assert claim == snapshot, "enrich_claim mutated its input"


def test_subdomains_and_techniques_are_slugs(adapter):
    """A slug carrying a slash breaks anything that treats it as a path segment,
    and CCS spells one branch "Philosophical/theoretical foundations ..."."""
    for value in (*adapter.subdomains, *adapter.techniques):
        assert "/" not in value and " " not in value, value


def test_the_self_evolution_vocabulary_is_present(adapter):
    """Self-evolving systems are the reason this domain was collected; a claim
    about one has nowhere to land without these four qualifiers."""
    assert {"evolves_via", "selects_by", "mutates", "bootstrapped_from"} <= adapter.qualifiers
