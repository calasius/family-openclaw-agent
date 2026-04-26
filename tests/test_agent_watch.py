from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_watch.config import AgentWatchSettings, build_x_query
from agent_watch.domain import WatchItem
from agent_watch.jobs import _limit_items_per_source
from agent_watch.model_scoring import _parse_json_object
from agent_watch.page_chunk import html_to_text
from agent_watch.scoring import score_item
from agent_watch.sources.x_source import _split_query
from agent_watch.sources.rss_source import _parse_feed
from agent_watch.store import AgentWatchStore
from agent_watch.summarizer import build_digest
from agent_watch.topics import count_topics, detect_topics, topic_query, topic_terms


class AgentWatchScoringTestCase(unittest.TestCase):
    def test_scores_relevant_agent_item(self) -> None:
        item = score_item(
            WatchItem(
                source="x",
                external_id="1",
                author="@dev",
                title="Claude Code and MCP",
                text="Claude Code now works better with MCP tool calling for agents.",
                url="https://x.com/dev/status/1",
            )
        )

        self.assertGreaterEqual(item.score, 4)
        self.assertEqual(item.status, "new")

    def test_html_to_text_removes_scripts(self) -> None:
        text = html_to_text("<html><script>bad()</script><h1>Title</h1><p>Agent tools</p></html>")

        self.assertIn("Title", text)
        self.assertIn("Agent tools", text)
        self.assertNotIn("bad", text)

    def test_parse_json_object_from_model_text(self) -> None:
        parsed = _parse_json_object('```json\n{"score": 8, "reason": "relevant"}\n```')

        self.assertEqual(parsed["score"], 8)

    def test_discards_irrelevant_item(self) -> None:
        item = score_item(
            WatchItem(
                source="x",
                external_id="2",
                author="@spam",
                title="Crypto giveaway",
                text="crypto airdrop giveaway",
                url="https://x.com/spam/status/2",
            )
        )

        self.assertEqual(item.score, 0)
        self.assertEqual(item.status, "discarded")

    def test_scores_repo_release_from_url(self) -> None:
        item = score_item(
            WatchItem(
                source="rss",
                external_id="release-1",
                author="github.com/sst/opencode",
                title="v1.2.3",
                text="Bug fixes",
                url="https://github.com/sst/opencode/releases/tag/v1.2.3",
            )
        )

        self.assertGreaterEqual(item.score, 4)
        self.assertEqual(item.category, "opencode")


class AgentWatchConfigTestCase(unittest.TestCase):
    def test_build_x_query_adds_accounts(self) -> None:
        settings = _settings_for(Path("/tmp"))
        settings = AgentWatchSettings(
            **{
                **settings.__dict__,
                "x_query": '"coding agent" -is:retweet',
                "x_accounts": ("simonw", "@latentspacepod"),
            }
        )

        query = build_x_query(settings)

        self.assertIn('"coding agent" -is:retweet', query)
        self.assertIn("from:simonw", query)
        self.assertIn("from:latentspacepod", query)

    def test_x_query_is_split_into_lines_for_keywords_and_accounts(self) -> None:
        settings = _settings_for(Path("/tmp"))
        settings = AgentWatchSettings(
            **{
                **settings.__dict__,
                "x_query": '"coding agent" -is:retweet',
                "x_accounts": ("simonw", "@latentspacepod"),
            }
        )

        queries = _split_query(build_x_query(settings))

        self.assertEqual(len(queries), 2)
        self.assertIn('"coding agent"', queries[0])
        self.assertIn("from:simonw", queries[1])


class AgentWatchTopicsTestCase(unittest.TestCase):
    def test_detect_topics_from_item_text(self) -> None:
        item = WatchItem(
            source="x",
            external_id="1",
            author="@dev",
            title="MCP server for coding agents",
            text="Claude Code can use this Model Context Protocol server.",
            url="https://x.com/dev/status/1",
        )

        topics = detect_topics(item)

        self.assertIn("mcp", topics)
        self.assertIn("claude-code", topics)
        self.assertIn("coding-agents", topics)

    def test_topic_query_expands_known_topic(self) -> None:
        self.assertIn("ollama", topic_query("#local-inference"))
        self.assertIn("mcp", topic_terms("#mcp"))


