#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MongoDB Database Manager - GUI Application Entry Point
A cross-platform GUI application for MongoDB database management.
"""

import sys
import os
from dotenv import load_dotenv
import traceback
from PyQt6.QtWidgets import QApplication, QStyleFactory, QMessageBox
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QPalette, QColor

from gui.main_window import MainWindow

def set_dark_fusion_style(app):
    """Apply a customized dark fusion style to the application."""
    app.setStyle("Fusion")
    
    # Set up a dark palette
    dark_palette = QPalette()
    
    # Base colors
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(127, 127, 127)
    text_color = QColor(210, 210, 210)
    highlight_color = QColor(42, 130, 218)
    
    # Configure color roles
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 18))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, text_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Text, text_color)
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    
    # Disabled colors
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_color)
    
    # Apply palette
    app.setPalette(dark_palette)
    
    # Additional styling with stylesheet
    app.setStyleSheet("""
        QToolTip { 
            color: #ffffff; 
            background-color: #2a2a2a; 
            border: 1px solid #76797c;
            padding: 5px;
        }
        }
        
        QTabWidget::pane {
            border: 1px solid #76797c;
            padding: 5px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected, QTabBar::tab:hover {
            background-color: #3daee9;
        }
        
        QPushButton {
            background-color: #31363b;
            border: 1px solid #76797c;
            color: #ffffff;
            padding: 5px 10px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #3daee9;
            border: 1px solid #3daee9;
        }
        
        QPushButton:pressed {
            background-color: #2980b9;
        }
        
        QLineEdit, QTextEdit {
            background-color: #1d1d1d;
            border: 1px solid #3daee9;
            color: #ffffff;
            padding: 5px;
            border-radius: 2px;
        }
    """)

def set_light_style(app):
    """Apply a clean, modern light style to the application."""
    app.setStyle("Fusion")
    
    # Set up a light palette
    light_palette = QPalette()
    
    # Base colors
    base_color = QColor(240, 240, 240)
    text_color = QColor(40, 40, 40)
    highlight_color = QColor(0, 120, 215)
    
    # Apply palette colors
    light_palette.setColor(QPalette.ColorRole.Window, base_color)
    light_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    light_palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    light_palette.setColor(QPalette.ColorRole.AlternateBase, base_color)
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    light_palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    light_palette.setColor(QPalette.ColorRole.Text, text_color)
    light_palette.setColor(QPalette.ColorRole.Button, base_color)
    light_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    light_palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
    light_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    light_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    # Apply the palette
    app.setPalette(light_palette)
    
    # Additional styling with stylesheet
    app.setStyleSheet("""
        QToolTip { 
            color: #000000; 
            background-color: #f0f0f0; 
            border: 1px solid #aaaaaa;
            padding: 5px;
        }
        
        QTabWidget::pane {
            border: 1px solid #cccccc;
            padding: 5px;
        }
        
        QTabBar::tab {
            background-color: #e0e0e0;
            color: #404040;
            padding: 8px 15px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected, QTabBar::tab:hover {
            background-color: #0078d7;
            color: #ffffff;
        }
        
        QPushButton {
            background-color: #e6e6e6;
            border: 1px solid #cccccc;
            color: #404040;
            padding: 5px 10px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #0078d7;
            border: 1px solid #0078d7;
            color: #ffffff;
        }
        
        QPushButton:pressed {
            background-color: #00589d;
        }
        
        QLineEdit, QTextEdit {
            background-color: #ffffff;
            border: 1px solid #aaaaaa;
            color: #404040;
            padding: 5px;
            border-radius: 2px;
        }
    """)

def manejar_senales():
    """Configura manejadores de señales para cierre controlado"""
    import signal
    
    def manejador_senal(signum, frame):
        print(f"\n--- Señal de terminación recibida ({signum}) ---")
        # Asegurar que existe una instancia de QApplication antes de intentar cerrarla
        if QApplication.instance():
            print("Iniciando cierre ordenado de la aplicación...")
            QApplication.instance().quit()
    
    # Configurar manejadores para SIGINT (Ctrl+C) y SIGTERM
    signal.signal(signal.SIGINT, manejador_senal)
    signal.signal(signal.SIGTERM, manejador_senal)

def limpiar_recursos(client=None):
    """Limpia todos los recursos antes de salir de la aplicación"""
    print("\n--- Limpiando recursos de la aplicación ---")
    
    try:
        # Cerrar conexión a MongoDB si existe
        if client:
            print("Cerrando conexión a MongoDB...")
            client.close()
            print("Conexión a MongoDB cerrada correctamente")
    except Exception as e:
        print(f"Error al limpiar recursos: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Punto de entrada principal de la aplicación."""
    # En PyQt6, el escalado para pantallas de alta resolución se maneja automáticamente
    # No es necesario establecer atributos DPI explícitamente
    
    print("\n=== Iniciando Gestor de Base de Datos MongoDB ===")
    
    # Cargar variables de entorno desde el archivo .env
    print("Cargando variables de entorno desde archivo .env")
    load_dotenv()
    # Verificar que MONGODB_URI está disponible
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("Advertencia: Variable de entorno MONGODB_URI no encontrada en el archivo .env")
    else:
        masked_uri = f"{mongodb_uri[:10]}...{mongodb_uri[-10:]}" if len(mongodb_uri) > 20 else "***enmascarada***"
        print(f"MONGODB_URI encontrada en variables de entorno (enmascarada): {masked_uri}")
    
    # Crear la aplicación
    print("Creando aplicación PyQt")
    app = QApplication(sys.argv)
    app.setApplicationName("Gestor de Base de Datos MongoDB")
    app.setApplicationVersion("1.0.0")
    
    # Mostrar estilos disponibles para depuración
    print("Estilos disponibles:", QStyleFactory.keys())
    
    # Aplicar el estilo moderno (usar oscuro o claro según preferencia)
    print("Aplicando estilo claro a la aplicación")
    set_light_style(app)  # Estilo claro moderno
    # set_dark_fusion_style(app)  # Estilo oscuro moderno
    
    # Crear la ventana principal
    print("Creando ventana principal de la aplicación")
    main_window = MainWindow()
    # Mostrar la ventana principal y asegurarse de que sea visible
    main_window.show()
    main_window.record_activity("app_opened")
    print("Ventana principal mostrada")
    app.processEvents()  # Procesar eventos pendientes
    
    # Asegurar que la ventana está activa
    main_window.activateWindow()
    main_window.raise_()
    
    # Intentar conectar a la base de datos si hay una cadena de conexión disponible
    if mongodb_uri:
        print("Cadena de conexión encontrada, programando conexión automática")
        
        # Programar intento de conexión con un retraso mayor
        def conexion_retrasada():
            try:
                main_window.initialize_connection()
            except Exception as e:
                print(f"Error durante la conexión inicial: {e}")
                traceback.print_exc()
                
        # Usar un retraso mayor para asegurar que la UI está completamente inicializada
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, conexion_retrasada)
        print("Temporizador de conexión programado con retraso de 1000ms")
    else:
        print("No hay cadena de conexión disponible, omitiendo conexión automática")
        main_window.statusBar().showMessage("No hay cadena de conexión disponible. Use Conexión > Conectar para conectarse manualmente.")
    print("Starting application event loop")
    # Start the application event loop 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
