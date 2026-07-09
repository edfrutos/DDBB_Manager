# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repositorio

Herramienta de administración de MongoDB (local y Atlas) escrita en Python con interfaz gráfica PyQt6. Permite conexión, CRUD de documentos, gestión de bases de datos/colecciones/índices, verificación de integridad, estadísticas, gestión de usuarios y limpieza/optimización. Destino: app de escritorio macOS.

## Estructura del proyecto

```
DDBB_Manager/
├── main_gui.py              # Punto de entrada (PyQt6)
├── gui/
│   └── main_window.py       # MainWindow (~6900 líneas): toda la UI PyQt6
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

- **`ConnectionDialog`** (línea ~39): diálogo de dos pasos — URI + perfiles guardados en `~/.mongodb_manager/connections.json` → conecta → combo de BD poblado con `list_database_names()`. Interfaz pública: `get_connection_data()` → `{"connection_string": ..., "database": ...}`.
- **`MainWindow`** (línea ~195): ventana principal con 87 métodos. Mantiene su propia conexión pymongo (`self.client`, `self.db`). Métodos de mantenimiento: `maintain_collections` → `execute_maintenance` → `schedule_maintenance_task`.
- La clase escribe en la colección `audit_log` (solo en esta GUI, no en `DatabaseManager`).

### `core/db_manager.py`

Clase `DatabaseManager` con lógica de negocio: `connect`, `set_database`, CRUD, `create_index`/`list_indexes`/`drop_index`, `verify_collection_integrity`, `get_database_statistics`, `get_user_databases`, `cleanup_user_databases`, `export_collection`/`import_collection`, gestión de usuarios. **No importado por la GUI aún** — referencia para futura unificación de capas.

## Comandos habituales

```bash
# Ejecutar la aplicación
source venv/bin/activate
python main_gui.py

# Verificar sintaxis sin ejecutar
venv/bin/python -m py_compile gui/main_window.py

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
