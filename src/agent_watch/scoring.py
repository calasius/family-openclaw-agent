from __future__ import annotations

from agent_watch.domain import WatchItem
from agent_watch.categories import infer_category


POSITIVE_TERMS = {
    "claude code": 5,
    "opencode": 5,
    "openclaw": 5,
    "agent": 2,
    "agents": 2,
    "mcp": 3,
    "tool calling": 3,
    "function calling": 2,
    "open source model": 3,
    "local model": 2,
    "inference": 1,
    "evals": 1,
    "orchestration": 2,
    "autonomous": 1,
}

NEGATIVE_TERMS = {
    "crypto": -5,
    "airdrop": -5,
    "giveaway": -4,
    "casino": -5,
    "nft": -4,
    "prompt pack": -3,
}


def score_item(item: WatchItem) -> WatchItem:
    haystack = f"{item.title}\n{item.text}\n{item.author}\n{item.source}\n{item.url}".lower()
    score = 0
    for term, weight in POSITIVE_TERMS.items():
        if term in haystack:
            score += weight
    for term, weight in NEGATIVE_TERMS.items():
        if term in haystack:
            score += weight

    title = item.title.strip() or _first_sentence(item.text)
    score = max(score, 0)
    return WatchItem(
        source=item.source,
        external_id=item.external_id,
        author=item.author,
        title=title[:180],
        text=item.text.strip(),
        url=item.url,
        published_at=item.published_at,
        raw_json=item.raw_json,
        score=score,
        status="new" if score > 0 else "discarded",
        category=infer_category(title, item.text, item.author, item.url),
        score_reason="rule-based keyword score" if score > 0 else "no relevant rule-based keywords",
    )


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return "Untitled"
    for separator in (". ", "\n"):
        if separator in cleaned:
            return cleaned.split(separator, 1)[0]
    return cleaned[:120]
