from __future__ import annotations

import json
from collections import defaultdict
from urllib.request import Request, urlopen

from agent_watch.categories import category_label
from agent_watch.domain import WatchItem


def build_digest(items: list[WatchItem], *, api_key: str | None, model_name: str) -> str:
    if not items:
        return "Agent Watch\n\nNo relevant updates to send."
    if api_key:
        generated = _build_openrouter_digest(items, api_key=api_key, model_name=model_name)
        if generated:
            return generated
    return _build_fallback_digest(items)


def _build_openrouter_digest(items: list[WatchItem], *, api_key: str, model_name: str) -> str | None:
    prompt = {
        "role": "user",
        "content": (
            "Write a short English digest for a Telegram channel called Agent Watch. "
            "The topic is AI agent implementation, Claude Code, OpenCode, OpenClaw, MCP, and open source models. "
            "Group items by category. Include only important items. Format: category header, short title, why it matters in one sentence, and link. "
            "Do not invent facts. Items:\n\n"
            + "\n\n".join(
                f"- category={item.category} source={item.source} author={item.author} score={item.score}\n"
                f"  title={item.title}\n  text={item.text[:1200]}\n  url={item.url}"
                for item in items
            )
        ),
    }
    payload = {
        "model": model_name.removeprefix("openrouter/"),
        "messages": [prompt],
        "temperature": 0.2,
        "max_tokens": 900,
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
    except Exception:
        return None

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    return content or None


def _build_fallback_digest(items: list[WatchItem]) -> str:
    lines = ["Agent Watch", ""]
    grouped: dict[str, list[WatchItem]] = defaultdict(list)
    for item in items:
        grouped[item.category].append(item)

    for category, category_items in grouped.items():
        lines.append(f"# {category_label(category)}")
        for index, item in enumerate(category_items, start=1):
            text = " ".join(item.text.split())
            why = item.score_reason or _why_it_matters(text)
            lines.append(f"{index}. {item.title}")
            if item.author:
                lines.append(f"Source: {item.author} / {item.source}")
            lines.append(f"Why it matters: {why}")
            lines.append(f"Link: {item.url}")
            lines.append("")
        lines.append("")
    return "\n".join(lines).strip()


def _why_it_matters(text: str) -> str:
    lowered = text.lower()
    if "mcp" in lowered:
        return "it may improve integrations and tool access for agents."
    if "claude code" in lowered or "opencode" in lowered:
        return "it affects coding-agent workflows and local automation."
    if "open source model" in lowered or "local model" in lowered:
        return "it may change cost, privacy, or performance tradeoffs for custom agents."
    if "tool" in lowered or "function calling" in lowered:
        return "it touches the practical action-execution layer for agents."
    return "it looks relevant to agent design, operation, or evaluation."
