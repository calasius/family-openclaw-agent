from __future__ import annotations

import json
from urllib.request import Request, urlopen

from agent_watch.domain import WatchItem
from agent_watch.categories import CATEGORY_LABELS, infer_category
from agent_watch.page_chunk import fetch_page_chunk


def model_score_items(
    items: list[WatchItem],
    *,
    api_key: str | None,
    model_name: str,
    max_items: int,
    page_chars: int,
) -> list[WatchItem]:
    if not api_key or max_items <= 0:
        return items

    rescored: list[WatchItem] = []
    for index, item in enumerate(items):
        if index >= max_items:
            rescored.append(item)
            continue
        scored = _model_score_item(item, api_key=api_key, model_name=model_name, page_chars=page_chars)
        rescored.append(scored or item)
    return rescored


def _model_score_item(
    item: WatchItem,
    *,
    api_key: str,
    model_name: str,
    page_chars: int,
) -> WatchItem | None:
    try:
        chunk = fetch_page_chunk(item.url, max_chars=page_chars)
    except Exception:
        chunk = ""
    if not chunk:
        chunk = item.text[:page_chars]

    payload = {
        "model": model_name.removeprefix("openrouter/"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You score technical news for an AI agent implementation radar. "
                    "Return only JSON with keys score, category, and reason. "
                    "score is an integer from 0 to 10. 10 means immediately relevant to building, operating, "
                    "or evaluating AI agents, coding agents, MCP/tool use, OpenClaw/OpenCode/Claude Code/Codex, "
                    "or strong open source/local models. 0 means irrelevant or hype. "
                    "category must be one of: "
                    + ", ".join(CATEGORY_LABELS)
                    + "."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Title: {item.title}\n"
                    f"Source: {item.author or item.source}\n"
                    f"URL: {item.url}\n"
                    f"Feed text: {item.text[:1200]}\n\n"
                    f"Page chunk:\n{chunk[:page_chars]}"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 120,
    }
    request = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://local.school-guardian",
            "X-Title": "Agent Watch",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        parsed = _parse_json_object(content)
        score = int(parsed.get("score", item.score))
        category = str(parsed.get("category") or infer_category(item.title, item.text, item.author, item.url))
        if category not in CATEGORY_LABELS:
            category = infer_category(item.title, item.text, item.author, item.url)
        reason = str(parsed.get("reason") or "").strip()
    except Exception:
        return None

    score = max(0, min(score, 10)) * 2
    return WatchItem(
        source=item.source,
        external_id=item.external_id,
        author=item.author,
        title=item.title,
        text=item.text,
        url=item.url,
        published_at=item.published_at,
        raw_json=item.raw_json,
        score=score,
        status="new" if score > 0 else "discarded",
        category=category,
        score_reason=reason[:500],
    )


def _parse_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
