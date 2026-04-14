from __future__ import annotations

import unittest
from pathlib import Path

from school_guardian.classroom import GoogleClassroomClient


class _ExecuteCall:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _CourseWorkResource:
    def __init__(self, payloads_by_course):
        self.payloads_by_course = payloads_by_course
        self.calls = {}

    def list(self, courseId, pageSize, pageToken=None):
        index = self.calls.get(courseId, 0)
        self.calls[courseId] = index + 1
        return _ExecuteCall(self.payloads_by_course[courseId][index])


class _CoursesResource:
    def __init__(self, course_payloads, coursework_payloads):
        self.course_payloads = course_payloads
        self.course_calls = 0
        self.coursework_resource = _CourseWorkResource(coursework_payloads)

    def list(self, studentId, courseStates, pageSize, pageToken=None):
        payload = self.course_payloads[self.course_calls]
        self.course_calls += 1
        return _ExecuteCall(payload)

    def courseWork(self):
        return self.coursework_resource


class _FakeService:
    def __init__(self, course_payloads, coursework_payloads):
        self.courses_resource = _CoursesResource(course_payloads, coursework_payloads)

    def courses(self):
        return self.courses_resource


class GoogleClassroomClientTestCase(unittest.TestCase):
    def test_fetch_tasks_normalizes_courses_and_coursework(self) -> None:
        service = _FakeService(
            course_payloads=[
                {
                    "courses": [
                        {"id": "course-1", "name": "Matematica"},
                        {"id": "course-2", "name": "Ciencias"},
                    ]
                }
            ],
            coursework_payloads={
                "course-1": [
                    {
                        "courseWork": [
                            {
                                "id": "cw-1",
                                "title": "Ejercicios",
                                "description": "Practicar",
                                "state": "PUBLISHED",
                                "dueDate": {"year": 2026, "month": 4, "day": 8},
                                "updateTime": "2026-04-07T10:15:00Z",
                            }
                        ]
                    }
                ],
                "course-2": [
                    {
                        "courseWork": [
                            {
                                "id": "cw-2",
                                "title": "Resumen",
                                "state": "PUBLISHED",
                                "creationTime": "2026-04-07T08:00:00Z",
                            }
                        ]
                    }
                ],
            },
        )

        client = GoogleClassroomClient(
            credentials_path=Path("unused.json"),
            token_path=Path("unused-token.json"),
            scopes=("scope-1",),
            student_id="me",
            course_states=("ACTIVE",),
            page_size=100,
            open_browser=False,
            service=service,
        )

        tasks = client.fetch_tasks()

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].course_name, "Matematica")
        self.assertEqual(tasks[0].due_date.isoformat(), "2026-04-08")
        self.assertEqual(tasks[1].source_updated_at, "2026-04-07T08:00:00Z")
        self.assertEqual(tasks[0].materials, ())


if __name__ == "__main__":
    unittest.main()
