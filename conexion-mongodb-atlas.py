#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo para importar tablas y crear catálogos en MongoDB
Compatible con la aplicación principal de gestión de MongoDB
"""

import os
import sys
import traceback
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv  # Añadido para cargar variables de entorno
from pymongo import MongoClient  # Añadido para manejar la conexión
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QMessageBox, QProgressDialog, QComboBox,
    QTableView, QHeaderView, QCheckBox, QLineEdit, QDialog,
    QApplication, QMainWindow, QStatusBar
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QColor

class ImportadorCatalogo(QWidget):
    """Widget para importar datos de tablas y crear catálogos en MongoDB"""
    
    # Señal para notificar que se ha creado un catálogo exitosamente
    catalogo_creado = pyqtSignal(str, str)  # (nombre_coleccion, mensaje)
    
    def __init__(self, mongodb_client=None, parent=None):
        super().__init__(parent)
        self.client = mongodb_client
        self.db = None
        self.datos_importados = None
        self.encabezados = None
        self.datos_validos = None
        self.errores = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz de usuario"""
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Título
        titulo = QLabel("Importador de Catálogos")
        titulo_font = QFont()
        titulo_font.setBold(True)
        titulo_font.setPointSize(14)
        titulo.setFont(titulo_font)
        layout.addWidget(titulo)
        
        # Botón de importación
        btn_importar = QPushButton("Importar Tabla")
        btn_importar.clicked.connect(self.importar_tabla_dialogo)
        layout.addWidget(btn_importar)
        
        # Selector de base de datos
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Base de Datos:"))
        self.combo_db = QComboBox()
        self.combo_db.currentTextChanged.connect(self.actualizar_colecciones)
        db_layout.addWidget(self.combo_db)
        layout.addLayout(db_layout)
        
        # Nombre de la colección
        coleccion_layout = QHBoxLayout()
        coleccion_layout.addWidget(QLabel("Nombre de Colección:"))
        self.input_coleccion = QLineEdit()
        coleccion_layout.addWidget(self.input_coleccion)
        layout.addLayout(coleccion_layout)
        
        # Información de importación
        self.info_label = QLabel("No hay datos importados")
        layout.addWidget(self.info_label)
        
        # Botón para crear catálogo
        self.btn_crear = QPushButton("Crear Catálogo")
        self.btn_crear.clicked.connect(self.crear_catalogo)
        self.btn_crear.setEnabled(False)
        layout.addWidget(self.btn_crear)
        
        # Espacio flexible
        layout.addStretch(1)
        
        # Botón para ver errores
        self.btn_ver_errores = QPushButton("Ver Errores")
        self.btn_ver_errores.clicked.connect(self.mostrar_errores)
        self.btn_ver_errores.setEnabled(False)
        layout.addWidget(self.btn_ver_errores)
        
    def set_mongodb_client(self, client):
        """Establecer el cliente MongoDB y actualizar UI"""
        self.client = client
        self.actualizar_bases_datos()
        
    def actualizar_bases_datos(self):
        """Actualizar la lista de bases de datos disponibles"""
        if not self.client:
            self.combo_db.clear()
            return
            
        try:
            # Obtener lista de bases de datos
            db_list = self.client.list_database_names()
            
            # Actualizar el combo box
            self.combo_db.clear()
            self.combo_db.addItems(db_list)
            
        except Exception as e:
            print(f"Error al actualizar bases de datos: {e}")
            QMessageBox.warning(self, "Error", f"No se pudo obtener la lista de bases de datos: {str(e)}")
    
    def actualizar_colecciones(self, db_name):
        """Actualizar cuando cambia la base de datos seleccionada"""
        if not self.client or not db_name:
            return
            
        self.db = self.client[db_name]
        
        # Sugerir un nombre para la colección de catálogo
        self.input_coleccion.setText(f"catalogo_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    def importar_tabla_dialogo(self):
        """Mostrar diálogo para seleccionar archivo de tabla a importar"""
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de datos", "", 
            "Archivos de datos (*.csv *.xlsx *.xls);;Todos los archivos (*)"
        )
        
        if not archivo:
            return  # El usuario canceló la selección
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Importando tabla...", "Cancelar", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Importar datos
            self.encabezados, self.datos_validos, self.errores = importar_catalogo_desde_tabla(archivo)
            progress.setValue(100)
            
            # Verificar si hay errores fatales
            if self.encabezados is None:
                QMessageBox.critical(self, "Error de importación", 
                                    "\n".join(self.errores[:5]) + 
                                    ("\n..." if len(self.errores) > 5 else ""))
                return
            
            # Actualizar información
            self.datos_importados = True
            self.actualizar_info_importacion()
            
            # Habilitar/deshabilitar botones según los datos
            self.btn_crear.setEnabled(len(self.datos_validos) > 0)
            self.btn_ver_errores.setEnabled(len(self.errores) > 0)
            
            # Mostrar mensaje de éxito
            QMessageBox.information(self, "Importación Completada", 
                                   f"Se importaron {len(self.datos_validos)} registros válidos.\n"
                                   f"Se encontraron {len(self.errores)} registros con errores.")
            
        except Exception as e:
            progress.cancel()
            QMessageBox.critical(self, "Error", f"Error al importar la tabla: {str(e)}")
            traceback.print_exc()
    
    def actualizar_info_importacion(self):
        """Actualizar la etiqueta de información con el resumen de la importación"""
        if not self.datos_importados:
            self.info_label.setText("No hay datos importados")
            return
            
        info = f"<b>Datos importados:</b><br>"
        info += f"- Encabezados: {len(self.encabezados)}<br>"
        info += f"- Registros válidos: {len(self.datos_validos)}<br>"
        info += f"- Registros con errores: {len(self.errores)}"
        
        self.info_label.setText(info)
    
    def mostrar_errores(self):
        """Mostrar una ventana con los errores de importación"""
        if not self.errores or len(self.errores) == 0:
            QMessageBox.information(self, "Sin errores", "No hay errores que mostrar.")
            return
            
        # Crear diálogo para mostrar errores
        dialogo = ErroresDialog(self.errores, self)
        dialogo.exec()
    
    def crear_catalogo(self):
        """Crear un catálogo en MongoDB con los datos válidos importados"""
        if not self.client or not self.db:
            QMessageBox.warning(self, "Error", "No hay conexión a la base de datos.")
            return
            
        if not self.datos_validos or len(self.datos_validos) == 0:
            QMessageBox.warning(self, "Error", "No hay datos válidos para crear el catálogo.")
            return
            
        # Obtener nombre de la colección
        nombre_coleccion = self.input_coleccion.text().strip()
        if not nombre_coleccion:
            QMessageBox.warning(self, "Error", "Debe especificar un nombre para la colección.")
            return
            
        # Confirmar creación
        respuesta = QMessageBox.question(
            self, "Confirmar Creación", 
            f"¿Desea crear el catálogo '{nombre_coleccion}' con {len(self.datos_validos)} registros?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if respuesta != QMessageBox.StandardButton.Yes:
            return
            
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Creando catálogo...", "Cancelar", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            # Verificar si la colección ya existe
            if nombre_coleccion in self.db.list_collection_names():
                respuesta = QMessageBox.question(
                    self, "Colección existente", 
                    f"La colección '{nombre_coleccion}' ya existe. ¿Desea reemplazarla?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if respuesta != QMessageBox.StandardButton.Yes:
                    progress.cancel()
                    return
                    
                # Eliminar colección existente
                self.db.drop_collection(nombre_coleccion)
            
            # Crear colección y añadir documentos
            coleccion = self.db[nombre_coleccion]
            
            # Añadir metadatos a cada documento
            documentos = []
            timestamp = datetime.now()
            
            for i, doc in enumerate(self.datos_validos):
                # Simular progreso
                if i % 10 == 0:
                    progress.setValue(min(99, int((i / len(self.datos_validos)) * 100)))
                    QApplication.processEvents()
                
                # Añadir metadatos
                doc_con_meta = doc.copy()
                doc_con_meta['_meta'] = {
                    'created_at': timestamp,
                    'importacion_id': timestamp.strftime('%Y%m%d%H%M%S'),
                    'indice_importacion': i
                }
                documentos.append(doc_con_meta)
            
            # Insertar todos los documentos
            if documentos:
                coleccion.insert_many(documentos)
            
            # Crear índices para mejor rendimiento
            for campo in self.encabezados:
                if campo in ['Número', 'DESCRIPCION']:
                    coleccion.create_index(campo)
            
            # Completar progreso
            progress.setValue(100)
            
            # Mostrar mensaje de éxito
            QMessageBox.information(
                self, "Catálogo Creado", 
                f"Se ha creado el catálogo '{nombre_coleccion}' con {len(self.datos_validos)} registros."
            )
            
            # Emitir señal de catálogo creado
            self.catalogo_creado.emit(nombre_coleccion, f"Catálogo creado con {len(self.datos_validos)} registros")
            
        except Exception as e:
            progress.cancel()
            QMessageBox.critical(self, "Error", f"Error al crear el catálogo: {str(e)}")
            traceback.print_exc()

class ErroresDialog(QDialog):
    """Diálogo para mostrar los errores de importación"""
    
    def __init__(self, errores, parent=None):
        super().__init__(parent)
        self.errores = errores
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz de usuario"""
        self.setWindowTitle("Errores de Importación")
        self.resize(800, 600)
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Título
        titulo = QLabel(f"Se encontraron {len(self.errores)} registros con errores")
        titulo_font = QFont()
        titulo_font.setBold(True)
        titulo.setFont(titulo_font)
        layout.addWidget(titulo)
        
        # Tabla de errores
        modelo = ErroresTableModel(self.errores)
        tabla = QTableView()
        tabla.setModel(modelo)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(tabla)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_exportar = QPushButton("Exportar Errores")
        btn_exportar.clicked.connect(self.exportar_errores)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_exportar)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_cerrar)
        layout.addLayout(btn_layout)
    
    def exportar_errores(self):
        """Exportar los errores a un archivo CSV"""
        archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar errores", "", 
            "Archivos CSV (*.csv);;Todos los archivos (*)"
        )
        
        if not archivo:
            return  # El usuario canceló la selección
            
        try:
            # Crear dataframe con los errores
            datos = []
            for error in self.errores:
                datos.append({
                    'Fila': error['fila'],
                    'Errores': '; '.join(error['errores'])
                })
                
            df = pd.DataFrame(datos)
            df.to_csv(archivo, index=False, encoding='utf-8')
            
            QMessageBox.information(
                self, "Exportación Completada", 
                f"Se exportaron {len(self.errores)} registros de errores a {archivo}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar errores: {str(e)}")
            traceback.print_exc()

class ErroresTableModel(QAbstractTableModel):
    """Modelo de tabla para mostrar los errores de importación"""
    
    def __init__(self, errores, parent=None):
        super().__init__(parent)
        self.errores = errores
        self.columnas = ['Fila', 'Errores']
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.errores)
        
    def columnCount(self, parent=QModelIndex()):
        return len(self.columnas)
        
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.errores)):
            return None
            
        error = self.errores[index.row()]
        columna = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if columna == 0:
                return error['fila']
            elif columna == 1:
                return '\n'.join(error['errores'])
                
        elif role == Qt.ItemDataRole.BackgroundRole:
            # Colorear filas alternas
            if index.row() % 2 == 0:
                return QColor(240, 240, 240)
                
        return None
        
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columnas[section]
        return None

def importar_catalogo_desde_tabla(archivo_tabla):
    """
    Importa datos de una tabla (CSV, Excel, etc.) para crear un catálogo,
    extrayendo automáticamente los encabezados y filtrando datos válidos.
    
    Args:
        archivo_tabla: Ruta al archivo de tabla a importar
    
    Returns:
        tuple: (encabezados, datos_validos, errores)
    """
    try:
        # Detectar el tipo de archivo y leer los datos
        if archivo_tabla.endswith('.csv'):
            df = pd.read_csv(archivo_tabla, encoding='utf-8')
        elif archivo_tabla.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(archivo_tabla)
        else:
            return None, None, ["Formato de archivo no soportado"]
        
        # Eliminar filas completamente vacías
        df.dropna(how='all', inplace=True)
        
        # Extraer encabezados y convertir a lista de diccionarios
        encabezados = list(df.columns)
        datos = df.fillna("").to_dict('records')  # Convertir NaN a string vacío
        
        # Validar datos
        datos_validos = []
        errores = []
        
        for i, fila in enumerate(datos):
            fila_valida = True
            errores_fila = []
            
            # Crear una copia de la fila para modificar
            fila_limpia = {k: v for k, v in fila.items()}
            
            # Validar campos requeridos
            campos_requeridos = ["Número", "DESCRIPCION", "PESO en gr.", "VALOR ESTIMADO"]
            
            for campo in campos_requeridos:
                if campo in fila:
                    # Verificar si el valor está vacío (string vacío o None)
                    valor = fila[campo]
                    if valor == "" or valor is None:
                        errores_fila.append(f"El campo '{campo}' no puede estar vacío")
                        fila_valida = False
            
            # Registrar errores si los hay
            if errores_fila:
                errores.append({
                    'fila': i+2,  # +2 porque: +1 por encabezados y +1 porque i empieza en 0
                    'errores': errores_fila
                })
            
            # Si la fila es válida, añadirla a los datos válidos
            if fila_valida:
                datos_validos.append(fila_limpia)
        
        return encabezados, datos_validos, errores
        
    except Exception as e:
        import traceback
        return None, None, [f"Error al importar la tabla: {str(e)}", traceback.format_exc()]

def conectar_mongodb_desde_env():
    """
    Conecta a MongoDB Atlas utilizando la URI del archivo .env
    
    Returns:
        MongoClient o None si hay error
    """
    try:
        # Cargar variables de entorno desde .env
        load_dotenv()
        
        # Obtener la URI de MongoDB Atlas
        mongodb_uri = os.getenv('MONGODB_URI')
        
        if not mongodb_uri:
            print("Error: No se encontró la variable MONGODB_URI en el archivo .env")
            return None
            
        # Establecer conexión
        client = MongoClient(mongodb_uri)
        
        # Verificar conexión
        client.admin.command('ping')
        print("Conexión a MongoDB Atlas establecida correctamente")
        
        return client
        
    except Exception as e:
        print(f"Error al conectar con MongoDB Atlas: {e}")
        traceback.print_exc()
        return None

# Ejemplo de uso independiente
if __name__ == "__main__":
    # Esta parte sólo se ejecuta si se ejecuta este script directamente
    app = QApplication(sys.argv)
    
    # Crear una ventana principal para contener nuestro widget
    main_window = QMainWindow()
    main_window.setWindowTitle("Importador de Catálogos - MongoDB Atlas")
    
    # Intentar conectar a MongoDB Atlas
    client = conectar_mongodb_desde_env()
    
    # Crear el importador
    importador = ImportadorCatalogo(client)
    
    # Establecer como widget central
    main_window.setCentralWidget(importador)
    
    # Configurar status bar
    status_bar = QStatusBar()
    main_window.setStatusBar(status_bar)
    
    # Mostrar mensaje informativo según el estado de la conexión
    if client:
        status_bar.showMessage("Conectado a MongoDB Atlas")
    else:
        status_bar.showMessage("No se pudo conectar a MongoDB Atlas. Revise el archivo .env")
    
    # Mostrar la ventana
    main_window.resize(800, 600)
    main_window.show()
    
    # Ejecutar la aplicación
    sys.exit(app.exec())
