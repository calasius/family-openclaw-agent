# school-guardian

Primer corte del agente `school-guardian` descrito en `PLAN.md`.

La implementación actual cubre la fase 1:

- sincronizar tareas desde una fuente Classroom configurable,
- normalizar y guardar tareas en un store interno,
- evitar duplicados vía `upsert`,
- responder consultas de pendientes, vencimientos y foco diario,
- exponer jobs programados listos para usar con OpenClaw o cron externo,
- detectar materiales por tarea y descargar PDF/DOCX soportados,
- responder por Telegram con el backlog escolar,
- exponer tools reales para OpenClaw vía un plugin local del workspace.

## Requisitos

- `uv`
- `python 3.12`
- `docker compose` para ejecutar en contenedores

## Uso local

```bash
uv sync
cp .env.example .env
PYTHONPATH=src uv run python -m school_guardian init-db
PYTHONPATH=src uv run python -m school_guardian reset-db
PYTHONPATH=src uv run python -m school_guardian sync-classroom
PYTHONPATH=src uv run python -m school_guardian pending
PYTHONPATH=src uv run python -m school_guardian due-tomorrow
PYTHONPATH=src uv run python -m school_guardian daily-focus
```

Para desarrollo local sin red o sin credenciales, la fuente por defecto sigue siendo `fixture`.

## Variables de entorno

Podés ponerlas en `.env`. El proyecto lo carga automáticamente al ejecutar el CLI.

```bash
SCHOOL_GUARDIAN_DB_PATH=data/school_guardian.db
SCHOOL_GUARDIAN_CLASSROOM_SOURCE=fixture
SCHOOL_GUARDIAN_FIXTURE_PATH=data/classroom_fixture.json
SCHOOL_GUARDIAN_GOOGLE_CREDENTIALS_PATH=secrets/google_credentials.json
SCHOOL_GUARDIAN_GOOGLE_TOKEN_PATH=secrets/google_token.json
SCHOOL_GUARDIAN_GOOGLE_STUDENT_ID=me
SCHOOL_GUARDIAN_GOOGLE_COURSE_STATES=ACTIVE,PROVISIONED
SCHOOL_GUARDIAN_GOOGLE_PAGE_SIZE=100
SCHOOL_GUARDIAN_GOOGLE_OPEN_BROWSER=true
SCHOOL_GUARDIAN_GOOGLE_SCOPES=https://www.googleapis.com/auth/classroom.courses.readonly,https://www.googleapis.com/auth/classroom.coursework.me.readonly,https://www.googleapis.com/auth/classroom.student-submissions.me.readonly,https://www.googleapis.com/auth/drive.readonly
SCHOOL_GUARDIAN_DOWNLOAD_DIR=data/downloads
SCHOOL_GUARDIAN_TELEGRAM_BOT_TOKEN=
SCHOOL_GUARDIAN_TELEGRAM_ALLOWED_CHAT_ID=
SCHOOL_GUARDIAN_TELEGRAM_POLL_TIMEOUT_SECONDS=30
```

## Google Classroom real

La fuente `google` ya está soportada. Usa OAuth de aplicación de escritorio y los métodos oficiales `courses.list` y `courses.courseWork.list` de Classroom.

1. Instalá dependencias opcionales:

```bash
uv sync --extra google
```

2. En Google Cloud, habilitá Classroom API y descargá un OAuth Client de tipo Desktop App en `secrets/google_credentials.json`.

3. Ejecutá:

```bash
SCHOOL_GUARDIAN_CLASSROOM_SOURCE=google PYTHONPATH=src uv run python -m school_guardian auth-info
SCHOOL_GUARDIAN_CLASSROOM_SOURCE=google PYTHONPATH=src uv run python -m school_guardian sync-classroom
```

En la primera corrida, el cliente abre el flujo OAuth local y guarda el token en `secrets/google_token.json`.

Si Google devuelve un scope equivalente pero distinto al solicitado, el cliente ya relaja esa validación para no abortar la creación del token.

Fuentes oficiales:

- https://developers.google.com/workspace/classroom/quickstart/python
- https://developers.google.com/workspace/classroom/reference/rest/v1/courses/list
- https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWork/list

## Docker Compose

```bash
cp .env.example .env
docker compose up --build school-guardian
```

También podés ejecutar comandos puntuales:

