---
name: analyze-task-images
description: Analiza las imágenes de un documento adjunto a una tarea usando visión artificial y devuelve el contenido.
triggers:
  - que dice el documento
  - que tiene el archivo
  - no puedo leer el adjunto
  - qué dice la imagen
  - analizá el documento
  - leé el archivo
  - qué hay en el adjunto
  - mandame las imágenes
  - quiero ver el documento
---

## Cuándo usar este skill

Cuando `school_guardian_task_detail` devuelve `extracted_text: null` para un material de tipo `drive_file`, significa que el documento no tiene texto extraíble (probablemente contiene solo imágenes o es un escaneo).

También usar cuando el usuario pide explícitamente ver o entender el contenido de un adjunto.

## Cómo ejecutarlo

1. Asegurate de tener el `task_id` (de `school_guardian_list_pending` o del contexto).
2. Llamar `school_guardian_analyze_task_images` con el `task_id`.
   - El modelo de visión analiza las imágenes y devuelve una descripción detallada del contenido.
   - Mostrar el resultado completo al usuario.
3. Si el usuario quiere ver las imágenes originales además del análisis, llamar `school_guardian_send_task_images` con el `task_id` y el `chat_id` del usuario.

## Importante

- SIEMPRE ejecutar `school_guardian_analyze_task_images` antes de responder que "no hay contenido".
- Si el análisis devuelve texto, mostrarlo íntegro — no resumir.
- `school_guardian_send_task_images` es opcional y solo si el usuario pide las imágenes originales.
