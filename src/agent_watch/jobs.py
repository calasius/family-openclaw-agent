from __future__ import annotations

from agent_watch.config import AgentWatchSettings, build_x_query
from agent_watch.model_scoring import model_score_items
from agent_watch.scoring import score_item
from agent_watch.sources.rss_source import fetch_rss_items
from agent_watch.sources.x_source import fetch_x_items
from agent_watch.store import AgentWatchStore, IngestStats
from agent_watch.summarizer import build_digest
from agent_watch.telegram import AgentWatchTelegram


def run_fetch(settings: AgentWatchSettings, store: AgentWatchStore) -> IngestStats:
    store.initialize()
    items = []
    if settings.x_bearer_token:
        items.extend(fetch_x_items(settings.x_bearer_token, build_x_query(settings)))
    if settings.rss_urls:
        items.extend(fetch_rss_items(settings.rss_urls))
    scored = [score_item(item) for item in items]
    if settings.model_scoring_enabled:
        scored = model_score_items(
            scored,
            api_key=settings.openrouter_api_key,
            model_name=settings.model_name,
            max_items=settings.model_scoring_max_items,
            page_chars=settings.model_scoring_page_chars,
        )
    return store.upsert_items(scored)


def run_digest(settings: AgentWatchSettings, store: AgentWatchStore) -> tuple[str, list]:
    store.initialize()
    items = store.candidate_items(
        threshold=settings.score_threshold,
        limit=settings.max_digest_items * max(settings.max_items_per_source, 1),
        window_hours=settings.digest_window_hours,
    )
    items = _limit_items_per_source(
        items,
        max_items=settings.max_digest_items,
        max_per_source=settings.max_items_per_source,
    )
    digest = build_digest(
        items,
        api_key=settings.openrouter_api_key,
        model_name=settings.model_name,
    )
    return digest, items


def run_send_digest(settings: AgentWatchSettings, store: AgentWatchStore) -> str:
    if not settings.telegram_bot_token or not settings.telegram_target:
        raise RuntimeError("Missing AGENT_WATCH_TELEGRAM_BOT_TOKEN and AGENT_WATCH_TELEGRAM_TARGET.")

    digest, items = run_digest(settings, store)
    if not items:
        return "No relevant updates to send."

    AgentWatchTelegram(settings.telegram_bot_token, settings.telegram_target).send_message(digest)
    store.mark_sent(items, digest)
    return f"Digest sent with {len(items)} items."


def _limit_items_per_source(
    items: list,
    *,
    max_items: int,
    max_per_source: int,
) -> list:
    selected = []
    counts: dict[str, int] = {}
    for item in items:
        source_key = item.author or item.source
        if counts.get(source_key, 0) >= max_per_source:
            continue
        selected.append(item)
        counts[source_key] = counts.get(source_key, 0) + 1
        if len(selected) >= max_items:
            break
    return selected
