from __future__ import annotations


CATEGORY_LABELS: dict[str, str] = {
    "courses-tutorials": "Courses & Tutorials",
    "papers-research": "Papers & Research",
    "demos": "Demos",
    "openclaw": "OpenClaw",
    "opencode": "OpenCode",
    "agent-harnesses": "Agent Harnesses",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "open-source-llms": "Open Source LLMs",
    "mcp-tooling": "MCP & Tooling",
    "coding-agents": "Coding Agents",
    "local-inference": "Local Inference",
    "benchmarks-evals": "Benchmarks & Evals",
    "funding-product": "Products & Funding",
    "general": "General Agent News",
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "courses-tutorials": ("course", "tutorial", "guide", "workshop", "lesson", "learn", "how to"),
    "papers-research": ("paper", "arxiv", "research", "technical report", "study"),
    "demos": ("demo", "showcase", "video", "launch demo", "built with"),
    "openclaw": ("openclaw",),
    "opencode": ("opencode",),
    "agent-harnesses": ("harness", "agent harness", "sandbox", "eval harness", "test harness"),
    "openai": ("openai", "codex", "gpt-5", "gpt-4", "responses api"),
    "anthropic": ("anthropic", "claude", "claude code"),
    "open-source-llms": ("open source model", "open-source model", "open weights", "qwen", "deepseek", "llama", "mistral"),
    "mcp-tooling": ("mcp", "model context protocol", "tool calling", "function calling", "server"),
    "coding-agents": ("coding agent", "claude code", "codex", "cursor", "aider"),
    "local-inference": ("ollama", "vllm", "llama.cpp", "local inference", "local model"),
    "benchmarks-evals": ("benchmark", "eval", "evals", "swe-bench", "terminal-bench"),
    "funding-product": ("raises", "funding", "startup", "product launch", "pricing"),
}


def infer_category(title: str, text: str, author: str, url: str) -> str:
    haystack = f"{title}\n{text}\n{author}\n{url}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "general"


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS["general"])

