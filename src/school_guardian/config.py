from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    db_path: Path
    classroom_source: str
    fixture_path: Path
    google_credentials_path: Path
    google_token_path: Path
    google_student_id: str
    google_course_states: tuple[str, ...]
    google_page_size: int
    google_open_browser: bool
    google_scopes: tuple[str, ...]
    download_dir: Path
    telegram_bot_token: str | None
    telegram_allowed_chat_id: str | None
    telegram_poll_timeout_seconds: int
    azure_openai_api_key: str | None
    azure_openai_base_url: str | None
    azure_openai_vision_deployment: str
    azure_document_intelligence_endpoint: str | None
    azure_document_intelligence_key: str | None
    azure_document_intelligence_model: str
    azure_document_intelligence_api_version: str


def get_settings() -> Settings:
    load_dotenv()
    db_path = Path(os.getenv("SCHOOL_GUARDIAN_DB_PATH", "data/school_guardian.db"))
    download_dir = Path(os.getenv("SCHOOL_GUARDIAN_DOWNLOAD_DIR", "data/downloads"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        db_path=db_path,
        classroom_source=os.getenv("SCHOOL_GUARDIAN_CLASSROOM_SOURCE", "fixture"),
        fixture_path=Path(os.getenv("SCHOOL_GUARDIAN_FIXTURE_PATH", "data/classroom_fixture.json")),
        google_credentials_path=Path(
            os.getenv("SCHOOL_GUARDIAN_GOOGLE_CREDENTIALS_PATH", "secrets/google_credentials.json")
        ),
        google_token_path=Path(
            os.getenv("SCHOOL_GUARDIAN_GOOGLE_TOKEN_PATH", "secrets/google_token.json")
        ),
        google_student_id=os.getenv("SCHOOL_GUARDIAN_GOOGLE_STUDENT_ID", "me"),
        google_course_states=tuple(
            state.strip()
            for state in os.getenv(
                "SCHOOL_GUARDIAN_GOOGLE_COURSE_STATES", "ACTIVE,PROVISIONED"
            ).split(",")
            if state.strip()
        ),
        google_page_size=int(os.getenv("SCHOOL_GUARDIAN_GOOGLE_PAGE_SIZE", "100")),
        google_open_browser=os.getenv(
            "SCHOOL_GUARDIAN_GOOGLE_OPEN_BROWSER", "true"
        ).lower()
        in {"1", "true", "yes", "on"},
        google_scopes=tuple(
            scope.strip()
            for scope in os.getenv(
                "SCHOOL_GUARDIAN_GOOGLE_SCOPES",
                "https://www.googleapis.com/auth/classroom.courses.readonly,"
                "https://www.googleapis.com/auth/classroom.coursework.me.readonly,"
                "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly,"
                "https://www.googleapis.com/auth/drive.readonly",
            ).split(",")
            if scope.strip()
        ),
        download_dir=download_dir,
        telegram_bot_token=os.getenv("SCHOOL_GUARDIAN_TELEGRAM_BOT_TOKEN"),
        telegram_allowed_chat_id=os.getenv("SCHOOL_GUARDIAN_TELEGRAM_ALLOWED_CHAT_ID"),
        telegram_poll_timeout_seconds=int(
            os.getenv("SCHOOL_GUARDIAN_TELEGRAM_POLL_TIMEOUT_SECONDS", "30")
        ),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_base_url=os.getenv("AZURE_OPENAI_BASE_URL"),
        azure_openai_vision_deployment=os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT", "gpt-4o-mini"),
        azure_document_intelligence_endpoint=os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        azure_document_intelligence_key=os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY"),
        azure_document_intelligence_model=os.getenv(
            "AZURE_DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout"
        ),
        azure_document_intelligence_api_version=os.getenv(
            "AZURE_DOCUMENT_INTELLIGENCE_API_VERSION", "2024-11-30"
        ),
    )
    return settings
