from __future__ import annotations

from school_guardian.classroom import FixtureClassroomClient, GoogleClassroomClient
from school_guardian.config import get_settings


def build_client() -> FixtureClassroomClient | GoogleClassroomClient:
    settings = get_settings()
    if settings.classroom_source == "fixture":
        return FixtureClassroomClient(settings.fixture_path)

    if settings.classroom_source == "google":
        return GoogleClassroomClient(
            credentials_path=settings.google_credentials_path,
            token_path=settings.google_token_path,
            scopes=settings.google_scopes,
            student_id=settings.google_student_id,
            course_states=settings.google_course_states,
            page_size=settings.google_page_size,
            open_browser=settings.google_open_browser,
        )

    raise ValueError(
        f"Fuente Classroom no soportada: {settings.classroom_source}. Usá 'fixture' o 'google'."
    )
