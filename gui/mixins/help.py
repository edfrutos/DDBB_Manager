from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class HelpMixin:
    """Métodos de ayuda e información para MainWindow."""

    def show_about(self):
        """Mostrar información sobre la aplicación."""
        about_text = """
<h2>Gestor de Base de Datos MongoDB</h2>
<p>Versión 1.0.0</p>
<p>Una aplicación GUI multiplataforma para la gestión de bases de datos MongoDB.</p>
<p>Características:</p>
<ul>
    <li>Conectar a bases de datos MongoDB</li>
    <li>Ver y gestionar colecciones</li>
    <li>Ejecutar consultas MongoDB</li>
    <li>Importar y exportar datos</li>
    <li>Gestión de usuarios y permisos</li>
    <li>Interfaz moderna e intuitiva</li>
</ul>
<p>Creado por Eugenio de Frutos con ❤️</p>
<p>&copy; 2025 Eugenio de Frutos - Todos los derechos reservados</p>
"""

        QMessageBox.about(self, "Acerca de Gestor de Base de Datos MongoDB", about_text)

    def show_tutorial(self):
        """Mostrar un tutorial sobre cómo usar la aplicación."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Tutorial - Gestor de Base de Datos MongoDB")
            dialog.resize(800, 600)
            layout = QVBoxLayout(dialog)

            title = QLabel("Guía de Uso - Gestor de Base de Datos MongoDB")
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
            layout.addWidget(title)

            tab_widget = QTabWidget()

            intro_widget = QWidget()
            intro_layout = QVBoxLayout(intro_widget)
            intro_text = QLabel("""
<h3>Bienvenido al Gestor de Base de Datos MongoDB</h3>

<p>Esta aplicación le permite gestionar sus bases de datos MongoDB de forma sencilla e intuitiva.</p>

<p><b>Características principales:</b></p>
<ul>
  <li>Conectar a servidores MongoDB locales o remotos</li>
  <li>Gestionar bases de datos y colecciones</li>
  <li>Importar y exportar datos en diferentes formatos</li>
  <li>Ejecutar consultas MongoDB</li>
  <li>Gestionar usuarios y permisos</li>
  <li>Verificar la integridad de las bases de datos</li>
</ul>

<p>En las siguientes secciones encontrará información detallada sobre cómo utilizar cada función.</p>
""")
            intro_text.setWordWrap(True)
            intro_text.setTextFormat(Qt.TextFormat.RichText)
            intro_layout.addWidget(intro_text)

            connect_widget = QWidget()
            connect_layout = QVBoxLayout(connect_widget)
            connect_text = QLabel("""
<h3>Conectarse a MongoDB</h3>

<p><b>Para conectarse a una base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Conexión > Conectar</b> o haga clic en el botón <b>Conectar a MongoDB</b> en el panel principal.</li>
  <li>Introduzca su cadena de conexión MongoDB en el formato: <code>mongodb://usuario:contraseña@host:puerto/</code></li>
  <li>Especifique el nombre de la base de datos a la que desea conectarse.</li>
  <li>Haga clic en <b>Aceptar</b> para establecer la conexión.</li>
</ol>

<p><b>Para cambiar de base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Base de Datos > Cambiar Base de Datos</b>.</li>
  <li>Seleccione la base de datos deseada de la lista.</li>
</ol>

<p><b>Para desconectar:</b></p>
<ol>
  <li>Utilice el menú <b>Conexión > Desconectar</b>.</li>
</ol>
""")
            connect_text.setWordWrap(True)
            connect_text.setTextFormat(Qt.TextFormat.RichText)
            connect_layout.addWidget(connect_text)

            collections_widget = QWidget()
            collections_layout = QVBoxLayout(collections_widget)
            collections_text = QLabel("""
<h3>Gestión de Colecciones</h3>

<p><b>Para ver colecciones:</b></p>
<ol>
  <li>Una vez conectado, la pestaña <b>Colecciones</b> muestra todas las colecciones disponibles.</li>
  <li>Haga doble clic en una colección para ver sus documentos.</li>
</ol>

<p><b>Para crear una nueva colección:</b></p>
<ol>
  <li>Utilice el menú <b>Colecciones > Crear Colección</b>.</li>
  <li>Introduzca el nombre de la nueva colección.</li>
  <li>Haga clic en <b>Aceptar</b> para crearla.</li>
