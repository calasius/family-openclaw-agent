from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agent_watch.domain import WatchItem


TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "claude-code": ("claude code",),
    "opencode": ("opencode",),
    "openclaw": ("openclaw",),
    "codex": ("codex",),
    "coding-agents": ("coding agent", "coding agents", "aider", "cursor"),
    "mcp": ("mcp", "model context protocol"),
    "tool-calling": ("tool calling", "function calling", "tools"),
    "browser-agents": ("browser agent", "computer use", "browser automation"),
    "agent-frameworks": ("agent framework", "langgraph", "autogen", "crewai", "crew ai"),
    "open-source-models": ("open source model", "open-source model", "open weights", "open-weight"),
    "local-inference": ("ollama", "vllm", "llama.cpp", "local model", "local inference"),
    "evals": ("eval", "evals", "benchmark", "benchmarks"),
}


@dataclass(frozen=True)
class TopicCount:
    topic: str
    count: int
    query: str


def detect_topics(item: WatchItem) -> set[str]:
    haystack = f"{item.title}\n{item.text}\n{item.author}\n{item.source}".lower()
    topics: set[str] = set()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            topics.add(topic)
    return topics


def topic_query(topic: str) -> str:
    normalized = normalize_topic(topic)
    keywords = TOPIC_KEYWORDS.get(normalized)
    if not keywords:
        return topic
    return " ".join(keywords)


def topic_terms(topic: str) -> tuple[str, ...]:
    normalized = normalize_topic(topic)
    return TOPIC_KEYWORDS.get(normalized, (topic,))


def normalize_topic(value: str) -> str:
    return value.strip().lower().replace("_", "-").lstrip("#")


def count_topics(items: list[WatchItem]) -> list[TopicCount]:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update(detect_topics(item))
    return [
        TopicCount(topic=topic, count=count, query=topic_query(topic))
        for topic, count in counter.most_common()
    ]


def format_topic_counts(topic_counts: list[TopicCount]) -> str:
    if not topic_counts:
        return "No topics detected yet."
    lines = ["Available topics:"]
    for topic_count in topic_counts:
        lines.append(f"- #{topic_count.topic} ({topic_count.count}) query: {topic_count.query}")
    return "\n".join(lines)
