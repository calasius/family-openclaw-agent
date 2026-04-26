from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchItem:
    source: str
    external_id: str
    author: str
    title: str
    text: str
    url: str
    published_at: str | None = None
    raw_json: str | None = None
    score: int = 0
    status: str = "new"
    category: str = "general"
    score_reason: str = ""
