---
name: school-task-store
description: Persiste tareas escolares, hace upsert y responde consultas de pendientes y vencimientos.
---

## Responsibilities

- upsert de tareas,
- deduplicación por `external_id`,
- consulta de pendientes,
- consulta de vencimientos,
- consulta de tareas sincronizadas recientemente.

## Current implementation

- Store: SQLite
- Punto de entrada: `src/school_guardian/store.py`
- Base por defecto: `data/school_guardian.db`
