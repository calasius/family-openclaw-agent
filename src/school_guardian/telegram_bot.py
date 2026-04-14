from __future__ import annotations

import json
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from school_guardian.focus import daily_focus
from school_guardian.store import TaskStore


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    chat_id: str
    text: str


class TelegramBotService:
    def __init__(self, bot_token: str, allowed_chat_id: str | None, poll_timeout_seconds: int) -> None:
        self.bot_token = bot_token
        self.allowed_chat_id = allowed_chat_id
        self.poll_timeout_seconds = poll_timeout_seconds
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def get_updates(self, offset: int | None = None) -> list[TelegramUpdate]:
        query = {"timeout": self.poll_timeout_seconds}
        if offset is not None:
            query["offset"] = offset
        payload = self._get_json(f"{self.base_url}/getUpdates?{urlencode(query)}")
        updates: list[TelegramUpdate] = []
        for item in payload.get("result", []):
            message = item.get("message") or {}
            chat = message.get("chat") or {}
            text = message.get("text")
            if not text:
                continue
            updates.append(
                TelegramUpdate(
                    update_id=item["update_id"],
                    chat_id=str(chat["id"]),
                    text=text.strip(),
                )
            )
        return updates

    def send_message(self, chat_id: str, text: str) -> None:
        payload = urlencode({"chat_id": chat_id, "text": text}).encode()
        request = Request(f"{self.base_url}/sendMessage", data=payload, method="POST")
        urlopen(request).read()

    def send_document(self, chat_id: str, filename: str, data: bytes, caption: str = "") -> None:
        boundary = uuid.uuid4().hex
        body = _multipart_body(boundary, chat_id, filename, data, caption)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
        request = Request(f"{self.base_url}/sendDocument", data=body, headers=headers, method="POST")
        urlopen(request).read()

    def handle_update(self, update: TelegramUpdate, store: TaskStore) -> str | None:
        if self.allowed_chat_id and update.chat_id != self.allowed_chat_id:
            return None

        command = update.text.split()[0].lower()
        if command in {"/start", "/help"}:
            return (
                "Comandos: /pendientes, /manana, /foco, /nuevo.\n"
                "OpenClaw usa este bot para responder tareas y foco diario."
            )
        if command == "/pendientes":
            return format_task_list(store.pending_tasks(), "No hay tareas pendientes.")
        if command == "/manana":
            tomorrow = date.today() + timedelta(days=1)
            return format_task_list(
                store.due_between(tomorrow, tomorrow),
                "No hay tareas que venzan mañana.",
            )
        if command == "/foco":
            return format_task_list(
                daily_focus(store.pending_tasks()),
                "No hay tareas para foco de hoy.",
            )
        if command == "/nuevo":
            return format_task_list(
                store.new_since(24),
                "No hubo tareas nuevas en las últimas 24 horas.",
            )
        return "No entendí el comando. Usá /help."

    def _get_json(self, url: str) -> dict:
        with urlopen(url) as response:
            return json.loads(response.read().decode())


def _multipart_body(boundary: str, chat_id: str, filename: str, data: bytes, caption: str) -> bytes:
    sep = f"--{boundary}\r\n".encode()
    end = f"--{boundary}--\r\n".encode()
    parts = [
        sep,
        b'Content-Disposition: form-data; name="chat_id"\r\n\r\n',
        chat_id.encode() + b"\r\n",
        sep,
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/pdf\r\n\r\n",
        data + b"\r\n",
    ]
    if caption:
        parts += [
            sep,
            b'Content-Disposition: form-data; name="caption"\r\n\r\n',
            caption.encode() + b"\r\n",
        ]
    parts.append(end)
    return b"".join(parts)


def format_task_list(tasks, empty_message: str) -> str:
    if not tasks:
        return empty_message
    lines = []
    for task in tasks[:10]:
        due_label = task.due_date.isoformat() if task.due_date else "sin fecha"
        material_label = f" | materiales: {len(task.materials)}" if task.materials else ""
        lines.append(f"id:{task.external_id} | {task.course_name} | {task.title} | {due_label}{material_label}")
    return "\n".join(lines)
