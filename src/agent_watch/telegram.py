from __future__ import annotations

from urllib.parse import urlencode
from urllib.request import Request, urlopen


class AgentWatchTelegram:
    def __init__(self, bot_token: str, target: str) -> None:
        self.bot_token = bot_token
        self.target = target
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str) -> None:
        for chunk in _telegram_chunks(text):
            payload = urlencode(
                {
                    "chat_id": self.target,
                    "text": chunk,
                    "disable_web_page_preview": "true",
                }
            ).encode()
            request = Request(f"{self.base_url}/sendMessage", data=payload, method="POST")
            urlopen(request).read()


def _telegram_chunks(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return chunks

