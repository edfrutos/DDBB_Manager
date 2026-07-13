# Checklist de prueba humana: gestión de índices

## Alcance
- Flujo 10 del decálogo: `manage_indexes()` y `verify_integrity()`.
- Objetivo: validar la experiencia real de selección de colección, creación de índice, reindexación e integridad.

## Prerrequisitos
- La app arranca con una base de datos conectada.
- Existen al menos dos colecciones con datos.
- Una colección tiene campos aptos para indexar.

## Verificación manual
- Abrir la ventana principal.
- Entrar en gestión de índices.
- Seleccionar una colección con datos.
- Confirmar que la tabla de índices existentes se carga.
- Crear un índice estándar sobre un campo simple.
- Confirmar que el índice nuevo aparece en la tabla.
- Crear un índice único sobre un campo válido.
- Confirmar que la operación informa éxito o rechazo si hay duplicados.
- Probar un índice TTL sobre un campo de fecha.
- Confirmar que pide segundos y crea el índice.
- Cancelar la creación de un índice y verificar que no cambia nada.
- Lanzar una reindexación.
- Confirmar que el proceso termina con éxito o con un error explicado.
- Ejecutar la verificación de integridad.
- Confirmar que el resumen coincide con el estado de las colecciones.

## Criterio de aceptación
- La UI responde sin bloqueos.
- Los mensajes de éxito/error son coherentes.
- La tabla de índices se actualiza tras crear o reindexar.
- No aparecen errores no controlados.