</ol>

<p><b>Para eliminar una colección:</b></p>
<ol>
  <li>Utilice el menú <b>Colecciones > Eliminar Colección</b>.</li>
  <li>Seleccione la colección que desea eliminar.</li>
  <li>Confirme la eliminación cuando se solicite.</li>
</ol>
""")
            collections_text.setWordWrap(True)
            collections_text.setTextFormat(Qt.TextFormat.RichText)
            collections_layout.addWidget(collections_text)

            queries_widget = QWidget()
            queries_layout = QVBoxLayout(queries_widget)
            queries_text = QLabel("""
<h3>Consultas MongoDB</h3>

<p>En la pestaña <b>Consultas</b> puede ejecutar comandos MongoDB utilizando la sintaxis:</p>
<code>db.collection.operation(parameters)</code>

<p><b>Ejemplos de consultas:</b></p>
<ul>
  <li><code>db.users.find({})</code> - Buscar todos los documentos en la colección "users"</li>
  <li><code>db.users.find({"nombre": "Juan"})</code> - Buscar documentos donde el campo "nombre" sea "Juan"</li>
  <li><code>db.users.insertOne({"nombre": "Ana", "email": "ana@ejemplo.com"})</code> - Insertar un nuevo documento</li>
  <li><code>db.users.updateOne({"nombre": "Juan"}, {"$set": {"email": "juan@ejemplo.com"}})</code> - Actualizar un documento</li>
  <li><code>db.users.deleteOne({"nombre": "Juan"})</code> - Eliminar un documento</li>
  <li><code>db.users.countDocuments({"activo": true})</code> - Contar documentos según un criterio</li>
</ul>

<p><b>Operadores comunes:</b></p>
<ul>
  <li><code>$eq</code> - Igual a (=)</li>
  <li><code>$ne</code> - No igual a (!=)</li>
  <li><code>$gt</code> - Mayor que (>)</li>
  <li><code>$lt</code> - Menor que (<)</li>
  <li><code>$in</code> - En un array de valores</li>
  <li><code>$and</code> - Operador lógico AND</li>
  <li><code>$or</code> - Operador lógico OR</li>
</ul>

<p>Para ejecutar una consulta, escriba el comando en el editor y pulse el botón <b>Ejecutar</b>.</p>
""")
            queries_text.setWordWrap(True)
            queries_text.setTextFormat(Qt.TextFormat.RichText)
            queries_layout.addWidget(queries_text)

            import_export_widget = QWidget()
            import_export_layout = QVBoxLayout(import_export_widget)
            import_export_text = QLabel("""
<h3>Importación y Exportación de Datos</h3>

<p><b>Para importar datos:</b></p>
<ol>
  <li>Utilice el menú <b>Datos > Importar Datos</b>.</li>
  <li>Seleccione el formato de origen (JSON, CSV, BSON).</li>
  <li>Elija el archivo a importar.</li>
  <li>Seleccione la colección de destino.</li>
  <li>Configure las opciones adicionales de importación.</li>
  <li>Haga clic en <b>Importar</b> para iniciar el proceso.</li>
</ol>

<p><b>Para exportar datos:</b></p>
<ol>
  <li>Utilice el menú <b>Datos > Exportar Datos</b>.</li>
  <li>Seleccione la colección a exportar.</li>
  <li>Elija el formato de exportación (JSON, CSV, BSON).</li>
  <li>Especifique la ubicación del archivo de salida.</li>
  <li>Configure las opciones adicionales de exportación.</li>
  <li>Haga clic en <b>Exportar</b> para iniciar el proceso.</li>
</ol>

<p><b>Formatos soportados:</b></p>
<ul>
  <li><b>JSON</b> - Formato estándar para intercambio de datos</li>
  <li><b>CSV</b> - Formato de valores separados por comas</li>
  <li><b>BSON</b> - Formato binario de MongoDB</li>
</ul>
""")
            import_export_text.setWordWrap(True)
            import_export_text.setTextFormat(Qt.TextFormat.RichText)
            import_export_layout.addWidget(import_export_text)

            users_widget = QWidget()
            users_layout = QVBoxLayout(users_widget)
            users_text = QLabel("""
<h3>Gestión de Usuarios</h3>

