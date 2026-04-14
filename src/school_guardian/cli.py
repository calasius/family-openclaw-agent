from __future__ import annotations

import argparse
from datetime import date, timedelta
import io
import os
import subprocess
import sys
from pathlib import Path

from school_guardian.config import get_settings
from school_guardian.export import build_solution_metadata, solution_to_pdf
from school_guardian.focus import daily_focus
from school_guardian.jobs import (
    run_classroom_sync,
    run_material_downloads,
    run_school_morning_summary,
    run_telegram_poll_once,
)
from school_guardian.materials import (
    _download_google_drive_material_bytes,
    analyze_images_with_vision,
    dump_task_material_manifest,
    extract_images_from_docx,
    extract_text_from_material,
    extract_text_with_source_from_material,
    MaterialDownloadService,
)
from school_guardian.services import build_client
from school_guardian.store import TaskStore
from school_guardian.telegram_bot import TelegramBotService, format_task_list
from school_guardian.text_utils import normalize_math_text


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    args.handler(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="school-guardian")
    subparsers = parser.add_subparsers(dest="command")

    init_db = subparsers.add_parser("init-db", help="Create the SQLite database.")
    init_db.set_defaults(handler=handle_init_db)

    reset_db = subparsers.add_parser("reset-db", help="Delete all tasks and materials from the SQLite database.")
    reset_db.set_defaults(handler=handle_reset_db)

    sync = subparsers.add_parser("sync-classroom", help="Sync tasks from Classroom source.")
    sync.set_defaults(handler=handle_sync)

    pending = subparsers.add_parser("pending", help="List pending tasks.")
    pending.set_defaults(handler=handle_pending)

    subjects = subparsers.add_parser("list-subjects", help="List unique subjects from current pending tasks.")
    subjects.set_defaults(handler=handle_list_subjects)

    due = subparsers.add_parser("due-tomorrow", help="List tasks due tomorrow.")
    due.set_defaults(handler=handle_due_tomorrow)

    new_items = subparsers.add_parser("new-items", help="List recently synced tasks.")
    new_items.add_argument("--hours", type=int, default=24)
    new_items.set_defaults(handler=handle_new_items)

    focus = subparsers.add_parser("daily-focus", help="Build the daily focus list.")
    focus.set_defaults(handler=handle_daily_focus)

    materials = subparsers.add_parser(
        "list-materials", help="List task materials known by the internal store."
    )
    materials.set_defaults(handler=handle_list_materials)

    download = subparsers.add_parser(
        "download-materials", help="Download supported PDF/DOCX task materials."
    )
    download.set_defaults(handler=handle_download_materials)

    telegram = subparsers.add_parser("telegram-poll-once", help="Poll Telegram once and answer commands.")
    telegram.add_argument("--offset", type=int, default=None)
    telegram.set_defaults(handler=handle_telegram_poll_once)

    job = subparsers.add_parser("run-job", help="Run a predefined scheduled job.")
    job.add_argument("job_name", choices=["classroom-sync", "school-morning-summary"])
    job.set_defaults(handler=handle_run_job)

    serve = subparsers.add_parser("serve", help="Container entrypoint.")
    serve.set_defaults(handler=handle_serve)

    print_auth = subparsers.add_parser("auth-info", help="Show current Classroom auth/source config.")
    print_auth.set_defaults(handler=handle_auth_info)

    task_detail = subparsers.add_parser("task-detail", help="Show full detail for a task by external_id.")
    task_detail.add_argument("task_id")
    task_detail.set_defaults(handler=handle_task_detail)

    export_solution = subparsers.add_parser(
        "export-solution", help="Generate a PDF solution and send it by Telegram."
    )
    export_solution.add_argument("--title", required=True)
    export_solution.add_argument("--solution-file", required=True)
    export_solution.add_argument("--task-id", default="")
    export_solution.add_argument("--chat-id", default=None)
    export_solution.set_defaults(handler=handle_export_solution)

    analyze_task_images = subparsers.add_parser(
        "analyze-task-images", help="Analyze images found in a task's attached DOCX files."
    )
    analyze_task_images.add_argument("task_id")
    analyze_task_images.set_defaults(handler=handle_analyze_task_images)

    send_task_images = subparsers.add_parser(
        "send-task-images", help="Extract images from a task's attached DOCX files and send them by Telegram."
    )
    send_task_images.add_argument("task_id")
    send_task_images.add_argument("--chat-id", default=None)
    send_task_images.set_defaults(handler=handle_send_task_images)

    return parser


def handle_init_db(_args: argparse.Namespace) -> None:
    settings = get_settings()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    store = TaskStore(settings)
    store.initialize()
    print(f"DB initialized at {store.db_path}")


def handle_reset_db(_args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)
    store.initialize()
    store.reset()
    print(f"DB reset at {store.db_path}")


