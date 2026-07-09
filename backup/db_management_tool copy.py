#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongoDB Database Management Tool

Esta herramienta permite realizar operaciones comunes de administración en bases de datos
MongoDB, tanto locales como en Atlas, incluyendo:
- Conexión a bases de datos
- Listado y gestión de colecciones
- Consulta y manipulación de documentos (CRUD)
- Exportación e importación de datos (JSON y CSV)
- Gestión de índices, renombrado, respaldo y eliminación de colecciones
- Gestión básica de usuarios (búsqueda, actualización y eliminación)

Autor: ED Frutos / Revisión y depuración por Eugenio
"""

import argparse
import csv
import json
import logging
import os
import sys
import datetime
import getpass
from bson import json_util, ObjectId
from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure,
    OperationFailure,
    DuplicateKeyError,
    CollectionInvalid,
    ServerSelectionTimeoutError,
    PyMongoError
)
from dotenv import load_dotenv
load_dotenv()

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("db_management_tool")

def get_mongodb_uri():
    """
    Obtiene la URI de MongoDB desde la variable de entorno 'MONGODB_URI'.
    Si se detecta una duplicación en la cadena, se elimina la parte redundante.
    """
    uri = os.environ.get("MONGODB_URI", "").strip()
    # Si se detecta una concatenación accidental, se toma la primera parte
    if "MONGODB_URI=" in uri:
        uri = uri.split("MONGODB_URI=")[0]
    return uri

# Funciones utilitarias

def serialize_to_json(data, format_type='pretty'):
    try:
        if format_type == 'compact':
            return json_util.dumps(data, separators=(',', ':'))
        elif format_type == 'pretty':
            return json_util.dumps(data, indent=2)
        elif format_type == 'detailed':
            return json_util.dumps(data, indent=2, sort_keys=True, default=str)
        else:
            return json_util.dumps(data, indent=2)
    except Exception as e:
        logger.error(f"Error al serializar a JSON: {e}")
        return str(data)

def parse_json_query(query_str):
    if not query_str or query_str.strip() == '':
        return {}
    try:
        return json.loads(query_str)
    except json.JSONDecodeError:
        try:
            return json_util.loads(query_str)
        except Exception as e:
            logger.error(f"Error al parsear la consulta: {e}")
            raise ValueError(f"Formato de consulta inválido: {e}")

def validate_objectid(id_str):
    try:
        return ObjectId(id_str)
    except Exception:
        return None

# Clase principal para la gestión de la base de datos

class DatabaseManager:
    def __init__(self, connection_uri=None, database_name=None, debug=False):
        self.connection_uri = connection_uri
        self.database_name = database_name
        self.client = None
        self.db = None
        self.is_admin = False
        self.debug = debug
        if self.debug:
            logger.setLevel(logging.DEBUG)

    def verify_collection_integrity(self, collection_name):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            # Verificar si la colección existe
            if collection_name not in self.db.list_collection_names():
                logger.error(f"La colección {collection_name} no existe")
                return False
            
            # Verificar índices
            indexes = list(self.db[collection_name].list_indexes())
            logger.info(f"Índices encontrados: {len(indexes)}")
            
            # Verificar documentos
            doc_count = self.db[collection_name].count_documents({})
            logger.info(f"Documentos en la colección: {doc_count}")
            
            # Verificar validación de esquema si existe
            collection_info = self.db.validate_collection(collection_name)
            logger.info(f"Validación de colección: {collection_info['valid']}")
            
            return True
        except Exception as e:
            logger.error(f"Error al verificar la integridad: {e}")
            return False

    def list_user_databases(self, username):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return []
        try:
            # Obtener todas las bases de datos
            all_dbs = self.client.list_database_names()
            user_dbs = []
            
            # Verificar permisos del usuario en cada base de datos
            for db_name in all_dbs:
                try:
                    db = self.client[db_name]
                    users = db.command('usersInfo', {'user': username})
                    if users.get('users'):
                        user_dbs.append(db_name)
                except Exception:
                    continue
            
            return user_dbs
        except Exception as e:
            logger.error(f"Error al listar bases de datos del usuario: {e}")
            return []

    def cleanup_user_databases(self, username):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return False
        try:
            user_dbs = self.list_user_databases(username)
            for db_name in user_dbs:
                db = self.client[db_name]
                # Verificar y eliminar colecciones vacías
                for collection_name in db.list_collection_names():
                    collection = db[collection_name]
                    if collection.count_documents({}) == 0:
                        collection.drop()
                        logger.info(f"Colección vacía eliminada: {db_name}.{collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error al depurar bases de datos del usuario: {e}")
            return False

    def connect(self, connection_uri=None, admin_username=None, admin_password=None):
        # Si se proporciona una URI de conexión, usarla
        if connection_uri:
            self.connection_uri = connection_uri
        # Si no hay URI, intentar construirla con las credenciales proporcionadas
        elif admin_username and admin_password:
            self.connection_uri = f"mongodb+srv://{admin_username}:{admin_password}@cluster0.pmokh.mongodb.net/"
        # Si no hay URI ni credenciales, intentar obtener la URI desde las variables de entorno
        else:
            self.connection_uri = os.getenv('MONGODB_URI')
            
        if not self.connection_uri:
            logger.error("No se proporcionó una URI de conexión válida")
            return False
            
        print(f"MONGODB_URI: {self.connection_uri}")
        
        # Configuración del cliente MongoDB
        client_kwargs = {
            'serverSelectionTimeoutMS': 5000,
            'connectTimeoutMS': 10000,
            'retryWrites': True
        }
        
        # Crear el cliente de MongoDB
        try:
            self.client = MongoClient(self.connection_uri, **client_kwargs)
            # Verificar la conexión
            self.client.admin.command('ping')
        except Exception as e:
            logger.error(f"Error al conectar a MongoDB: {e}")
            self.client = None
            return False
        
        # Verificar roles del usuario actual
        try:
            admin_db = self.client.get_database('admin')
            user_info = admin_db.command('usersInfo')
            
            # Obtener el nombre de usuario actual de la URI de conexión
            parsed_uri = parse_uri(self.connection_uri)
            current_username = parsed_uri['username']
            
            # Buscar el usuario actual en la lista de usuarios
            for user in user_info.get('users', []):
                if user['user'] == current_username:
                    # Verificar si tiene rol de administrador
                    for role in user.get('roles', []):
                        if role['role'] in ['root', 'userAdmin', 'userAdminAnyDatabase']:
                            self.is_admin = True
                            break
                    break
            
            logger.info(f"Conexión exitosa como {'administrador' if self.is_admin else 'usuario normal'}")
            return True
            
        except Exception as e:
            logger.error(f"Error al verificar roles: {e}")
            self.is_admin = False
            return True  
            # Intentar verificar permisos mediante operaciones
            try:
                # Intentar listar bases de datos (requiere permisos de lectura)
                self.client.list_database_names()
                # Si llegamos aquí, al menos tenemos permisos de lectura
                logger.info("Conexión exitosa a MongoDB con permisos básicos")
                self.is_admin = True
                return True
            except Exception as e:
                logger.warning(f"No se tienen permisos suficientes: {e}")
                self.is_admin = False
                return False

    def set_database(self, database_name):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return False
        try:
            self.db = self.client[database_name]
            self.database_name = database_name
            logger.info(f"Base de datos establecida: {database_name}")
            return True
        except Exception as e:
            logger.error(f"Error al establecer la base de datos: {e}")
            return False

    def list_databases(self):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return []
        try:
            return self.client.list_database_names()
        except Exception as e:
            logger.error(f"Error al listar bases de datos: {e}")
            return []
        
    def select_database(self, db_name):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return False
            
        try:
            self.db = self.client[db_name]
            # Intentar una operación simple para verificar acceso
            self.db.list_collection_names()
            logger.info(f"Base de datos '{db_name}' seleccionada")
            return True
        except Exception as e:
            logger.error(f"Error al seleccionar la base de datos: {e}")
            self.db = None
            return False

    def list_collections(self):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            return self.db.list_collection_names()
        except Exception as e:
            logger.error(f"Error al listar colecciones: {e}")
            return []

    def get_collection_stats(self, collection_name):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            return self.db.command("collstats", collection_name)
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de la colección: {e}")
            return None
            
    def get_collection_stats_formatted(self, collection_name):
        stats = self.get_collection_stats(collection_name)
        if stats:
            formatted_stats = [
                f"Collection: {collection_name}",
                f"Size: {stats.get('size', 0)} bytes",
                f"Count: {stats.get('count', 0)} documents",
                f"Average document size: {stats.get('avgObjSize', 0)} bytes",
                f"Storage size: {stats.get('storageSize', 0)} bytes",
                f"Indexes: {len(stats.get('indexSizes', {}))}"
            ]
            return "\n".join(formatted_stats)
        return None
            
    def find_documents(self, collection_name, query={}):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            collection = self.db[collection_name]
            return list(collection.find(query))
        except Exception as e:
            logger.error(f"Error al buscar documentos: {e}")
            return []
            return None
            
    def find_one_document(self, collection_name, query):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            collection = self.db[collection_name]
            return collection.find_one(query)
        except Exception as e:
            logger.error(f"Error al buscar documento: {e}")
            return None
            
    def insert_document(self, collection_name, document):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            collection = self.db[collection_name]
            result = collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error al insertar documento: {e}")
            return None
            
    def update_document(self, collection_name, query, update):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            collection = self.db[collection_name]
            result = collection.update_one(query, update)
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error al actualizar documento: {e}")
            return False
            
    def delete_document(self, collection_name, query):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            collection = self.db[collection_name]
            result = collection.delete_one(query)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error al eliminar documento: {e}")
            raise
            
    def drop_database(self, database_name):
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            raise ConnectionError("No hay conexión activa a MongoDB")
            
        try:
            self.client.drop_database(database_name)
            logger.info(f"Base de datos {database_name} eliminada")
            if self.db and self.db.name == database_name:
                self.db = None
            return True
        except Exception as e:
            logger.error(f"Error al eliminar la base de datos: {e}")
            raise
            
    def list_users(self):
        try:
            if self.client is None:
                logger.error("No hay conexión a MongoDB")
                return None
                
            if not self.is_admin:
                logger.error("Se requieren permisos de administrador para listar usuarios")
                return None
            
            # Obtener la lista de usuarios
            admin_db = self.client.get_database('admin')
            users = admin_db.command('usersInfo')
            
            # Formatear la información de usuarios
            formatted_users = []
            for user in users.get('users', []):
                roles = [f"{role['role']}@{role['db']}" for role in user.get('roles', [])]
                formatted_user = {
                    'user': user['user'],
                    'roles': roles,
                    'mechanisms': user.get('mechanisms', []),
                    'db': user.get('db', 'admin')
                }
                formatted_users.append(formatted_user)
            
            logger.info(f"Se encontraron {len(formatted_users)} usuarios")
            return formatted_users
            
        except Exception as e:
            logger.error(f"Error al listar usuarios: {str(e)}")
            return None
            logger.error(f"Error al listar usuarios: {e}")
            return None
            
    def get_user_by_id(self, user_id):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            user = self.db.command('usersInfo', {'_id': user_id})['users']
            return user[0] if user else None
        except Exception as e:
            if 'Unauthorized' in str(e):
                logger.error("No tiene permisos para gestionar usuarios. Se requieren privilegios de administrador.")
            else:
                logger.error(f"Error al buscar usuario por ID: {e}")
            return None
            
    def get_user_by_name(self, username):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            user = self.db.command('usersInfo', {'user': username})['users']
            return user[0] if user else None
        except Exception as e:
            if 'Unauthorized' in str(e):
                logger.error("No tiene permisos para gestionar usuarios. Se requieren privilegios de administrador.")
            else:
                logger.error(f"Error al buscar usuario: {e}")
            return None
            
    def create_user(self, username, password, roles=None):
        try:
            if self.client is None:
                logger.error("No hay conexión a MongoDB")
                return False
                
            if not self.is_admin:
                logger.error("Se requieren permisos de administrador para crear usuarios")
                return False
            
            # Validar el nombre de usuario
            if not username or not isinstance(username, str):
                logger.error("Nombre de usuario inválido")
                return False
                
            # Validar la contraseña
            if not password or not isinstance(password, str):
                logger.error("Contraseña inválida")
                return False
                
            # Validar roles
            if roles is None:
                roles = [{'role': 'readWrite', 'db': 'admin'}]
            elif not isinstance(roles, list):
                logger.error("Los roles deben ser una lista")
                return False
                
            # Verificar si el usuario ya existe
            admin_db = self.client.get_database('admin')
            existing_users = admin_db.command('usersInfo')
            for user in existing_users.get('users', []):
                if user['user'] == username:
                    logger.error(f"El usuario {username} ya existe")
                    return False
                
            # Crear el usuario
            admin_db.command(
                'createUser',
                username,
                pwd=password,
                roles=roles
            )
            
            logger.info(f"Usuario {username} creado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al crear usuario: {str(e)}")
            return False

    def update_user(self, username, password=None, roles=None):
        try:
            if self.client is None:
                logger.error("No hay conexión a MongoDB")
                return False
                
            if not self.is_admin:
                logger.error("Se requieren permisos de administrador para actualizar usuarios")
                return False
            
            # Validar el nombre de usuario
            if not username or not isinstance(username, str):
                logger.error("Nombre de usuario inválido")
                return False
            
            # Verificar que el usuario exista
            admin_db = self.client.get_database('admin')
            existing_users = admin_db.command('usersInfo')
            user_exists = False
            for user in existing_users.get('users', []):
                if user['user'] == username:
                    user_exists = True
                    break
            
            if not user_exists:
                logger.error(f"El usuario {username} no existe")
                return False
            
            # Preparar comando de actualización
            update_cmd = {}
            
            # Validar y agregar contraseña si se proporciona
            if password is not None:
                if not isinstance(password, str) or not password:
                    logger.error("Contraseña inválida")
                    return False
                update_cmd['pwd'] = password
            
            # Validar y agregar roles si se proporcionan
            if roles is not None:
                if not isinstance(roles, list):
                    logger.error("Los roles deben ser una lista")
                    return False
                update_cmd['roles'] = roles
            
            # Actualizar el usuario si hay cambios
            if update_cmd:
                admin_db.command('updateUser', username, **update_cmd)
                logger.info(f"Usuario {username} actualizado exitosamente")
                return True
            else:
                logger.warning("No se especificaron cambios para actualizar")
                return False
            
        except Exception as e:
            error_msg = str(e)
            if 'Unauthorized' in error_msg:
                logger.error("No tiene permisos para gestionar usuarios")
            else:
                logger.error(f"Error al actualizar usuario: {error_msg}")
            return False

    def delete_user(self, username):
        try:
            if self.client is None:
                logger.error("No hay conexión a MongoDB")
                return False
                
            if not self.is_admin:
                logger.error("Se requieren permisos de administrador para eliminar usuarios")
                return False
            
            # Validar el nombre de usuario
            if not username or not isinstance(username, str):
                logger.error("Nombre de usuario inválido")
                return False
            
            # Verificar que el usuario exista
            admin_db = self.client.get_database('admin')
            existing_users = admin_db.command('usersInfo')
            user_exists = False
            for user in existing_users.get('users', []):
                if user['user'] == username:
                    user_exists = True
                    break
            
            if not user_exists:
                logger.error(f"El usuario {username} no existe")
                return False
            
            # Eliminar el usuario
            admin_db.command('dropUser', username)
            logger.info(f"Usuario {username} eliminado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar usuario: {str(e)}")
            return False

    def export_collection(self, collection_name, filename):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            collection = self.db[collection_name]
            documents = list(collection.find({}))
            
            # Convertir ObjectId a string para serialización JSON
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            # Asegurar que el nombre del archivo termine en .json
            if not filename.endswith('.json'):
                filename += '.json'
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Colección exportada a {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error al exportar la colección: {e}")
            return False
            
    def import_collection(self, collection_name, filename):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
            
        try:
            # Verificar que el archivo existe
            if not os.path.exists(filename):
                logger.error(f"El archivo {filename} no existe")
                return False
                
            # Leer el archivo JSON
            with open(filename, 'r', encoding='utf-8') as f:
                documents = json.load(f)
                
            if not isinstance(documents, list):
                logger.error("El archivo no contiene un array de documentos")
                return False
                
            collection = self.db[collection_name]
            
            # Insertar documentos
            for doc in documents:
                # Convertir _id de string a ObjectId si existe
                if '_id' in doc and isinstance(doc['_id'], str):
                    try:
                        doc['_id'] = ObjectId(doc['_id'])
                    except:
                        # Si no es un ObjectId válido, eliminar el _id
                        del doc['_id']
                        
                try:
                    collection.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Error al insertar documento: {e}")
                    continue
                    
            logger.info(f"Datos importados a la colección {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al importar datos: {e}")
            return False

    def get_collection_stats_formatted(self, collection_name):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            stats = self.db.command("collstats", collection_name)
            if stats:
                # Formatear las estadísticas para mejor legibilidad
                formatted_stats = {
                    "Nombre": stats.get("ns", "").split(".")[-1],
                    "Tamaño": f"{stats.get('size', 0) / 1024 / 1024:.2f} MB",
                    "Documentos": stats.get("count", 0),
                    "Tamaño promedio": f"{stats.get('avgObjSize', 0) / 1024:.2f} KB",
                    "Índices": len(stats.get("indexSizes", {})),
                    "Tamaño índices": f"{sum(stats.get('indexSizes', {}).values()) / 1024 / 1024:.2f} MB"
                }
                return formatted_stats
            return None
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return None

    def create_collection(self, collection_name, options=None):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            if not options:
                options = {}
            self.db.create_collection(collection_name, **options)
            logger.info(f"Colección creada: {collection_name}")
            return True
        except CollectionInvalid as e:
            logger.error(f"La colección ya existe: {e}")
            return False
        except Exception as e:
            logger.error(f"Error al crear la colección: {e}")
            return False

    def drop_collection(self, collection_name):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            if collection_name in self.db.list_collection_names():
                self.db.drop_collection(collection_name)
                logger.info(f"Colección {collection_name} eliminada")
                return True
            else:
                logger.error(f"La colección {collection_name} no existe")
                return False
        except Exception as e:
            logger.error(f"Error al eliminar colección: {e}")
            return False

    def rename_collection(self, old_name, new_name):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            self.db[old_name].rename(new_name)
            logger.info(f"Colección renombrada de {old_name} a {new_name}")
            return True
        except Exception as e:
            logger.error(f"Error al renombrar la colección: {e}")
            return False

    def backup_collection(self, collection_name):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{collection_name}_backup_{timestamp}"
        try:
            docs = list(self.db[collection_name].find({}))
            if docs:
                self.db.create_collection(backup_name)
                self.db[backup_name].insert_many(docs)
                logger.info(f"Copia de seguridad creada: {backup_name}")
                return backup_name
            else:
                logger.warning(f"La colección {collection_name} está vacía")
                return None
        except Exception as e:
            logger.error(f"Error al crear copia de seguridad: {e}")
            return None

    def create_index(self, collection_name, fields, index_options=None):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            if not index_options:
                index_options = {}
            index_name = self.db[collection_name].create_index(fields, **index_options)
            logger.info(f"Índice creado: {index_name} en {collection_name}")
            return index_name
        except Exception as e:
            logger.error(f"Error al crear índice: {e}")
            return None

    def list_indexes(self, collection_name):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            return list(self.db[collection_name].list_indexes())
        except Exception as e:
            logger.error(f"Error al listar índices: {e}")
            return []

    def drop_index(self, collection_name, index_name):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            self.db[collection_name].drop_index(index_name)
            logger.info(f"Índice eliminado: {index_name} en {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error al eliminar índice: {e}")
            return False

    # Operaciones CRUD

    def find_documents(self, collection_name, query=None, projection=None, limit=0, sort=None):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            query = query or {}
            cursor = self.db[collection_name].find(query, projection)
            if sort:
                cursor = cursor.sort(sort)
            if limit > 0:
                cursor = cursor.limit(limit)
            result = list(cursor)
            if self.debug:
                logger.debug(f"Documentos encontrados: {len(result)} en {collection_name}")
            return result
        except Exception as e:
            logger.error(f"Error al buscar documentos: {e}")
            return []

    def find_one_document(self, collection_name, query, projection=None):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            return self.db[collection_name].find_one(query, projection)
        except Exception as e:
            logger.error(f"Error al buscar documento: {e}")
            return None

    def insert_document(self, collection_name, document):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            result = self.db[collection_name].insert_one(document)
            if result.inserted_id:
                logger.info(f"Documento insertado con ID: {result.inserted_id}")
                return result.inserted_id
            return None
        except DuplicateKeyError:
            logger.error("Error: Documento duplicado")
            return None
        except Exception as e:
            logger.error(f"Error al insertar documento: {e}")
            return None

    def update_document(self, collection_name, query, update, upsert=False):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            result = self.db[collection_name].update_one(query, update, upsert=upsert)
            if result.modified_count > 0 or (upsert and result.upserted_id):
                logger.info(f"Documento actualizado: {result.modified_count} modificado(s)")
                return True
            logger.warning("No se encontró el documento para actualizar")
            return False
        except Exception as e:
            logger.error(f"Error al actualizar documento: {e}")
            return False

    def delete_document(self, collection_name, query):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            result = self.db[collection_name].delete_one(query)
            if result.deleted_count > 0:
                logger.info(f"Documento eliminado: {result.deleted_count} eliminado(s)")
                return True
            logger.warning("No se encontró el documento para eliminar")
            return False
        except Exception as e:
            logger.error(f"Error al eliminar documento: {e}")
            return False

    # Función para gestión de usuarios (suponiendo que se almacenen en la colección "users")
    def get_user_by_id(self, user_id):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            # Primero intentamos convertir a ObjectId
            oid = validate_objectid(user_id)
            if oid:
                user = self.find_one_document("users", {"_id": oid})
                if user:
                    return user
            
            # Si no funciona, intentamos buscar por el ID como string
            return self.find_one_document("users", {"_id": user_id})
        except Exception as e:
            logger.error(f"Error al buscar usuario por ID: {e}")
            return None

    # Exportación de colección

    def export_collection(self, collection_name, output_file, format_type='json', query=None, fields=None, batch_size=1000, show_progress=True):
        if not self.db:
            logger.error("No hay base de datos seleccionada")
            return (False, 0)
        try:
            collection = self.db[collection_name]
            query = query or {}
            total_docs = collection.count_documents(query)
            if total_docs == 0:
                logger.warning(f"No se encontraron documentos en {collection_name}")
                return (False, 0)
            pbar = tqdm(total=total_docs, desc=f"Exportando {collection_name}", unit="doc") if show_progress and tqdm else None

            if format_type.lower() == 'json':
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('[\n')
                    doc_count = 0
                    for doc in collection.find(query):
                        json_str = json_util.dumps(doc)
                        doc_count += 1
                        if doc_count < total_docs:
                            f.write(json_str + ',\n')
                        else:
                            f.write(json_str + '\n')
                        if pbar:
                            pbar.update(1)
                    f.write(']\n')
                if pbar:
                    pbar.close()
                logger.info(f"Exportados {doc_count} documentos a {output_file} en formato JSON")
                return (True, doc_count)
            elif format_type.lower() == 'csv':
                docs = list(collection.find(query))
                if not docs:
                    logger.warning("No hay documentos para exportar")
                    return (False, 0)
                if not fields:
                    fields = list(docs[0].keys())
                    if '_id' in fields:
                        fields.remove('_id')
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    doc_count = 0
                    for doc in docs:
                        row = {}
                        for field in fields:
                            value = doc.get(field, "")
                            if isinstance(value, ObjectId):
                                row[field] = str(value)
                            elif isinstance(value, datetime.datetime):
                                row[field] = value.isoformat()
                            else:
                                row[field] = value
                        writer.writerow(row)
                        doc_count += 1
                        if pbar:
                            pbar.update(1)
                if pbar:
                    pbar.close()
                logger.info(f"Exportados {doc_count} documentos a {output_file} en formato CSV")
                return (True, doc_count)
            else:
                logger.error(f"Formato de exportación no soportado: {format_type}")
                return (False, 0)
        except Exception as e:
            logger.error(f"Error al exportar colección: {e}")
            if pbar:
                pbar.close()
            return (False, 0)

    # Importación de colección

    def import_collection(self, collection_name, input_file, format_type='json', duplicate_handling='skip', validate=True, batch_size=1000, show_progress=True):
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return (False, {})
        stats = {"processed": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        try:
            if not os.path.exists(input_file):
                logger.error(f"Archivo no encontrado: {input_file}")
                return (False, stats)
            data = []
            if format_type.lower() == 'json':
                with open(input_file, 'r', encoding='utf-8') as f:
                    data = json_util.loads(f.read())
                if not isinstance(data, list):
                    data = [data]
            elif format_type.lower() == 'csv':
                with open(input_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        doc = {}
                        for key, value in row.items():
                            if value.isdigit():
                                doc[key] = int(value)
                            else:
                                try:
                                    doc[key] = float(value)
                                except ValueError:
                                    if value.lower() in ['true', 'yes', 'verdadero', 'sí']:
                                        doc[key] = True
                                    elif value.lower() in ['false', 'no', 'falso']:
                                        doc[key] = False
                                    else:
                                        doc[key] = value
                        data.append(doc)
            else:
                logger.error(f"Formato no soportado: {format_type}")
                return (False, stats)
            total_docs = len(data)
            if total_docs == 0:
                logger.warning("No hay datos para importar")
                return (True, stats)
            pbar = tqdm(total=total_docs, desc=f"Importando a {collection_name}", unit="doc") if show_progress and tqdm else None
            collection = self.db[collection_name]
            for doc in data:
                stats["processed"] += 1
                try:
                    if "_id" in doc:
                        existing = collection.find_one({"_id": doc["_id"]})
                        if existing:
                            if duplicate_handling == 'skip':
                                stats["skipped"] += 1
                            elif duplicate_handling == 'replace':
                                collection.replace_one({"_id": doc["_id"]}, doc)
                                stats["updated"] += 1
                            elif duplicate_handling == 'merge':
                                merged = existing.copy()
                                merged.update(doc)
                                collection.replace_one({"_id": doc["_id"]}, merged)
                                stats["updated"] += 1
                        else:
                            collection.insert_one(doc)
                            stats["inserted"] += 1
                    else:
                        collection.insert_one(doc)
                        stats["inserted"] += 1
                except Exception as e:
                    logger.error(f"Error al procesar documento: {e}")
                    stats["errors"] += 1
                if pbar:
                    pbar.update(1)
            if pbar:
                pbar.close()
            return (True, stats)
        except Exception as e:
            logger.error(f"Error en la importación: {e}")
            if pbar:
                pbar.close()
            return (False, stats)

# Función para seleccionar la base de datos

def select_database(db_manager):
    databases = db_manager.list_databases()
    if not databases:
        print("No se encontraron bases de datos.")
        return
    print("\nBases de datos disponibles:")
    for i, db in enumerate(databases, 1):
        print(f"{i}. {db}")
    seleccion = input("Seleccione el número de la base de datos: ")
    try:
        index = int(seleccion) - 1
        if 0 <= index < len(databases):
            selected_db = databases[index]
            if db_manager.set_database(selected_db):
                print(f"Base de datos seleccionada: {selected_db}")
            else:
                print("Error al seleccionar la base de datos.")
        else:
            print("Selección fuera de rango.")
    except ValueError:
        print("Entrada no válida.")

# Menú principal

def display_menu():
    print("\n" + "=" * 50)
    print("HERRAMIENTA DE GESTIÓN DE BASES DE DATOS MONGODB")
    print("=" * 50)
    print("1. Listar bases de datos")
    print("2. Listar colecciones")
    print("3. Buscar documentos")
    print("4. Exportar colección")
    print("5. Importar colección")
    print("6. Eliminar colección")
    print("7. Verificar integridad")
    print("8. Crear índices")
    print("9. Estadísticas")
    print("10. Gestión de usuarios")
    print("11. Listar bases de datos por usuario")
    print("12. Depurar bases de datos de usuario")
    print("13. Seleccionar base de datos")
    print("0. Salir")
    print("=" * 50)

def handle_choice(choice, db_manager):
    if not db_manager:
        print("Error: No hay conexión a la base de datos.")
        return
    try:
        if choice == "1":
            databases = db_manager.list_databases()
            print("\nBases de datos disponibles:")
            for db in databases:
                print(f"- {db}")
        elif choice == "2":
            collections = db_manager.list_collections()
            print("\nColecciones en la base de datos actual:")
            for collection in collections:
                print(f"- {collection}")
        elif choice == "3":
            collection = input("Nombre de la colección: ")
            query_str = input("Consulta (JSON, vacío para todos): ")
            query = parse_json_query(query_str)
            documents = db_manager.find_documents(collection, query)
            print("\nDocumentos encontrados:")
        elif choice == "4":
            collections = db_manager.list_collections()
            if collections:
                print("\nColecciones disponibles:")
                for collection in collections:
                    print(f"- {collection}")
            else:
                print("No se encontraron colecciones o no hay base de datos seleccionada.")
                
        elif choice == "5":
            if db_manager.db is None:
                print("Debe seleccionar una base de datos primero.")
                return True
                
            collections = db_manager.list_collections()
            if not collections:
                print("No hay colecciones disponibles.")
                return True
                
            print("\nColecciones disponibles:")
            for i, collection in enumerate(collections, 1):
                print(f"{i}. {collection}")
                
            try:
                idx = int(input("\nSeleccione el número de la colección: "))
                if 1 <= idx <= len(collections):
                    collection_name = collections[idx - 1]
                    handle_collection_operations(db_manager, collection_name)
                else:
                    print("Número de colección no válido.")
            except ValueError:
                print("Debe ingresar un número válido.")
                
        elif choice == "6":
            handle_user_management(db_manager)
            
        else:
            print("Opción no válida.")
            
    except Exception as e:
        logger.error(f"Error en el menú principal: {e}")
        print(f"Error: {e}")
        
    return True

def handle_export_import(db_manager, operation):
    collection = input("Nombre de la colección: ")
    format_type = input("Formato (json/csv): ").lower()
    if format_type not in ['json', 'csv']:
        print("Formato no soportado. Use 'json' o 'csv'.")
        return
    file_path = input(f"Ruta del archivo para {operation}: ")
    if operation == "exportar":
        query_str = input("Consulta para filtrar (JSON, vacío para todos): ")
        try:
            query = parse_json_query(query_str)
        except Exception as e:
            print(f"Error en la consulta: {e}")
            return
        success, count = db_manager.export_collection(collection_name, file_path, format_type, query)
        if success:
            print(f"Exportados {count} documentos a {file_path}")
        else:
            print("Error durante la exportación.")
    elif operation == "importar":
        duplicate_strategy = input("Manejo de duplicados (skip/replace/merge): ").lower()
        if duplicate_strategy not in ['skip', 'replace', 'merge']:
            duplicate_strategy = 'skip'
        success, stats = db_manager.import_collection(collection_name, file_path, format_type, duplicate_strategy)
        if success:
            print(f"Importación completada. Estadísticas: {stats}")
        else:
            print("Error durante la importación.")

def handle_user_management(db_manager):
    while True:
        print("\n--- GESTIÓN DE USUARIOS ---")
        print("1. Listar todos los usuarios")
        print("2. Buscar usuario por ID")
        print("3. Buscar usuario por nombre")
        print("4. Crear usuario")
        print("5. Editar usuario")
        print("6. Eliminar usuario")
        print("0. Volver al menú principal")
        choice = input("Seleccione una opción: ")
        
        try:
            if choice == "0":
                break
                
            elif choice == "1":
                users = db_manager.find_documents("users", {})
                if users:
                    print("\nUsuarios registrados:")
                    for i, user in enumerate(users, 1):
                        print(f"{i}. ID: {user.get('_id')} - Nombre: {user.get('name', 'N/A')} - Email: {user.get('email', 'N/A')} - Rol: {user.get('role', 'user')}")
                else:
                    print("No se encontraron usuarios.")
                    
            elif choice == "2":
                user_id = input("ID del usuario: ").strip()
                if not user_id:
                    print("Debe proporcionar un ID de usuario.")
                    continue
                    
                user = db_manager.get_user_by_id(user_id)
                if user:
                    print("\nInformación del usuario:")
                    print(serialize_to_json(user))
                else:
                    print("Usuario no encontrado.")
                    
            elif choice == "3":
                name = input("Nombre del usuario: ").strip()
                if not name:
                    print("Debe proporcionar un nombre de usuario.")
                    continue
                    
                users = db_manager.find_documents("users", {"name": {"$regex": name, "$options": "i"}})
                if users:
                    print("\nUsuarios encontrados:")
                    for i, user in enumerate(users, 1):
                        print(f"{i}. ID: {user.get('_id')} - Nombre: {user.get('name', 'N/A')} - Email: {user.get('email', 'N/A')} - Rol: {user.get('role', 'user')}")
                else:
                    print("No se encontraron usuarios.")
                    
            elif choice == "4":
                print("\n--- Crear nuevo usuario ---")
                name = input("Nombre: ").strip()
                email = input("Email: ").strip()
                role = input("Rol (admin/user): ").lower().strip()
                
                if not name or not email:
                    print("Nombre y email son obligatorios.")
                    continue
                    
                if role not in ['admin', 'user']:
                    role = 'user'
                
                new_user = {
                    "name": name,
                    "email": email,
                    "role": role,
                    "created_at": datetime.datetime.utcnow()
                }
                
                user_id = db_manager.insert_document("users", new_user)
                if user_id:
                    print(f"\nUsuario creado exitosamente con ID: {user_id}")
                else:
                    print("Error al crear el usuario.")
                    
            elif choice == "5":
                user_id = input("ID del usuario a editar: ").strip()
                if not user_id:
                    print("Debe proporcionar un ID de usuario.")
                    continue
                
                user = db_manager.get_user_by_id(user_id)
                if not user:
                    print("Usuario no encontrado.")
                    continue
                    
                print("\nDatos actuales del usuario:")
                print(serialize_to_json(user))
                
                print("\nIngrese los nuevos datos (deje en blanco para mantener el valor actual):")
                name = input("Nuevo nombre: ").strip()
                email = input("Nuevo email: ").strip()
                role = input("Nuevo rol (admin/user): ").lower().strip()
                
                update = {"$set": {}}
                if name:
                    update["$set"]["name"] = name
                if email:
                    update["$set"]["email"] = email
                if role in ['admin', 'user']:
                    update["$set"]["role"] = role
                
                if update["$set"]:
                    if db_manager.update_document("users", {"_id": user.get("_id")}, update):
                        print("Usuario actualizado correctamente.")
                    else:
                        print("Error al actualizar el usuario.")
                else:
                    print("No se realizaron cambios.")
                    
            elif choice == "6":
                user_id = input("ID del usuario a eliminar: ").strip()
                if not user_id:
                    print("Debe proporcionar un ID de usuario.")
                    continue
                    
                user = db_manager.get_user_by_id(user_id)
                if not user:
                    print("Usuario no encontrado.")
                    continue
                    
                confirm = input(f"\n¿Está seguro de eliminar el usuario {user.get('name')}? (s/n): ")
                if confirm.lower() == 's':
                    if db_manager.delete_document("users", {"_id": user.get("_id")}):
                        print("Usuario eliminado correctamente.")
                    else:
                        print("Error al eliminar el usuario.")
                else:
                    print("Operación cancelada.")
                    
            else:
                print("Opción no válida.")
                
        except Exception as e:
            logger.error(f"Error en la gestión de usuarios: {e}")
            print(f"Error: {e}")
        
        pause()
        
def serialize_to_json(data):
    return json.dumps(data, default=str, indent=2, ensure_ascii=False)

def validate_objectid(id_str):
    try:
        return ObjectId(id_str)
    except:
        return None

print("MONGODB_URI:", os.environ.get("MONGODB_URI"))

def handle_collection_operations(db_manager, collection_name):
    while True:
        print(f"\n=== OPERACIONES EN COLECCIÓN: {collection_name} ===")
        print("1. Ver estadísticas")
        print("2. Buscar documentos")
        print("3. Insertar documento")
        print("4. Editar documento")
        print("5. Eliminar documento")
        print("6. Exportar colección")
        print("7. Importar datos")
        print("0. Volver al menú principal")
        
        choice = input("\nSeleccione una opción: ")
        
        try:
            if choice == "0":
                break
                
            elif choice == "1":
                stats = db_manager.get_collection_stats(collection_name)
                if stats:
                    print("\nEstadísticas de la colección:")
                    print(serialize_to_json(stats))
                else:
                    print("No se pudieron obtener las estadísticas.")
                    
            elif choice == "2":
                print("\n--- BUSCAR DOCUMENTOS ---")
                print("1. Ver todos los documentos")
                print("2. Buscar por campo")
                search_choice = input("Seleccione una opción: ")
                
                if search_choice == "1":
                    docs = db_manager.find_documents(collection_name, {})
                    if docs:
                        print("\nDocumentos encontrados:")
                        for i, doc in enumerate(docs, 1):
                            print(f"\nDocumento {i}:")
                            print(serialize_to_json(doc))
                    else:
                        print("No se encontraron documentos.")
                        
                elif search_choice == "2":
                    field = input("Nombre del campo: ").strip()
                    value = input("Valor a buscar: ").strip()
                    if field and value:
                        docs = db_manager.find_documents(collection_name, {field: {"$regex": value, "$options": "i"}})
                        if docs:
                            print("\nDocumentos encontrados:")
                            for i, doc in enumerate(docs, 1):
                                print(f"\nDocumento {i}:")
                                print(serialize_to_json(doc))
                        else:
                            print("No se encontraron documentos.")
                    else:
                        print("Campo y valor son requeridos.")
                        
            elif choice == "3":
                print("\n--- INSERTAR DOCUMENTO ---")
                print("Ingrese los campos del documento (deje vacío para terminar):")
                doc = {}
                while True:
                    field = input("\nNombre del campo (Enter para terminar): ").strip()
                    if not field:
                        break
                    value = input(f"Valor para {field}: ").strip()
                    doc[field] = value
                
                if doc:
                    doc_id = db_manager.insert_document(collection_name, doc)
                    if doc_id:
                        print(f"\nDocumento insertado con ID: {doc_id}")
                    else:
                        print("Error al insertar el documento.")
                else:
                    print("No se proporcionaron datos para insertar.")
                    
            elif choice == "4":
                print("\n--- EDITAR DOCUMENTO ---")
                doc_id = input("ID del documento a editar: ").strip()
                if doc_id:
                    oid = validate_objectid(doc_id)
                    query = {"_id": oid} if oid else {"_id": doc_id}
                    doc = db_manager.find_one_document(collection_name, query)
                    
                    if doc:
                        print("\nDocumento actual:")
                        print(serialize_to_json(doc))
                        
                        print("\nIngrese los nuevos valores (deje vacío para mantener el valor actual):")
                        update = {"$set": {}}
                        
                        for field in doc.keys():
                            if field != "_id":
                                new_value = input(f"Nuevo valor para {field}: ").strip()
                                if new_value:
                                    update["$set"][field] = new_value
                        
                        if update["$set"]:
                            if db_manager.update_document(collection_name, query, update):
                                print("Documento actualizado correctamente.")
                            else:
                                print("Error al actualizar el documento.")
                        else:
                            print("No se realizaron cambios.")
                    else:
                        print("Documento no encontrado.")
                else:
                    print("Debe proporcionar un ID de documento.")
                    
            elif choice == "5":
                print("\n--- ELIMINAR DOCUMENTO ---")
                doc_id = input("ID del documento a eliminar: ").strip()
                if doc_id:
                    oid = validate_objectid(doc_id)
                    query = {"_id": oid} if oid else {"_id": doc_id}
                    doc = db_manager.find_one_document(collection_name, query)
                    
                    if doc:
                        print("\nDocumento a eliminar:")
                        print(serialize_to_json(doc))
                        
                        confirm = input("\n¿Está seguro de eliminar este documento? (s/n): ")
                        if confirm.lower() == 's':
                            if db_manager.delete_document(collection_name, query):
                                print("Documento eliminado correctamente.")
                            else:
                                print("Error al eliminar el documento.")
                        else:
                            print("Operación cancelada.")
                    else:
                        print("Documento no encontrado.")
                else:
                    print("Debe proporcionar un ID de documento.")
                    
            elif choice == "6":
                print("\n--- EXPORTAR COLECCIÓN ---")
                filename = input("Nombre del archivo de salida (sin extensión): ").strip()
                if filename:
                    if db_manager.export_collection(collection_name, filename):
                        print(f"Colección exportada exitosamente a {filename}.json")
                    else:
                        print("Error al exportar la colección.")
                else:
                    print("Debe proporcionar un nombre de archivo.")
                    
            elif choice == "7":
                print("\n--- IMPORTAR DATOS ---")
                filename = input("Ruta del archivo a importar: ").strip()
                if filename:
                    if db_manager.import_collection(collection_name, filename):
                        print("Datos importados exitosamente.")
                    else:
                        print("Error al importar los datos.")
                else:
                    print("Debe proporcionar una ruta de archivo.")
                    
            else:
                print("Opción no válida.")
                
        except Exception as e:
            logger.error(f"Error en operaciones de colección: {e}")
            print(f"Error: {e}")
            
        pause()

def pause():
    try:
        input("\nPresione Enter para continuar...")
    except (KeyboardInterrupt, EOFError):
        print("\n")
        pass

def main():
    db_manager = DatabaseManager()
    while True:
        if db_manager.client is None:
            print("\n=== CONEXIÓN A MONGODB ===")
            print("1. Conectar a MongoDB")
            print("0. Salir")
            choice = input("\nSeleccione una opción: ")
            
            try:
                if choice == "0":
                    print("\n¡Hasta luego!")
                    break
                elif choice == "1":
                    uri = input("URI de MongoDB (Enter para usar valor por defecto): ").strip()
                    if not uri:
                        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
                    if db_manager.connect(uri):
                        print("Conexión exitosa a MongoDB.")
                    else:
                        print("Error al conectar a MongoDB.")
                else:
                    print("Opción no válida.")
                    
            except Exception as e:
                logger.error(f"Error al conectar: {e}")
                print(f"Error: {e}")
                
        elif db_manager.db is None:
            print("\n=== SELECCIÓN DE BASE DE DATOS ===")
            dbs = db_manager.list_databases()
            if not dbs:
                print("No se encontraron bases de datos.")
                if input("\n¿Desea desconectarse? (s/n): ").lower() == 's':
                    db_manager.client = None
                continue
                
            print("\nBases de datos disponibles:")
            for i, db in enumerate(dbs, 1):
                print(f"{i}. {db}")
            print("0. Desconectarse")
            
            try:
                choice = input("\nSeleccione el número de la base de datos: ")
                if choice == "0":
                    db_manager.client = None
                    continue
                    
                idx = int(choice)
                if 1 <= idx <= len(dbs):
                    db_name = dbs[idx - 1]
                    if db_manager.select_database(db_name):
                        print(f"Base de datos '{db_name}' seleccionada.")
                    else:
                        print("Error al seleccionar la base de datos.")
                else:
                    print("Número de base de datos no válido.")
                    
            except ValueError:
                print("Debe ingresar un número válido.")
                
        else:
            print(f"\n=== BASE DE DATOS: {db_manager.db.name} ===")
            print("1. Listar colecciones")
            print("2. Seleccionar colección")
            print("3. Gestión de usuarios")
            print("4. Cambiar de base de datos")
            print("0. Desconectarse")
            choice = input("\nSeleccione una opción: ")
            
            try:
                if choice == "0":
                    db_manager.client = None
                    continue
                    
                elif choice == "1":
                    collections = db_manager.list_collections()
                    if collections:
                        print("\nColecciones disponibles:")
                        for collection in collections:
                            print(f"- {collection}")
                    else:
                        print("No se encontraron colecciones.")
                        
                elif choice == "2":
                    collections = db_manager.list_collections()
                    if not collections:
                        print("No hay colecciones disponibles.")
                        continue
                        
                    print("\nColecciones disponibles:")
                    for i, collection in enumerate(collections, 1):
                        print(f"{i}. {collection}")
                        
                    try:
                        idx = int(input("\nSeleccione el número de la colección: "))
                        if 1 <= idx <= len(collections):
                            collection_name = collections[idx - 1]
                            handle_collection_operations(db_manager, collection_name)
                        else:
                            print("Número de colección no válido.")
                    except ValueError:
                        print("Debe ingresar un número válido.")
                        
                elif choice == "3":
                    handle_user_management(db_manager)
                    
                elif choice == "4":
                    db_manager.db = None
                    continue
                    
                else:
                    print("Opción no válida.")
                    
            except Exception as e:
                logger.error(f"Error en el menú principal: {e}")
                print(f"Error: {e}")
                
        pause()

if __name__ == "__main__":
    import msvcrt
    import sys
    
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n¡Hasta luego!")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        print(f"Error: {e}")
    finally:
        # Limpiar el buffer de entrada
        while msvcrt.kbhit():
            msvcrt.getch()
        sys.stdout.flush()
        sys.stderr.flush()