class AgentWatchStoreTestCase(unittest.TestCase):
    def test_upsert_select_and_mark_sent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = AgentWatchStore(settings)
            store.initialize()
            item = score_item(
                WatchItem(
                    source="rss",
                    external_id="post-1",
                    author="https://example.com/feed.xml",
                    title="OpenClaw agent tools",
                    text="OpenClaw agent orchestration with tool calling.",
                    url="https://example.com/post-1",
                    published_at="2026-04-24T10:00:00+00:00",
                )
            )

            stats = store.upsert_items([item])
            candidates = store.candidate_items(threshold=4, limit=5, window_hours=96)
            store.mark_sent(candidates, "digest")
            remaining = store.candidate_items(threshold=4, limit=5, window_hours=96)

            self.assertEqual(stats.inserted, 1)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(remaining, [])

    def test_search_recent_and_topics_from_base(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = AgentWatchStore(settings)
            store.initialize()
            item = score_item(
                WatchItem(
                    source="x",
                    external_id="123",
                    author="@dev",
                    title="LangGraph MCP release",
                    text="New MCP server for agent framework workflows.",
                    url="https://x.com/dev/status/123",
                    published_at="2026-04-24T10:00:00+00:00",
                )
            )

            store.upsert_items([item])
            search_results = store.search_items("mcp agent", limit=5)
            topic_results = store.search_any_terms(topic_terms("mcp"), limit=5)
            recent_results = store.recent_items(days=7, limit=5)
            topic_counts = count_topics(store.all_relevant_items())

            self.assertEqual(len(search_results), 1)
            self.assertEqual(len(topic_results), 1)
            self.assertEqual(len(recent_results), 1)
            self.assertIn("mcp", {topic.topic for topic in topic_counts})


class AgentWatchDigestTestCase(unittest.TestCase):
    def test_fallback_digest_includes_links(self) -> None:
        digest = build_digest(
            [
                WatchItem(
                    source="x",
                    external_id="1",
                    author="@dev",
                    title="OpenCode release",
                    text="OpenCode improves coding agents.",
                    url="https://x.com/dev/status/1",
                    score=5,
                    category="opencode",
                )
            ],
            api_key=None,
            model_name="openrouter/test",
        )

        self.assertIn("Agent Watch", digest)
        self.assertIn("OpenCode", digest)
        self.assertIn("https://x.com/dev/status/1", digest)

    def test_limits_digest_items_per_source(self) -> None:
        items = [
            WatchItem("rss", "1", "source-a", "A1", "agent", "https://a/1", score=5),
            WatchItem("rss", "2", "source-a", "A2", "agent", "https://a/2", score=5),
            WatchItem("rss", "3", "source-a", "A3", "agent", "https://a/3", score=5),
            WatchItem("rss", "4", "source-b", "B1", "agent", "https://b/1", score=5),
        ]

        selected = _limit_items_per_source(items, max_items=4, max_per_source=2)

        self.assertEqual([item.external_id for item in selected], ["1", "2", "4"])


class AgentWatchRssTestCase(unittest.TestCase):
    def test_atom_parser_prefers_post_link_over_feed_link(self) -> None:
        raw = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>OpenClaw update</title>
            <link rel="self" href="https://example.com/feed.xml" />
            <link rel="alternate" type="text/html" href="https://example.com/posts/openclaw-update" />
            <summary>OpenClaw agent tooling update.</summary>
            <id>tag:example.com,2026:openclaw-update</id>
            <published>2026-04-24T10:00:00+00:00</published>
          </entry>
        </feed>
        """

        items = _parse_feed("https://example.com/feed.xml", raw)

        self.assertEqual(items[0].url, "https://example.com/posts/openclaw-update")
        self.assertEqual(items[0].author, "example.com")


def _settings_for(temp_dir: Path) -> AgentWatchSettings:
    return AgentWatchSettings(
        db_path=temp_dir / "agent_watch.db",
        telegram_bot_token=None,
        telegram_target=None,
        x_bearer_token=None,
        x_query="",
        x_accounts=(),
        rss_urls=(),
        score_threshold=4,
        max_digest_items=8,
        max_items_per_source=2,
        digest_window_hours=24,
        openrouter_api_key=None,
        model_name="openrouter/test",
        model_scoring_enabled=False,
        model_scoring_max_items=20,
        model_scoring_page_chars=5000,
    )


if __name__ == "__main__":
    unittest.main()
