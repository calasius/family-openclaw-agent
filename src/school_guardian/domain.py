from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class TaskMaterial:
    material_id: str
    task_external_id: str
    title: str
    material_type: str
    url: str | None = None
    drive_file_id: str | None = None
    mime_type: str | None = None
    extracted_text: str | None = None
    extracted_text_source: str | None = None
    extracted_text_updated_at: str | None = None


@dataclass(frozen=True)
class ClassroomTask:
    external_id: str
    course_id: str
    course_name: str
    title: str
    description: str
    due_date: date | None
    state: str
    source_updated_at: str
    materials: tuple[TaskMaterial, ...] = field(default_factory=tuple)

    @property
    def is_pending(self) -> bool:
        return self.state.lower() not in {"done", "submitted", "completed", "archived"}
