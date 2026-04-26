from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from school_guardian.config import load_dotenv


@dataclass(frozen=True)
class AgentWatchSettings:
    db_path: Path
    telegram_bot_token: str | None
    telegram_target: str | None
    x_bearer_token: str | None
    x_query: str
    x_accounts: tuple[str, ...]
    rss_urls: tuple[str, ...]
    score_threshold: int
    max_digest_items: int
    max_items_per_source: int
    digest_window_hours: int
    openrouter_api_key: str | None
    model_name: str
    model_scoring_enabled: bool
    model_scoring_max_items: int
    model_scoring_page_chars: int


def get_agent_watch_settings() -> AgentWatchSettings:
    load_dotenv()
    db_path = Path(os.getenv("AGENT_WATCH_DB_PATH", "data/agent_watch.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return AgentWatchSettings(
        db_path=db_path,
        telegram_bot_token=os.getenv("AGENT_WATCH_TELEGRAM_BOT_TOKEN"),
        telegram_target=os.getenv("AGENT_WATCH_TELEGRAM_TARGET"),
        x_bearer_token=os.getenv("AGENT_WATCH_X_BEARER_TOKEN"),
        x_query=os.getenv("AGENT_WATCH_X_QUERY", _default_x_query()),
        x_accounts=_split_csv(os.getenv("AGENT_WATCH_X_ACCOUNTS", "")),
        rss_urls=tuple(
            url.strip()
            for url in os.getenv("AGENT_WATCH_RSS_URLS", "").split(",")
            if url.strip()
        ),
        score_threshold=int(os.getenv("AGENT_WATCH_SCORE_THRESHOLD", "4")),
        max_digest_items=int(os.getenv("AGENT_WATCH_MAX_DIGEST_ITEMS", "8")),
        max_items_per_source=int(os.getenv("AGENT_WATCH_MAX_ITEMS_PER_SOURCE", "2")),
        digest_window_hours=int(os.getenv("AGENT_WATCH_DIGEST_WINDOW_HOURS", "24")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
        or os.getenv("AGENT_WATCH_OPENROUTER_API_KEY"),
        model_name=os.getenv("AGENT_WATCH_MODEL_NAME", "openrouter/google/gemma-4-26b-a4b-it"),
        model_scoring_enabled=_env_bool("AGENT_WATCH_MODEL_SCORING_ENABLED", default=False),
        model_scoring_max_items=int(os.getenv("AGENT_WATCH_MODEL_SCORING_MAX_ITEMS", "20")),
        model_scoring_page_chars=int(os.getenv("AGENT_WATCH_MODEL_SCORING_PAGE_CHARS", "5000")),
    )


def build_x_query(settings: AgentWatchSettings) -> str:
    queries = []
    query = settings.x_query.strip()
    if query:
        queries.append(query)
    if settings.x_accounts:
        account_query = " OR ".join(f"from:{account.lstrip('@')}" for account in settings.x_accounts)
        queries.append(f"({account_query}) -is:retweet")
    return "\n".join(queries)


def _default_x_query() -> str:
    return (
        '("claude code" OR opencode OR openclaw OR codex OR cursor OR aider '
        'OR "coding agent" OR "AI agent" OR "agent framework" OR "MCP server" '
        'OR "tool calling" OR "computer use" OR "browser agent" OR "open source agents" '
        'OR "local agents" OR "open source model" OR "open weights" OR langgraph '
        'OR autogen OR crewai OR ollama OR vllm) -is:retweet'
    )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
