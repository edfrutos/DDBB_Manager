# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repositorio

Herramienta de administración de MongoDB (local y Atlas) escrita en Python: conexión, CRUD de documentos, gestión de bases de datos/colecciones/índices, verificación de integridad, estadísticas, gestión de usuarios y limpieza/optimización. La configuración de conexión se lee de un archivo `.env` (variables `MONGODB_URI`, `MONGODB_DATABASE`, etc.) vía `python-dotenv`.

## Arquitectura: dos bases de código independientes (clave)

El repositorio contiene **dos implementaciones que NO comparten código**. Identifica siempre en cuál estás trabajando antes de editar.

### 1. `ddbb_manager/` — proyecto mantenido (el "de verdad")

Es el único directorio con control de versiones propio (`ddbb_manager/.git`, rama activa `develop`, con CI y pre-commit). venv de Python **3.13**.

- **`ddbb_manager/ddbb_manager.py`** (~4250 líneas): el núcleo. La clase **`DatabaseManager`** concentra toda la lógica de negocio (`connect`, `set_database`, CRUD, `create_index`/`list_indexes`/`drop_index`, `verify_collection_integrity`, `get_database_statistics`, `get_user_databases`, `cleanup_user_databases`, `export_collection`/`import_collection`, gestión de usuarios y permisos). Al final, `main()` monta un menú de texto interactivo con `argparse` (`--uri`, `--db`, `--debug`). **La lógica va en la clase; el menú solo la invoca.**
- **`ddbb_manager/ddbb_manager_gui.py`**: GUI en **Tkinter** que importa y envuelve `DatabaseManager` (`from ddbb_manager import DatabaseManager`). Es la capa de presentación del núcleo anterior.

### 2. Raíz del repo — GUIs alternativas, utilidades y legado (SIN git)

El directorio padre no está bajo control de versiones. Aquí conviven una GUI activa, scripts sueltos y código antiguo:

- **`main_gui.py` + `gui/main_window.py`**: GUI de escritorio en **PyQt6** (`MainWindow`, ~7500 líneas). Punto de entrada = `main_gui.py`. **Reimplementa su propia conexión pymongo** (`self.client`, `self.db`) y **no reutiliza `DatabaseManager`**. Es la única parte que lee/escribe la colección `audit_log`.
- **`conexion-mongodb-atlas.py`**: herramienta PyQt6 independiente (`ImportadorCatalogo`) para importar catálogos desde Excel/CSV con `pandas`.
- **Utilidades sueltas** (scripts standalone, cada uno con su `main()`/`__main__` y su propia conexión pymongo): `check_indexes.py`, `create_user_indexes.py`, `normalize_users.py`, `verify_users_migration.py`.
- **Tests**: `test_connection.py`, `test_user_searches.py` (funciones `test_*`, descubribles por pytest; **requieren una conexión MongoDB real**).
- **`gui_app.py`**: GUI Tkinter legada; importa `db_management_tool.DatabaseManager`, módulo que solo existe en `backup/`, así que **no funciona tal cual**. Tratar como legado.
- **`main_gui_copia.py`**, **`main_window.py` duplicados**, **`backup/`**, **`respaldos/`**: copias y respaldos antiguos. **No editar**; son referencia histórica.

## Comandos habituales

```bash
# --- Núcleo CLI (subproyecto ddbb_manager) ---
cd ddbb_manager
python ddbb_manager.py                 # menú interactivo de texto
python ddbb_manager.py --uri "mongodb+srv://..." --db mibd --debug
python ddbb_manager_gui.py             # GUI Tkinter sobre DatabaseManager

# --- GUI PyQt6 (raíz) ---
python main_gui.py                     # aplicación de escritorio principal (PyQt6)
python conexion-mongodb-atlas.py       # importador de catálogos Excel/CSV

# --- Utilidades de mantenimiento (raíz) ---
python create_user_indexes.py          # crear/recrear índices de usuarios
python check_indexes.py                # inspeccionar índices y campos
python normalize_users.py              # normalizar documentos de usuarios
python verify_users_migration.py       # verificar migración de usuarios

# --- Tests (necesitan MongoDB accesible vía .env) ---
pytest                                 # descubre test_connection.py y test_user_searches.py
python test_connection.py              # comprobar conexión de forma directa
pytest test_user_searches.py::test_email_search   # un solo test

# --- Lint / formato (config en ddbb_manager/) ---
cd ddbb_manager
pre-commit run --all-files             # black + isort + flake8 + hooks básicos
```

## Entornos y dependencias

- Hay **dos venv distintos**: raíz (Python **3.10**) y `ddbb_manager/venv` (Python **3.13**). Usa el que corresponda a la parte que estés tocando.
- `requirements.txt` (raíz) cubre lo básico: `pymongo`, `python-dotenv`, `tqdm`, `PyQt6`. El subproyecto `ddbb_manager/` **no tiene requirements propio** y depende del de la raíz.
- Dependencias usadas por el código pero **ausentes** de `requirements.txt` (instalar aparte si trabajas con esos módulos): `pandas` (importador de catálogos) y `tabulate` (tests de búsqueda).

## Calidad de código y CI

- El linting solo está configurado dentro de `ddbb_manager/` (`.pre-commit-config.yaml`): `black`, `isort`, `flake8` y hooks de whitespace/EOF/YAML. Sigue **PEP 8** y respeta `black`/`isort` al modificar ese subproyecto.
- El workflow `ddbb_manager/.github/workflows/ci.yml` ejecuta `pre-commit run --all-files` en push/PR a `master` y `develop`. **No hay tests en CI**; solo lint.

## Convenciones y avisos

- **Idioma del dominio**: identificadores, menús y comentarios están en español, a veces sin tildes (`accion`, `contrasena`, `direccion`, `telefono`, `movil`, `isdeleted` — ver `.vscode/settings.json`). Mantén ese estilo al añadir código.
- **Operaciones destructivas**: `drop_collection`, `drop_database`, `cleanup_user_databases`, `delete_document` borran datos de forma irreversible. Conserva las confirmaciones existentes antes de ejecutarlas.
- El `.env` contiene credenciales reales de MongoDB Atlas y **no debe** subirse ni volcarse en logs/salida.
- Antes de editar, confirma que el archivo no es una copia de `backup/`, `respaldos/` o un `*_copia.py`: hay varias versiones casi idénticas del mismo código repartidas por el repo.
