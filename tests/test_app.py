from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from school_guardian.config import Settings
from school_guardian.domain import ClassroomTask, TaskMaterial
from school_guardian.focus import daily_focus
from school_guardian.jobs import run_classroom_sync
from school_guardian.store import TaskStore


class TaskStoreTestCase(unittest.TestCase):
    def test_upsert_and_pending(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = TaskStore(settings)
            store.initialize()

            task = ClassroomTask(
                external_id="task-1",
                course_id="course-1",
                course_name="Matematica",
                title="Tarea 1",
                description="Desc",
                due_date=date(2026, 4, 8),
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
                materials=(
                    TaskMaterial(
                        material_id="mat-1",
                        task_external_id="task-1",
                        title="Guia",
                        material_type="link",
                        url="https://example.com/guia.pdf",
                    ),
                ),
            )

            stats = store.replace_tasks([task])
            pending = store.pending_tasks()

            self.assertEqual(stats.total, 1)
            self.assertEqual(stats.inserted, 1)
            self.assertEqual(stats.updated, 0)
            self.assertEqual(len(pending), 1)
            self.assertEqual(len(pending[0].materials), 1)

    def test_replace_tasks_preserves_cached_material_text_when_task_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = TaskStore(settings)
            store.initialize()

            task = ClassroomTask(
                external_id="task-1",
                course_id="course-1",
                course_name="Matematica",
                title="Tarea 1",
                description="Desc",
                due_date=date(2026, 4, 8),
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
                materials=(
                    TaskMaterial(
                        material_id="mat-1",
                        task_external_id="task-1",
                        title="Guia",
                        material_type="link",
                        url="https://example.com/guia.pdf",
                    ),
                ),
            )

            store.replace_tasks([task])
            store.update_material_extraction(
                material_id="mat-1",
                extracted_text="texto cacheado",
                extracted_text_source="azure_document_intelligence",
                task_source_updated_at="2026-04-07T10:00:00",
            )

            store.replace_tasks([task])

            refreshed = store.get_task("task-1")
            assert refreshed is not None
            self.assertEqual(refreshed.materials[0].extracted_text, "texto cacheado")
            self.assertEqual(refreshed.materials[0].extracted_text_source, "azure_document_intelligence")

    def test_run_classroom_sync_warms_material_cache(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = TaskStore(settings)
            store.initialize()

            task = ClassroomTask(
                external_id="task-1",
                course_id="course-1",
                course_name="Matematica",
                title="Tarea 1",
                description="Desc",
                due_date=date(2026, 4, 8),
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
                materials=(
                    TaskMaterial(
                        material_id="mat-1",
                        task_external_id="task-1",
                        title="Guia",
                        material_type="link",
                        url="https://example.com/guia.pdf",
                    ),
                ),
            )

            class _Client:
                def fetch_tasks(self):
                    return [task]

            from unittest.mock import patch

            with patch(
                "school_guardian.jobs.extract_text_with_source_from_material",
                return_value=type("Result", (), {"text": "texto sync", "source": "azure_document_intelligence"})(),
            ):
                run_classroom_sync(_Client(), store)

            refreshed = store.get_task("task-1")
            assert refreshed is not None
            self.assertEqual(refreshed.materials[0].extracted_text, "texto sync")
            self.assertEqual(refreshed.materials[0].extracted_text_source, "azure_document_intelligence")

    def test_replace_tasks_prunes_old_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _settings_for(Path(temp_dir))
            store = TaskStore(settings)
            store.initialize()

            first = ClassroomTask(
                external_id="task-1",
                course_id="course-1",
                course_name="Matematica",
                title="Tarea 1",
                description="Desc",
                due_date=date(2026, 4, 8),
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
            )
            second = ClassroomTask(
                external_id="task-2",
                course_id="course-1",
                course_name="Matematica",
                title="Tarea 2",
                description="Desc",
                due_date=date(2026, 4, 9),
                state="PENDING",
                source_updated_at="2026-04-07T11:00:00",
            )

            store.replace_tasks([first])
            store.replace_tasks([second])

            pending = store.pending_tasks()
            self.assertEqual([task.external_id for task in pending], ["task-2"])


class DailyFocusTestCase(unittest.TestCase):
    def test_daily_focus_orders_urgent_first(self) -> None:
        tasks = [
            ClassroomTask(
                external_id="task-1",
                course_id="course-1",
                course_name="Ingles",
                title="Sin fecha",
                description="",
                due_date=None,
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
                materials=(),
            ),
            ClassroomTask(
                external_id="task-2",
                course_id="course-2",
                course_name="Matematica",
                title="Urgente",
                description="",
                due_date=date(2026, 4, 8),
                state="PENDING",
                source_updated_at="2026-04-07T10:00:00",
                materials=(),
            ),
        ]

        ordered = daily_focus(tasks, today=date(2026, 4, 7))

        self.assertEqual(ordered[0].title, "Urgente")


if __name__ == "__main__":
    unittest.main()


def _settings_for(temp_dir: Path) -> Settings:
    return Settings(
        db_path=temp_dir / "test.db",
        classroom_source="fixture",
        fixture_path=temp_dir / "fixture.json",
        google_credentials_path=temp_dir / "credentials.json",
        google_token_path=temp_dir / "token.json",
        google_student_id="me",
        google_course_states=("ACTIVE",),
        google_page_size=100,
        google_open_browser=False,
        google_scopes=("scope-1",),
        download_dir=temp_dir / "downloads",
        telegram_bot_token=None,
        telegram_allowed_chat_id=None,
        telegram_poll_timeout_seconds=1,
        azure_openai_api_key=None,
        azure_openai_base_url=None,
        azure_openai_vision_deployment="gpt-4o-mini",
        azure_document_intelligence_endpoint="https://example.cognitiveservices.azure.com/",
        azure_document_intelligence_key="secret",
        azure_document_intelligence_model="prebuilt-layout",
        azure_document_intelligence_api_version="2024-11-30",
    )
