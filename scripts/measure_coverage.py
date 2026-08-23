#!/usr/bin/env python3
"""Measure what fraction of this field's working vocabulary the index resolves.

    python scripts/measure_coverage.py --papers 300 --out coverage.json

An adapter that ships a vocabulary should say how much of the literature that
vocabulary actually reaches, and say it with a number taken from the literature
rather than from the author's intuition. This samples recent arXiv papers from
the queries the corpus wave itself uses, extracts the phrases their titles and
abstracts repeat, and reports how many resolve.

The interesting half of the output is the list of frequent phrases that resolve
to nothing: that is where the field's working vocabulary has outrun its published
thesauri, and it is the input to the next release rather than something to hide.

Phrases are counted, not judged: a phrase qualifies by appearing in at least
``--min-papers`` distinct papers, so what is measured is the field's usage and
not a list anyone wrote down.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from indicium_adapters_agentic_ai import _concepts  # noqa: E402

ARXIV_API: Final[str] = "https://export.arxiv.org/api/query"
ARXIV_PAUSE: Final[float] = 3.0
_AGENT: Final[str] = "indicium-adapters-agentic-ai/0.1 (https://github.com/HolobiomicsLab)"

# The corpus wave's own queries, so the sample is the population the adapter
# will meet rather than a convenience sample of whatever arXiv returns first.
QUERIES: Final[tuple[str, ...]] = (
    'abs:"agentic"',
    'abs:"LLM agent" OR abs:"LLM agents"',
    'abs:"multi-agent" AND abs:"large language model"',
    'abs:"tool calling" OR abs:"function calling"',
    'abs:"chain of thought" OR abs:"chain-of-thought"',
    'abs:"self-evolving" OR abs:"self-improving" OR abs:"self-evolution"',
    'abs:"agent framework" OR abs:"agentic framework" OR abs:"agent harness"',
    'abs:"retrieval-augmented generation"',
)

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_SUMMARY = re.compile(r"<summary>(.*?)</summary>", re.S)
_WORD = re.compile(r"[a-z][a-z0-9-]*")

# Stopwords only; nothing domain-specific, so the measurement cannot be tuned by
# quietly excluding the phrases that would have failed.
_STOP: Final[frozenset[str]] = frozenset(
    (  # noqa: SIM905 -- a word-per-line list literal would be unreadable
        "a an and are as at about above across after against among be been "
        "before behind below beneath beside between beyond both but by can do does during "
        "each either for from further has have how in into is it its may more most neither "
        "no nor not of off on once only onto or our out over own same so some such "
        "than that the their them "
        "then there these they this those through to toward towards under until up upon use "
        "used using via was we were what when where which while who whom will with within "
        "without you"
    ).split()
)


def _fetch(query: str, rows: int) -> list[tuple[str, str]]:
    """Return (title, abstract) for the most recent `rows` papers of `query`."""
    encoded = urllib.parse.urlencode(
        {
            "search_query": query,
            "max_results": rows,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    request = urllib.request.Request(f"{ARXIV_API}?{encoded}", headers={"User-Agent": _AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        feed = response.read().decode("utf-8", "replace")
    titles = [" ".join(t.split()) for t in _TITLE.findall(feed)][1:]  # [0] is the feed title
    summaries = [" ".join(s.split()) for s in _SUMMARY.findall(feed)]
    return list(zip(titles, summaries, strict=False))


def phrases(text: str, min_len: int = 2, max_len: int = 4) -> set[str]:
    """Multiword grams of `text` containing no stopword at any position.

    Two decisions, both to keep the denominator honest rather than flattering:

    Single words are excluded. "model", "agent" and "large" are the most frequent
    tokens in this literature and none of them is a term; counting them drags the
    resolved fraction toward zero and measures the tokeniser, not the vocabulary.

    A stopword anywhere disqualifies the gram, not only at the ends. "reasoning
    with tools" is a fragment of a sentence, "tool-augmented reasoning" is a
    term, and only the second should be asked of a thesaurus.
    """
    words = _WORD.findall(text.lower())
    found: set[str] = set()
    for size in range(min_len, max_len + 1):
        for i in range(len(words) - size + 1):
            gram = words[i : i + size]
            if any(word in _STOP for word in gram):
                continue
            found.add(" ".join(gram))
    return found


def measure(papers: list[tuple[str, str]], min_papers: int, titles_only: bool = True) -> dict:
    """Document frequency over `papers`, then resolve everything frequent enough.

    Titles by default: a title is almost entirely terms, while an abstract is
    mostly connective prose, so an abstract-wide sweep measures the extractor
    more than it measures the vocabulary. ``--abstracts`` widens it.
    """
    counts: Counter[str] = Counter()
    for title, abstract in papers:
        counts.update(phrases(title if titles_only else f"{title}. {abstract}"))
    common = [p for p, n in counts.items() if n >= min_papers]
    resolved = {p: _concepts.lookup(p) for p in common}
    hits = {p: c for p, c in resolved.items() if c}
    misses = sorted((p for p, c in resolved.items() if not c), key=lambda p: -counts[p])
    by_source: Counter[str] = Counter(_concepts.source_of(c) or "?" for c in hits.values())
    generic = sum(1 for c in hits.values() if _concepts.is_generic(c))
    return {
        "papers": len(papers),
        "scope": "titles" if titles_only else "titles+abstracts",
        "min_papers": min_papers,
        "phrases_considered": len(common),
        "resolved": len(hits),
        "resolved_fraction": round(len(hits) / len(common), 3) if common else 0.0,
        "by_source": dict(by_source),
        "resolved_under_a_generic_branch": generic,
        "top_unresolved": [{"phrase": p, "papers": counts[p]} for p in misses[:60]],
        "sample_resolved": [
            {"phrase": p, "curie": c, "label": _concepts.concept_label(c)}
            for p, c in sorted(hits.items(), key=lambda kv: -counts[kv[0]])[:30]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", type=int, default=40, help="papers per query")
    parser.add_argument("--min-papers", type=int, default=5, help="phrase frequency floor")
    parser.add_argument("--cache", type=Path, help="reuse a saved paper sample")
    parser.add_argument("--abstracts", action="store_true",
                        help="sweep abstracts too, not titles alone")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.cache and args.cache.exists():
        papers = [tuple(row) for row in json.loads(args.cache.read_text())]
        print(f"  {len(papers)} papers from {args.cache}", flush=True)
    else:
        papers = []
        for query in QUERIES:
            got = _fetch(query, args.papers)
            papers.extend(got)
            print(f"  {len(got):3} papers  {query}", flush=True)
            time.sleep(ARXIV_PAUSE)
        if args.cache:
            args.cache.write_text(json.dumps(papers))
    report = measure(papers, args.min_papers, titles_only=not args.abstracts)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(
        f"\n{report['resolved']}/{report['phrases_considered']} frequent phrases resolve "
        f"({report['resolved_fraction']:.0%}) across {report['papers']} papers"
    )
    print(f"  by source: {report['by_source']}")
    print(f"  under a generic branch: {report['resolved_under_a_generic_branch']}")
    print("  most frequent unresolved:")
    for row in report["top_unresolved"][:15]:
        print(f"    {row['papers']:4}  {row['phrase']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
