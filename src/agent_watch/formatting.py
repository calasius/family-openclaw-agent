from __future__ import annotations

from agent_watch.domain import WatchItem
from agent_watch.categories import category_label


def format_items(items: list[WatchItem], *, empty_message: str = "No results found.") -> str:
    if not items:
        return empty_message

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"id: {item.source}:{item.external_id}")
        lines.append(
            f"category: {category_label(item.category)} | source: {item.author or item.source} | "
            f"score: {item.score} | status: {item.status}"
        )
        if item.published_at:
            lines.append(f"date: {item.published_at}")
        if item.score_reason:
            lines.append(f"reason: {item.score_reason}")
        snippet = _snippet(item.text)
        if snippet and snippet != item.title:
            lines.append(f"text: {snippet}")
        lines.append(f"link: {item.url}")
        lines.append("")
    return "\n".join(lines).strip()


def format_item_detail(item: WatchItem | None) -> str:
    if item is None:
        return "Item not found."

    lines = [
        item.title,
        f"id: {item.source}:{item.external_id}",
        f"category: {category_label(item.category)}",
        f"source: {item.author or item.source}",
        f"score: {item.score}",
        f"status: {item.status}",
    ]
    if item.published_at:
        lines.append(f"date: {item.published_at}")
    lines.extend(["", item.text.strip(), "", f"link: {item.url}"])
    return "\n".join(lines).strip()


def _snippet(text: str, limit: int = 360) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
