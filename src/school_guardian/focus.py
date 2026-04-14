from __future__ import annotations

from datetime import date

from school_guardian.domain import ClassroomTask


def daily_focus(tasks: list[ClassroomTask], today: date | None = None) -> list[ClassroomTask]:
    today = today or date.today()

    def score(task: ClassroomTask) -> tuple[int, date, str, str]:
        if task.due_date is None:
            return (2, date.max, task.course_name, task.title)

        days_left = (task.due_date - today).days
        urgency = 0 if days_left <= 1 else 1
        return (urgency, task.due_date, task.course_name, task.title)

    return sorted(tasks, key=score)[:5]
