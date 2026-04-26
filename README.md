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

## OpenClaw con OpenRouter

El repo incluye una base para correr OpenClaw por Docker usando OpenRouter y Telegram:

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
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_FROM=<tu-user-id-numerico-de-telegram>
```

Si `OPENROUTER_API_KEY` ya está exportada en el sistema, `compose.openclaw.yaml` la inyecta al contenedor y podés omitirla en `openclaw/.env`.

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

### Operar openclaw-gateway

Levantar en background:

```bash
podman compose --env-file openclaw/.env -f compose.openclaw.yaml up -d openclaw-gateway
```

Bajar:

```bash
podman compose --env-file openclaw/.env -f compose.openclaw.yaml down
```

Reiniciar (mantiene volúmenes):

```bash
podman restart openclaw-gateway
```

Logs en vivo:

```bash
podman logs -f openclaw-gateway
```

Últimas N líneas:

```bash
podman logs --tail 200 openclaw-gateway
```

Shell dentro del contenedor:

```bash
podman exec -it openclaw-gateway bash
```

Notas:

- La config fija `openrouter/google/gemma-4-26b-a4b-it` como modelo principal.
- Si venías pensando en "Gemma 4 24B", el ref disponible en OpenRouter al 24 de abril de 2026 es `google/gemma-4-26b-a4b-it`.
- Telegram en OpenClaw usa `Bot API` y `dmPolicy: "allowlist"` con tu `user id` numérico.
- `school-guardian` y `family-orchestrator` quedan en el mismo workspace `/workspace`, que es este repo.
- El plugin local `school-guardian-tools` ejecuta la CLI real del proyecto para pendientes, materias, detalle y foco diario leyendo desde la base local.
- El gateway registra automáticamente un cron interno de OpenClaw para correr `school_guardian_sync` al iniciar y luego cada 10 minutos en background, pero recién después de que el gateway queda listo.
- `openclaw-gateway` ya trae el runtime Python y las dependencias del proyecto horneadas en la imagen; al arrancar sólo copia config y plugin local.

Fuentes oficiales:

- Docker opcional y prebuilt image: https://docs.openclaw.ai/install/docker
- Config en `~/.openclaw/openclaw.json`: https://docs.openclaw.ai/gateway/configuration
- Telegram channel config: https://docs.openclaw.ai/channels/telegram
- OpenRouter en OpenClaw: https://docs.openclaw.ai/providers/openrouter

## OpenClaw

La estructura OpenClaw del repo quedó separada así:

- `agents/family-orchestrator/AGENTS.md`: orquestador principal.
- `agents/school-guardian/AGENTS.md`: agente escolar.
- `agents/agent-watch/AGENTS.md`: AI agent/news watcher for a separate Telegram channel.
- `agents/school-guardian/skills/classroom-read`: sync de Classroom.
- `agents/school-guardian/skills/classroom-materials`: materiales y descargas.
- `agents/school-guardian/skills/school-task-store`: store y consultas.
- `agents/school-guardian/skills/school-daily-focus`: priorización diaria.
- `agents/school-guardian/skills/telegram-bridge`: atención por Telegram.

Con esto, OpenClaw puede usar `school-guardian` como agente especializado y disparar comandos del CLI para sincronizar, listar tareas, bajar materiales y contestar mensajes.

## Agent Watch

`agent-watch` is a separate flow for sending updates about agents, Claude Code, OpenCode, OpenClaw, MCP, and open source models to another Telegram channel. It does not use the school channel.

Main variables:

```bash
AGENT_WATCH_DB_PATH=data/agent_watch.db
AGENT_WATCH_TELEGRAM_BOT_TOKEN=
AGENT_WATCH_TELEGRAM_TARGET=@your_channel
AGENT_WATCH_X_BEARER_TOKEN=
AGENT_WATCH_X_QUERY=("claude code" OR opencode OR openclaw OR codex OR cursor OR aider OR "coding agent" OR "AI agent" OR "agent framework" OR "MCP server" OR "tool calling" OR "computer use" OR "browser agent" OR "open source agents" OR "local agents" OR "open source model" OR "open weights" OR langgraph OR autogen OR crewai OR ollama OR vllm) -is:retweet
AGENT_WATCH_X_ACCOUNTS=simonw,swyx,latentspacepod,karpathy,jeremyphoward,rasbt,NathanpmYoung,reach_vb,LangChainAI,ollama,OpenRouterAI
AGENT_WATCH_RSS_URLS=
AGENT_WATCH_SCORE_THRESHOLD=4
AGENT_WATCH_MAX_DIGEST_ITEMS=8
AGENT_WATCH_MAX_ITEMS_PER_SOURCE=2
AGENT_WATCH_DIGEST_WINDOW_HOURS=24
AGENT_WATCH_MODEL_SCORING_ENABLED=false
AGENT_WATCH_MODEL_SCORING_MAX_ITEMS=20
AGENT_WATCH_MODEL_SCORING_PAGE_CHARS=5000
```

`AGENT_WATCH_X_ACCOUNTS` is combined with `AGENT_WATCH_X_QUERY` using X `from:` filters. This helps catch new tools early even when they do not match the keyword query perfectly.

`AGENT_WATCH_MODEL_SCORING_ENABLED=true` makes fetch score a limited number of items with the configured model after reading a short page chunk. Keep `AGENT_WATCH_MODEL_SCORING_MAX_ITEMS` low to control cost.

Local operation:

```bash
PYTHONPATH=src uv run python -m school_guardian agent-watch-init
PYTHONPATH=src uv run python -m school_guardian agent-watch-fetch
PYTHONPATH=src uv run python -m school_guardian agent-watch-digest
PYTHONPATH=src uv run python -m school_guardian agent-watch-send
```

For Telegram, create a new channel, create a separate bot with BotFather, add it as channel admin, and set `AGENT_WATCH_TELEGRAM_TARGET` to `@channel_name` or the numeric `chat_id`.

In OpenClaw, the gateway registers two crons: `agent-watch-fetch-15m` for ingestion and `agent-watch-digest-2h` for sending the digest to the separate channel.

## Troubleshooting: token OAuth de Google expirado o revocado

Síntoma (en logs del gateway o al correr `sync-classroom`):

```
google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', ...)
```

Google invalida el refresh token por inactividad prolongada, revocación manual, o rotación de credenciales. El refresh automático ya no funciona y hay que rehacer el flujo OAuth:

1. Borrar el token viejo del host:

```bash
rm secrets/google_token.json
```

2. Regenerar el token con el flujo OAuth local (abre el browser para autorizar):

```bash
SCHOOL_GUARDIAN_CLASSROOM_SOURCE=google PYTHONPATH=src uv run python -m school_guardian sync-classroom
```

Esto crea un nuevo `secrets/google_token.json`.

3. **Importante para openclaw-gateway:** el startup del gateway copia el token al volumen `openclaw-home` sólo si no existe (ver `compose.openclaw.yaml`, condición `[ ! -f ... ]`). Como el volumen persiste entre reinicios, el token viejo sigue adentro incluso después de un restart. Hay que pisarlo manualmente:

```bash
podman cp secrets/google_token.json openclaw-gateway:/home/node/.openclaw/secrets/google_token.json
podman restart openclaw-gateway
```

Alternativa nuclear (borra también crons, workspaces y sesiones de OpenClaw):

```bash
podman compose --env-file openclaw/.env -f compose.openclaw.yaml down -v
```

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
