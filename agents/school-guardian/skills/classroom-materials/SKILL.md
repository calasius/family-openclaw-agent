---
name: classroom-materials
description: Detecta materiales de Classroom y descarga PDF/DOCX cuando están disponibles.
---

## Responsibilities

- inspeccionar materiales por tarea,
- generar un manifest local,
- descargar adjuntos PDF/DOCX,
- exportar Google Docs a PDF cuando corresponda.

## Current implementation

- Lógica: `src/school_guardian/materials.py`
- Comandos:
  - `uv run python -m school_guardian list-materials`
  - `uv run python -m school_guardian download-materials`
