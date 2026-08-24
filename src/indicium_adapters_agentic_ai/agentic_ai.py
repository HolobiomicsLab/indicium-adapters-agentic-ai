"""AgenticAIAdapter -- the agentic-AI DomainAdapter (api_version=1)."""

from __future__ import annotations

from typing import Final

from . import _concepts

# Claim slots worth resolving. ``qualifier`` is included because a qualifier
# literal sometimes carries a method name ("fine-tuning"), itself a concept.
_ENRICHABLE_SLOTS: Final[tuple[str, ...]] = ("subject", "object", "qualifier")

# SSSOM justification for a label / alias string match. Every CURIE this adapter
# emits comes from exact-after-normalisation matching against a published
# vocabulary, so this is the only justification it can honestly claim.
_LEXICAL: Final[str] = "semapv:LexicalMatching"


class AgenticAIAdapter:
    """Agentic AI: LLM-based agents, multi-agent systems and the stack around them.

    Owns the tier-3 concerns only (ADR 0001): the classification vocabulary and
    claim/ontology enrichment. It deliberately does **not** recognise repository
    accessions -- those belong to the canonical accession table in
    ``asb-domain-core``, and a second copy here would be the duplicate-then-drift
    failure ADR 0001 exists to prevent. What it contributes for identifiers is
    ``ontology_prefixes``, so a consumer can expand the CURIEs that tier produces.

    **This domain has no single thesaurus, and the adapter does not pretend
    otherwise.** Its curated vocabulary -- the ACM Computing Classification
    System -- froze in 2012, before the subject matter existed. Measured against
    35 terms drawn from representative papers of the corpus wave, CCS 2012
    matches 15; every miss is a term coined after it froze. Wikidata supplies the
    rest and is the only published, stable-IRI vocabulary that carries them.
    Both are shipped, ``concept_source`` records which answered, and a term in
    neither is reported as unmatched rather than passed over. See
    ``scripts/generate_concept_index.py`` for the measurement and the anchors.

    ``subdomains`` and ``techniques`` were read from the ACM's own tree until the
    2026-08-25 cross-domain audit measured what that tree admits. CCS below
    "Artificial intelligence" is 13 branches and 154 terms of general AI, machine
    learning and vision -- ``cross-validation``, ``anomaly-detection``,
    ``3d-imaging`` -- so declaring it lets this adapter claim any quantitative
    paper in any science that happens to use one of them. Measured against the
    harvested corpus the whole tree matched ZERO rows: it bought nothing and
    risked everything. The terms declared below are the ones the corpus attests.
    Both published trees are still shipped and still answer ``enrich_claim``;
    what narrowed is the claim about which field a paper belongs to.

    Every qualifier matches ``^[a-z][a-z0-9_]*$`` (snake_case), required because
    Perspicacite routes adapter qualifiers onto the open ``asb:domainQualifier``
    slot whose SHACL shape enforces that pattern; non-conforming values would be
    rejected at the RDF boundary. Enforced by
    ``tests/test_protocol_conformance.py``.
    """

    domain_id = "agentic-ai"
    api_version = 1

    # ASB's classification layer reads ``primary_domain`` in preference to
    # ``domain_id`` and unions it into the controlled vocabulary. Declaring it
    # here is what stops an agentic-AI paper classifying as "other".
    primary_domain = "agentic-ai"

    qualifiers: frozenset[str] = frozenset(
        {
            # --- What the system is built out of ------------------------------
            "built_on",  # object is a base model or architecture
            "implemented_with",  # object is a framework, library or harness
            "prompted_with",  # object is a prompting strategy
            "fine_tuned_on",  # object is a training corpus or task mixture
            "trained_with",  # object is a training method (RLHF, DPO, SFT)
            # --- How the agents are arranged ----------------------------------
            "orchestrated_by",  # object is a controller, planner or scheduler
            "delegates_to",  # object is a sub-agent or a role
            "communicates_via",  # object is a protocol or message format
            "invokes_tool",  # object is a tool, API or function
            "retrieves_from",  # object is an index, corpus or knowledge store
            "stores_state_in",  # object is a memory or scratchpad
            "operates_in",  # object is an environment or sandbox
            # --- How it reasons -----------------------------------------------
            "reasons_by",  # object is a reasoning strategy
            "decomposes_into",  # object is the sub-task structure
            "verified_by",  # object is a critic, verifier or test
            "reflects_on",  # object is a trace or a prior attempt
            "grounded_in",  # object is the evidence a claim is tied to
            # --- How it changes itself ----------------------------------------
            "evolves_via",  # object is the self-improvement mechanism
            "selects_by",  # object is a fitness or selection criterion
            "mutates",  # object is the artefact modified (prompt, tool, policy)
            "bootstrapped_from",  # object is the seed artefact or data
            # --- How it is judged ---------------------------------------------
            "evaluated_on",  # object is a benchmark or task suite
            "measured_by",  # object is a metric
            "compared_against",  # object is a baseline or ablation
            "outperforms",
            "ablated_by",  # object is the component removed
            # --- Where it stops -----------------------------------------------
            "constrained_by",  # object is a budget, context window or latency cap
            "fails_by",  # object is a named failure mode
            "scales_with",  # object is the quantity performance scales with
        }
    )

    ontology_prefixes: dict[str, str] = {
        # The two concept spines.
        "CCS": _concepts.CCS_BASE_IRI,
        "WD": _concepts.WD_BASE_IRI,
        # Identifier namespaces this adapter does NOT mine but whose CURIEs a
        # consumer may need to expand. Recognition of these lives in
        # asb-domain-core's canonical accession table.
        "arxiv": "https://arxiv.org/abs/",
        "ACL": "https://aclanthology.org/",
        "HF": "https://huggingface.co/",
        "OpenML": "https://www.openml.org/d/",
        "PWC": "https://paperswithcode.com/paper/",
        "swh": "https://archive.softwareheritage.org/",
    }

    # ---- vocabulary the corpus attests -------------------------------------
    # Not read from CCS; see the class docstring for what that tree admits.

    subdomains: tuple[str, ...] = (
        "llm-agent",
        "language-model-agent",
        "multi-agent-llm",
    )

    techniques: tuple[str, ...] = (
        "chain-of-thought",
        "retrieval-augmented",
        "prompt-engineering",
        "tool-calling",
        "agent-harness",
        "agent-benchmark",
    )

    # ---- protocol methods --------------------------------------------------

    def extraction_context(self) -> str:
        return (
            "Domain: agentic AI -- language-model agents, multi-agent systems, "
            "tool use, reasoning and the engineering stack around them. Name "
            "subjects and objects concretely: prefer the model, framework, "
            "benchmark or dataset a paper actually names ('GPT-4o', 'SWE-bench', "
            "'ReAct') over a generic word ('the model', 'the benchmark'). Use the "
            "singular preferred term for a method ('chain-of-thought prompting', "
            "'retrieval-augmented generation') rather than a paraphrase. When a "
            "system changes itself, say what is modified -- a prompt, a tool, a "
            "policy, a population of agents -- rather than 'the system'. Domain "
            "qualifiers available in addition to the base set: "
            + ", ".join(sorted(self.qualifiers))
            + "."
        )

    def enrich_claim(self, claim: dict) -> dict:
        """Attach CCS or Wikidata CURIEs to the slots whose text names a concept.

        Pure: returns a new dict and never mutates the input.

        Matching is exact after case-folding and whitespace collapse. Substring
        and fuzzy matching over thousands of labels manufacture
        confident-looking wrong CURIEs, and a wrong identifier is worse than no
        identifier.

        Three companion maps are written beside ``ontology_terms``, and each
        exists because collapsing it into silence would destroy a distinction a
        downstream mapping set needs:

        * ``ontology_term_sources`` -- which vocabulary answered. A curated,
          frozen thesaurus and a crowd-maintained current one do not carry the
          same authority, and the CURIE prefix alone is easy to overlook.
        * ``ontology_term_branches`` -- the CCS branch or Wikidata anchor the
          concept sits under, so a consumer can see that "regression" matched
          under "Mathematics of computing" rather than under this domain.
        * ``ontology_terms_unmatched`` -- text that named nothing. Without it,
          "not in either vocabulary" is indistinguishable from "not attempted",
          and in this domain the first case is common and interesting: it is
          where the field's vocabulary has outrun its published thesauri.
        """
        out = dict(claim)
        terms: dict[str, str] = dict(out.get("ontology_terms") or {})
        justifications: dict[str, str] = dict(out.get("ontology_term_justifications") or {})
        sources: dict[str, str] = dict(out.get("ontology_term_sources") or {})
        branches: dict[str, str] = dict(out.get("ontology_term_branches") or {})
        unmatched: dict[str, str] = dict(out.get("ontology_terms_unmatched") or {})

        for slot in _ENRICHABLE_SLOTS:
            if slot in terms:
                continue  # another adapter already resolved this slot
            value = out.get(slot)
            if not isinstance(value, str) or not value.strip():
                continue
            curie = _concepts.lookup(value)
            if not curie:
                unmatched[slot] = value
                continue
            terms[slot] = curie
            justifications[slot] = _LEXICAL
            source = _concepts.source_of(curie)
            if source:
                sources[slot] = source
            branch = _concepts.concept_branch(curie)
            if branch:
                branches[slot] = branch
            unmatched.pop(slot, None)

        if terms:
            out["ontology_terms"] = terms
            out["ontology_term_justifications"] = justifications
        if sources:
            out["ontology_term_sources"] = sources
        if branches:
            out["ontology_term_branches"] = branches
        if unmatched:
            out["ontology_terms_unmatched"] = unmatched
        return out


def _slug(label: str) -> str:
    """ "Natural language processing" -> "natural-language-processing".

    Slashes become separators too: CCS spells one branch
    "Philosophical/theoretical foundations of artificial intelligence", and a
    slug carrying a slash breaks anything that treats it as a path segment.
    """
    return "-".join(str(label).lower().replace("/", " ").split())