```bash
docker compose run --rm school-guardian uv run python -m school_guardian pending
docker compose run --rm school-guardian uv run python -m school_guardian run-job classroom-sync
docker compose run --rm school-guardian uv run python -m school_guardian download-materials
docker compose run --rm school-guardian uv run python -m school_guardian telegram-poll-once
```

## OpenClaw con Azure OpenAI

El repo incluye una base para correr OpenClaw por Docker usando Azure OpenAI y Telegram:

- [compose.openclaw.yaml](/var/home/calasius/repos/school-guardian/compose.openclaw.yaml)
- [openclaw/.env.example](/var/home/calasius/repos/school-guardian/openclaw/.env.example)
- [openclaw/openclaw.json.example](/var/home/calasius/repos/school-guardian/openclaw/openclaw.json.example)
- [.openclaw/extensions/school-guardian-tools/index.ts](/var/home/calasius/repos/school-guardian/.openclaw/extensions/school-guardian-tools/index.ts)

Preparación:

```bash
cp openclaw/.env.example openclaw/.env
```

Después completá `openclaw/.env` con:

```bash
OPENCLAW_GATEWAY_TOKEN=un-token-largo
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_BASE_URL=https://<tu-recurso>.openai.azure.com/openai/v1/
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_FROM=<tu-user-id-numerico-de-telegram>
```

Levantar Gateway:

```bash
docker compose --env-file openclaw/.env -f compose.openclaw.yaml up -d openclaw-gateway
```

Ver estado:

```bash
docker compose --env-file openclaw/.env -f compose.openclaw.yaml run --rm openclaw-cli gateway status --url ws://127.0.0.1:18789 --token "$OPENCLAW_GATEWAY_TOKEN"
```

Abrir dashboard:

```bash
docker compose --env-file openclaw/.env -f compose.openclaw.yaml run --rm openclaw-cli dashboard --no-open
```

Notas:

- La config fija `azure-openai-responses/gpt-4o` como modelo principal.
- Telegram en OpenClaw usa `Bot API` y `dmPolicy: "allowlist"` con tu `user id` numérico.
- `school-guardian` y `family-orchestrator` quedan en el mismo workspace `/workspace`, que es este repo.
- El plugin local `school-guardian-tools` ejecuta la CLI real del proyecto para pendientes, materias, detalle y foco diario leyendo desde la base local.
- El gateway registra automáticamente un cron interno de OpenClaw para correr `school_guardian_sync` al iniciar y luego cada 10 minutos en background, pero recién después de que el gateway queda listo.
- `openclaw-gateway` ya trae el runtime Python y las dependencias del proyecto horneadas en la imagen; al arrancar sólo copia config y plugin local.

Fuentes oficiales:

- Docker opcional y prebuilt image: https://docs.openclaw.ai/install/docker
- Config en `~/.openclaw/openclaw.json`: https://docs.openclaw.ai/gateway/configuration
- Telegram channel config: https://docs.openclaw.ai/channels/telegram
- OpenAI/Azure model refs en OpenClaw: https://docs.openclaw.ai/providers/openai

## OpenClaw

La estructura OpenClaw del repo quedó separada así:

- `agents/family-orchestrator/AGENTS.md`: orquestador principal.
- `agents/school-guardian/AGENTS.md`: agente escolar.
- `agents/school-guardian/skills/classroom-read`: sync de Classroom.
- `agents/school-guardian/skills/classroom-materials`: materiales y descargas.
- `agents/school-guardian/skills/school-task-store`: store y consultas.
- `agents/school-guardian/skills/school-daily-focus`: priorización diaria.
- `agents/school-guardian/skills/telegram-bridge`: atención por Telegram.

Con esto, OpenClaw puede usar `school-guardian` como agente especializado y disparar comandos del CLI para sincronizar, listar tareas, bajar materiales y contestar mensajes.

## Tests

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests
```

## Migrations

Schema y evolución de base ahora usan `SQLAlchemy` + `Alembic`.

```bash
PYTHONPATH=src uv run python -m alembic upgrade head
```

## Workspace OpenClaw

El workspace del agente quedó modelado en:

- `agents/school-guardian/AGENTS.md`
- `agents/school-guardian/TOOLS.md`
- `agents/school-guardian/skills/*`

Eso deja separadas las instrucciones persistentes, las herramientas del agente y las skills mínimas pedidas por el plan.
