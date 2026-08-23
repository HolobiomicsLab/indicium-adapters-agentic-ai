# Changelog

## 0.1.0

First release.

- `AgenticAIAdapter`, api_version 1, `domain_id` and `primary_domain`
  `agentic-ai`.
- Concept index built from ACM CCS 2012 and the Wikidata subclass closure of 15
  verified anchors: 2,521 concepts, 2,813 lookup labels.
- 29 domain qualifiers, including the self-evolution group (`evolves_via`,
  `selects_by`, `mutates`, `bootstrapped_from`) that the corpus wave was
  collected for.
- `subdomains` (13) and `techniques` (154) read from the ACM tree.
- Lookup is exact after normalisation, with singular/plural agreement — the two
  sources disagree about number, and a variant resolves only when it is itself a
  published label.
- `enrich_claim` records the answering vocabulary, the concept's branch, and any
  text that resolved to nothing.
- `coverage.json`: 19 of 152 frequent title phrases across 800 arXiv papers
  resolve (12%). The unresolved list ships with it.
