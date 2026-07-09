#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import json
import os
import traceback
from db_management_tool import DatabaseManager
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
class MongoDBManagerGUI:
    def __init__(self, root):
        self.root = root
        
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=5, font=('Helvetica', 10))
        style.configure('TLabel', font=('Helvetica', 10))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        
        # Variables
        self.db_manager = DatabaseManager()
        self.current_collection = None
        self.user_buttons = None  # Will be initialized in create_main_layout
        
        # Frame temporal
        self.temp_frame = ttk.Frame(self.root, padding="10")
        self.temp_frame.pack(fill=tk.BOTH, expand=True)
        
        loading_label = ttk.Label(
            self.temp_frame,
            text="Iniciando MongoDB Database Manager...",
            font=('Helvetica', 12)
        )
        loading_label.pack(expand=True)
        
        # Asegurar que la ventana principal esté lista antes de mostrar el diálogo
        self.root.update()
        self.root.after(500, self.show_connect_dialog)
    
    def show_connect_dialog(self):
        """Muestra el diálogo de conexión a MongoDB."""
        try:
            # Destruir el frame temporal
            if hasattr(self, 'temp_frame'):
                self.temp_frame.destroy()
            
            # Crear el diálogo
            dialog = tk.Toplevel(self.root)
            dialog.title("Conectar a MongoDB")
            dialog.geometry("500x400")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.focus_force()
            
            # Centrar el diálogo
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
            y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")
            
            # Frame principal
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            ttk.Label(
                main_frame,
                text="Conectar a MongoDB",
                font=('Helvetica', 12, 'bold'),
                anchor='center'
            ).pack(fill=tk.X, pady=(0, 10))
            
            # URI Frame
            uri_frame = ttk.LabelFrame(main_frame, text="Servidor", padding="5")
            uri_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Host
            host_frame = ttk.Frame(uri_frame)
            host_frame.pack(fill=tk.X, pady=2)
            ttk.Label(host_frame, text="Host:").pack(side=tk.LEFT, padx=5)
            host_var = tk.StringVar(value="cluster0.pmokh.mongodb.net")
            host_entry = ttk.Entry(host_frame, textvariable=host_var, width=40)
            host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # Authentication Frame
            auth_frame = ttk.LabelFrame(main_frame, text="Autenticación", padding="5")
            auth_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Username
            username_frame = ttk.Frame(auth_frame)
            username_frame.pack(fill=tk.X, pady=2)
            ttk.Label(username_frame, text="Usuario:").pack(side=tk.LEFT, padx=5)
            username_var = tk.StringVar(value="edfrutos")
            username_entry = ttk.Entry(username_frame, textvariable=username_var)
            username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # Password
            password_frame = ttk.Frame(auth_frame)
            password_frame.pack(fill=tk.X, pady=2)
            ttk.Label(password_frame, text="Contraseña:").pack(side=tk.LEFT, padx=5)
            password_var = tk.StringVar()
            password_entry = ttk.Entry(password_frame, textvariable=password_var, show="*")
            password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # Botón mostrar/ocultar contraseña
            toggle_btn = ttk.Button(
                password_frame, 
                text='○',
                width=3,
                command=lambda: [
                    password_entry.configure(show='' if password_entry['show'] == '*' else '*'),
                    toggle_btn.configure(text='●' if password_entry['show'] == '' else '○')
                ]
            )
            toggle_btn.pack(side=tk.RIGHT, padx=5)
            
            # Status Frame
            status_frame = ttk.LabelFrame(main_frame, text="Estado", padding="5")
            status_frame.pack(fill=tk.X, pady=5)
            
            status_label = ttk.Label(
                status_frame,
                text="Ingrese sus credenciales y presione Conectar",
                wraplength=400,
                justify=tk.LEFT,
                anchor='w'
            )
            status_label.pack(fill=tk.X, padx=5, pady=5)
            
            # Botón de conexión con estilo
            style = ttk.Style()
            style.configure('Accent.TButton', padding=5)
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=10)
            
            connect_btn = ttk.Button(
                button_frame, 
                text="Conectar",
                style='Accent.TButton'
            )
            connect_btn.pack(side=tk.RIGHT, padx=5)
            
            cancel_btn = ttk.Button(
                button_frame, 
                text="Cancelar",
                command=dialog.destroy
            )
            cancel_btn.pack(side=tk.RIGHT, padx=5)
            
            # Funciones auxiliares
            def update_status(message, is_error=False):
                status_label.configure(
                    text=message,
                    foreground='red' if is_error else 'black'
                )
                dialog.update_idletasks()
            
            def validate_input():
                host = host_var.get().strip()
                username = username_var.get().strip()
                password = password_var.get().strip()
                
                if not host:
                    update_status("Por favor, ingrese el host", True)
                    host_entry.focus()
                    return False
                
                if not username:
                    update_status("Por favor, ingrese el nombre de usuario", True)
                    username_entry.focus()
                    return False
                
                if not password:
                    update_status("Por favor, ingrese la contraseña", True)
                    password_entry.focus()
                    return False
                
                return True
            
            def do_connect():
                if not validate_input():
                    return
                
                # Obtener valores
                host = host_var.get().strip()
                username = username_var.get().strip()
                password = password_var.get().strip()
                
                # Deshabilitar controles
                for widget in [host_entry, username_entry, password_entry, toggle_btn, connect_btn, cancel_btn]:
                    widget.configure(state='disabled')
                
                update_status("Conectando...")
                
                try:
                    # Construir URI de conexión
                    # Construir URI de conexión
                    connection_uri = f"mongodb+srv://{username}:{password}@{host}?retryWrites=true&w=majority"
                    
                    # Intentar conectar
                    if self.db_manager.connect(connection_uri):
                        update_status("Conexión exitosa")
                        dialog.after(1000, lambda: [
                            dialog.destroy(),
                            self.create_main_layout()
                        ])
                    else:
                        update_status("Error: No se pudo establecer la conexión", True)
                        # Rehabilitar controles
                        for widget in [host_entry, username_entry, password_entry, toggle_btn, connect_btn, cancel_btn]:
                            widget.configure(state='normal')
                
                except Exception as e:
                    update_status(f"Error: {str(e)}", True)
                    # Rehabilitar controles
                    for widget in [host_entry, username_entry, password_entry, toggle_btn, connect_btn, cancel_btn]:
                        widget.configure(state='normal')
            
            # Configurar comando del botón de conexión
            connect_btn.configure(command=do_connect)
            
            # Configurar teclas de acceso rápido
            dialog.bind('<Return>', lambda e: do_connect())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # Enfocar el primer campo vacío
            if not host_var.get():
                host_entry.focus()
            elif not username_var.get():
                username_entry.focus()
            else:
                password_entry.focus()
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error detallado:\n{error_details}")
            messagebox.showerror(
                "Error", 
                f"Error al crear el diálogo de conexión:\n{str(e)}\n\n" +
                "Revise la consola para más detalles."
            )

    def create_main_layout(self):
        # Limpiar la ventana principal
        for widget in self.root.winfo_children():
            widget.destroy()

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)

        # Bases de datos
        db_frame = ttk.LabelFrame(left_panel, text="Bases de datos", padding="5")
        db_frame.pack(fill=tk.X, pady=(0, 10))

        db_list_frame = ttk.Frame(db_frame)
        db_list_frame.pack(fill=tk.BOTH, expand=True)

        self.db_listbox = tk.Listbox(db_list_frame, height=5)
        self.db_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        db_scrollbar = ttk.Scrollbar(db_list_frame, orient=tk.VERTICAL, command=self.db_listbox.yview)
        db_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.db_listbox.configure(yscrollcommand=db_scrollbar.set)
        self.db_listbox.bind('<<ListboxSelect>>', lambda e: self.on_database_select())

        self.db_buttons = ttk.Frame(db_frame)
        self.db_buttons.pack(fill=tk.X, pady=5)
        ttk.Button(self.db_buttons, text="Crear", command=self.create_database).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.db_buttons, text="Eliminar", command=self.drop_database).pack(side=tk.LEFT, padx=2)

        # Colecciones
        collections_frame = ttk.LabelFrame(left_panel, text="Colecciones", padding="5")
        collections_frame.pack(fill=tk.BOTH, expand=True)

        coll_list_frame = ttk.Frame(collections_frame)
        coll_list_frame.pack(fill=tk.BOTH, expand=True)

        self.coll_listbox = tk.Listbox(coll_list_frame, height=10, exportselection=False)
        self.coll_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        coll_scrollbar = ttk.Scrollbar(coll_list_frame, orient=tk.VERTICAL, command=self.coll_listbox.yview)
        coll_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.coll_listbox.configure(yscrollcommand=coll_scrollbar.set)
        self.coll_listbox.bind('<<ListboxSelect>>', self.on_collection_select)

        self.coll_buttons = ttk.Frame(collections_frame)
        self.coll_buttons.pack(fill=tk.X, pady=5)
        ttk.Button(self.coll_buttons, text="Crear", command=self.create_collection).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.coll_buttons, text="Eliminar", command=self.drop_collection).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.coll_buttons, text="Importar", command=self.import_collection).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.coll_buttons, text="Exportar", command=self.export_collection).pack(side=tk.LEFT, padx=2)

        # Panel derecho
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Barra de herramientas
        toolbar = ttk.Frame(right_panel)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # Botones de documentos
        doc_buttons = ttk.LabelFrame(toolbar, text="Documentos", padding="5")
        doc_buttons.pack(side=tk.LEFT, fill=tk.X, padx=5)
        ttk.Button(doc_buttons, text="Buscar", command=self.find_documents).pack(side=tk.LEFT, padx=2)
        ttk.Button(doc_buttons, text="Insertar", command=self.insert_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(doc_buttons, text="Estadísticas", command=self.view_stats).pack(side=tk.LEFT, padx=2)

        # Botones de usuarios
        self.user_buttons = ttk.LabelFrame(toolbar, text="Usuarios", padding="5")
        self.user_buttons.pack(side=tk.LEFT, fill=tk.X, padx=5)
        ttk.Button(self.user_buttons, text="Listar", command=self.list_users).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.user_buttons, text="Crear", command=self.create_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.user_buttons, text="Editar", command=self.edit_user).pack(side=tk.LEFT, padx=2)

        # Área de resultados
        result_frame = ttk.LabelFrame(right_panel, text="Resultados", padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.results_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Refrescar las listas y actualizar estados de botones
        self.refresh_databases()
        self.update_button_states()
    
    def on_database_select(self):
        selection = self.db_listbox.curselection()
        if selection:
            db_name = self.db_listbox.get(selection[0])
            try:
                if self.db_manager.set_database(db_name):
                    self.refresh_collections()
                    self.update_button_states()
                    self.results_text.delete(1.0, tk.END)
                    self.results_text.insert(tk.END, f"Base de datos seleccionada: {db_name}\n")
                    
                    # Mostrar permisos disponibles
                    permissions = self.db_manager.check_user_permissions()
                    self.results_text.insert(tk.END, "\nPermisos disponibles en esta base de datos:\n")
                    for perm, value in permissions.items():
                        if perm != 'error':
                            self.results_text.insert(tk.END, f"- {perm}: {'Sí' if value else 'No'}\n")
                else:
                    messagebox.showerror("Error", f"No se pudo seleccionar la base de datos {db_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al seleccionar la base de datos: {str(e)}")
                self.coll_listbox.delete(0, tk.END)
                self.current_collection = None
                self.update_button_states()
        else:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "No hay base de datos seleccionada\n")
            self.update_button_states()
    
    def on_collection_select(self, event=None):
        """Maneja la selección de una colección en la lista."""
        try:
            selection = self.coll_listbox.curselection()
            if not selection:
                self.current_collection = None
                return
                
            collection_name = self.coll_listbox.get(selection[0])
            if not collection_name:
                self.current_collection = None
                return
                
            # Verificar que la colección aún existe
            collections = self.db_manager.list_collections()
            if collection_name not in collections:
                self.refresh_collections()
                return
                
            if collection_name == self.current_collection:
                return  # No hacer nada si es la misma colección
                
            self.current_collection = collection_name
            self.results_text.delete(1.0, tk.END)
            
            # Mostrar información de la colección seleccionada
            try:
                count = self.db_manager.db[collection_name].count_documents({})
                self.results_text.insert(tk.END, f"Colección seleccionada: {collection_name}\n\nNúmero de documentos: {count}\n")
            except Exception as e:
                self.results_text.insert(tk.END, f"No se pudieron obtener las estadísticas para la colección {collection_name}")
                
        except Exception as e:
            logger.error(f"Error al seleccionar colección: {e}")
            messagebox.showerror("Error", f"Error al seleccionar la colección: {str(e)}")
            self.current_collection = None
            self.refresh_collections()
    
    def refresh_databases(self):
        """Actualiza la lista de bases de datos en la GUI."""
        # Limpiar lista actual
        self.db_listbox.delete(0, tk.END)
        
        try:
            # Obtener bases de datos
            databases = self.db_manager.list_databases()
            
            if not databases:
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "No se encontraron bases de datos\n")
                return
            
            # Mostrar bases de datos en la lista
            for db in databases:
                self.db_listbox.insert(tk.END, db)
            
            # Actualizar área de resultados
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "Conexión exitosa a MongoDB\n")
            self.results_text.insert(tk.END, f"Bases de datos disponibles: {len(databases)}\n")
            
            # Actualizar estado de botones
            self.update_button_states()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar bases de datos: {str(e)}")
            print(f"Error detallado:\n{traceback.format_exc()}")

    def update_button_states(self):
        """Actualiza el estado de los botones según los permisos del usuario."""
        try:
            # Verificar si el usuario está conectado
            has_connection = hasattr(self.db_manager, 'client') and self.db_manager.client is not None
            has_db = self.db_manager.db is not None if has_connection else False
            has_collection = self.current_collection is not None if has_db else False

            if not has_connection:
                return

            # Database buttons
            for button in self.db_btn_frame.winfo_children():
                if isinstance(button, ttk.Button):
                    if button['text'] == "Crear":
                        button['state'] = 'normal'
                    elif button['text'] == "Eliminar":
                        button['state'] = 'normal' if has_db else 'disabled'

            # Collection buttons
            for button in self.coll_btn_frame.winfo_children():
                if isinstance(button, ttk.Button):
                    if button['text'] == "Crear Colección":
                        button['state'] = 'normal' if has_db else 'disabled'
                    elif button['text'] == "Eliminar Colección":
                        button['state'] = 'normal' if has_collection else 'disabled'

            # Operation buttons
            self.insert_btn['state'] = 'normal' if has_collection else 'disabled'
            self.find_btn['state'] = 'normal' if has_collection else 'disabled'
            self.export_btn['state'] = 'normal' if has_collection else 'disabled'
            self.import_btn['state'] = 'normal' if has_db else 'disabled'
            self.stats_btn['state'] = 'normal' if has_collection else 'disabled'
            self.users_btn['state'] = 'normal'

        except Exception as e:
            logger.error(f"Error al actualizar estado de botones: {e}")
            
    def refresh_collections(self):
        """Actualiza la lista de colecciones en la GUI."""
        try:
            if self.db_manager.db is None:
                self.coll_listbox.delete(0, tk.END)
                return
                
            collections = self.db_manager.list_collections()
            self.coll_listbox.delete(0, tk.END)
            
            if collections:
                for collection in collections:
                    self.coll_listbox.insert(tk.END, collection)
            else:
                self.current_collection = None
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "No hay colecciones en esta base de datos")
            
            # Actualizar estados de botones después de refrescar colecciones
            self.update_button_states()
                
        except Exception as e:
            logger.error(f"Error al actualizar colecciones: {e}")
            messagebox.showerror("Error", f"Error al obtener las colecciones: {str(e)}")
            self.coll_listbox.delete(0, tk.END)
    
    def view_stats(self):
        """Muestra estadísticas de la colección seleccionada."""
        try:
            if self.current_collection is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una colección primero")
                return
                
            # Obtener estadísticas básicas
            count = self.db_manager.db[self.current_collection].count_documents({})
            
            # Mostrar estadísticas
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Estadísticas de la colección: {self.current_collection}\n\n")
            self.results_text.insert(tk.END, f"Número total de documentos: {count}\n")
            
            # Obtener un documento de muestra si existe
            sample = self.db_manager.db[self.current_collection].find_one()
            if sample:
                self.results_text.insert(tk.END, "\nEstructura de documento de muestra:\n")
                self.results_text.insert(tk.END, json.dumps(sample, indent=2, ensure_ascii=False))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener estadísticas: {str(e)}")
    
    def insert_document(self):
        try:
            if self.current_collection is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una colección primero")
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title("Insertar Documento")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Frame superior para plantillas y validación
            top_frame = ttk.Frame(main_frame)
            top_frame.pack(fill=tk.X, pady=(0, 5))
            
            # Plantillas
            templates = {
                "Documento vacío": "{}",
                "Ejemplo básico": '''{
    "nombre": "ejemplo",
    "número": 42,
    "lista": [1, 2, 3],
    "objeto": {
        "clave": "valor"
    }
}'''
            }
            
            ttk.Label(top_frame, text="Plantilla:").pack(side=tk.LEFT, padx=(0, 5))
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(top_frame, textvariable=template_var, values=list(templates.keys()), state="readonly")
            template_combo.pack(side=tk.LEFT)
            template_combo.set("Documento vacío")
            
            # Frame para el documento
            doc_frame = ttk.LabelFrame(main_frame, text="Documento JSON", padding="5")
            doc_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            doc_text = scrolledtext.ScrolledText(doc_frame, height=15, font=("Consolas", 10))
            doc_text.pack(fill=tk.BOTH, expand=True)
            doc_text.insert(tk.END, "{}")
            
            # Frame para mensajes de validación
            validation_frame = ttk.Frame(main_frame)
            validation_frame.pack(fill=tk.X, pady=5)
            validation_label = ttk.Label(validation_frame, text="")
            validation_label.pack(fill=tk.X)
            
            def update_validation(event=None):
                try:
                    content = doc_text.get(1.0, tk.END).strip()
                    if not content:
                        validation_label.configure(
                            text="El documento está vacío",
                            foreground="red"
                        )
                        return False
                    
                    # Intentar parsear el JSON
                    document = json.loads(content)
                    
                    # Validaciones adicionales
                    if not isinstance(document, dict):
                        validation_label.configure(
                            text="Error: El documento debe ser un objeto JSON",
                            foreground="red"
                        )
                        return False
                    
                    # Verificar tamaño
                    json_size = len(content.encode('utf-8'))
                    if json_size > 16777216:  # 16MB límite de MongoDB
                        validation_label.configure(
                            text="Error: El documento excede el límite de 16MB",
                            foreground="red"
                        )
                        return False
                    
                    validation_label.configure(
                        text=f"JSON válido - Tamaño: {json_size/1024:.1f}KB",
                        foreground="green"
                    )
                    return True
                    
                except json.JSONDecodeError as e:
                    line_no = e.lineno
                    col_no = e.colno
                    validation_label.configure(
                        text=f"Error de sintaxis en línea {line_no}, columna {col_no}: {str(e)}",
                        foreground="red"
                    )
                    return False
            
            def on_template_change(*args):
                selected = template_var.get()
                if selected in templates:
                    doc_text.delete(1.0, tk.END)
                    doc_text.insert(tk.END, templates[selected])
                    update_validation()
            
            template_var.trace('w', on_template_change)
            
            # Vincular la validación a cambios en el texto
            doc_text.bind('<KeyRelease>', lambda e: dialog.after(500, update_validation))
            
            def format_json():
                try:
                    content = doc_text.get(1.0, tk.END).strip()
                    if content:
                        parsed = json.loads(content)
                        formatted = json.dumps(parsed, indent=4, ensure_ascii=False)
                        doc_text.delete(1.0, tk.END)
                        doc_text.insert(tk.END, formatted)
                        update_validation()
                except Exception as e:
                    pass  # Si hay error, no formatear
            
            def do_insert():
                if not update_validation():
                    return
                
                try:
                    document = json.loads(doc_text.get(1.0, tk.END).strip())
                    result = self.db_manager.insert_document(self.current_collection, document)
                    
                    if result:
                        messagebox.showinfo("Éxito", "Documento insertado correctamente")
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "No se pudo insertar el documento")
                except Exception as e:
                    messagebox.showerror("Error", f"Error al insertar el documento: {str(e)}")
            
            # Barra de herramientas
            toolbar = ttk.Frame(main_frame)
            toolbar.pack(fill=tk.X, pady=5)
            
            ttk.Button(toolbar, text="Formatear JSON", command=format_json).pack(side=tk.LEFT, padx=5)
            
            # Botones principales
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=5)
            ttk.Button(btn_frame, text="Insertar", command=do_insert).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            # Configurar teclas de acceso rápido
            dialog.bind('<Control-Return>', lambda e: do_insert())
            dialog.bind('<Control-f>', lambda e: format_json())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al abrir el diálogo de inserción: {str(e)}")
    
    def export_collection(self):
        try:
            if self.current_collection is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una colección primero")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Exportar colección"
            )
            
            if filename:
                if self.db_manager.export_collection(self.current_collection, filename):
                    messagebox.showinfo("Éxito", f"Colección exportada a {filename}")
                else:
                    messagebox.showerror("Error", "No se pudo exportar la colección")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar colección: {str(e)}")
    
    def list_users(self):
        """Lista los usuarios de la base de datos."""
        try:
            self.results_text.delete(1.0, tk.END)
            users = self.db_manager.list_users()
            
            # Si es un mensaje de error o aviso
            if isinstance(users, str):
                self.results_text.insert(tk.END, f"{users}\n")
                return
            
            # Si no hay usuarios
            if not users:
                self.results_text.insert(tk.END, "No se encontraron usuarios.\n")
                return
            
            # Mostrar la lista de usuarios
            self.results_text.insert(tk.END, "Lista de usuarios:\n\n")
            for user in users:
                username = user.get('user', 'N/A')
                db_name = user.get('db', 'N/A')
                roles = user.get('roles', [])
                
                self.results_text.insert(tk.END, f"Usuario: {username}\n")
                self.results_text.insert(tk.END, f"Base de datos: {db_name}\n")
                
                if roles:
                    self.results_text.insert(tk.END, "Roles:\n")
                    for role in roles:
                        role_name = role.get('role', 'N/A')
                        role_db = role.get('db', 'N/A')
                        self.results_text.insert(tk.END, f"- {role_name} en {role_db}\n")
                
                self.results_text.insert(tk.END, "\n")
        
        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            error_msg = f"Error al listar usuarios: {str(e)}"
            self.results_text.insert(tk.END, error_msg)
            logger.error(error_msg)

    def create_user(self):
        try:
            if self.db_manager.db is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title("Crear Usuario")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Campos de entrada
            ttk.Label(main_frame, text="Nombre de usuario:").pack(pady=5)
            username_var = tk.StringVar()
            username_entry = ttk.Entry(main_frame, textvariable=username_var)
            username_entry.pack(fill=tk.X, pady=5)
            
            ttk.Label(main_frame, text="Contraseña:").pack(pady=5)
            password_var = tk.StringVar()
            password_entry = ttk.Entry(main_frame, textvariable=password_var, show="*")
            password_entry.pack(fill=tk.X, pady=5)
            
            # Frame para roles
            roles_frame = ttk.LabelFrame(main_frame, text="Roles", padding="5")
            roles_frame.pack(fill=tk.X, pady=10)
            
            # Lista de roles disponibles
            available_roles = [
                "read",
                "readWrite",
                "dbAdmin",
                "userAdmin",
                "clusterAdmin",
                "readAnyDatabase",
                "readWriteAnyDatabase",
                "userAdminAnyDatabase",
                "dbAdminAnyDatabase"
            ]
            
            # Variables para los checkboxes
            role_vars = {}
            
            # Crear checkboxes para cada rol
            for i, role in enumerate(available_roles):
                role_vars[role] = tk.BooleanVar()
                ttk.Checkbutton(
                    roles_frame,
                    text=role,
                    variable=role_vars[role]
                ).pack(anchor=tk.W)
            
            def do_create():
                username = username_var.get().strip()
                password = password_var.get().strip()
                
                if not username or not password:
                    messagebox.showwarning("Advertencia", "Por favor, complete todos los campos")
                    return
                
                selected_roles = [role for role, var in role_vars.items() if var.get()]
                
                if not selected_roles:
                    messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un rol")
                    return
                
                try:
                    if self.db_manager.create_user(username, password, selected_roles):
                        messagebox.showinfo("Éxito", "Usuario creado correctamente")
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "No se pudo crear el usuario")
                except Exception as e:
                    messagebox.showerror("Error", f"Error al crear usuario: {str(e)}")
            
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Crear", command=do_create).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            # Configurar teclas de acceso rápido
            dialog.bind('<Return>', lambda e: do_create())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # Enfocar el primer campo
            username_entry.focus()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear el diálogo de usuario: {str(e)}")

    def create_database(self):
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Crear Base de Datos")
            dialog.geometry("400x150")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text="Nombre de la base de datos:").pack(pady=5)
            name_var = tk.StringVar()
            name_entry = ttk.Entry(main_frame, textvariable=name_var)
            name_entry.pack(fill=tk.X, pady=5)
            
            def do_create():
                db_name = name_var.get().strip()
                if db_name:
                    if self.db_manager.create_database(db_name):
                        messagebox.showinfo("Éxito", "Base de datos creada correctamente")
                        self.refresh_databases()
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "No se pudo crear la base de datos")
                else:
                    messagebox.showwarning("Advertencia", "Por favor, ingrese un nombre para la base de datos")
            
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Crear", command=do_create).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            # Configurar teclas de acceso rápido
            dialog.bind('<Return>', lambda e: do_create())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # Enfocar el campo de entrada
            name_entry.focus()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear base de datos: {str(e)}")

    def find_documents(self):
        if self.db_manager.db is None:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
            return
        if self.current_collection is None:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una colección primero")
            return
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Buscar Documentos")
            dialog.geometry("600x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Campo de filtro
            ttk.Label(main_frame, text="Filtro (JSON):").pack(pady=5)
            filter_text = tk.Text(main_frame, height=5)
            filter_text.insert("1.0", "{}")
            filter_text.pack(fill=tk.X, pady=5)

            def do_find():
                try:
                    filter_json = json.loads(filter_text.get("1.0", tk.END).strip())
                    documents = self.db_manager.find_documents(self.current_collection, filter_json)
                    if documents:
                        self.results_text.delete(1.0, tk.END)
                        for doc in documents:
                            self.results_text.insert(tk.END, json.dumps(doc, indent=4, ensure_ascii=False) + "\n\n")
                        dialog.destroy()
                    else:
                        messagebox.showinfo("Información", "No se encontraron documentos")
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "El filtro no es un JSON válido")
                except Exception as e:
                    messagebox.showerror("Error", f"Error al buscar documentos: {str(e)}")

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Buscar", command=do_find).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

            dialog.bind('<Return>', lambda e: do_find())
            dialog.bind('<Escape>', lambda e: dialog.destroy())

            filter_text.focus()

        except Exception as e:
            messagebox.showerror("Error", f"Error al crear diálogo de búsqueda: {str(e)}")

    def edit_user(self):
        try:
            if self.db_manager.db is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
                return

            # Obtener lista de usuarios
            users = self.db_manager.list_users()
            if not users:
                messagebox.showinfo("Información", "No hay usuarios para editar")
                return

            # Diálogo para seleccionar usuario
            dialog = tk.Toplevel(self.root)
            dialog.title("Editar Usuario")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Lista de usuarios
            ttk.Label(main_frame, text="Seleccione un usuario:").pack(pady=5)
            user_listbox = tk.Listbox(main_frame, height=5)
            user_listbox.pack(fill=tk.X, pady=5)

            for user in users:
                user_listbox.insert(tk.END, user['user'])

            # Frame para roles
            roles_frame = ttk.LabelFrame(main_frame, text="Roles", padding="5")
            roles_frame.pack(fill=tk.X, pady=10)

            # Lista de roles disponibles
            available_roles = [
                "read",
                "readWrite",
                "dbAdmin",
                "userAdmin",
                "clusterAdmin",
                "readAnyDatabase",
                "readWriteAnyDatabase",
                "userAdminAnyDatabase",
                "dbAdminAnyDatabase"
            ]

            # Variables para los checkboxes
            role_vars = {}

            # Crear checkboxes para cada rol
            for role in available_roles:
                role_vars[role] = tk.BooleanVar()
                ttk.Checkbutton(
                    roles_frame,
                    text=role,
                    variable=role_vars[role]
                ).pack(anchor=tk.W)

            def on_user_select(*args):
                selection = user_listbox.curselection()
                if selection:
                    username = user_listbox.get(selection[0])
                    user_info = next((u for u in users if u['user'] == username), None)
                    if user_info:
                        # Resetear todos los roles
                        for var in role_vars.values():
                            var.set(False)
                        # Marcar los roles actuales del usuario
                        for role in user_info.get('roles', []):
                            role_name = role.get('role')
                            if role_name in role_vars:
                                role_vars[role_name].set(True)

            user_listbox.bind('<<ListboxSelect>>', on_user_select)

            def do_edit():
                selection = user_listbox.curselection()
                if not selection:
                    messagebox.showwarning("Advertencia", "Por favor, seleccione un usuario")
                    return

                username = user_listbox.get(selection[0])
                selected_roles = [role for role, var in role_vars.items() if var.get()]

                if not selected_roles:
                    messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un rol")
                    return

                try:
                    if self.db_manager.update_user(username, selected_roles):
                        messagebox.showinfo("Éxito", "Usuario actualizado correctamente")
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "No se pudo actualizar el usuario")
                except Exception as e:
                    messagebox.showerror("Error", f"Error al actualizar usuario: {str(e)}")

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Actualizar", command=do_edit).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

            # Configurar teclas de acceso rápido
            dialog.bind('<Return>', lambda e: do_edit())
            dialog.bind('<Escape>', lambda e: dialog.destroy())

        except Exception as e:
            messagebox.showerror("Error", f"Error al crear el diálogo de edición: {str(e)}")

    def drop_collection(self):
        """Elimina la colección seleccionada."""
        if self.current_collection is None:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una colección primero")
            return
            
        if messagebox.askyesno("Confirmar", f"¿Está seguro de eliminar la colección '{self.current_collection}'?"):
            try:
                if self.db_manager.drop_collection(self.current_collection):
                    messagebox.showinfo("Éxito", "Colección eliminada correctamente")
                    self.refresh_collections()
                else:
                    messagebox.showerror("Error", "No se pudo eliminar la colección")
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar colección: {str(e)}")
    
    def import_collection(self):
        """Importa datos a una colección desde un archivo JSON."""
        try:
            if self.db_manager.db is None:
                messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
                return
                
            filename = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Importar colección"
            )
            
            if not filename:
                return
                
            collection_name = os.path.splitext(os.path.basename(filename))[0]
            
            # Preguntar si desea usar un nombre diferente
            new_name = messagebox.askquestion(
                "Nombre de colección",
                f"¿Desea usar '{collection_name}' como nombre de la colección?"
            )
            
            if new_name == 'no':
                collection_name = simpledialog.askstring(
                    "Nombre de colección",
                    "Ingrese el nombre para la nueva colección:"
                )
                if not collection_name:
                    return
            
            if self.db_manager.import_collection(filename, collection_name):
                messagebox.showinfo("Éxito", f"Datos importados correctamente a la colección {collection_name}")
                self.refresh_collections()
            else:
                messagebox.showerror("Error", "No se pudieron importar los datos")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al importar colección: {str(e)}")
    
    def drop_database(self):
        if self.db_manager.db is None:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
            return
        if messagebox.askyesno("Confirmar", f"¿Está seguro de eliminar la base de datos '{self.db_manager.db.name}'?"):
            try:
                if self.db_manager.drop_database():
                    messagebox.showinfo("Éxito", "Base de datos eliminada correctamente")
                    self.refresh_databases()
                else:
                    messagebox.showerror("Error", "No se pudo eliminar la base de datos")
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar base de datos: {str(e)}")
    
    def create_collection(self):
        if self.db_manager.db is None:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una base de datos primero")
            return
        
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Crear Colección")
            dialog.geometry("400x150")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text="Nombre de la colección:").pack(pady=5)
            name_var = tk.StringVar()
            name_entry = ttk.Entry(main_frame, textvariable=name_var)
            name_entry.pack(fill=tk.X, pady=5)
            
            def do_create():
                coll_name = name_var.get().strip()
                if coll_name:
                    if self.db_manager.create_collection(coll_name):
                        messagebox.showinfo("Éxito", "Colección creada correctamente")
                        self.refresh_collections()
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "No se pudo crear la colección")
                else:
                    messagebox.showwarning("Advertencia", "Por favor, ingrese un nombre para la colección")
            
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Crear", command=do_create).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            # Configurar teclas de acceso rápido
            dialog.bind('<Return>', lambda e: do_create())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # Enfocar el campo de entrada
            name_entry.focus()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear la colección: {str(e)}")
    
    def create_main_layout(self):
        # Limpiar la ventana principal
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(
            main_frame,
            text="MongoDB Database Manager",
            style='Header.TLabel'
        )
        title_label.pack(fill=tk.X, pady=(0, 10))
        
        # Frame izquierdo (navegación)
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Lista de bases de datos
        db_frame = ttk.LabelFrame(left_frame, text="Bases de Datos", padding="5")
        db_frame.pack(fill=tk.BOTH, expand=True)
        
        self.db_listbox = tk.Listbox(
            db_frame,
            width=30,
            selectmode=tk.SINGLE,
            exportselection=False
        )
        self.db_listbox.pack(fill=tk.BOTH, expand=True)
        self.db_listbox.bind('<<ListboxSelect>>', lambda e: self.on_database_select())
        
        # Botones de base de datos
        # Botones de base de datos
        self.db_btn_frame = ttk.Frame(left_frame)
        self.db_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            self.db_btn_frame,
            text="Crear",
            command=self.create_database
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            self.db_btn_frame,
            text="Eliminar",
            command=self.drop_database,
            state=tk.DISABLED
        ).pack(side=tk.LEFT, padx=2)
        # Lista de colecciones
        coll_frame = ttk.LabelFrame(left_frame, text="Colecciones", padding="5")
        coll_frame.pack(fill=tk.BOTH, expand=True)
        
        self.coll_listbox = tk.Listbox(
            coll_frame,
            width=30,
            selectmode=tk.SINGLE,
            exportselection=False
        )
        self.coll_listbox.pack(fill=tk.BOTH, expand=True)
        self.coll_listbox.bind('<<ListboxSelect>>', self.on_collection_select)
        
        # Botones de colección
        self.coll_btn_frame = ttk.Frame(left_frame)
        self.coll_btn_frame.pack(fill=tk.X, pady=5)
        
        self.create_coll_btn = ttk.Button(
            self.coll_btn_frame,
            text="Crear Colección",
            command=self.create_collection,
            state=tk.DISABLED
        )
        self.create_coll_btn.pack(side=tk.LEFT, padx=2)
        
        self.drop_coll_btn = ttk.Button(
            self.coll_btn_frame,
            text="Eliminar Colección",
            command=self.drop_collection,
            state=tk.DISABLED
        )
        self.drop_coll_btn.pack(side=tk.LEFT, padx=2)
        
        # Frame derecho (operaciones)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Barra de herramientas
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        self.insert_btn = ttk.Button(
            toolbar,
            text="Insertar",
            command=self.insert_document,
            state=tk.DISABLED
        )
        self.insert_btn.pack(side=tk.LEFT, padx=2)
        
        self.find_btn = ttk.Button(
            toolbar,
            text="Buscar",
            command=self.find_documents,
            state=tk.DISABLED
        )
        self.find_btn.pack(side=tk.LEFT, padx=2)
        
        self.export_btn = ttk.Button(
            toolbar,
            text="Exportar",
            command=self.export_collection,
            state=tk.DISABLED
        )
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        self.import_btn = ttk.Button(
            toolbar,
            text="Importar",
            command=self.import_collection,
            state=tk.DISABLED
        )
        self.import_btn.pack(side=tk.LEFT, padx=2)
        
        self.stats_btn = ttk.Button(
            toolbar,
            text="Estadísticas",
            command=self.view_stats,
            state=tk.DISABLED
        )
        self.stats_btn.pack(side=tk.LEFT, padx=2)
        
        # Botón de usuarios
        self.users_btn = ttk.Button(
            toolbar,
            text="Usuarios",
            command=self.list_users,
            state=tk.DISABLED
        )
        self.users_btn.pack(side=tk.RIGHT, padx=2)
        
        # Área de resultados
        results_frame = ttk.LabelFrame(right_frame, text="Resultados", padding="5")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            wrap=tk.WORD,
            width=50,
            height=20
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Update button states and refresh databases
        self.update_button_states()
        self.refresh_databases()
def main():
    # Crear y configurar la ventana principal
    root = tk.Tk()
    root.title("MongoDB Database Manager")
    root.geometry("1000x600")
    root.configure(bg="#f0f0f0")
    
    # Centrar la ventana en la pantalla
    window_width = 1000
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Crear la aplicación
    app = MongoDBManagerGUI(root)
    
    # Iniciar el bucle principal
    root.mainloop()

if __name__ == "__main__":
    main()
