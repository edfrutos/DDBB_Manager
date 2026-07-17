# Checklist de prueba humana: edición de registros y contenido anidado

## Alcance
- Flujo de colecciones: edición de registros desde la tabla de datos.
- Objetivo: validar que el contenido se puede abrir, modificar y guardar sin editar JSON manualmente.

## Prerrequisitos
- La app arranca con una base de datos conectada.
- Existe una colección con documentos que incluyan:
  - campos simples (`string`, `int`, `bool`)
  - un objeto anidado
  - una lista anidada
- La colección tiene al menos un documento editable.

## Verificación manual
- Abrir la pestaña de colecciones.
- Seleccionar una colección con datos.
- Verificar que la tabla de datos no se edita directamente en celdas.
- Hacer doble clic sobre un registro.
- Confirmar que se abre el editor del documento.
- Cambiar un campo de texto.
- Cambiar un campo numérico.
- Cambiar un campo booleano.
- Abrir un objeto anidado con el botón de edición y cambiar un valor interno.
- Abrir una lista anidada con el botón de edición y añadir o modificar un elemento.
- Guardar los cambios.
- Confirmar que la tabla se refresca y muestra el valor actualizado.
- Reabrir el mismo registro y verificar que los cambios persisten en la base.

## Criterio de aceptación
- La edición se hace con widgets visibles y comprensibles.
- Los valores anidados se conservan correctamente al guardar.
- No aparecen errores al abrir o guardar campos complejos.
- El usuario no necesita escribir JSON a mano para editar un documento normal.
