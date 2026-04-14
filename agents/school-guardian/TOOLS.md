# TOOLS

## Available commands

- `uv run python -m school_guardian sync-classroom`
- `uv run python -m school_guardian reset-db`
- `uv run python -m school_guardian pending`
- `uv run python -m school_guardian list-subjects`
- `uv run python -m school_guardian due-tomorrow`
- `uv run python -m school_guardian new-items --hours 24`
- `uv run python -m school_guardian daily-focus`
- `uv run python -m school_guardian list-materials`
- `uv run python -m school_guardian download-materials`
- `uv run python -m school_guardian telegram-poll-once`
- `uv run python -m school_guardian auth-info`
- `uv run python -m school_guardian run-job classroom-sync`
- `uv run python -m school_guardian run-job school-morning-summary`
- `uv run python -m school_guardian task-detail <task_id>`
- `uv run python -m school_guardian analyze-task-images <task_id>`
- `uv run python -m school_guardian send-task-images <task_id> [--chat-id <chat_id>]`
- `uv run python -m school_guardian export-solution --title "<titulo>" --solution-file /ruta/solucion.md [--task-id <task_id>] [--chat-id <chat_id>]`

## Scheduled jobs

- `classroom-sync`: refresca cursos y tareas, y hace upsert del store.
- `school-morning-summary`: genera un resumen corto con pendientes, urgencias y foco.
- `download-materials`: baja PDF/DOCX de materiales soportados.
- `telegram-poll-once`: atiende mensajes de Telegram por polling.
