from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from school_guardian.config import Settings
from school_guardian.db import TaskMaterialModel, TaskModel, ensure_schema, session_scope, utc_now_iso
from school_guardian.domain import ClassroomTask, TaskMaterial


@dataclass(frozen=True)
class SyncStats:
    total: int
    inserted: int
    updated: int
    deleted: int


class TaskStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db_path = settings.db_path

    def initialize(self) -> None:
        self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        ensure_schema(self.settings)

    def replace_tasks(self, tasks: list[ClassroomTask]) -> SyncStats:
        inserted = 0
        updated = 0
        deleted = 0
        synced_at = utc_now_iso()
        incoming_ids = {task.external_id for task in tasks}

        with session_scope(self.settings) as session:
            existing_by_id = {
                model.external_id: model
                for model in session.scalars(
                    select(TaskModel).options(selectinload(TaskModel.materials))
                ).all()
            }
            deleted = len(set(existing_by_id) - incoming_ids)

            for task in tasks:
                existing = existing_by_id.get(task.external_id)
                if existing is None:
                    model = TaskModel(
                        external_id=task.external_id,
                        course_id=task.course_id,
                        course_name=task.course_name,
                        title=task.title,
                        description=task.description,
                        due_date=task.due_date.isoformat() if task.due_date else None,
                        state=task.state,
                        source_updated_at=task.source_updated_at,
                        synced_at=synced_at,
                    )
                    model.materials = [_to_material_model(material, synced_at, None, task.source_updated_at) for material in task.materials]
                    session.add(model)
                    inserted += 1
                    continue

                if existing.source_updated_at != task.source_updated_at:
                    updated += 1

                existing.course_id = task.course_id
                existing.course_name = task.course_name
                existing.title = task.title
                existing.description = task.description
                existing.due_date = task.due_date.isoformat() if task.due_date else None
                existing.state = task.state
                existing.source_updated_at = task.source_updated_at
                existing.synced_at = synced_at
                existing_materials = {
                    material.material_id: material
                    for material in existing.materials
                }
                existing.materials = [
                    _to_material_model(
                        material,
                        synced_at,
                        existing_materials.get(material.material_id),
                        task.source_updated_at,
                    )
                    for material in task.materials
                ]

            if incoming_ids:
                session.execute(
                    delete(TaskMaterialModel).where(
                        TaskMaterialModel.task_external_id.not_in(incoming_ids)
                    )
                )
                session.execute(delete(TaskModel).where(TaskModel.external_id.not_in(incoming_ids)))
            else:
                session.execute(delete(TaskMaterialModel))
                session.execute(delete(TaskModel))

        return SyncStats(total=len(tasks), inserted=inserted, updated=updated, deleted=deleted)

    def reset(self) -> None:
        with session_scope(self.settings) as session:
            session.execute(delete(TaskMaterialModel))
            session.execute(delete(TaskModel))

    def get_task(self, external_id: str) -> ClassroomTask | None:
        with session_scope(self.settings) as session:
            model = session.scalar(
                select(TaskModel)
                .options(selectinload(TaskModel.materials))
                .where(TaskModel.external_id == external_id)
            )
            return _to_domain_task(model) if model is not None else None

    def tasks_by_external_ids(self, external_ids: set[str]) -> list[ClassroomTask]:
        if not external_ids:
            return []

        with session_scope(self.settings) as session:
            models = session.scalars(
                select(TaskModel)
                .options(selectinload(TaskModel.materials))
                .where(TaskModel.external_id.in_(external_ids))
                .order_by(TaskModel.course_name, TaskModel.title)
            ).all()
            return [_to_domain_task(model) for model in models]

    def pending_tasks(self) -> list[ClassroomTask]:
        with session_scope(self.settings) as session:
            models = session.scalars(
                select(TaskModel)
                .options(selectinload(TaskModel.materials))
                .where(TaskModel.state.not_in(["done", "submitted", "completed", "archived"]))
                .order_by(TaskModel.due_date.is_(None), TaskModel.due_date, TaskModel.course_name, TaskModel.title)
            ).all()
            return [_to_domain_task(model) for model in models]

    def due_between(self, start: date, end: date) -> list[ClassroomTask]:
        with session_scope(self.settings) as session:
            models = session.scalars(
                select(TaskModel)
                .options(selectinload(TaskModel.materials))
                .where(TaskModel.due_date.is_not(None))
                .where(TaskModel.due_date >= start.isoformat())
                .where(TaskModel.due_date <= end.isoformat())
                .where(TaskModel.state.not_in(["done", "submitted", "completed", "archived"]))
                .order_by(TaskModel.due_date, TaskModel.course_name, TaskModel.title)
            ).all()
            return [_to_domain_task(model) for model in models]

    def new_since(self, since_hours: int) -> list[ClassroomTask]:
        cutoff = datetime.now().astimezone() - timedelta(hours=since_hours)
        with session_scope(self.settings) as session:
            models = session.scalars(
                select(TaskModel)
                .options(selectinload(TaskModel.materials))
                .where(TaskModel.synced_at >= cutoff.isoformat(timespec="seconds"))
                .order_by(TaskModel.synced_at.desc(), TaskModel.course_name, TaskModel.title)
            ).all()
            return [_to_domain_task(model) for model in models]

    def update_material_extraction(
        self,
        *,
        material_id: str,
        extracted_text: str,
        extracted_text_source: str,
        task_source_updated_at: str,
    ) -> None:
        with session_scope(self.settings) as session:
            material = session.get(TaskMaterialModel, material_id)
            if material is None:
                return

            material.extracted_text = extracted_text
            material.extracted_text_source = extracted_text_source
            material.extracted_text_updated_at = utc_now_iso()
            material.extracted_from_task_source_updated_at = task_source_updated_at


