from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_watch.domain import WatchItem


def fetch_x_items(bearer_token: str, query: str, *, max_results: int = 25) -> list[WatchItem]:
    items: list[WatchItem] = []
    for subquery in _split_query(query):
        items.extend(_fetch_x_query(bearer_token, subquery, max_results=max_results))
    return _dedupe_items(items)


def _fetch_x_query(bearer_token: str, query: str, *, max_results: int = 25) -> list[WatchItem]:
    params = urlencode(
        {
            "query": query,
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "created_at,author_id,public_metrics",
            "expansions": "author_id",
            "user.fields": "username,name",
        }
    )
    request = Request(
        f"https://api.x.com/2/tweets/search/recent?{params}",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except HTTPError as error:
        body = error.read().decode("utf-8", "ignore")[:500]
        print(
            json.dumps(
                {
                    "event": "agent_watch_x_fetch_failed",
                    "status": error.code,
                    "reason": error.reason,
                    "body": body,
                },
                ensure_ascii=False,
            )
        )
        return []
    except URLError as error:
        print(
            json.dumps(
                {
                    "event": "agent_watch_x_fetch_failed",
                    "reason": str(error.reason),
                },
                ensure_ascii=False,
            )
        )
        return []

    users = {
        user["id"]: user
        for user in payload.get("includes", {}).get("users", [])
    }
    items: list[WatchItem] = []
    for tweet in payload.get("data", []):
        user = users.get(tweet.get("author_id"), {})
        username = user.get("username") or tweet.get("author_id", "")
        url = f"https://x.com/{username}/status/{tweet['id']}" if username else f"https://x.com/i/web/status/{tweet['id']}"
        items.append(
            WatchItem(
                source="x",
                external_id=tweet["id"],
                author=f"@{username}" if username else "",
                title=tweet["text"][:120],
                text=tweet["text"],
                url=url,
                published_at=tweet.get("created_at"),
                raw_json=json.dumps(tweet, ensure_ascii=False),
            )
        )
    return items


def _split_query(query: str, *, max_chars: int = 450) -> list[str]:
    base_queries = [line.strip() for line in query.splitlines() if line.strip()]
    if all(len(base_query) <= max_chars for base_query in base_queries):
        return base_queries

    split_queries: list[str] = []
    for base_query in base_queries:
        split_queries.extend(_split_long_query(base_query, max_chars=max_chars))
    return split_queries


def _split_long_query(query: str, *, max_chars: int) -> list[str]:
    parts = [part.strip() for part in query.split(" OR ") if part.strip()]
    queries: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current} OR {part}"
        if len(candidate) > max_chars:
            queries.append(_clean_query(current))
            current = part
            continue
        current = candidate
    if current:
        queries.append(_clean_query(current))
    return [query for query in queries if query]


def _clean_query(query: str) -> str:
    query = query.strip()
    while query.startswith("(") and not query.endswith(")"):
        query = query[1:].strip()
    while query.endswith(")") and query.count("(") < query.count(")"):
        query = query[:-1].strip()
    if "-is:retweet" not in query:
        query = f"({query}) -is:retweet"
    return query


def _dedupe_items(items: list[WatchItem]) -> list[WatchItem]:
    seen: set[tuple[str, str]] = set()
    deduped: list[WatchItem] = []
    for item in items:
        key = (item.source, item.external_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
