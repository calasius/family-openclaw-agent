from __future__ import annotations

from email.utils import parsedate_to_datetime
import hashlib
from urllib.parse import urlparse
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from agent_watch.domain import WatchItem


def fetch_rss_items(urls: tuple[str, ...]) -> list[WatchItem]:
    items: list[WatchItem] = []
    for url in urls:
        try:
            with urlopen(url, timeout=20) as response:
                raw = response.read()
        except Exception:
            continue
        try:
            items.extend(_parse_feed(url, raw))
        except ET.ParseError:
            continue
    return items


def _parse_feed(feed_url: str, raw: bytes) -> list[WatchItem]:
    root = ET.fromstring(raw)
    parsed: list[WatchItem] = []
    for entry in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = _text(entry, "title")
        link = _entry_link(entry)
        description = _text(entry, "description") or _text(entry, "{http://www.w3.org/2005/Atom}summary")
        published = (
            _text(entry, "pubDate")
            or _text(entry, "published")
            or _text(entry, "{http://www.w3.org/2005/Atom}published")
            or None
        )
        external_id = _text(entry, "guid") or link or hashlib.sha256(f"{feed_url}:{title}".encode()).hexdigest()
        parsed.append(
            WatchItem(
                source="rss",
                external_id=external_id,
                author=_feed_label(feed_url),
                title=title,
                text=description or title,
                url=link or feed_url,
                published_at=_normalize_published_at(published),
            )
        )
    return parsed


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is None and not tag.startswith("{"):
        child = element.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    return "".join(child.itertext()).strip() if child is not None else ""


def _entry_link(entry: ET.Element) -> str:
    rss_link = _direct_child_text(entry, "link")
    if rss_link:
        return rss_link

    atom_links = entry.findall("{http://www.w3.org/2005/Atom}link")
    for link in atom_links:
        rel = link.attrib.get("rel", "alternate")
        href = link.attrib.get("href", "")
        link_type = link.attrib.get("type", "")
        if href and rel == "alternate" and (not link_type or link_type == "text/html"):
            return href
    for link in atom_links:
        href = link.attrib.get("href", "")
        if href:
            return href
    return ""


def _direct_child_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return "".join(child.itertext()).strip() if child is not None else ""


def _feed_label(feed_url: str) -> str:
    parsed = urlparse(feed_url)
    return parsed.netloc or feed_url


def _normalize_published_at(value: str | None) -> str | None:
    if not value:
        return None
    if "T" in value:
        return value
    try:
        return parsedate_to_datetime(value).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return value
