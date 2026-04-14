from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from school_guardian.config import Settings
from school_guardian.domain import TaskMaterial
from school_guardian.materials import (
    MaterialBlob,
    _resolve_url_material_blob,
    extract_text_from_material,
    extract_text_with_source_from_material,
)


class MaterialsExtractionTestCase(unittest.TestCase):
    def test_extract_text_from_material_prefers_document_intelligence(self) -> None:
        settings = _settings()
        material = TaskMaterial(
            material_id="mat-1",
            task_external_id="task-1",
            title="Worksheet",
            material_type="link",
            url="https://example.com/worksheet.pdf",
        )

        with patch(
            "school_guardian.materials._resolve_material_blob",
            return_value=MaterialBlob(
                filename="worksheet.pdf",
                mime_type="application/pdf",
                data=b"%PDF-1.7",
            ),
        ), patch(
            "school_guardian.materials._analyze_with_document_intelligence",
            return_value="# Texto desde DI",
        ), patch("school_guardian.materials._extract_from_url") as fallback:
            extracted = extract_text_from_material(material, settings)

        self.assertEqual(extracted, "# Texto desde DI")
        fallback.assert_not_called()

    def test_resolve_url_material_blob_supports_images(self) -> None:
        material = TaskMaterial(
            material_id="mat-2",
            task_external_id="task-1",
            title="Foto",
            material_type="link",
            url="https://example.com/photo.jpg",
        )

        class _Headers:
            def get_content_type(self) -> str:
                return "image/jpeg"

        class _Response:
            headers = _Headers()

            def read(self) -> bytes:
                return b"fake-image"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("school_guardian.materials.urlopen", return_value=_Response()):
            blob = _resolve_url_material_blob(material)

        assert blob is not None
        self.assertEqual(blob.filename, "photo.jpg")
        self.assertEqual(blob.mime_type, "image/jpeg")
        self.assertEqual(blob.data, b"fake-image")

    def test_extract_text_from_material_falls_back_when_di_returns_none(self) -> None:
        settings = _settings()
        material = TaskMaterial(
            material_id="mat-3",
            task_external_id="task-1",
            title="Worksheet",
            material_type="link",
            url="https://example.com/worksheet.pdf",
        )

        with patch(
            "school_guardian.materials._resolve_material_blob",
            return_value=MaterialBlob(
                filename="worksheet.pdf",
                mime_type="application/pdf",
                data=b"%PDF-1.7",
            ),
        ), patch(
            "school_guardian.materials._analyze_with_document_intelligence",
            return_value=None,
        ), patch(
            "school_guardian.materials._extract_from_url",
            return_value="texto fallback",
        ):
            extracted = extract_text_from_material(material, settings)

        self.assertEqual(extracted, "texto fallback")

    def test_extract_text_with_source_reports_document_intelligence(self) -> None:
        settings = _settings()
        material = TaskMaterial(
            material_id="mat-4",
            task_external_id="task-1",
            title="Worksheet",
            material_type="link",
            url="https://example.com/worksheet.pdf",
        )

        with patch(
            "school_guardian.materials._resolve_material_blob",
            return_value=MaterialBlob(
                filename="worksheet.pdf",
                mime_type="application/pdf",
                data=b"%PDF-1.7",
            ),
        ), patch(
            "school_guardian.materials._analyze_with_document_intelligence",
            return_value="# Texto desde DI",
        ):
            extracted = extract_text_with_source_from_material(material, settings)

        self.assertEqual(extracted.text, "# Texto desde DI")
        self.assertEqual(extracted.source, "azure_document_intelligence")


def _settings() -> Settings:
    root = Path("/tmp/school-guardian-tests")
    return Settings(
        db_path=root / "test.db",
        classroom_source="fixture",
        fixture_path=root / "fixture.json",
        google_credentials_path=root / "credentials.json",
        google_token_path=root / "token.json",
        google_student_id="me",
        google_course_states=("ACTIVE",),
        google_page_size=100,
        google_open_browser=False,
        google_scopes=("scope-1",),
        download_dir=root / "downloads",
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


if __name__ == "__main__":
    unittest.main()
