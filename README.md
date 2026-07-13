<!-- generated-by: gsd-doc-writer -->
# DDBB Manager

Aplicación de escritorio en Python y PyQt6 para administrar bases de datos MongoDB locales o alojadas en Atlas mediante una interfaz gráfica.

## Funciones principales

- Conexión manual o automática a MongoDB y selección de base de datos.
- Exploración de bases de datos y colecciones con diferentes modos de agrupación.
- Consulta, creación, edición y eliminación de documentos.
- Creación, consulta y reconstrucción de índices.
- Importación y exportación de colecciones.
- Copias de seguridad, restauración y tareas programadas.
- Estadísticas, mantenimiento y verificación de integridad.
- Gestión de usuarios, roles y contraseñas.
- Importación de catálogos desde Excel o CSV.

## Requisitos

- Python 3.12 recomendado.
- Una instancia accesible de MongoDB local o MongoDB Atlas.
- Credenciales con permisos adecuados para las operaciones que se quieran realizar.

Las dependencias principales son PyQt6, PyMongo, python-dotenv, pandas, tqdm y tabulate. La lista completa está en [`requirements.txt`](requirements.txt).

## Instalación

```bash
git clone https://github.com/edfrutos/DDBB_Manager.git
cd DDBB_Manager

python3.12 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Windows, la activación del entorno virtual es:

```powershell
venv\Scripts\Activate.ps1
```

## Configuración

La aplicación puede iniciarse sin archivo `.env` y conectarse después desde **Conexión > Conectar**. Para intentar una conexión automática al arrancar, cree un archivo `.env` en la raíz:

```dotenv
MONGODB_URI=mongodb://usuario:contrasena@servidor:27017/
MONGODB_DATABASE=nombre_base_datos
```

| Variable | Obligatoria | Descripción |
|---|---|---|
| `MONGODB_URI` | No | URI utilizada para el intento de conexión automática. |
| `MONGODB_DATABASE` | No | Base de datos inicial; si no se define, la GUI utiliza su valor predeterminado. |

No añada `.env` al control de versiones ni publique URIs que contengan credenciales.

### Integración opcional con WakaTime

La aplicación puede enviar heartbeats opcionales a WakaTime si define estas variables:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `WAKATIME_ENABLED` | No | Activa la integración cuando vale `true`, `1`, `yes` o `on`. |
| `WAKATIME_API_KEY` | Sí, para usarla | Clave de API de WakaTime. |
| `WAKATIME_PROJECT_NAME` | No | Nombre del proyecto que aparecerá en WakaTime. |

Si la integración no está activada, la aplicación sigue funcionando con normalidad.

## Inicio rápido

1. Active el entorno virtual.
2. Ejecute la aplicación:

   ```bash
   python main_gui.py
   ```

3. Si no configuró `MONGODB_URI`, abra **Conexión > Conectar**, introduzca la URI y seleccione una base de datos.
4. Utilice las pestañas y menús para explorar colecciones, ejecutar consultas y realizar tareas administrativas.

La aplicación carga un estilo claro, muestra la ventana principal y, cuando existe `MONGODB_URI`, programa el intento de conexión automática después de iniciar la interfaz.

El mapa compacto de flujos está en [`docs/flow_decalogo.md`](docs/flow_decalogo.md).

## Uso habitual

### Explorar datos

Conéctese a MongoDB, seleccione una base de datos y abra la vista de colecciones. Desde ella puede inspeccionar documentos y metadatos, cambiar el modo de agrupación y actualizar la vista.

### Ejecutar una consulta

Abra la pestaña de consultas, seleccione la colección y escriba un filtro MongoDB válido. Revise siempre la colección activa antes de ejecutar operaciones de escritura.

### Administrar índices

Use la opción de gestión de índices para seleccionar una colección, consultar sus índices y crear índices estándar, únicos, de texto o TTL. La misma ventana permite solicitar una reindexación.

### Importar o exportar

Las acciones de importación y exportación permiten trasladar datos entre MongoDB y archivos compatibles. El importador de catálogos utiliza pandas para procesar fuentes Excel y CSV.

## Arquitectura

```text
main_gui.py
    └── gui/main_window.py
            ├── gui/dialogs/       diálogos reutilizables
            └── gui/mixins/        dominios funcionales de la GUI

core/
    ├── db_manager.py              gestor MongoDB y menú CLI independiente
    └── importer.py                importador de catálogos Excel/CSV
```

`MainWindow` coordina la interfaz, el cliente PyMongo y la base de datos activa. La funcionalidad se está separando progresivamente en mixins especializados:

- `MaintenanceMixin`
- `BackupMixin`
- `UserManagementMixin`
- `ImportExportMixin`
- `DatabaseManagementMixin`
- `IndexManagementMixin`
- `HelpMixin`
- `CollectionViewMixin`
- `QueryMixin`

`core/db_manager.py` sigue siendo una implementación independiente de referencia y todavía no es la capa de servicios de la GUI.

La GUI incluye una integración opcional con WakaTime para registrar actividad de uso en los flujos principales. Es completamente opt-in y se desactiva si no se define `WAKATIME_API_KEY`.

## Desarrollo y verificación

Ejecute una comprobación de sintaxis de todos los módulos principales con:

```bash
venv/bin/python -m py_compile \
  main_gui.py \
  gui/main_window.py \
  gui/mixins/*.py \
  gui/dialogs/*.py \
  core/*.py
```

Actualmente el repositorio no contiene una suite de pruebas automatizadas. Los cambios de interfaz y operaciones MongoDB deben validarse también de forma manual contra una base de datos de prueba.

Como apoyo mínimo, existe un smoke test en `tests/test_smoke_flows.py` que valida los flujos básicos de creación, consulta, cambio de base de datos, backup, restore, gestión de contraseñas, edición/borrado de usuarios, importación/exportación, vistas de colección, metadatos e historial de acceso, descubrimiento de propietarios, estadísticas globales, integridad y borrado usando dobles de base de datos.

## Estado del proyecto

La fase activa es una refactorización incremental de `gui/main_window.py`. Los dominios de mantenimiento, respaldo, usuarios, importación/exportación, bases de datos, índices, ayuda/tutorial, vistas de colecciones y consultas ya están separados en mixins. La lógica de metadatos, detección de contenido y descripción de campos de colecciones vive en `CollectionViewMixin`, los propietarios y la creación/borrado de colecciones ya están en `DatabaseManagementMixin`, y la validación de integridad vive en `MaintenanceMixin`. Lo que queda en `MainWindow` son principalmente helpers de ventana y pegamento de UI.

## Seguridad

- Utilice una base de datos de prueba durante el desarrollo.
- Aplique el principio de mínimo privilegio a las credenciales de MongoDB.
- Revise las confirmaciones antes de eliminar documentos, colecciones o bases de datos.
- No almacene credenciales reales en documentación, capturas, logs o commits.

## Licencia

Este repositorio no incluye actualmente un archivo de licencia. Hasta que se añada uno, no se conceden permisos explícitos de uso, modificación o distribución.
