# Checklist de prueba humana: mantenimiento

## Alcance
- Flujo 10 del decálogo: `maintain_collections()`, `execute_maintenance()` y `verify_integrity()`.
- Objetivo: validar selección de colecciones, ejecución de tareas de mantenimiento y lectura del resultado.

## Prerrequisitos
- La app arranca con una base de datos conectada.
- Existen varias colecciones con datos distintos.
- Al menos una colección tiene duplicados, otra tiene índices y otra tiene documentos válidos para validar.

## Verificación manual
- Abrir la ventana principal.
- Entrar en mantenimiento de colecciones.
- Confirmar que la lista de colecciones se muestra.
- Usar selección total y limpieza de selección.
- Ejecutar mantenimiento con una sola opción activa.
- Ejecutar mantenimiento con varias opciones activas.
- Probar la programación de mantenimiento periódico.
- Confirmar que la zona de resultados se llena con mensajes coherentes.
- Lanzar la verificación de integridad.
- Confirmar que el resumen de colecciones válidas/inválidas coincide con la base real.

## Criterio de aceptación
- No hay bloqueos en la UI.
- Las acciones muestran resultados comprensibles.
- La ejecución programada y la ejecución inmediata se distinguen bien.
- Los mensajes de error aparecen solo cuando hay una condición real de fallo.
