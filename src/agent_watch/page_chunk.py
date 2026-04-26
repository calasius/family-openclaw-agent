from __future__ import annotations

from html.parser import HTMLParser
from urllib.request import Request, urlopen


def fetch_page_chunk(url: str, *, max_chars: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "AgentWatch/0.1 (+https://local.school-guardian)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=20) as response:
        content_type = response.headers.get("content-type", "")
        raw = response.read(max(max_chars * 4, 4096))
    if "html" not in content_type and b"<html" not in raw[:500].lower():
        return raw.decode("utf-8", "ignore")[:max_chars].strip()
    return html_to_text(raw.decode("utf-8", "ignore"))[:max_chars].strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return " ".join(parser.text.split())


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self.text += " "

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "article", "section"}:
            self.text += " "

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.text += f" {data}"

