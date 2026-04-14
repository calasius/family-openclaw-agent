from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from school_guardian.config import Settings
from school_guardian.domain import ClassroomTask
from school_guardian.store import TaskStore
from school_guardian.telegram_bot import TelegramBotService, TelegramUpdate


class TelegramBotServiceTestCase(unittest.TestCase):
    def test_handle_pending_command(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = TaskStore(
                Settings(
                    db_path=Path(temp_dir) / "test.db",
                    classroom_source="fixture",
                    fixture_path=Path(temp_dir) / "fixture.json",
                    google_credentials_path=Path(temp_dir) / "credentials.json",
                    google_token_path=Path(temp_dir) / "token.json",
                    google_student_id="me",
                    google_course_states=("ACTIVE",),
                    google_page_size=100,
                    google_open_browser=False,
                    google_scopes=("scope-1",),
                    download_dir=Path(temp_dir) / "downloads",
                    telegram_bot_token=None,
                    telegram_allowed_chat_id=None,
                    telegram_poll_timeout_seconds=1,
                    azure_openai_api_key=None,
                    azure_openai_base_url=None,
                    azure_openai_vision_deployment="gpt-4o-mini",
                    azure_document_intelligence_endpoint=None,
                    azure_document_intelligence_key=None,
                    azure_document_intelligence_model="prebuilt-layout",
                    azure_document_intelligence_api_version="2024-11-30",
                )
            )
            store.initialize()
            store.replace_tasks(
                [
                    ClassroomTask(
                        external_id="task-1",
                        course_id="course-1",
                        course_name="Matematica",
                        title="Ejercicios",
                        description="",
                        due_date=date(2026, 4, 8),
                        state="PENDING",
                        source_updated_at="2026-04-07T10:00:00",
                    )
                ]
            )

            bot = TelegramBotService("token", "123", 1)
            response = bot.handle_update(TelegramUpdate(1, "123", "/pendientes"), store)

            self.assertIn("Matematica", response)


if __name__ == "__main__":
    unittest.main()
