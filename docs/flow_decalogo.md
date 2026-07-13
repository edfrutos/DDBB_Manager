# Decálogo de flujos

Este documento resume el mapa compacto de dependencias del proyecto. Se usa como orden de trabajo cuando hay que seguir la evolución de la app sin perder el hilo funcional.

## 1. Arranque

`main_gui.py -> main() -> QApplication -> MainWindow`

Depende de:
- `load_dotenv()`
- `set_light_style()`
- `MainWindow.__init__()`

Valida:
- carga de entorno
- ventana principal
- arranque automático opcional de conexión

## 2. Conexión

`MainWindow.open_connection_dialog() -> ConnectionDialog -> initialize_connection() -> _connect_to_database()`

Depende de:
- `MONGODB_URI`
- `ConnectionDialog.get_connection_data()`
- `connection_status_changed`

Valida:
- URI
- base de datos activa
- activación de pestañas de trabajo

## 3. Colecciones

`show_collections() -> create_user_grouped_view() / create_type_grouped_view() / create_flat_view()`

Depende de:
- `CollectionViewMixin`
- `detect_collection_content_type()`
- `find_collection_owner()`
- `is_tree_view_valid()`

Valida:
- árbol de colecciones
- modos de agrupación
- navegación visual

## 4. Metadatos

`load_collection_metadata() -> detect_collection_content_type() -> load_access_history()`

Depende de:
- `find_collection_owner()`
- `meta_*` widgets
- `audit_log` si existe

Valida:
- tamaño
- índices
- propietario
- fechas
- historial de acceso

## 5. Consultas

`execute_query()`

Depende de:
- `query_editor`
- `results_view`
- `show_status_message()`

Valida:
- `find`
- `insertOne`
- `insertMany`
- `updateOne`
- `updateMany`
- `deleteOne`
- `deleteMany`

## 6. Bases de datos

`create_collection() / drop_collection() / switch_to_database() / show_global_stats() / list_databases_by_owner()`

Depende de:
- `self.client`
- `self.db`
- `show_collections()`
- `update_database_stats()`

Valida:
- cambio de contexto
- estadísticas globales
- propietarios de bases de datos
- cambios destructivos con confirmación

## 7. Respaldo

`backup_database() -> execute_backup() -> restore_database() -> execute_restore()`

Depende de:
- `QFileDialog`
- `QProgressDialog`
- archivos `metadata.json`, `collections/*`

Valida:
- respaldo completo o selectivo
- compresión
- restauración con conflictos

## 8. Importación y exportación

`import_data() / export_data()`

Depende de:
- `ImportDialog`
- `ExportDialog`
- `QFileDialog`

Valida:
- JSON
- CSV
- limpieza previa de colección

## 9. Usuarios

`list_users() / search_user() / edit_user() / delete_user() / manage_password()`

Depende de:
- `PasswordManageDialog`
- `users_unified`
- `show_user_results()`

Valida:
- búsqueda
- edición
- borrado
- contraseña

## 10. Índices y mantenimiento

`manage_indexes() / verify_integrity() / maintain_collections()`

Depende de:
- `CollectionSelectDialog`
- `QProgressDialog`
- `validate`
- `collStats`

Valida:
- creación de índices
- reindexación
- integridad
- mantenimiento programado

## Dependencias compartidas

Estos helpers aparecen en varios flujos y conviene tratarlos como contrato común:

- `show_status_message()`
- `update_database_stats()`
- `show_collections()`
- `record_activity()`
- `find_collection_owner()`
- `detect_collection_content_type()`

## Regla de trabajo

Seguir este orden cuando haya que ampliar la app o añadir pruebas:
1. arranque y conexión
2. colecciones y metadatos
3. consultas
4. bases de datos
5. respaldo
6. import/export
7. usuarios
8. índices
9. mantenimiento
10. telemetría opcional

## Criterio de cierre

Un flujo se considera cubierto cuando:
- tiene ruta funcional clara
- tiene verificación automática
- sus dependencias compartidas están estables
- no depende de Atlas para la prueba básica
