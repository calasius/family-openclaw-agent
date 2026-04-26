from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import sqlite3

from agent_watch.config import AgentWatchSettings
from agent_watch.domain import WatchItem


@dataclass(frozen=True)
class IngestStats:
    fetched: int
    inserted: int
    updated: int


class AgentWatchStore:
    def __init__(self, settings: AgentWatchSettings) -> None:
        self.settings = settings
        self.db_path = settings.db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT,
                    raw_json TEXT,
                    score INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'new',
                    category TEXT NOT NULL DEFAULT 'general',
                    score_reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sent_at TEXT,
                    UNIQUE(source, external_id)
                )
                """
            )
            _ensure_column(connection, "watch_items", "category", "TEXT NOT NULL DEFAULT 'general'")
            _ensure_column(connection, "watch_items", "score_reason", "TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_text TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                )
                """
            )

    def upsert_items(self, items: list[WatchItem]) -> IngestStats:
        now = _utc_now_iso()
        inserted = 0
        updated = 0
        with self._connect() as connection:
            for item in items:
                existing = connection.execute(
                    "SELECT id, text, score, status, category, score_reason FROM watch_items WHERE source = ? AND external_id = ?",
                    (item.source, item.external_id),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO watch_items (
                            source, external_id, author, title, text, url, published_at,
                            raw_json, score, status, category, score_reason, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.source,
                            item.external_id,
                            item.author,
                            item.title,
                            item.text,
                            item.url,
                            item.published_at,
                            item.raw_json,
                            item.score,
                            item.status,
                            item.category,
                            item.score_reason,
                            now,
                            now,
                        ),
                    )
                    inserted += 1
                    continue

                existing_id, existing_text, existing_score, existing_status, existing_category, existing_reason = existing
                if (
                    existing_text == item.text
                    and existing_score == item.score
                    and existing_category == item.category
                    and existing_reason == item.score_reason
                ):
                    continue

                connection.execute(
                    """
                    UPDATE watch_items
                    SET author = ?, title = ?, text = ?, url = ?, published_at = ?,
                        raw_json = ?, score = ?, status = ?, category = ?, score_reason = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        item.author,
                        item.title,
                        item.text,
                        item.url,
                        item.published_at,
                        item.raw_json,
                        item.score,
                        existing_status if existing_status == "sent" else item.status,
                        item.category,
                        item.score_reason,
                        now,
                        existing_id,
                    ),
                )
                updated += 1
        return IngestStats(fetched=len(items), inserted=inserted, updated=updated)

    def candidate_items(self, *, threshold: int, limit: int, window_hours: int) -> list[WatchItem]:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE status = 'new'
                  AND score >= ?
                  AND (published_at IS NULL OR published_at >= ?)
                ORDER BY score DESC, COALESCE(published_at, created_at) DESC
                LIMIT ?
                """,
                (threshold, cutoff.isoformat(timespec="seconds"), limit),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def search_items(self, query: str, *, limit: int = 10) -> list[WatchItem]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []

        where = " AND ".join(["lower(title || ' ' || text || ' ' || author || ' ' || source) LIKE ?"] * len(terms))
        params = [f"%{term}%" for term in terms]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE {where}
                ORDER BY score DESC, COALESCE(published_at, created_at) DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def search_any_terms(self, terms: tuple[str, ...], *, limit: int = 10) -> list[WatchItem]:
        cleaned_terms = [term.lower() for term in terms if term.strip()]
        if not cleaned_terms:
            return []

        where = " OR ".join(["lower(title || ' ' || text || ' ' || author || ' ' || source) LIKE ?"] * len(cleaned_terms))
        params = [f"%{term}%" for term in cleaned_terms]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE {where}
                ORDER BY score DESC, COALESCE(published_at, created_at) DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def recent_items(self, *, days: int = 7, limit: int = 10) -> list[WatchItem]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE score > 0
                  AND COALESCE(published_at, created_at) >= ?
                ORDER BY COALESCE(published_at, created_at) DESC, score DESC
                LIMIT ?
                """,
                (cutoff.isoformat(timespec="seconds"), limit),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def item_detail(self, source: str, external_id: str) -> WatchItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE source = ? AND external_id = ?
                """,
                (source, external_id),
            ).fetchone()
        return _row_to_item(row) if row else None

    def all_relevant_items(self, *, limit: int = 500) -> list[WatchItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason
                FROM watch_items
                WHERE score > 0
                ORDER BY COALESCE(published_at, created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def mark_sent(self, items: list[WatchItem], summary_text: str) -> None:
        if not items:
            return
        now = _utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO watch_digests (summary_text, item_count, created_at, sent_at) VALUES (?, ?, ?, ?)",
                (summary_text, len(items), now, now),
            )
            for item in items:
                connection.execute(
                    """
                    UPDATE watch_items
                    SET status = 'sent', sent_at = ?, updated_at = ?
                    WHERE source = ? AND external_id = ?
                    """,
                    (now, now, item.source, item.external_id),
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _row_to_item(row: sqlite3.Row | tuple) -> WatchItem:
    source, external_id, author, title, text, url, published_at, raw_json, score, status, category, score_reason = row
    return WatchItem(
        source=source,
        external_id=external_id,
        author=author,
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        raw_json=raw_json,
        score=score,
        status=status,
        category=category,
        score_reason=score_reason,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