def handle_sync(_args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)
    client = build_client()
    stats = run_classroom_sync(client, store)
    print(
        f"Sincronicé {stats.total} tareas. Nuevas: {stats.inserted}. Actualizadas: {stats.updated}."
    )


def handle_pending(_args: argparse.Namespace) -> None:
    store = TaskStore(get_settings())
    store.initialize()
    _print_tasks(store.pending_tasks(), empty_message="No hay tareas pendientes.")


def handle_list_subjects(_args: argparse.Namespace) -> None:
    store = TaskStore(get_settings())
    store.initialize()
    subjects = sorted({task.course_name for task in store.pending_tasks()})
    if not subjects:
        print("No hay materias con tareas pendientes.")
        return
    for index, subject in enumerate(subjects, start=1):
        print(f"{index}. {subject}")


def handle_due_tomorrow(_args: argparse.Namespace) -> None:
    store = TaskStore(get_settings())
    store.initialize()
    tomorrow = date.today() + timedelta(days=1)
    _print_tasks(
        store.due_between(tomorrow, tomorrow),
        empty_message="No hay tareas que venzan mañana.",
    )


def handle_new_items(args: argparse.Namespace) -> None:
    store = TaskStore(get_settings())
    store.initialize()
    _print_tasks(
        store.new_since(args.hours),
        empty_message=f"No hubo tareas nuevas en las últimas {args.hours} horas.",
    )


def handle_daily_focus(_args: argparse.Namespace) -> None:
    store = TaskStore(get_settings())
    store.initialize()
    tasks = daily_focus(store.pending_tasks())
    _print_tasks(tasks, empty_message="No hay tareas para foco de hoy.")


def handle_list_materials(_args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)
    store.initialize()
    tasks = store.pending_tasks()
    manifest = dump_task_material_manifest(tasks, settings.download_dir / "materials_manifest.json")
    print(f"Manifest generado en {manifest}")
    for task in tasks:
        if not task.materials:
            continue
        print(f"{task.course_name} | {task.title}")
        for material in task.materials:
            print(f"- {material.material_type} | {material.title}")


def handle_download_materials(_args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)
    downloader = MaterialDownloadService(settings)
    downloaded = run_material_downloads(store, downloader)
    if not downloaded:
        print("No hubo materiales PDF/DOCX descargables.")
        return
    for item in downloaded:
        print(item)


