# Checklist de prueba humana: propietarios de bases de datos

## Alcance
- Flujo 6 del decálogo: `show_databases()`, `switch_database()`, `show_global_stats()` y `list_databases_by_owner()`.
- Objetivo: validar que el usuario puede ver bases de datos, cambiar entre ellas y revisar el agrupado por propietario.

## Prerrequisitos
- La app arranca con un servidor MongoDB accesible.
- Existen varias bases de datos no del sistema.
- Al menos una base de datos tiene metadatos de propietario o colecciones de usuarios/admins.

## Verificación manual
- Abrir la lista de bases de datos.
- Confirmar que aparecen solo las bases accesibles.
- Cambiar a otra base de datos desde la lista.
- Verificar que la ventana principal actualiza el contexto.
- Abrir estadísticas globales.
- Confirmar que el resumen de versión, conexiones y tamaño es coherente.
- Abrir el listado de bases de datos por propietario.
- Confirmar que las pestañas agrupan las bases de datos correctamente.
- Revisar que los datos de propietario, tamaño y colecciones coinciden con la base real.

## Criterio de aceptación
- La navegación entre bases no rompe el estado.
- Los paneles muestran información consistente.
- No hay errores al abrir bases de datos sin metadatos explícitos.
- Los mensajes de aviso solo aparecen cuando falta conexión o no hay datos.
