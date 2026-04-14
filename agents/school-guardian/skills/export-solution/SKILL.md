---
name: export-solution
description: Exporta la solución de una tarea como PDF y la envía por Telegram.
triggers:
  - exportar solución
  - mandar por telegram
  - bajar como pdf
  - enviar pdf
  - quiero el pdf
  - mandame la solución
---

## Cuándo usar este skill

Cuando el usuario pide exportar, bajar, guardar o recibir por Telegram la resolución de una tarea.

## Cómo ejecutarlo

1. Asegurate de tener el `task_id` y el título de la tarea (de `school_guardian_list_pending` o `school_guardian_task_detail`).
2. Tené la solución completa en markdown prolijo y estructurado.
   - Usá `#` o `##` para títulos cortos.
   - Usá listas numeradas para pasos, respuestas o ejercicios.
   - Usá `-` para observaciones o recordatorios.
   - Usá `**negrita**` para remarcar ideas clave.
   - Si la tarea no exige otra cosa, usá esta plantilla:

```md
# [Título breve]

## Respuestas
1. ...
2. ...
3. ...

## Explicación breve
- ...
- ...

## Entrega
- ...
```
3. Llamá SIEMPRE `school_guardian_export_solution` con:
   - `task_id`: el external_id de la tarea
   - `title`: nombre de la tarea
   - `solution`: texto completo de la solución en markdown
   - `chat_id`: el SenderId numérico de Telegram de quien hizo el pedido (está en el contexto de la sesión)

## Importante

- NUNCA respondas solo con texto si el usuario pidió el PDF.
- SIEMPRE ejecutar `school_guardian_export_solution` — no hay alternativa manual.
- Si la solución todavía no fue generada, primero generala y luego llamá el tool.
