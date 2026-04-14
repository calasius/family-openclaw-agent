from __future__ import annotations

import json
from datetime import date
import os
from pathlib import Path
from typing import Any

from school_guardian.domain import ClassroomTask, TaskMaterial


class ClassroomClient:
    def fetch_tasks(self) -> list[ClassroomTask]:
        raise NotImplementedError


class FixtureClassroomClient(ClassroomClient):
    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def fetch_tasks(self) -> list[ClassroomTask]:
        payload = json.loads(self.fixture_path.read_text())
        tasks: list[ClassroomTask] = []

        for course in payload.get("courses", []):
            for item in course.get("courseWork", []):
                raw_due_date = item.get("dueDate")
                due_date = date.fromisoformat(raw_due_date) if raw_due_date else None
                tasks.append(
                    ClassroomTask(
                        external_id=item["id"],
                        course_id=course["id"],
                        course_name=course["name"],
                        title=item["title"],
                        description=item.get("description", ""),
                        due_date=due_date,
                        state=item.get("state", "PENDING"),
                        source_updated_at=item.get("updatedAt", item.get("createdAt", "")),
                        materials=_parse_fixture_materials(item.get("materials", []), item["id"]),
                    )
                )

        return tasks


class GoogleClassroomClient(ClassroomClient):
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        scopes: tuple[str, ...],
        student_id: str,
        course_states: tuple[str, ...],
        page_size: int,
        open_browser: bool,
        service: Any | None = None,
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes
        self.student_id = student_id
        self.course_states = course_states
        self.page_size = page_size
        self.open_browser = open_browser
        self._service = service

    def fetch_tasks(self) -> list[ClassroomTask]:
        service = self._service or self._build_service()
        tasks: list[ClassroomTask] = []

        for course in self._list_courses(service):
            course_id = course["id"]
            course_name = course.get("name", course_id)
            for item in self._list_coursework(service, course_id):
                tasks.append(
                    ClassroomTask(
                        external_id=item["id"],
                        course_id=course_id,
                        course_name=course_name,
                        title=item["title"],
                        description=item.get("description", ""),
                        due_date=_parse_google_due_date(item.get("dueDate")),
                        state=item.get("state", "PENDING"),
                        source_updated_at=item.get("updateTime", item.get("creationTime", "")),
                        materials=_parse_google_materials(item.get("materials", []), item["id"]),
                    )
                )

        return tasks

    def _build_service(self) -> Any:
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "La fuente 'google' requiere instalar las dependencias opcionales de Google Classroom."
            ) from exc

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.scopes
                )
                creds = flow.run_local_server(
                    port=0,
                    open_browser=self.open_browser,
                    authorization_prompt_message="Abrí esta URL para autorizar school-guardian:\n{url}",
                )

            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json())

        return build("classroom", "v1", credentials=creds)

    def _list_courses(self, service: Any) -> list[dict[str, Any]]:
        courses: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            response = (
                service.courses()
                .list(
                    studentId=self.student_id,
                    courseStates=list(self.course_states),
                    pageSize=self.page_size,
                    pageToken=page_token,
                )
                .execute()
            )
            courses.extend(response.get("courses", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return courses

    def _list_coursework(self, service: Any, course_id: str) -> list[dict[str, Any]]:
        coursework: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            response = (
                service.courses()
                .courseWork()
                .list(courseId=course_id, pageSize=self.page_size, pageToken=page_token)
                .execute()
            )
            coursework.extend(response.get("courseWork", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return coursework


def _parse_google_due_date(raw_due_date: dict[str, Any] | None) -> date | None:
    if not raw_due_date:
        return None

    year = raw_due_date.get("year")
    month = raw_due_date.get("month")
    day = raw_due_date.get("day")
    if not year or not month or not day:
        return None

    return date(year=year, month=month, day=day)


def _parse_fixture_materials(
    materials_payload: list[dict[str, Any]], task_external_id: str
) -> tuple[TaskMaterial, ...]:
    materials: list[TaskMaterial] = []
    for index, item in enumerate(materials_payload, start=1):
        materials.append(
            TaskMaterial(
                material_id=f"{task_external_id}:material:{index}",
                task_external_id=task_external_id,
                title=item.get("title", f"material-{index}"),
                material_type=item.get("type", "link"),
                url=item.get("url"),
                drive_file_id=item.get("driveFileId"),
                mime_type=item.get("mimeType"),
            )
        )
    return tuple(materials)


def _parse_google_materials(
    materials_payload: list[dict[str, Any]], task_external_id: str
) -> tuple[TaskMaterial, ...]:
    materials: list[TaskMaterial] = []

    for index, item in enumerate(materials_payload, start=1):
        if "driveFile" in item:
            drive_file = item["driveFile"].get("driveFile", {})
            materials.append(
                TaskMaterial(
                    material_id=f"{task_external_id}:drive:{drive_file.get('id', index)}",
                    task_external_id=task_external_id,
                    title=drive_file.get("title", f"drive-{index}"),
                    material_type="drive_file",
                    url=drive_file.get("alternateLink"),
                    drive_file_id=drive_file.get("id"),
                )
            )
            continue

        if "link" in item:
            link = item["link"]
            materials.append(
                TaskMaterial(
                    material_id=f"{task_external_id}:link:{index}",
                    task_external_id=task_external_id,
                    title=link.get("title", f"link-{index}"),
                    material_type="link",
                    url=link.get("url"),
                )
            )
            continue

        if "form" in item:
            form = item["form"]
            materials.append(
                TaskMaterial(
                    material_id=f"{task_external_id}:form:{index}",
                    task_external_id=task_external_id,
                    title=form.get("title", f"form-{index}"),
                    material_type="form",
                    url=form.get("formUrl"),
                )
            )
            continue

        if "youtubeVideo" in item:
            video = item["youtubeVideo"]
            materials.append(
                TaskMaterial(
                    material_id=f"{task_external_id}:youtube:{index}",
                    task_external_id=task_external_id,
                    title=video.get("title", f"youtube-{index}"),
                    material_type="youtube",
                    url=video.get("alternateLink"),
                )
            )

    return tuple(materials)