<p><b>Para ver usuarios existentes:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Listar Usuarios</b>.</li>
  <li>Se mostrará una tabla con todos los usuarios en la base de datos.</li>
</ol>

<p><b>Para crear un nuevo usuario:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Crear Usuario</b>.</li>
  <li>Complete la información del usuario (nombre, email, contraseña).</li>
  <li>Seleccione el rol del usuario (admin, readWrite, readOnly).</li>
  <li>Haga clic en <b>Crear Usuario</b> para guardarlo.</li>
</ol>

<p><b>Para buscar usuarios:</b></p>
<ol>
  <li>Utilice el menú <b>Administración > Buscar Usuario</b>.</li>
  <li>Seleccione el tipo de búsqueda (Por ID, Por Nombre, Por Email).</li>
  <li>Introduzca el texto de búsqueda.</li>
  <li>Haga clic en <b>Buscar</b> para encontrar usuarios que coincidan.</li>
</ol>

<p><b>Para modificar un usuario:</b></p>
<ol>
  <li>Primero localice el usuario mediante la lista o búsqueda.</li>
  <li>Seleccione el usuario y haga clic en <b>Editar Seleccionado</b>.</li>
  <li>Modifique los campos necesarios.</li>
  <li>Haga clic en <b>Guardar Cambios</b> para actualizar la información.</li>
</ol>
""")
            users_text.setWordWrap(True)
            users_text.setTextFormat(Qt.TextFormat.RichText)
            users_layout.addWidget(users_text)

            integrity_widget = QWidget()
            integrity_layout = QVBoxLayout(integrity_widget)
            integrity_text = QLabel("""
<h3>Verificación de Integridad</h3>

<p><b>Para verificar la integridad de la base de datos:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Verificar Integridad</b>.</li>
  <li>La aplicación verificará la validez de todas las colecciones.</li>
  <li>Se mostrará un informe con los resultados de la verificación.</li>
</ol>

<p><b>Para editar los campos de una colección:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Editar Estructura de Campos</b>.</li>
  <li>Seleccione la colección que desea modificar.</li>
  <li>Modifique, añada o elimine campos según sea necesario.</li>
  <li>Especifique si los campos son requeridos o de solo lectura.</li>
  <li>Haga clic en <b>Guardar Cambios</b> para aplicar las modificaciones.</li>
</ol>

<p><b>Para gestionar índices:</b></p>
<ol>
  <li>Utilice el menú <b>Herramientas > Gestionar Índices</b>.</li>
  <li>Seleccione la colección para gestionar sus índices.</li>
  <li>Cree, modifique o elimine índices según sea necesario.</li>
</ol>

<p>La verificación regular de la integridad ayuda a mantener la salud de su base de datos y prevenir problemas de datos.</p>
""")
            integrity_text.setWordWrap(True)
            integrity_text.setTextFormat(Qt.TextFormat.RichText)
            integrity_layout.addWidget(integrity_text)

            tab_widget.addTab(intro_widget, "Introducción")
            tab_widget.addTab(connect_widget, "Conexión")
            tab_widget.addTab(collections_widget, "Colecciones")
            tab_widget.addTab(queries_widget, "Consultas")
            tab_widget.addTab(import_export_widget, "Importación/Exportación")
            tab_widget.addTab(users_widget, "Usuarios")
            tab_widget.addTab(integrity_widget, "Integridad")

            layout.addWidget(tab_widget)

            nav_layout = QHBoxLayout()
            prev_button = QPushButton("Anterior")
            prev_button.setIcon(QIcon.fromTheme("go-previous"))
            prev_button.clicked.connect(lambda: tab_widget.setCurrentIndex(max(0, tab_widget.currentIndex() - 1)))

            next_button = QPushButton("Siguiente")
            next_button.setIcon(QIcon.fromTheme("go-next"))
            next_button.clicked.connect(lambda: tab_widget.setCurrentIndex(min(tab_widget.count() - 1, tab_widget.currentIndex() + 1)))

            close_button = QPushButton("Cerrar")
            close_button.clicked.connect(dialog.accept)

            nav_layout.addWidget(prev_button)
            nav_layout.addWidget(next_button)
            nav_layout.addStretch()
            nav_layout.addWidget(close_button)
            layout.addLayout(nav_layout)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar el tutorial: {str(e)}")
