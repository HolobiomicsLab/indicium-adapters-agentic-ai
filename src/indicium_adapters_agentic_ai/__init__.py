"""Agentic-AI DomainAdapter for the indicium ecosystem.

Concept enrichment and classification vocabulary for language-model agents,
multi-agent systems and the engineering stack around them, backed by the ACM
Computing Classification System 2012 and Wikidata.
"""

from __future__ import annotations

from ._concepts import provenance
from .agentic_ai import AgenticAIAdapter

__all__ = ["AgenticAIAdapter", "provenance"]
__version__ = "0.1.0"