def _to_material_model(
    material: TaskMaterial,
    synced_at: str,
    existing_material: TaskMaterialModel | None,
    task_source_updated_at: str,
) -> TaskMaterialModel:
    extracted_text = material.extracted_text
    extracted_text_source = material.extracted_text_source
    extracted_text_updated_at = material.extracted_text_updated_at
    extracted_from_task_source_updated_at: str | None = task_source_updated_at if extracted_text else None

    if (
        existing_material is not None
        and existing_material.extracted_text
        and existing_material.extracted_from_task_source_updated_at == task_source_updated_at
        and _material_cache_identity_matches(existing_material, material)
    ):
        extracted_text = existing_material.extracted_text
        extracted_text_source = existing_material.extracted_text_source
        extracted_text_updated_at = existing_material.extracted_text_updated_at
        extracted_from_task_source_updated_at = existing_material.extracted_from_task_source_updated_at

    return TaskMaterialModel(
        material_id=material.material_id,
        task_external_id=material.task_external_id,
        title=material.title,
        material_type=material.material_type,
        url=material.url,
        drive_file_id=material.drive_file_id,
        mime_type=material.mime_type,
        extracted_text=extracted_text,
        extracted_text_source=extracted_text_source,
        extracted_text_updated_at=extracted_text_updated_at,
        extracted_from_task_source_updated_at=extracted_from_task_source_updated_at,
        synced_at=synced_at,
    )


def _to_domain_task(model: TaskModel) -> ClassroomTask:
    return ClassroomTask(
        external_id=model.external_id,
        course_id=model.course_id,
        course_name=model.course_name,
        title=model.title,
        description=model.description,
        due_date=date.fromisoformat(model.due_date) if model.due_date else None,
        state=model.state,
        source_updated_at=model.source_updated_at,
        materials=tuple(
            TaskMaterial(
                material_id=material.material_id,
                task_external_id=material.task_external_id,
                title=material.title,
                material_type=material.material_type,
                url=material.url,
                drive_file_id=material.drive_file_id,
                mime_type=material.mime_type,
                extracted_text=material.extracted_text,
                extracted_text_source=material.extracted_text_source,
                extracted_text_updated_at=material.extracted_text_updated_at,
            )
            for material in model.materials
        ),
    )


def _material_cache_identity_matches(existing_material: TaskMaterialModel, material: TaskMaterial) -> bool:
    return (
        existing_material.title == material.title
        and existing_material.material_type == material.material_type
        and existing_material.url == material.url
        and existing_material.drive_file_id == material.drive_file_id
        and existing_material.mime_type == material.mime_type
    )
