"""Concept lookup for the agentic-AI adapter -- its only vocabulary.

Loaded once from the generated ``_concept_index.json`` (see
``scripts/generate_concept_index.py``). No network, no I/O beyond that one read,
so ``enrich_claim`` stays the pure function the DomainAdapter protocol requires.

The index carries two published vocabularies side by side. The ACM Computing
Classification System is this field's curated thesaurus but froze in 2012, before
this subject matter existed; Wikidata is uneven but holds the terms coined since.
Neither is sufficient alone, and the generator's docstring records the
measurement that establishes it. :func:`source_of` lets a consumer see which of
the two answered, because the two do not carry the same authority.

Why the whole of both rather than a curated subset: a hand-picked list is a
closed vocabulary that silently returns "no term" for everything outside it, and
a term absent for that reason is indistinguishable from a term that genuinely has
no concept. :func:`lookup` reports a miss explicitly so a caller can tell "not in
either vocabulary" from "not attempted".
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

_INDEX_PATH: Final[Path] = Path(__file__).with_name("_concept_index.json")

CCS_PREFIX: Final[str] = "CCS"
CCS_BASE_IRI: Final[str] = "https://dl.acm.org/topic/ccs2012/"
WD_PREFIX: Final[str] = "WD"
WD_BASE_IRI: Final[str] = "http://www.wikidata.org/entity/"

_BASE_IRIS: Final[dict[str, str]] = {CCS_PREFIX: CCS_BASE_IRI, WD_PREFIX: WD_BASE_IRI}


def _normalise(label: str) -> str:
    """Lookup key: case-folded, whitespace-collapsed.

    Must stay identical to ``scripts/generate_concept_index.py::normalise`` -- if
    the two ever diverge every lookup silently misses, so a test pins them.
    """
    return " ".join(str(label).lower().split())


@lru_cache(maxsize=1)
def _index() -> dict:
    return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))


def provenance() -> dict:
    """Where the vocabulary came from -- sources, anchors, licences, date."""
    return dict(_index()["_provenance"])


def subdomains() -> dict[str, str]:
    """Immediate children of CCS "Artificial intelligence" and "Machine
    learning", ``{label: curie}``.

    Taken from the ACM's tree rather than invented, so the decomposition is the
    field's own and moves with a CCS release rather than with an editor.
    """
    return dict(_index()["subdomains"])


def techniques() -> dict[str, str]:
    """Everything deeper than those children, ``{label: curie}``."""
    return dict(_index()["techniques"])


def concept_label(curie: str) -> str | None:
    """Preferred label for a CURIE this index knows, else None."""
    return _index()["concepts"].get(str(curie))


def concept_branch(curie: str) -> str | None:
    """The branch a concept sits under: a CCS top-level branch, or the Wikidata
    anchor whose subtree it came from. None if the CURIE is unknown."""
    return _index()["branch_of"].get(str(curie)) or None


def generic_branches() -> frozenset[str]:
    """CCS branches whose leaves are vocabulary shared with all of computing.

    A match under one of these ("Mathematics of computing", "Theory of
    computation") is a true mapping of the label and weak evidence that this
    domain's sense was meant -- the same ambiguity the astronomy adapter reports
    for its interdisciplinary branch.
    """
    return frozenset(_index()["generic_branches"])


def is_generic(curie: str) -> bool:
    """True when `curie` sits under a branch listed in :func:`generic_branches`."""
    return concept_branch(curie) in generic_branches()


def source_of(curie: str) -> str | None:
    """``"ACM CCS 2012"`` or ``"Wikidata"`` for a known CURIE, else None.

    The two vocabularies are not equally authoritative -- one is curated and
    frozen, the other is current and crowd-maintained -- so a consumer weighing a
    mapping needs to know which answered.
    """
    prefix = str(curie).partition(":")[0]
    if prefix == CCS_PREFIX:
        return "ACM CCS 2012"
    return "Wikidata" if prefix == WD_PREFIX else None


#: Endings whose singular form is obtained by dropping "es" rather than "s".
_ES_PLURAL: Final[tuple[str, ...]] = ("ses", "xes", "zes", "ches", "shes")


def _number_variants(key: str) -> tuple[str, ...]:
    """`key` with its final word singularised and pluralised.

    The two vocabularies disagree about number -- CCS writes "Multi-agent
    systems", Wikidata writes "multi-agent system" -- so a query phrased either
    way misses one of them for a reason that has nothing to do with meaning.

    This is morphology, not fuzzy matching. A variant is only ever *offered* to
    the index; it resolves solely when the variant is itself a published label,
    so no CURIE is invented and the "Mass" inside "Mass function" failure mode
    the exact rule exists to prevent cannot occur.
    """
    head, _, last = key.rpartition(" ")
    prefix = f"{head} " if head else ""
    forms: list[str] = []
    if last.endswith(_ES_PLURAL):
        forms.append(last[:-2])
    elif last.endswith("ies") and len(last) > 4:
        forms.append(f"{last[:-3]}y")
    elif last.endswith("s") and not last.endswith("ss"):
        forms.append(last[:-1])
    else:
        forms.extend((f"{last}s", f"{last}es"))
    return tuple(f"{prefix}{form}" for form in forms)


def lookup(text: str) -> str | None:
    """Return the CURIE whose preferred or alternative label matches *text*,
    exactly after normalisation or after singular/plural agreement, else None.

    Deliberately exact. Substring or fuzzy matching over thousands of labels
    manufactures confident-looking wrong CURIEs ("agent" inside "user agent"),
    and a wrong identifier is worse than none. The one concession is number --
    see :func:`_number_variants` for why that concession cannot invent a CURIE.
    """
    if not text:
        return None
    labels = _index()["labels"]
    key = _normalise(text)
    if key in labels:
        return labels[key]
    return next((labels[v] for v in _number_variants(key) if v in labels), None)


def expand(curie: str) -> str | None:
    """``CCS:10010147`` -> its ACM IRI; ``WD:Q11660`` -> its Wikidata IRI."""
    prefix, _, local = str(curie).partition(":")
    base = _BASE_IRIS.get(prefix)
    return f"{base}{local}" if base and local else None
