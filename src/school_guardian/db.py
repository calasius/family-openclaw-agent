from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from school_guardian.config import Settings


class Base(DeclarativeBase):
    pass


class TaskModel(Base):
    __tablename__ = "tasks"

    external_id: Mapped[str] = mapped_column(primary_key=True)
    course_id: Mapped[str]
    course_name: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    due_date: Mapped[str | None]
    state: Mapped[str]
    source_updated_at: Mapped[str]
    synced_at: Mapped[str]

    materials: Mapped[list["TaskMaterialModel"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskMaterialModel(Base):
    __tablename__ = "task_materials"

    material_id: Mapped[str] = mapped_column(primary_key=True)
    task_external_id: Mapped[str] = mapped_column(ForeignKey("tasks.external_id", ondelete="CASCADE"))
    title: Mapped[str]
    material_type: Mapped[str]
    url: Mapped[str | None]
    drive_file_id: Mapped[str | None]
    mime_type: Mapped[str | None]
    extracted_text: Mapped[str | None]
    extracted_text_source: Mapped[str | None]
    extracted_text_updated_at: Mapped[str | None]
    extracted_from_task_source_updated_at: Mapped[str | None]
    synced_at: Mapped[str]

    task: Mapped[TaskModel] = relationship(back_populates="materials")


def create_session_factory(settings: Settings):
    engine = create_engine(f"sqlite:///{settings.db_path}")
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_schema(settings: Settings) -> None:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    if alembic_ini.exists():
        alembic_config = Config(str(alembic_ini))
        alembic_config.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
        alembic_config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")
        command.upgrade(alembic_config, "head")
        return

    engine = create_engine(f"sqlite:///{settings.db_path}")
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(settings: Settings):
    session_factory = create_session_factory(settings)
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
