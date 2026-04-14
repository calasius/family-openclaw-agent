---
name: tarea-detalle
description: Muestra el detalle estructurado de una tarea y permite explorar sus secciones una por una.
triggers:
  - ver tarea
  - detalle de la tarea
  - quiero ver esa
  - mostrame esa
  - la número
  - abrir tarea
  - qué dice la tarea
  - qué tengo que hacer en
---

## Cuándo usar este skill

Cuando el usuario selecciona una tarea específica de una lista, o pide ver el detalle o contenido de una tarea puntual.

## Cómo ejecutarlo

### Paso 1 — Registrar activación del skill

Llamá `school_guardian_skill_log` con `skill: "tarea-detalle"` y `context: "task_id=<el_id>"`.

### Paso 2 — Obtener el detalle

Llamá `school_guardian_task_detail` con el `task_id` (external_id) de la tarea.

### Paso 3 — Presentar el resumen estructurado

Mostrá siempre este encabezado:

```
📚 [MATERIA] — [TÍTULO]
📅 Vence: [fecha] (o "sin fecha")

Secciones:
1. [Nombre de la sección o actividad]
2. [Nombre de la sección o actividad]
3. ...

¿Por cuál querés empezar?
```

Para identificar las secciones: buscá títulos en mayúsculas o encabezados dentro del `extracted_text` (ej: PUNTO DE PARTIDA, INDAGACIÓN, PRODUCCIÓN, EVALUACIÓN, ACTIVIDADES). Si el documento no tiene secciones claras, listá los materiales adjuntos como ítems.

### Paso 4 — Expandir la sección elegida

Cuando el usuario elige una sección (por número o por nombre):
- Mostrá el contenido **completo** de esa sección, sin resumir, sin cortar, sin parafrasear.
- Si hay ejercicios numerados, mostrarlos todos.
- Si hay una URL o video, incluirla al final como referencia.
- Al terminar, preguntá: "¿Querés ver otra sección o necesitás ayuda para resolver algo?"

## Reglas

- NUNCA mostrar el texto completo del documento de entrada — siempre presentar primero el índice de secciones.
- NUNCA resumir el contenido de una sección cuando se expande — el texto va completo.
- Si `extracted_text` está vacío o es muy corto para una sección, avisalo: "Esta sección no tiene texto extraíble, puede que tenga imágenes. ¿Querés que intente analizarlas?"
- No inventar secciones que no estén en el documento.
- Mantener el tono amigable: "¿Por cuál arrancamos?" en vez de "Seleccione una opción".