def handle_telegram_poll_once(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("Falta SCHOOL_GUARDIAN_TELEGRAM_BOT_TOKEN.")
    store = TaskStore(settings)
    bot = TelegramBotService(
        bot_token=settings.telegram_bot_token,
        allowed_chat_id=settings.telegram_allowed_chat_id,
        poll_timeout_seconds=settings.telegram_poll_timeout_seconds,
    )
    next_offset = run_telegram_poll_once(store, bot, offset=args.offset)
    print(f"next_offset={next_offset}")


def handle_run_job(args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)

    if args.job_name == "classroom-sync":
        client = build_client()
        stats = run_classroom_sync(client, store)
        print(
            f"[classroom-sync] total={stats.total} inserted={stats.inserted} updated={stats.updated}"
        )
        return

    print(run_school_morning_summary(store))


def handle_serve(_args: argparse.Namespace) -> None:
    print("school-guardian container ready")


def handle_auth_info(_args: argparse.Namespace) -> None:
    settings = get_settings()
    print(f"source={settings.classroom_source}")
    if settings.classroom_source == "fixture":
        print(f"fixture_path={settings.fixture_path}")
        return

    print(f"credentials_path={settings.google_credentials_path}")
    print(f"token_path={settings.google_token_path}")
    print(f"student_id={settings.google_student_id}")
    print(f"course_states={','.join(settings.google_course_states)}")
    print(f"page_size={settings.google_page_size}")
    print(f"open_browser={settings.google_open_browser}")
    print(f"download_dir={settings.download_dir}")
    print(f"telegram_allowed_chat_id={settings.telegram_allowed_chat_id}")
    print(
        "azure_document_intelligence="
        + ("configured" if settings.azure_document_intelligence_endpoint and settings.azure_document_intelligence_key else "disabled")
    )
    print(f"azure_document_intelligence_model={settings.azure_document_intelligence_model}")
    print(
        "azure_document_intelligence_api_version="
        + settings.azure_document_intelligence_api_version
    )


def handle_task_detail(args: argparse.Namespace) -> None:
    settings = get_settings()
    store = TaskStore(settings)
    store.initialize()
    task = store.get_task(args.task_id)
    if task is None:
        raise RuntimeError(f"No existe una tarea con id {args.task_id}.")

    text = f"**{task.course_name} — {task.title}**\n"
    if task.due_date:
        text += f"Vencimiento: {task.due_date.isoformat()}\n"
    if task.description and task.description.strip():
        text += f"\nDescripción:\n{normalize_math_text(task.description)}\n"

    if task.materials:
        text += f"\nMateriales ({len(task.materials)}):\n"
        for material in task.materials:
            text += f"\n- {material.title} [{material.material_type}]"
            if material.url:
                text += f"\n  URL: {material.url}"
            extracted = material.extracted_text
            extracted_source = material.extracted_text_source
            if not extracted:
                extraction = extract_text_with_source_from_material(material, settings)
                extracted = extraction.text
                extracted_source = extraction.source
                if extracted and extracted_source:
                    store.update_material_extraction(
                        material_id=material.material_id,
                        extracted_text=extracted,
                        extracted_text_source=extracted_source,
                        task_source_updated_at=task.source_updated_at,
                    )
            if extracted:
                normalized_extracted = normalize_math_text(extracted)
                snippet = normalized_extracted[:20000] + (
                    "\n[... texto truncado]" if len(normalized_extracted) > 20000 else ""
                )
                if extracted_source:
                    text += f"\n  Fuente cache/extracción: {extracted_source}"
                text += f"\n  Contenido:\n{snippet}"
            else:
                text += "\n  (sin texto extraible)"
    else:
        text += "\nSin materiales adjuntos."

    print(normalize_math_text(text))


def handle_export_solution(args: argparse.Namespace) -> None:
    settings = get_settings()
    chat_id = args.chat_id or settings.telegram_allowed_chat_id
    if not settings.telegram_bot_token or not chat_id:
        raise RuntimeError("Telegram no está configurado para exportar el PDF.")

    solution = Path(args.solution_file).read_text(encoding="utf-8")
    metadata = build_solution_metadata()
    if args.task_id:
        store = TaskStore(settings)
        store.initialize()
        task = store.get_task(args.task_id)
        if task is not None:
            metadata = build_solution_metadata(
                task_name=task.title,
                course_name=task.course_name,
                due_date=task.due_date.isoformat() if task.due_date else None,
            )
    pdf_bytes = solution_to_pdf(args.title, solution, metadata=metadata)
    filename = f"solucion_{args.task_id or 'tarea'}.pdf"
    bot = TelegramBotService(
        bot_token=settings.telegram_bot_token,
        allowed_chat_id=settings.telegram_allowed_chat_id,
        poll_timeout_seconds=settings.telegram_poll_timeout_seconds,
    )
    bot.send_document(
        chat_id=chat_id,
        filename=filename,
        data=pdf_bytes,
        caption=f"Solución: {args.title}",
    )
    print(f'PDF enviado por Telegram: "{args.title}"')


def handle_analyze_task_images(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.azure_openai_api_key or not settings.azure_openai_base_url:
        raise RuntimeError("Vision no está configurado.")

    store = TaskStore(settings)
    store.initialize()
    task = store.get_task(args.task_id)
    if task is None:
        raise RuntimeError(f"No existe una tarea con id {args.task_id}.")

    all_images: list[tuple[str, bytes]] = []
    for material in task.materials:
        if material.material_type != "drive_file" or not material.drive_file_id:
            continue
        raw = _download_google_drive_material_bytes(material, settings)
        if raw is None:
            continue
        all_images.extend(extract_images_from_docx(io.BytesIO(raw)))

    if not all_images:
        print("No se encontraron imágenes o no se pudo analizar el documento.")
        return

    analysis = analyze_images_with_vision(
        all_images,
        settings.azure_openai_api_key,
        settings.azure_openai_base_url,
        settings.azure_openai_vision_deployment,
    )
    print(analysis or "No se encontraron imágenes o no se pudo analizar el documento.")


def handle_send_task_images(args: argparse.Namespace) -> None:
    settings = get_settings()
    chat_id = args.chat_id or settings.telegram_allowed_chat_id
    if not settings.telegram_bot_token or not chat_id:
        raise RuntimeError("Telegram no está configurado para enviar imágenes.")

    store = TaskStore(settings)
    store.initialize()
    task = store.get_task(args.task_id)
    if task is None:
        raise RuntimeError(f"No existe una tarea con id {args.task_id}.")

    bot = TelegramBotService(
        bot_token=settings.telegram_bot_token,
        allowed_chat_id=settings.telegram_allowed_chat_id,
        poll_timeout_seconds=settings.telegram_poll_timeout_seconds,
    )

    sent = 0
    for material in task.materials:
        if material.material_type != "drive_file" or not material.drive_file_id:
            continue
        raw = _download_google_drive_material_bytes(material, settings)
        if raw is None:
            continue
        for filename, img_bytes in extract_images_from_docx(io.BytesIO(raw)):
            bot.send_document(
                chat_id=chat_id,
                filename=filename,
                data=img_bytes,
                caption=f"{task.title} — {material.title}",
            )
            sent += 1

    if sent > 0:
        suffix = "s" if sent > 1 else ""
        print(f"{sent} imagen{suffix} enviada{suffix} por Telegram.")
        return

    print("No se encontraron imágenes en los documentos adjuntos.")


def _print_tasks(tasks, empty_message: str) -> None:
    print(format_task_list(tasks, empty_message))
