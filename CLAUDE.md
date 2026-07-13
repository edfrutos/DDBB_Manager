# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repositorio

Herramienta de administración de MongoDB (local y Atlas) escrita en Python con interfaz gráfica PyQt6. Permite conexión, CRUD de documentos, gestión de bases de datos/colecciones/índices, verificación de integridad, estadísticas, gestión de usuarios y limpieza/optimización. Destino: app de escritorio macOS.

## Estructura del proyecto

```
DDBB_Manager/
├── main_gui.py              # Punto de entrada (PyQt6)
├── gui/
│   ├── main_window.py       # MainWindow (~2900 líneas): ventana principal y flujos aún no extraídos
│   ├── dialogs/             # Diálogos PyQt6 reutilizables extraídos de MainWindow
│   └── mixins/              # Grupos funcionales extraídos de MainWindow
├── core/
│   ├── db_manager.py        # DatabaseManager: motor CLI sin UI (referencia)
│   └── importer.py          # ImportadorCatalogo: importación Excel/CSV con pandas
├── docs/
│   └── history/
│       └── ddbb_manager_develop.bundle  # Bundle git del subproyecto original
├── requirements.txt         # PyQt6, pymongo, python-dotenv, tqdm, pandas, tabulate
├── venv/                    # Python 3.12 (usar este para ejecutar)
└── .env                     # MONGODB_URI, MONGODB_DATABASE (credenciales reales, no subir)
```

## Clases principales

### `gui/main_window.py`

- **`ConnectionDialog`** (línea ~48): diálogo de dos pasos — URI + perfiles guardados en `~/.mongodb_manager/connections.json` → conecta → combo de BD poblado con `list_database_names()`. Interfaz pública: `get_connection_data()` → `{"connection_string": ..., "database": ...}`.
- **`MainWindow`** (línea ~220): ventana principal PyQt6. Mantiene su propia conexión pymongo (`self.client`, `self.db`) y hereda mixins funcionales para reducir el tamaño del archivo principal.
- La clase escribe en la colección `audit_log` (solo en esta GUI, no en `DatabaseManager`).

### `gui/mixins/`

Mixins funcionales ya extraídos de `MainWindow`:

- **`MaintenanceMixin`**: mantenimiento de colecciones (`maintain_collections`, `execute_maintenance`, `schedule_maintenance_task`).
- **`BackupMixin`**: respaldo, programación y restauración de bases de datos (`backup_database`, `execute_backup`, `restore_database`).
- **`UserManagementMixin`**: listado, búsqueda, edición, borrado y contraseñas de usuarios.
- **`ImportExportMixin`**: importación y exportación de colecciones.
- **`DatabaseManagementMixin`**: listado/cambio de bases de datos, estadísticas globales, propietarios, detalles y edición de campos.
- **`IndexManagementMixin`**: consulta, creación y reconstrucción de índices de colecciones.
- **`HelpMixin`**: pantalla de ayuda/tutorial y cuadro "Acerca de".
- **`CollectionViewMixin`**: árbol de colecciones, navegación, recreación de la vista y carga de documentos.
- **`QueryMixin`**: ejecución de consultas MongoDB desde el editor de consultas.

### `gui/dialogs/`

Diálogos reutilizables extraídos de código inline: selección de colección, creación y borrado de colecciones, importación, exportación y gestión de contraseña.

### `core/db_manager.py`

Clase `DatabaseManager` con lógica de negocio: `connect`, `set_database`, CRUD, `create_index`/`list_indexes`/`drop_index`, `verify_collection_integrity`, `get_database_statistics`, `get_user_databases`, `cleanup_user_databases`, `export_collection`/`import_collection`, gestión de usuarios. **No importado por la GUI aún** — referencia para futura unificación de capas.

## Estado arquitectónico actual

- La fase activa es la reducción incremental de `gui/main_window.py` mediante extracción a `gui/dialogs/` y `gui/mixins/`.
- `MainWindow` sigue siendo el coordinador de UI y conexión, pero parte de los dominios de mantenimiento, respaldo, usuarios, import/export, bases de datos e índices ya vive fuera del archivo principal.
- Lo que queda en `MainWindow` son principalmente helpers de ventana, inicialización de UI y cierre. No fuerces más mixins si no se gana claridad real.
- `core/db_manager.py` continúa siendo referencia/CLI independiente; no modificarlo para cambios de GUI salvo que se planifique explícitamente la integración de capas.
- El orden de trabajo operativo vive en `docs/flow_decalogo.md`. Seguir ese mapa cuando haya que priorizar pruebas o nuevas mejoras.

## Comandos habituales

```bash
# Ejecutar la aplicación
source venv/bin/activate
python main_gui.py

# Verificar sintaxis sin ejecutar
venv/bin/python -m py_compile gui/main_window.py

# Verificar sintaxis de los módulos principales
venv/bin/python -m py_compile main_gui.py gui/*.py gui/mixins/*.py gui/dialogs/*.py core/*.py

# Smoke test de los flujos básicos sin depender de Atlas
venv/bin/python -m unittest tests.test_smoke_flows -q

# Instalar dependencias en el venv
venv/bin/pip install -r requirements.txt
```

## Entorno

- **Python 3.12** en `venv/` (el único intérprete con PyQt6 disponible en este sistema)
- El `.env` contiene `MONGODB_URI` con credenciales reales de MongoDB Atlas — **no subir, no volcar en logs**
- Perfiles de conexión guardados en `~/.mongodb_manager/connections.json`

## Convenciones y avisos

- **Idioma del dominio**: identificadores, menús y comentarios en español (a veces sin tildes: `accion`, `contrasena`, `direccion`, `telefono`). Mantener al añadir código.
- **Operaciones destructivas**: `drop_collection`, `drop_database`, `cleanup_user_databases`, `delete_document` borran datos de forma irreversible. Conservar todas las confirmaciones existentes.
- Los warnings de Pyright sobre imports de PyQt6/pymongo son esperados cuando el linter usa el Python del sistema (3.14) en lugar del venv (3.12).
- `core/` existe para futura integración incremental. No modificar `core/db_manager.py` para cambios en la GUI — son capas independientes hasta que se fusionen explícitamente.
- Existe `tests/test_smoke_flows.py` para validar los flujos básicos de la UI con dobles en memoria cuando no se puede llegar a MongoDB real. Cubre creación, consulta, cambio de base de datos, backup, restore, gestión de contraseñas, edición/borrado de usuarios, importación/exportación, vistas de colección, metadatos e historial de acceso, descubrimiento de propietarios, estadísticas globales, integridad y borrado.
- La integración con WakaTime es opcional y depende de `WAKATIME_ENABLED=true` junto con `WAKATIME_API_KEY`. Si no están definidos, no debe afectar a la ejecución ni a los tests.
