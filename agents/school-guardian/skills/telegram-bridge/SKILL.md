---
name: telegram-bridge
description: Responde por Telegram con pendientes, vencimientos y foco diario usando el store del agente.
---

## Responsibilities

- atender `/pendientes`, `/manana`, `/foco`, `/nuevo`,
- responder solo al chat permitido,
- usar el store interno como fuente de verdad,
- servir de puente entre OpenClaw y Telegram.

## Current implementation

- Lógica: `src/school_guardian/telegram_bot.py`
- Comando: `uv run python -m school_guardian telegram-poll-once`
