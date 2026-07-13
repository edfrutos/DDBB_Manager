# Graph Report - DDBB_Manager  (2026-07-12)

## Corpus Check
- 21 files · ~40,331 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 419 nodes · 616 edges · 57 communities (19 shown, 38 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `52b42a9e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ImportadorCatalogo
- user_management_menu
- ConnectionDialog
- .get_database_statistics
- .show_status_message
- main_window.py
- DatabaseManagementMixin
- database_menu
- Destructive operations guard pattern (drop_collection, drop_database, delete_document, cleanup_user_databases)
- DatabaseManager
- .find_one_document
- db_manager.py
- BackupMixin
- .create_collection
- UserManagementMixin
- CLAUDE.md
- handle_choice
- DatabaseManager.get_collection_stats
- audit_log collection (MainWindow-only)
- DatabaseManager.find_documents
- .github/workflows/ci.yml
- DatabaseManager.backup_collection
- DatabaseManager.create_collection
- DatabaseManager.create_database
- DatabaseManager.create_index
- DatabaseManager.drop_index
- DatabaseManager.export_collection
- DatabaseManager.import_collection
- DatabaseManager.insert_document
- DatabaseManager.list_collections
- DatabaseManager.list_databases
- DatabaseManager.rename_collection
- DatabaseManager.update_document
- Connection profiles persisted in ~/.mongodb_manager/connections.json
- core/ future unification layer — DatabaseManager not imported by GUI yet
- .env MongoDB credentials (MONGODB_URI, MONGODB_DATABASE)
- DatabaseManager.check_role_permissions
- DatabaseManager.cleanup_user_databases
- DatabaseManager.connect
- DatabaseManager.delete_document
- DatabaseManager.detect_user_collections
- DatabaseManager.drop_collection
- DatabaseManager.drop_database
- DatabaseManager.find_document_in_collections
- DatabaseManager.find_documents_in_collections
- DatabaseManager.find_one_document
- DatabaseManager.get_database_statistics
- DatabaseManager.get_user_by_id
- DatabaseManager.get_user_databases
- DatabaseManager.has_admin_permissions
- DatabaseManager.list_indexes
- DatabaseManager.set_database
- DatabaseManager.validate_user_access
- DatabaseManager.verify_collection_integrity
- main_window.py
- main_gui.py

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 50 edges
2. `DatabaseManager` - 35 edges
3. `database_menu()` - 17 edges
4. `DatabaseManagementMixin` - 16 edges
5. `handle_choice()` - 15 edges
6. `collection_menu()` - 14 edges
7. `UserManagementMixin` - 14 edges
8. `ImportadorCatalogo` - 12 edges
9. `ConnectionDialog` - 12 edges
10. `DDBB Manager` - 12 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `MainWindow`  [EXTRACTED]
  main_gui.py → gui/main_window.py
- `MainWindow` --inherits--> `BackupMixin`  [EXTRACTED]
  gui/main_window.py → gui/mixins/backup.py
- `MainWindow` --inherits--> `DatabaseManagementMixin`  [EXTRACTED]
  gui/main_window.py → gui/mixins/database_management.py
- `MainWindow` --inherits--> `HelpMixin`  [EXTRACTED]
  gui/main_window.py → gui/mixins/help.py
- `MainWindow` --inherits--> `ImportExportMixin`  [EXTRACTED]
  gui/main_window.py → gui/mixins/import_export.py

## Import Cycles
- None detected.

## Communities (57 total, 38 thin omitted)

### Community 0 - "ImportadorCatalogo"
Cohesion: 0.06
Nodes (21): conectar_mongodb_desde_env(), ErroresDialog, ErroresTableModel, ImportadorCatalogo, importar_catalogo_desde_tabla(), Actualizar la lista de bases de datos disponibles, Actualizar cuando cambia la base de datos seleccionada, Mostrar diálogo para seleccionar archivo de tabla a importar (+13 more)

### Community 1 - "user_management_menu"
Cohesion: 0.14
Nodes (12): format_user_role(), handle_user_management(), Busca documentos en una colección.                  Args:             collect, Detecta las colecciones que probablemente contengan usuarios., Busca documentos en múltiples colecciones y devuelve la primera lista de resulta, Actualiza documentos en una colección.                  Args:             col, Elimina documentos de una colección.                  Args:             colle, Busca un usuario por su ID en todas las colecciones de usuarios detectadas. (+4 more)

### Community 2 - "ConnectionDialog"
Cohesion: 0.19
Nodes (4): ConnectionDialog, Clean up resources and disconnect signals to prevent memory leaks, Handle window close event, Diálogo de conexión a MongoDB.      Flujo de dos pasos:       1. El usuario intr

### Community 3 - ".get_database_statistics"
Cohesion: 0.29
Nodes (4): Obtiene estadísticas de una colección.                  Args:             col, Lista todos los índices de una colección.                  Args:, Verifica la integridad de una colección.                  Args:             c, Recopila estadísticas completas de la base de datos actual.                  R

### Community 4 - ".show_status_message"
Cohesion: 0.05
Nodes (34): MainWindow, Abrir el diálogo de conexión a MongoDB, Cierra la conexión activa a MongoDB y deja la ventana en estado 'no conectado'., Configura la barra de menús con los menús y acciones necesarios, Update the database statistics display, Ensure the collections tree view exists and is valid, recreate if needed, Refresh the user interface, Handle double-click event on collections tree to view collection data (+26 more)

### Community 5 - "main_window.py"
Cohesion: 0.06
Nodes (19): CollectionSelectDialog, Diálogo genérico para seleccionar una colección de una lista., CreateCollectionDialog, DropCollectionDialog, ExportDialog, ImportDialog, PasswordManageDialog, Mostrar un diálogo con los propietarios de todas las colecciones de la base de d (+11 more)

### Community 6 - "DatabaseManagementMixin"
Cohesion: 0.09
Nodes (15): Actualiza la vista previa de acuerdo al tipo de contenido seleccionado, DatabaseManagementMixin, Mostrar estadísticas y detalles de la base de datos seleccionada, Editar campos de la base de datos, Cambiar a una base de datos específica, Ver estadísticas globales de MongoDB, Listar bases de datos agrupadas por propietario con información detallada, Métodos de gestión de bases de datos para MainWindow. (+7 more)

### Community 8 - "database_menu"
Cohesion: 0.15
Nodes (10): collection_menu(), handle_export_import(), parse_json_query(), Inserta un documento en una colección.                  Args:             col, Exporta documentos de una colección a un archivo.                  Args:, Importa documentos desde un archivo a una colección.                  Args:, Menú persistente para operaciones en la colección seleccionada.     Mantiene el, Gestiona la exportación e importación de colecciones.          Args: (+2 more)

### Community 10 - "DatabaseManager"
Cohesion: 0.20
Nodes (7): database_menu(), Crea una nueva base de datos. En MongoDB, la base de datos se crea al crear la p, Menú persistente para operaciones en la base de datos seleccionada.     Mantien, Crea una nueva colección.                  Args:             collection_name:, Elimina una colección.                  Args:             collection_name: No, Renombra una colección.                  Args:             old_name: Nombre a, Crea una copia de seguridad de una colección.                  Args:

### Community 11 - ".find_one_document"
Cohesion: 0.16
Nodes (10): DatabaseManager, Busca un documento en una colección.                  Args:             colle, Busca un documento en múltiples colecciones y devuelve el primero que encuentre., Verifica si el usuario tiene permisos administrativos.                  Args:, Valida si un usuario tiene acceso a una base de datos específica., Verifica si el usuario tiene los permisos requeridos para una operación., Elimina una base de datos completa., Elimina un índice de una colección.                  Args:             collec (+2 more)

### Community 13 - "db_manager.py"
Cohesion: 0.15
Nodes (14): get_mongodb_uri(), handle_choice(), handle_integrity_verification(), main(), _print_integrity_report(), Valida y convierte una cadena a ObjectId.          Args:         id_str: Cade, Lista todas las bases de datos disponibles.                  Returns:, Muestra por consola el informe de integridad generado. (+6 more)

### Community 14 - "BackupMixin"
Cohesion: 0.19
Nodes (7): BackupMixin, Ejecutar el respaldo con las opciones configuradas, Métodos de respaldo y restauración de la base de datos para MainWindow., Crear un respaldo de la base de datos, Programar un respaldo para ejecutarse periódicamente, Restaurar la base de datos desde un respaldo, Ejecutar la restauración con las opciones configuradas.

### Community 16 - ".create_collection"
Cohesion: 0.12
Nodes (16): Administrar índices, Arquitectura, Configuración, DDBB Manager, Desarrollo y verificación, Ejecutar una consulta, Estado del proyecto, Explorar datos (+8 more)

### Community 17 - "UserManagementMixin"
Cohesion: 0.15
Nodes (10): Métodos de gestión de usuarios para MainWindow., List all users from the unified users collection, Editar el usuario seleccionado de los resultados de búsqueda, Editar información de usuario, Eliminar un usuario de la base de datos, Gestionar contraseñas de usuarios, Actualizar la contraseña de un usuario seleccionado, Buscar un usuario para asociarlo al diálogo de cambio de contraseña (+2 more)

### Community 18 - "CLAUDE.md"
Cohesion: 0.15
Nodes (11): Clases principales, Comandos habituales, Convenciones y avisos, `core/db_manager.py`, Entorno, Estado arquitectónico actual, Estructura del proyecto, `gui/dialogs/` (+3 more)

### Community 19 - "handle_choice"
Cohesion: 0.33
Nodes (3): Inicializa el gestor de base de datos.                  Args:             con, Conecta a MongoDB.                  Args:             connection_uri: URI a u, Selecciona la base de datos a utilizar.                  Args:             da

### Community 59 - "main_window.py"
Cohesion: 0.24
Nodes (6): MaintenanceMixin, Seleccionar o deseleccionar todos los elementos de un QListWidget, Ejecutar operaciones de mantenimiento en las colecciones seleccionadas, Métodos de mantenimiento de colecciones para MainWindow., Realizar tareas de mantenimiento en colecciones, Programar tareas de mantenimiento para ejecutarse periódicamente

### Community 60 - "main_gui.py"
Cohesion: 0.20
Nodes (10): limpiar_recursos(), main(), manejar_senales(), Apply a clean, modern light style to the application., Configura manejadores de señales para cierre controlado, Apply a customized dark fusion style to the application., Limpia todos los recursos antes de salir de la aplicación, Punto de entrada principal de la aplicación. (+2 more)

## Knowledge Gaps
- **59 isolated node(s):** `Qué es este repositorio`, `Estructura del proyecto`, ``gui/main_window.py``, ``gui/mixins/``, ``gui/dialogs/`` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `.show_status_message` to `ConnectionDialog`, `main_window.py`, `DatabaseManagementMixin`, `BackupMixin`, `UserManagementMixin`, `main_window.py`, `main_gui.py`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `ImportadorCatalogo` connect `ImportadorCatalogo` to `DatabaseManagementMixin`?**
  _High betweenness centrality (0.205) - this node is a cross-community bridge._
- **Why does `ErroresDialog` connect `ImportadorCatalogo` to `main_window.py`?**
  _High betweenness centrality (0.158) - this node is a cross-community bridge._
- **What connects `Obtiene la URI de MongoDB desde la variable de entorno 'MONGODB_URI'.     Si se`, `Serializa datos de MongoDB a JSON.          Args:         data: Datos a seria`, `Parsea una cadena JSON para formar una consulta MongoDB.          Args:` to the rest of the system?**
  _204 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ImportadorCatalogo` be split into smaller, more focused modules?**
  _Cohesion score 0.06153846153846154 - nodes in this community are weakly interconnected._
- **Should `user_management_menu` be split into smaller, more focused modules?**
  _Cohesion score 0.1437908496732026 - nodes in this community are weakly interconnected._
- **Should `.show_status_message` be split into smaller, more focused modules?**
  _Cohesion score 0.05004389815627744 - nodes in this community are weakly interconnected._