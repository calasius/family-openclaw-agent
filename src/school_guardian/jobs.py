from __future__ import annotations

from datetime import date, timedelta
import json

from school_guardian.classroom import ClassroomClient
from school_guardian.focus import daily_focus
from school_guardian.materials import (
    extract_text_with_source_from_material,
    MaterialDownloadService,
)
from school_guardian.store import SyncStats, TaskStore
from school_guardian.telegram_bot import TelegramBotService


def run_classroom_sync(client: ClassroomClient, store: TaskStore) -> SyncStats:
    tasks = client.fetch_tasks()
    store.initialize()
    watch_ids = {
        "796567213177",
        "796540322025",
    }
    incoming_ids = {task.external_id for task in tasks}
    print(json.dumps({
        "event": "classroom_sync_fetched",
        "db_path": str(store.db_path),
        "task_count": len(tasks),
        "watched_ids_present": {task_id: task_id in incoming_ids for task_id in sorted(watch_ids)},
    }, ensure_ascii=False))
    stats = store.replace_tasks(tasks)
    cache_stats = _warm_material_extraction_cache(store, incoming_ids)
    print(json.dumps({
        "event": "classroom_sync_applied",
        "db_path": str(store.db_path),
        "total": stats.total,
        "inserted": stats.inserted,
        "updated": stats.updated,
        "deleted": stats.deleted,
        "material_cache_hits": cache_stats["hits"],
        "material_cache_writes": cache_stats["writes"],
        "material_cache_misses": cache_stats["misses"],
    }, ensure_ascii=False))
    return stats


def run_school_morning_summary(store: TaskStore) -> str:
    store.initialize()
    pending = store.pending_tasks()
    urgent = store.due_between(date.today(), date.today() + timedelta(days=2))
    focus = daily_focus(pending)

    lines = [f"Pendientes: {len(pending)}"]
    if urgent:
        lines.append("Urgente en 48h:")
        lines.extend(_format_task(task) for task in urgent[:3])
    if focus:
        lines.append("Foco de hoy:")
        lines.extend(_format_task(task) for task in focus[:3])
    return "\n".join(lines)


def run_material_downloads(
    store: TaskStore, downloader: MaterialDownloadService
) -> list[str]:
    store.initialize()
    return [str(path) for path in downloader.download_supported_materials(store.pending_tasks())]


def run_telegram_poll_once(store: TaskStore, bot: TelegramBotService, offset: int | None = None) -> int | None:
    store.initialize()
    last_offset = offset
    for update in bot.get_updates(offset=offset):
        response = bot.handle_update(update, store)
        if response:
            bot.send_message(update.chat_id, response)
        last_offset = update.update_id + 1
    return last_offset


def _format_task(task) -> str:
    due_label = task.due_date.isoformat() if task.due_date else "sin fecha"
    return f"- {task.course_name} | {task.title} | {due_label}"


def _warm_material_extraction_cache(store: TaskStore, task_ids: set[str]) -> dict[str, int]:
    if not store.settings.azure_document_intelligence_endpoint or not store.settings.azure_document_intelligence_key:
        print(json.dumps({"event": "material_cache_skipped", "reason": "document_intelligence_not_configured"}, ensure_ascii=False))
        return {"hits": 0, "writes": 0, "misses": 0}

    hits = 0
    writes = 0
    misses = 0
    for task in store.tasks_by_external_ids(task_ids):
        for material in task.materials:
            if material.extracted_text:
                hits += 1
                print(json.dumps({
                    "event": "material_cache_hit",
                    "task_id": task.external_id,
                    "material_id": material.material_id,
                    "source": material.extracted_text_source,
                }, ensure_ascii=False))
                continue

            extracted = extract_text_with_source_from_material(material, store.settings)
            if extracted.text and extracted.source:
                store.update_material_extraction(
                    material_id=material.material_id,
                    extracted_text=extracted.text,
                    extracted_text_source=extracted.source,
                    task_source_updated_at=task.source_updated_at,
                )
                writes += 1
                print(json.dumps({
                    "event": "material_cache_write",
                    "task_id": task.external_id,
                    "material_id": material.material_id,
                    "source": extracted.source,
                    "content_length": len(extracted.text),
                }, ensure_ascii=False))
                continue

            misses += 1
            print(json.dumps({
                "event": "material_cache_miss",
                "task_id": task.external_id,
                "material_id": material.material_id,
            }, ensure_ascii=False))

    return {"hits": hits, "writes": writes, "misses": misses}
