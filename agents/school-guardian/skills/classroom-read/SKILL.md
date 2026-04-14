---
name: classroom-read
description: Lee cursos y coursework desde Classroom y los transforma al modelo interno.
---

## Responsibilities

- listar cursos,
- listar coursework,
- leer una tarea puntual,
- normalizar payloads externos a `ClassroomTask`.

## Current implementation

- Adapters activos: `fixture`, `google`
- Punto de entrada: `src/school_guardian/classroom.py`
- Comando principal: `uv run python -m school_guardian sync-classroom`

## Upgrade path

- Mantener la normalización en esta skill para no mezclar payloads externos con el store.
- Si se pasa a producción, revisar scopes y estrategia OAuth según el tipo de cuenta y tenant.
