#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
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
logger = logging.getLogger("ddbb_manager")

def get_mongodb_uri():
    """
    Obtiene la URI de MongoDB desde la variable de entorno 'MONGODB_URI'.
    Si se detecta que la cadena contiene duplicaciones (por ejemplo, "MONGODB_URI=" en el valor),
    se elimina la parte duplicada.
    """
    uri = os.environ.get("MONGODB_URI", "").strip()
    # Si la cadena contiene "MONGODB_URI=" en su interior, extraemos solo la parte correcta
    if "MONGODB_URI=" in uri:
        uri = uri.split("MONGODB_URI=")[0]
    return uri

# Funciones utilitarias

def serialize_to_json(data, format_type='pretty'):
    """
    Serializa datos de MongoDB a JSON.
    
    Args:
        data: Datos a serializar.
        format_type: 'compact', 'pretty' o 'detailed'.
        
    Returns:
        Cadena JSON.
    """
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
    """
    Parsea una cadena JSON para formar una consulta MongoDB.
    
    Args:
        query_str: Consulta en formato JSON.
        
    Returns:
        Diccionario con la consulta.
        
    Lanza:
        ValueError si el formato es inválido.
    """
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
    """
    Valida y convierte una cadena a ObjectId.
    
    Args:
        id_str: Cadena a validar.
        
    Returns:
        ObjectId si es válido o None.
    """
    try:
        return ObjectId(id_str)
    except Exception:
        return None

# Clase principal para la gestión de la base de datos

class DatabaseManager:
    def __init__(self, connection_uri=None, database_name=None, debug=False):
        """
        Inicializa el gestor de base de datos.
        
        Args:
            connection_uri: URI de conexión a MongoDB.
            database_name: Nombre de la base de datos a utilizar.
            debug: Activa el modo debug.
        """
        self.client = None
        self.db = None
        self.database_name = None
        self.current_collection = None
        self.debug = debug
        
        if connection_uri:
            self.connect(connection_uri)
            if database_name:
                self.set_database(database_name)

    def connect(self, connection_uri=None):
        """
        Conecta a MongoDB.
        
        Args:
            connection_uri: URI a utilizar. Si no se pasa, se usa el valor ya almacenado.
            
        Returns:
            True si la conexión es exitosa.
        """
        if connection_uri:
            self.connection_uri = connection_uri
        try:
            self.client = MongoClient(self.connection_uri)
            self.client.admin.command('ping')
            logger.info("Conexión exitosa a MongoDB")
            return True
        except ConnectionFailure as e:
            logger.error(f"Error de conexión a MongoDB: {e}")
            self.client = None
            return False
        except Exception as e:
            logger.error(f"Error al conectar a MongoDB: {e}")
            self.client = None
            return False

    def set_database(self, database_name):
        """
        Selecciona la base de datos a utilizar.
        
        Args:
            database_name: Nombre de la base de datos.
            
        Returns:
            True si se establece correctamente.
        """
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
        """
        Lista todas las bases de datos disponibles.
        
        Returns:
            Lista de nombres de bases de datos.
        """
        try:
            if self.client is None:
                logger.error("No hay conexión a MongoDB")
                return []
            return self.client.list_database_names()
        except Exception as e:
            logger.error(f"Error al listar bases de datos: {e}")
            return []

    def list_collections(self):
        """
        Lista todas las colecciones de la base de datos seleccionada.
        
        Returns:
            Lista de nombres de colecciones.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            collections = self.db.list_collection_names()
            if collections:
                print(f"\nColecciones en la base de datos '{self.database_name}':")
                for i, col in enumerate(collections, 1):
                    print(f"{i}. {col}")
                
                # Permitir selección de colección
                try:
                    selection = input("\nSeleccione el número de la colección (Enter para cancelar): ")
                    if selection.strip():
                        index = int(selection) - 1
                        if 0 <= index < len(collections):
                            selected_collection = collections[index]
                            print(f"\nColección seleccionada: {selected_collection}")
                            return [selected_collection]  # Retornamos la colección seleccionada
                        else:
                            print("\nNúmero de colección inválido")
                except ValueError:
                    print("\nSelección inválida")
            else:
                print(f"\nNo hay colecciones en la base de datos '{self.database_name}'.")
            return collections
        except Exception as e:
            logger.error(f"Error al listar colecciones: {e}")
            return []

    def get_collection_stats(self, collection_name):
        """
        Obtiene estadísticas de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            
        Returns:
            Diccionario con estadísticas o None en caso de error.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            return self.db.command("collStats", collection_name)
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de la colección: {e}")
            return None

    def create_collection(self, collection_name, options=None):
        """
        Crea una nueva colección.
        
        Args:
            collection_name: Nombre de la colección.
            options: Opciones adicionales (por ejemplo, validación).
            
        Returns:
            True si se crea correctamente.
        """
        if self.db is None:
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
        """
        Elimina una colección.
        
        Args:
            collection_name: Nombre de la colección.
            
        Returns:
            True si se elimina correctamente.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            self.db.drop_collection(collection_name)
            logger.info(f"Colección eliminada: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error al eliminar la colección: {e}")
            return False

    def rename_collection(self, old_name, new_name):
        """
        Renombra una colección.
        
        Args:
            old_name: Nombre actual de la colección.
            new_name: Nuevo nombre.
            
        Returns:
            True si se renombra correctamente.
        """
        if self.db is None:
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
        """
        Crea una copia de seguridad de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            
        Returns:
            Nombre de la colección de respaldo o None.
        """
        if self.db is None:
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
        """
        Crea un índice en una colección.
        
        Args:
            collection_name: Nombre de la colección.
            fields: Lista de tuplas (campo, dirección).
            index_options: Opciones adicionales.
            
        Returns:
            Nombre del índice creado o None.
        """
        if self.db is None:
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
        """
        Lista todos los índices de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            
        Returns:
            Lista de índices.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return []
        try:
            return list(self.db[collection_name].list_indexes())
        except Exception as e:
            logger.error(f"Error al listar índices: {e}")
            return []

    def drop_index(self, collection_name, index_name):
        """
        Elimina un índice de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            index_name: Nombre del índice.
            
        Returns:
            True si se elimina correctamente.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return False
        try:
            self.db[collection_name].drop_index(index_name)
            logger.info(f"Índice eliminado: {index_name} en {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error al eliminar índice: {e}")
            return False

    def verify_collection_integrity(self, collection_name, validate_schema=None, sample_size=100):
        """
        Verifica la integridad de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            validate_schema: Esquema para validar documentos (opcional).
            sample_size: Tamaño de la muestra para validación (por defecto 100, 0 para todos).
            
        Returns:
            Diccionario con resultados de la verificación.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return {"error": "No hay base de datos seleccionada"}
        report = {
            "collection_name": collection_name,
            "database_name": self.database_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "document_count": 0,
            "verified_documents": 0,
            "corrupt_documents": 0,
            "invalid_structure": 0,
            "index_status": "Sin comprobar",
            "sample_size": sample_size,
            "issues": [],
            "indexes": [],
            "field_types": {},
            "recommendations": []
        }
        
        try:
            # Verificar que la colección existe
            if collection_name not in self.db.list_collection_names():
                report["error"] = f"La colección '{collection_name}' no existe"
                return report
            
            collection = self.db[collection_name]
            
            # Obtener estadísticas de la colección
            try:
                stats = self.get_collection_stats(collection_name)
                report["document_count"] = stats.get("count", 0) if stats else 0
                report["size_bytes"] = stats.get("size", 0) if stats else 0
            except Exception as e:
                report["stats_error"] = str(e)
            
            # Verificar índices
            try:
                indexes = list(collection.list_indexes())
                report["indexes"] = [
                    {
                        "name": idx.get("name"),
                        "key": idx.get("key"),
                        "unique": idx.get("unique", False)
                    } for idx in indexes
                ]
                report["index_status"] = "OK" if len(indexes) > 0 else "Sin índices"
            except Exception as e:
                report["index_status"] = f"Error: {str(e)}"
                report["issues"].append(f"Error al verificar índices: {str(e)}")
            
            # Preparar consulta para muestra
            query = {}
            cursor = collection.find(query)
            
            # Limitar tamaño de muestra si se especifica
            if sample_size > 0:
                cursor = cursor.limit(sample_size)
            
            # Analizar documentos
            field_types = {}
            corrupt_count = 0
            structure_issues = 0
            verified_count = 0
            
            for doc in cursor:
                verified_count += 1
                
                # Verificar estructura básica
                if '_id' not in doc:
                    corrupt_count += 1
                    report["issues"].append(f"Documento sin _id encontrado")
                    continue
                
                # Analizar tipos de campos
                for field, value in doc.items():
                    field_type = type(value).__name__
                    if field not in field_types:
                        field_types[field] = {field_type: 1}
                    else:
                        if field_type in field_types[field]:
                            field_types[field][field_type] += 1
                        else:
                            field_types[field][field_type] = 1
                            # Tipos inconsistentes
                            structure_issues += 1
                            report["issues"].append(
                                f"Campo '{field}' tiene tipos inconsistentes: {list(field_types[field].keys())}"
                            )
                
                # Verificación de esquema personalizado
                if validate_schema:
                    try:
                        # Implementar validación de esquema según requisitos
                        # Por ejemplo, verificar campos obligatorios o tipos específicos
                        for field, expected_type in validate_schema.items():
                            if field in doc:
                                actual_type = type(doc[field]).__name__
                                if expected_type != actual_type:
                                    structure_issues += 1
                                    report["issues"].append(
                                        f"Documento con ID {doc['_id']}: Campo '{field}' tiene tipo {actual_type}, se esperaba {expected_type}"
                                    )
                            else:
                                structure_issues += 1
                                report["issues"].append(
                                    f"Documento con ID {doc['_id']}: Campo requerido '{field}' no está presente"
                                )
                    except Exception as e:
                        report["issues"].append(f"Error en validación personalizada: {str(e)}")
            
            # Actualizar estadísticas
            report["verified_documents"] = verified_count
            report["corrupt_documents"] = corrupt_count
            report["invalid_structure"] = structure_issues
            report["field_types"] = field_types
            
            # Generar recomendaciones
            if corrupt_count > 0:
                report["recommendations"].append("Reparar documentos corruptos o eliminarlos")
            
            if structure_issues > 0:
                report["recommendations"].append("Normalizar estructura de documentos con campos inconsistentes")
            
            if len(report["indexes"]) == 0:
                report["recommendations"].append("Crear índices para mejorar el rendimiento de consultas")
            
            report["status"] = "OK" if corrupt_count == 0 and structure_issues == 0 else "Problemas detectados"
            
            return report
            
        except Exception as e:
            logger.error(f"Error al verificar integridad de la colección: {e}")
            report["error"] = str(e)
            report["status"] = "Error"
            return report
    def get_database_statistics(self):
        """
        Recopila estadísticas completas de la base de datos actual.
        
        Returns:
            Diccionario con estadísticas de la base de datos o error.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return {"error": "No hay base de datos seleccionada"}
        stats = {
            "database_name": self.database_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "general": {},
            "collections": [],
            "storage": {},
            "indexes": {},
            "performance": {},
            "issues": []
        }
        
        try:
            # Obtener estadísticas generales de la base de datos
            try:
                db_stats = self.db.command("dbStats", scale=1024*1024)  # Escala en MB
                stats["general"] = {
                    "collections": db_stats.get("collections", 0),
                    "views": db_stats.get("views", 0),
                    "objects": db_stats.get("objects", 0),
                    "avg_object_size_bytes": db_stats.get("avgObjSize", 0),
                    "data_size_mb": db_stats.get("dataSize", 0),
                    "storage_size_mb": db_stats.get("storageSize", 0),
                    "num_extents": db_stats.get("numExtents", 0),
                    "indexes": db_stats.get("indexes", 0),
                    "index_size_mb": db_stats.get("indexSize", 0),
                    "file_size_mb": db_stats.get("fileSize", 0) if "fileSize" in db_stats else None,
                    "ns_size_mb": db_stats.get("nsSize", 0) if "nsSize" in db_stats else None,
                }
                stats["storage"] = {
                    "total_size_mb": (db_stats.get("dataSize", 0) + db_stats.get("indexSize", 0)),
                    "data_size_mb": db_stats.get("dataSize", 0),
                    "index_size_mb": db_stats.get("indexSize", 0),
                    "avg_object_size_kb": db_stats.get("avgObjSize", 0) / 1024 if db_stats.get("avgObjSize") else 0,
                }
            except Exception as e:
                error_msg = f"Error al obtener estadísticas generales: {str(e)}"
                logger.error(error_msg)
                stats["issues"].append(error_msg)
            
            # Obtener estadísticas de colecciones
            try:
                collection_names = self.db.list_collection_names()
                collection_stats = []
                
                for col_name in collection_names:
                    try:
                        col_stats = self.get_collection_stats(col_name)
                        if col_stats:
                            collection_stats.append({
                                "name": col_name,
                                "count": col_stats.get("count", 0),
                                "size_mb": col_stats.get("size", 0) / (1024 * 1024),
                                "storage_size_mb": col_stats.get("storageSize", 0) / (1024 * 1024),
                                "avg_object_size_bytes": col_stats.get("avgObjSize", 0),
                                "index_size_mb": col_stats.get("totalIndexSize", 0) / (1024 * 1024),
                                "capped": col_stats.get("capped", False),
                                "num_indexes": col_stats.get("nindexes", 0),
                                "indexes": self.list_indexes(col_name)
                            })
                    except Exception as e:
                        error_msg = f"Error al obtener estadísticas de colección {col_name}: {str(e)}"
                        logger.error(error_msg)
                        stats["issues"].append(error_msg)
                
                # Ordenar colecciones por tamaño (de mayor a menor)
                collection_stats.sort(key=lambda x: x.get("size_mb", 0), reverse=True)
                stats["collections"] = collection_stats
                
                # Calcular estadísticas de índices
                total_indexes = 0
                total_index_size_mb = 0
                
                for col_stat in collection_stats:
                    total_indexes += col_stat.get("num_indexes", 0)
                    total_index_size_mb += col_stat.get("index_size_mb", 0)
                
                stats["indexes"] = {
                    "total_count": total_indexes,
                    "total_size_mb": total_index_size_mb,
                    "avg_index_size_mb": total_index_size_mb / total_indexes if total_indexes > 0 else 0
                }
                
                # Métricas de rendimiento (estimadas)
                total_documents = stats["general"].get("objects", 0)
                stats["performance"] = {
                    "index_ratio": total_index_size_mb / stats["storage"].get("data_size_mb", 1) if stats["storage"].get("data_size_mb", 0) > 0 else 0,
                    "avg_doc_per_collection": total_documents / len(collection_stats) if collection_stats else 0,
                    "largest_collection": collection_stats[0]["name"] if collection_stats else "N/A",
                    "largest_collection_size_mb": collection_stats[0]["size_mb"] if collection_stats else 0,
                    "document_count": total_documents,
                }
                
                # Identificar problemas potenciales
                if stats["performance"].get("index_ratio", 0) > 1.0:
                    stats["issues"].append("El tamaño de los índices es mayor que los datos. Considere revisar los índices.")
                
                large_collections = [col for col in collection_stats if col.get("count", 0) > 100000]
                if large_collections:
                    stats["issues"].append(f"Hay {len(large_collections)} colecciones con más de 100,000 documentos que podrían necesitar optimización.")
                
                no_index_collections = [col for col in collection_stats if col.get("num_indexes", 0) <= 1 and col.get("count", 0) > 1000]
                if no_index_collections:
                    stats["issues"].append(f"Hay {len(no_index_collections)} colecciones con más de 1,000 documentos pero sin índices personalizados.")
                
            except Exception as e:
                error_msg = f"Error al procesar estadísticas de colecciones: {str(e)}"
                logger.error(error_msg)
                stats["issues"].append(error_msg)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error al recopilar estadísticas de la base de datos: {e}")
            stats["error"] = str(e)
            return stats
    
    def get_user_databases(self, username):
        """
        Obtiene información sobre las bases de datos asociadas a un usuario.
        
        Args:
            username: Nombre del usuario.
            
        Returns:
            Diccionario con información de bases de datos y permisos del usuario.
        """
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return {"error": "No hay conexión a MongoDB"}
        
        try:
            # Verificar que estamos autenticados con permisos adecuados para consultar usuarios
            user_info = {
                "username": username,
                "timestamp": datetime.datetime.now().isoformat(),
                "databases": [],
                "roles": [],
                "global_permissions": []
            }
            
            # Intentar acceder a la base de datos admin donde se almacena la información de usuarios
            admin_db = self.client.admin
            
            # Consultar usuarios - requiere permisos
            try:
                user_data = admin_db.command("usersInfo", {"user": username, "db": "admin"})
                if "users" in user_data and len(user_data["users"]) > 0:
                    user = user_data["users"][0]
                    user_info["user_found"] = True
                    user_info["user_id"] = str(user.get("_id", ""))
                    
                    # Extraer roles del usuario
                    if "roles" in user:
                        for role in user["roles"]:
                            role_info = {
                                "role": role.get("role", ""),
                                "db": role.get("db", ""),
                                "is_builtin": role.get("role", "") in ["read", "readWrite", "dbAdmin", "userAdmin", "dbOwner", "root"]
                            }
                            user_info["roles"].append(role_info)
                            
                            # Si el rol es "root", tiene acceso a todas las bases de datos
                            if role.get("role") == "root":
                                user_info["has_root_access"] = True
                else:
                    user_info["user_found"] = False
                    return user_info
                
            except Exception as e:
                logger.error(f"Error al obtener información del usuario: {e}")
                user_info["error_user_info"] = str(e)
                user_info["user_found"] = False
                
                # Si no podemos obtener la información directamente, intentamos inferir
                # basándonos en la base de datos actual y el usuario logueado
                try:
                    # Esta operación no requiere permisos especiales
                    connection_status = admin_db.command("connectionStatus")
                    if "authInfo" in connection_status and "authenticatedUsers" in connection_status["authInfo"]:
                        for auth_user in connection_status["authInfo"]["authenticatedUsers"]:
                            if auth_user.get("user") == username:
                                user_info["user_found"] = True
                                user_info["current_user"] = True
                                if "roles" in auth_user:
                                    for role in auth_user["roles"]:
                                        role_info = {
                                            "role": role.get("role", ""),
                                            "db": role.get("db", ""),
                                            "is_builtin": role.get("role", "") in ["read", "readWrite", "dbAdmin", "userAdmin", "dbOwner", "root"]
                                        }
                                        user_info["roles"].append(role_info)
                except Exception as e_conn:
                    logger.error(f"Error al obtener estado de conexión: {e_conn}")
                    user_info["error_connection_status"] = str(e_conn)
            
            # Analizar roles para determinar a qué bases de datos tiene acceso
            has_admin_access = False
            specific_db_access = set()
            
            for role in user_info["roles"]:
                if role["role"] == "root" or (role["role"] == "userAdminAnyDatabase" and role["db"] == "admin"):
                    has_admin_access = True
                    break
                elif role["db"] != "admin":
                    specific_db_access.add(role["db"])
                elif role["role"] in ["readAnyDatabase", "readWriteAnyDatabase", "dbAdminAnyDatabase"]:
                    has_admin_access = True
                    break
            
            # Listar bases de datos
            try:
                all_databases = self.client.list_database_names()
                
                for db_name in all_databases:
                    if has_admin_access or db_name in specific_db_access or db_name in ["local", "config"]:
                        try:
                            temp_db = self.client[db_name]
                            # Obtener estadísticas básicas
                            try:
                                db_stats = temp_db.command("dbStats", scale=1024*1024)  # Escala en MB
                                db_info = {
                                    "name": db_name,
                                    "collections": db_stats.get("collections", 0),
                                    "size_mb": db_stats.get("dataSize", 0),
                                    "storage_size_mb": db_stats.get("storageSize", 0),
                                    "indexes": db_stats.get("indexes", 0),
                                    "index_size_mb": db_stats.get("indexSize", 0),
                                }
                            except Exception as e_stat:
                                db_info = {
                                    "name": db_name,
                                    "error_stats": str(e_stat)
                                }
                            
                            # Determinar permisos en esta base de datos
                            permissions = []
                            for role in user_info["roles"]:
                                if role["role"] == "root" or (role["role"].endswith("AnyDatabase") and role["db"] == "admin"):
                                    if "read" in role["role"]:
                                        permissions.append("read")
                                    if "write" in role["role"] or role["role"] == "root":
                                        permissions.append("write")
                                    if "dbAdmin" in role["role"] or role["role"] == "root":
                                        permissions.append("admin")
                                    if "userAdmin" in role["role"] or role["role"] == "root":
                                        permissions.append("userAdmin")
                                    break
                                elif role["db"] == db_name:
                                    if role["role"] == "read":
                                        permissions.append("read")
                                    if role["role"] == "readWrite" or role["role"] == "dbOwner":
                                        permissions.append("read")
                                        permissions.append("write")
                                    if role["role"] == "dbAdmin" or role["role"] == "dbOwner":
                                        permissions.append("admin")
                                    if role["role"] == "userAdmin" or role["role"] == "dbOwner":
                                        permissions.append("userAdmin")
                            
                            # Eliminar duplicados
                            permissions = list(set(permissions))
                            db_info["permissions"] = permissions
                            db_info["access_level"] = "full" if len(permissions) >= 3 else ("read-write" if "write" in permissions else "read-only")
                            
                            # Agregar a la lista de bases de datos
                            user_info["databases"].append(db_info)
                            
                        except Exception as e_db:
                            logger.error(f"Error al procesar base de datos {db_name}: {e_db}")
                            user_info["databases"].append({
                                "name": db_name,
                                "error": str(e_db)
                            })
            except Exception as e_list:
                logger.error(f"Error al listar bases de datos: {e_list}")
                user_info["error_listing_dbs"] = str(e_list)
            
            # Ordenar bases de datos por tamaño
            user_info["databases"].sort(key=lambda x: x.get("size_mb", 0) if isinstance(x.get("size_mb", 0), (int, float)) else 0, reverse=True)
            
            # Resumen general
            total_size = sum(db.get("size_mb", 0) for db in user_info["databases"] if isinstance(db.get("size_mb", 0), (int, float)))
            total_collections = sum(db.get("collections", 0) for db in user_info["databases"] if isinstance(db.get("collections", 0), (int, float)))
            
            user_info["summary"] = {
                "total_databases": len(user_info["databases"]),
                "total_size_mb": total_size,
                "total_collections": total_collections,
                "admin_access": has_admin_access,
                "total_roles": len(user_info["roles"]),
            }
            
            return user_info
            
        except Exception as e:
            logger.error(f"Error al obtener bases de datos del usuario: {e}")
            return {"error": str(e), "username": username}

    def cleanup_user_databases(self, username, options=None):
        """
        Realiza tareas de depuración y optimización en las bases de datos de un usuario.
        
        Args:
            username: Nombre del usuario cuyas bases de datos se depurarán.
            options: Diccionario con opciones de depuración (opcional).
                - remove_empty_collections: Eliminar colecciones vacías (True/False)
                - optimize_indexes: Optimizar índices (True/False)
                - compact_data: Compactar datos (True/False)
                - remove_temp_data: Eliminar datos temporales (True/False)
                - remove_old_backups: Eliminar copias de seguridad antiguas (True/False)
                - max_backup_age_days: Edad máxima de las copias de seguridad (días)
            
        Returns:
            Diccionario con resultados de la depuración.
        """
        if self.client is None:
            logger.error("No hay conexión a MongoDB")
            return {"error": "No hay conexión a MongoDB"}
        # Establecer opciones predeterminadas si no se proporcionan
        if options is None:
            options = {
                "remove_empty_collections": True,
                "optimize_indexes": True,
                "compact_data": True,
                "remove_temp_data": True,
                "remove_old_backups": True,
                "max_backup_age_days": 30
            }
        
        results = {
            "username": username,
            "timestamp": datetime.datetime.now().isoformat(),
            "actions_performed": [],
            "details": {
                "empty_collections_removed": 0,
                "indexes_optimized": 0,
                "collections_compacted": 0,
                "temp_data_removed": 0,
                "backups_removed": 0,
                "errors": []
            },
            "databases_affected": []
        }
        
        try:
            # Obtener información de bases de datos del usuario
            user_info = self.get_user_databases(username)
            
            if "error" in user_info:
                logger.error(f"Error al obtener información del usuario: {user_info['error']}")
                return {"error": user_info["error"]}
            
            if not user_info.get("user_found", False):
                logger.error(f"Usuario no encontrado: {username}")
                return {"error": f"Usuario no encontrado: {username}"}
            
            # Iterar sobre las bases de datos a las que el usuario tiene acceso
            for db_info in user_info.get("databases", []):
                db_name = db_info.get("name")
                
                # Verificar si tenemos permisos suficientes para esta base de datos
                has_write_permission = "write" in db_info.get("permissions", [])
                has_admin_permission = "admin" in db_info.get("permissions", [])
                
                if not has_write_permission and not has_admin_permission:
                    logger.warning(f"Sin permisos suficientes para depurar la base de datos {db_name}")
                    results["details"]["errors"].append(f"Sin permisos suficientes para depurar {db_name}")
                    continue
                
                # Establecer la base de datos actual
                temp_db = self.client[db_name]
                db_result = {
                    "name": db_name,
                    "actions": [],
                    "collections_affected": []
                }
                
                try:
                    # Obtener lista de colecciones
                    collections = temp_db.list_collection_names()
                    
                    # 1. Eliminar colecciones vacías
                    if options.get("remove_empty_collections", False):
                        for col_name in collections:
                            try:
                                # Verificar si la colección no es del sistema
                                if not col_name.startswith("system."):
                                    # Verificar si la colección está vacía
                                    count = temp_db[col_name].count_documents({})
                                    if count == 0:
                                        # Eliminar colección vacía
                                        temp_db.drop_collection(col_name)
                                        results["details"]["empty_collections_removed"] += 1
                                        db_result["actions"].append(f"Colección vacía eliminada: {col_name}")
                                        db_result["collections_affected"].append(col_name)
                                        logger.info(f"Colección vacía eliminada: {db_name}.{col_name}")
                            except Exception as e:
                                error_msg = f"Error al procesar colección vacía {db_name}.{col_name}: {str(e)}"
                                logger.error(error_msg)
                                results["details"]["errors"].append(error_msg)
                                
                    # 2. Optimizar índices
                    if options.get("optimize_indexes", False):
                        # Actualizar lista de colecciones (podrían haber cambios)
                        collections = temp_db.list_collection_names()
                        for col_name in collections:
                            try:
                                if not col_name.startswith("system."):
                                    collection = temp_db[col_name]
                                    
                                    # Obtener información de índices actuales
                                    indexes = list(collection.list_indexes())
                                    
                                    # Verificar índices duplicados o no utilizados
                                    # Este es un análisis básico, en la práctica se requeriría análisis de consultas
                                    index_fields = {}
                                    indexes_to_drop = []
                                    
                                    for idx in indexes:
                                        # No eliminar el índice _id
                                        if idx["name"] == "_id_":
                                            continue
                                            
                                        # Comprobar si es un índice de un solo campo ya cubierto por otro compuesto
                                        if len(idx["key"]) == 1:
                                            field = list(idx["key"].keys())[0]
                                            if field in index_fields:
                                                # Este campo ya está indexado en otro índice
                                                indexes_to_drop.append(idx["name"])
                                            else:
                                                index_fields[field] = idx["name"]
                                    
                                    # Eliminar índices identificados
                                    for idx_name in indexes_to_drop:
                                        collection.drop_index(idx_name)
                                        results["details"]["indexes_optimized"] += 1
                                        db_result["actions"].append(f"Índice optimizado en {col_name}: {idx_name}")
                                        if col_name not in db_result["collections_affected"]:
                                            db_result["collections_affected"].append(col_name)
                                        logger.info(f"Índice eliminado para optimización: {db_name}.{col_name}.{idx_name}")
                            except Exception as e:
                                error_msg = f"Error al optimizar índices en {db_name}.{col_name}: {str(e)}"
                                logger.error(error_msg)
                                results["details"]["errors"].append(error_msg)
                    
                    # 3. Compactar datos
                    if options.get("compact_data", False) and has_admin_permission:
                        collections = temp_db.list_collection_names()
                        for col_name in collections:
                            try:
                                if not col_name.startswith("system."):
                                    # Ejecutar comando compact (requiere permisos de administrador)
                                    temp_db.command("compact", col_name)
                                    results["details"]["collections_compacted"] += 1
                                    db_result["actions"].append(f"Colección compactada: {col_name}")
                                    if col_name not in db_result["collections_affected"]:
                                        db_result["collections_affected"].append(col_name)
                                    logger.info(f"Colección compactada: {db_name}.{col_name}")
                            except Exception as e:
                                error_msg = f"Error al compactar colección {db_name}.{col_name}: {str(e)}"
                                logger.error(error_msg)
                                results["details"]["errors"].append(error_msg)
                    
                    # 4. Eliminar datos temporales
                    if options.get("remove_temp_data", False):
                        temp_patterns = ["temp", "tmp", "temporal", "cache", "log_", "logs_"]
                        
                        # Buscar colecciones temporales
                        collections = temp_db.list_collection_names()
                        for col_name in collections:
                            try:
                                # Verificar si la colección parece ser temporal
                                is_temp = any(pattern in col_name.lower() for pattern in temp_patterns)
                                
                                if is_temp and not col_name.startswith("system."):
                                    # Eliminar colección temporal
                                    temp_db.drop_collection(col_name)
                                    results["details"]["temp_data_removed"] += 1
                                    db_result["actions"].append(f"Datos temporales eliminados: {col_name}")
                                    if col_name not in db_result["collections_affected"]:
                                        db_result["collections_affected"].append(col_name)
                                    logger.info(f"Colección temporal eliminada: {db_name}.{col_name}")
                            except Exception as e:
                                error_msg = f"Error al eliminar datos temporales de {db_name}.{col_name}: {str(e)}"
                                logger.error(error_msg)
                                results["details"]["errors"].append(error_msg)
                    
                    # 5. Eliminar copias de seguridad antiguas
                    if options.get("remove_old_backups", False):
                        backup_patterns = ["backup", "respaldo", "copy", "copia"]
                        max_age_days = options.get("max_backup_age_days", 30)
                        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
                        
                        collections = temp_db.list_collection_names()
                        for col_name in collections:
                            # Verificar si es una colección de respaldo con timestamp en el nombre
                            is_backup = any(pattern in col_name.lower() for pattern in backup_patterns)
                            
                            if is_backup and not col_name.startswith("system."):
                                try:
                                    # Intentar extraer la fecha de la colección (formato común: nombre_backup_YYYYMMDD_HHMMSS)
                                    parts = col_name.split('_')
                                    date_str = None
                                    
                                    for i, part in enumerate(parts):
                                        if i < len(parts) - 1 and len(part) == 8 and part.isdigit() and len(parts[i+1]) == 6 and parts[i+1].isdigit():
                                            date_str = f"{part}_{parts[i+1]}"
                                            break
                                    
                                    if date_str:
                                        try:
                                            # Intentar parsear la fecha encontrada
                                            backup_date = datetime.datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                                            
                                            # Si la copia de seguridad es antigua, eliminarla
                                            if backup_date < cutoff_date:
                                                temp_db.drop_collection(col_name)
                                                results["details"]["backups_removed"] += 1
                                                db_result["actions"].append(f"Copia de seguridad antigua eliminada: {col_name}")
                                                if col_name not in db_result["collections_affected"]:
                                                    db_result["collections_affected"].append(col_name)
                                                logger.info(f"Copia de seguridad antigua eliminada: {db_name}.{col_name}")
                                        except ValueError:
                                            # Formato de fecha no reconocido
                                            pass
                                except Exception as e:
                                    error_msg = f"Error al procesar copia de seguridad {db_name}.{col_name}: {str(e)}"
                                    logger.error(error_msg)
                                    results["details"]["errors"].append(error_msg)
                
                    # Agregar resultado de esta base de datos si hubo cambios
                    if db_result["actions"]:
                        results["databases_affected"].append(db_result)
                        
                except Exception as e:
                    error_msg = f"Error al procesar base de datos {db_name}: {str(e)}"
                    logger.error(error_msg)
                    results["details"]["errors"].append(error_msg)
                    
            # Registrar acciones realizadas
            if results["databases_affected"]:
                for db in results["databases_affected"]:
                    for action in db["actions"]:
                        results["actions_performed"].append(action)
            
            # Resumen de operaciones
            if not results["actions_performed"]:
                results["summary"] = "No se realizaron cambios. Todas las bases de datos están optimizadas."
            else:
                results["summary"] = f"Se realizaron {len(results['actions_performed'])} acciones de depuración en {len(results['databases_affected'])} bases de datos."
                
            logger.info(f"Depuración completada para el usuario {username}. {results['summary']}")
            return results
            
        except Exception as e:
            logger.error(f"Error general en la depuración de bases de datos: {e}")
            results["error"] = str(e)
            return results

    def find_documents(self, collection_name, query=None, projection=None, limit=0, sort=None):
        """
        Busca documentos en una colección.
        
        Args:
            collection_name: Nombre de la colección.
            query: Consulta de filtro.
            projection: Campos a incluir o excluir.
            limit: Límite de documentos (0 = sin límite).
            sort: Especificación de ordenamiento.
            
        Returns:
            Lista de documentos encontrados.
        """
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
        """
        Busca un documento en una colección.
        
        Args:
            collection_name: Nombre de la colección.
            query: Consulta de filtro.
            projection: Campos a incluir o excluir.
            
        Returns:
            Documento o None.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            return self.db[collection_name].find_one(query, projection)
        except Exception as e:
            logger.error(f"Error al buscar documento: {e}")
            return None

    def insert_document(self, collection_name, document):
        """
        Inserta un documento en una colección.
        
        Args:
            collection_name: Nombre de la colección.
            document: Documento a insertar.
            
        Returns:
            ID del documento insertado o None.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        try:
            result = self.db[collection_name].insert_one(document)
            logger.info(f"Documento insertado con ID: {result.inserted_id}")
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            logger.error(f"Error de clave duplicada: {e}")
            return None
        except Exception as e:
            logger.error(f"Error al insertar documento: {e}")
            return None

    def update_document(self, collection_name, query, update, upsert=False):
        """
        Actualiza documentos en una colección.
        
        Args:
            collection_name: Nombre de la colección.
            query: Consulta para identificar los documentos.
            update: Operadores de actualización.
            upsert: Inserta si no existe (por defecto False).
            
        Returns:
            Número de documentos modificados.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return 0
        try:
            if not any(key.startswith('$') for key in update.keys()):
                update = {"$set": update}
            result = self.db[collection_name].update_many(query, update, upsert=upsert)
            logger.info(f"Documentos modificados: {result.modified_count} en {collection_name}")
            return result.modified_count
        except Exception as e:
            logger.error(f"Error al actualizar documento: {e}")
            return 0

    def delete_document(self, collection_name, query):
        """
        Elimina documentos de una colección.
        
        Args:
            collection_name: Nombre de la colección.
            query: Consulta para identificar los documentos a eliminar.
            
        Returns:
            Número de documentos eliminados.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return 0
        try:
            result = self.db[collection_name].delete_many(query)
            logger.info(f"Documentos eliminados: {result.deleted_count} en {collection_name}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error al eliminar documento: {e}")
            return 0

    # Función para gestión de usuarios (suponiendo que los usuarios se almacenan en la colección "users")
    def get_user_by_id(self, user_id):
        """
        Busca un usuario por su ID.
        
        Args:
            user_id: ID del usuario.
            
        Returns:
            Documento del usuario o None.
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return None
        oid = validate_objectid(user_id)
        query = {"_id": oid} if oid else {"_id": user_id}
        return self.find_one_document("users", query)

    # Exportación de colección

    def export_collection(self, collection_name, output_file, format_type='json', query=None, fields=None, batch_size=1000, show_progress=True):
        """
        Exporta documentos de una colección a un archivo.
        
        Args:
            collection_name: Nombre de la colección.
            output_file: Ruta del archivo de salida.
            format_type: Formato de salida ('json' o 'csv').
            query: Consulta de filtrado.
            fields: Campos a incluir (opcional).
            batch_size: Tamaño de lote (no utilizado en esta versión).
            show_progress: Muestra barra de progreso si tqdm está instalado.
            
        Returns:
            Tupla (éxito, número de documentos exportados).
        """
        if self.db is None:
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
        """
        Importa documentos desde un archivo a una colección.
        
        Args:
            collection_name: Nombre de la colección.
            input_file: Ruta del archivo de entrada.
            format_type: Formato del archivo ('json' o 'csv').
            duplicate_handling: Manejo de duplicados ('skip', 'replace' o 'merge').
            validate: Valida la estructura del archivo.
            batch_size: Tamaño de lote (no utilizado en esta versión).
            show_progress: Muestra barra de progreso.
            
        Returns:
            Tupla (éxito, estadísticas de importación).
        """
        if self.db is None:
            logger.error("No hay base de datos seleccionada")
            return (False, {"error": "No hay base de datos seleccionada"})
        
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        try:
            if not os.path.exists(input_file):
                logger.error(f"Archivo no encontrado: {input_file}")
                return (False, {"error": "Archivo no encontrado"})
                
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

# Funciones para el menú y la interacción con el usuario

def display_menu(db_manager=None):
    print("\n" + "=" * 50)
    print("HERRAMIENTA DE GESTIÓN DE BASES DE DATOS MONGODB")
    print("=" * 50)
    if db_manager:
        if db_manager.database_name:
            print(f"Base de datos actual: {db_manager.database_name}")
        if db_manager.current_collection:
            print(f"Colección actual: {db_manager.current_collection}")
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
            for i, db in enumerate(databases, 1):
                print(f"{i}. {db}")
            
            if databases:
                try:
                    selection = input("\nSeleccione el número de la base de datos (Enter para cancelar): ")
                    if selection.strip():
                        index = int(selection) - 1
                        if 0 <= index < len(databases):
                            selected_db = databases[index]
                            if db_manager.set_database(selected_db):
                                print(f"\nBase de datos seleccionada: {selected_db}")
                        else:
                            print("\nNúmero de base de datos inválido")
                except ValueError:
                    print("\nSelección inválida")
        elif choice == "2":
            # Verificar conexión y base de datos seleccionada
            if db_manager.client is None:
                print("Error: No hay conexión a MongoDB.")
                return
                
            if db_manager.db is None:
                print("Error: No hay base de datos seleccionada.")
                print("Por favor, primero seleccione una base de datos usando la opción 1.")
                return
            
            try:
                collections = db_manager.list_collections()
                # La función list_collections ya maneja la impresión y selección
                if len(collections) == 1:
                    # Si solo se retorna una colección, significa que fue seleccionada
                    db_manager.current_collection = collections[0]
            except PyMongoError as e:
                logger.error(f"Error de MongoDB al listar colecciones: {e}")
                print(f"Error de MongoDB: {e}")
            except Exception as e:
                logger.error(f"Error al listar colecciones: {e}")
                print(f"Error al listar colecciones: {e}")
        elif choice == "3":
            collection_name = input("Nombre de la colección: ")
            query_str = input("Consulta (JSON, vacío para todos): ")
            try:
                query = parse_json_query(query_str)
            except Exception as e:
                print(f"Error en la consulta: {e}")
                return
            limit_str = input("Límite de documentos (vacío para 10): ")
            limit = 10
            if limit_str.isdigit():
                limit = int(limit_str)
            docs = db_manager.find_documents(collection_name, query, limit=limit)
            print(f"\nDocumentos encontrados en {collection_name}:")
            for i, doc in enumerate(docs, 1):
                print(f"\n--- Documento {i} ---")
                print(serialize_to_json(doc))
        elif choice == "4" or choice == "5":
            operation = "exportar" if choice == "4" else "importar"
            handle_export_import(db_manager, operation)
        elif choice == "6":
            collection_name = input("Nombre de la colección a eliminar: ")
            confirm = input(f"¿Está seguro de eliminar la colección '{collection_name}'? (s/n): ")
            if confirm.lower() == 's':
                if db_manager.drop_collection(collection_name):
                    print(f"Colección '{collection_name}' eliminada con éxito.")
                else:
                    print(f"Error al eliminar la colección '{collection_name}'.")
            else:
                print("Operación cancelada.")
        elif choice == "7":
            # Verificar integridad
            if db_manager.db is None:
                print("Error: No hay base de datos seleccionada.")
                return
            
            collection_name = input("Nombre de la colección a verificar: ")
            use_schema = input("¿Desea validar con un esquema personalizado? (s/n): ").lower() == 's'
            sample_size_str = input("Tamaño de muestra para verificación (Enter para 100, 0 para todos): ")
            
            sample_size = 100
            if sample_size_str.strip():
                try:
                    sample_size = int(sample_size_str)
                except ValueError:
                    print("Valor inválido. Se usará 100 como predeterminado.")
            
            schema = None
            if use_schema:
                print("\nDefina el esquema de validación (formato: campo:tipo, separados por comas)")
                print("Ejemplo: nombre:str,edad:int,activo:bool")
                schema_str = input("Esquema: ")
                
                if schema_str.strip():
                    schema = {}
                    parts = schema_str.split(",")
                    for part in parts:
                        if ":" in part:
                            field, field_type = part.split(":")
                            schema[field.strip()] = field_type.strip()
            
            print("\nVerificando integridad de la colección. Esto puede tomar tiempo...")
            report = db_manager.verify_collection_integrity(collection_name, schema, sample_size)
            
            # Mostrar informe
            print("\n" + "="*60)
            print(f"INFORME DE INTEGRIDAD: {collection_name}")
            print("="*60)
            print(f"Estado: {report.get('status', 'Desconocido')}")
            print(f"Base de datos: {report.get('database_name', 'N/A')}")
            print(f"Documentos totales: {report.get('document_count', 0)}")
            print(f"Documentos verificados: {report.get('verified_documents', 0)}")
            print(f"Documentos corruptos: {report.get('corrupt_documents', 0)}")
            print(f"Problemas de estructura: {report.get('invalid_structure', 0)}")
            print(f"Estado de índices: {report.get('index_status', 'N/A')}")
            
            if report.get('indexes'):
                print("\nÍndices:")
                for idx in report.get('indexes', []):
                    print(f"  - {idx.get('name', 'N/A')}: {idx.get('key', 'N/A')}")
            
            if report.get('issues'):
                print("\nProblemas detectados:")
                for issue in report.get('issues', [])[:10]:  # Limitar a 10 para no saturar la pantalla
                    print(f"  - {issue}")
                if len(report.get('issues', [])) > 10:
                    print(f"  ... y {len(report.get('issues', [])) - 10} problemas más.")
            
            if report.get('recommendations'):
                print("\nRecomendaciones:")
                for rec in report.get('recommendations', []):
                    print(f"  - {rec}")
            
            # Preguntar si se desea exportar el informe completo
            export_report = input("\n¿Desea exportar el informe completo a un archivo JSON? (s/n): ").lower() == 's'
            if export_report:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"integrity_report_{collection_name}_{timestamp}.json"
                try:
                    with open(os.path.join("respaldos", filename), 'w', encoding='utf-8') as f:
                        f.write(serialize_to_json(report, format_type='detailed'))
                    print(f"Informe exportado a: {os.path.join('respaldos', filename)}")
                except Exception as e:
                    print(f"Error al exportar el informe: {e}")
                    logger.error(f"Error al exportar informe de integridad: {e}")
        elif choice == "8":
            collection_name = input("Nombre de la colección: ")
            field = input("Campo para indexar: ")
            direction_str = input("Dirección del índice (1 para ascendente, -1 para descendente): ")
            try:
                direction = int(direction_str)
            except:
                direction = 1
            index_name = db_manager.create_index(collection_name, [(field, direction)])
            if index_name:
                print(f"Índice creado: {index_name} en {collection_name}")
            else:
                print("Error al crear el índice.")
        elif choice == "9":
            # Estadísticas de la base de datos
            if db_manager.db is None:
                print("Error: No hay base de datos seleccionada.")
                return
            
            print("\nRecopilando estadísticas de la base de datos. Esto puede tomar tiempo...")
            stats = db_manager.get_database_statistics()
            
            if "error" in stats:
                print(f"Error al obtener estadísticas: {stats['error']}")
                return
                
            # Mostrar estadísticas generales
            print("\n" + "="*60)
            print(f"ESTADÍSTICAS DE LA BASE DE DATOS: {stats['database_name']}")
            print("="*60)
            print(f"Fecha y hora: {datetime.datetime.fromisoformat(stats['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
            print("\n--- INFORMACIÓN GENERAL ---")
            print(f"Número de colecciones: {stats['general'].get('collections', 0)}")
            print(f"Número de vistas: {stats['general'].get('views', 0)}")
            print(f"Total de documentos: {stats['general'].get('objects', 0):,}")
            print(f"Tamaño promedio de documento: {stats['general'].get('avg_object_size_bytes', 0):,.2f} bytes")
            
            # Información de almacenamiento
            print("\n--- ALMACENAMIENTO ---")
            print(f"Tamaño total: {stats['storage'].get('total_size_mb', 0):,.2f} MB")
            print(f"Tamaño de datos: {stats['storage'].get('data_size_mb', 0):,.2f} MB")
            print(f"Tamaño de índices: {stats['storage'].get('index_size_mb', 0):,.2f} MB")
            
            # Índices
            print("\n--- ÍNDICES ---")
            print(f"Número total de índices: {stats['indexes'].get('total_count', 0)}")
            print(f"Tamaño total de índices: {stats['indexes'].get('total_size_mb', 0):,.2f} MB")
            print(f"Ratio de índices/datos: {stats['performance'].get('index_ratio', 0):,.2f}")
            
            # Colecciones más grandes
            print("\n--- COLECCIONES MÁS GRANDES ---")
            collections = stats.get('collections', [])
            if collections:
                # Mostrar las 5 colecciones más grandes
                top_collections = collections[:5]
                for i, col in enumerate(top_collections, 1):
                    print(f"{i}. {col['name']}: {col['size_mb']:,.2f} MB, {col['count']:,} documentos, {col['num_indexes']} índices")
            else:
                print("No hay información de colecciones disponible")
                
            # Problemas detectados
            if stats.get('issues'):
                print("\n--- PROBLEMAS DETECTADOS ---")
                for issue in stats['issues']:
                    print(f"- {issue}")
            
            # Preguntar si se desea un informe detallado de colecciones
            show_detail = input("\n¿Desea ver detalles de todas las colecciones? (s/n): ").lower() == 's'
            if show_detail and collections:
                print("\n" + "="*60)
                print("DETALLES DE COLECCIONES")
                print("="*60)
                
                for col in collections:
                    print(f"\nColección: {col['name']}")
                    print(f"  Documentos: {col['count']:,}")
                    print(f"  Tamaño: {col['size_mb']:,.2f} MB")
                    print(f"  Tamaño de almacenamiento: {col['storage_size_mb']:,.2f} MB")
                    print(f"  Tamaño promedio de documento: {col['avg_object_size_bytes']:,.2f} bytes")
                    print(f"  Índices: {col['num_indexes']}")
                    print(f"  Tamaño de índices: {col['index_size_mb']:,.2f} MB")
                    
                    if col.get('indexes'):
                        print("  Lista de índices:")
                        for idx in col.get('indexes', []):
                            index_name = idx.get('name', 'N/A')
                            for idx in col.get('indexes', []):
                                index_name = idx.get('name', 'N/A')
                                print(f"    - {index_name}")
            
        elif choice == "10":
            handle_user_management(db_manager)
        elif choice == "11":
            # Listar bases de datos por usuario
            username = input("Nombre de usuario a consultar: ")
            if not username.strip():
                print("Debe especificar un nombre de usuario.")
                return
                
            print(f"\nConsultando bases de datos del usuario '{username}'...")
            user_info = db_manager.get_user_databases(username)
            
            if "error" in user_info:
                print(f"Error al obtener información: {user_info['error']}")
                return
                
            if not user_info.get("user_found", False):
                print(f"No se encontró información del usuario '{username}'.")
                if "error_user_info" in user_info:
                    print(f"Error: {user_info['error_user_info']}")
                    print("Nota: Es posible que no tenga permisos suficientes para consultar usuarios.")
                return
                
            # Mostrar resumen
            print("\n" + "="*60)
            print(f"INFORMACIÓN DE BASES DE DATOS DEL USUARIO: {username}")
            print("="*60)
            
            # Roles y permisos globales
            print("\n--- ROLES DEL USUARIO ---")
            if user_info.get("roles"):
                for role in user_info["roles"]:
                    print(f"• {role['role']} en base de datos {role['db']}")
                    if role["role"] == "root":
                        print("  (Acceso completo a todas las bases de datos)")
            else:
                print("No se encontraron roles asignados.")
                
            # Resumen de acceso
            print("\n--- RESUMEN DE ACCESO ---")
            summary = user_info.get("summary", {})
            print(f"Total de bases de datos: {summary.get('total_databases', 0)}")
            print(f"Tamaño total: {summary.get('total_size_mb', 0):,.2f} MB")
            print(f"Total de colecciones: {summary.get('total_collections', 0)}")
            if summary.get("admin_access"):
                print("Tiene acceso administrativo (puede acceder a todas las bases de datos)")
                
            # Bases de datos
            if user_info.get("databases"):
                print("\n--- BASES DE DATOS ---")
                for i, db in enumerate(user_info["databases"], 1):
                    db_name = db.get("name", "Desconocido")
                    size_mb = db.get("size_mb", 0)
                    collections = db.get("collections", 0)
                    access = db.get("access_level", "desconocido")
                    permissions = ", ".join(db.get("permissions", []))
                    
                    print(f"{i}. {db_name}")
                    if "error_stats" in db:
                        print(f"   Error al obtener estadísticas: {db['error_stats']}")
                    else:
                        print(f"   Tamaño: {size_mb:,.2f} MB")
                        print(f"   Colecciones: {collections}")
                        print(f"   Nivel de acceso: {access}")
                        print(f"   Permisos: {permissions}")
        elif choice == "12":
            # Depurar bases de datos de usuario
            username = input("Nombre de usuario cuyas bases de datos desea depurar: ")
            if not username.strip():
                print("Debe especificar un nombre de usuario.")
                return
                
            print("\n--- OPCIONES DE DEPURACIÓN ---")
            print("Seleccione las tareas de depuración a realizar:")
            
            remove_empty = input("¿Eliminar colecciones vacías? (s/n): ").lower() == 's'
            optimize_indexes = input("¿Optimizar índices? (s/n): ").lower() == 's'
            compact_data = input("¿Compactar datos? (s/n): ").lower() == 's'
            remove_temp = input("¿Eliminar datos temporales? (s/n): ").lower() == 's'
            remove_backups = input("¿Eliminar copias de seguridad antiguas? (s/n): ").lower() == 's'
            
            max_backup_age = 30
            if remove_backups:
                age_str = input("Edad máxima de copias de seguridad a mantener (días, Enter para 30): ")
                if age_str.strip() and age_str.isdigit():
                    max_backup_age = int(age_str)
            
            if not any([remove_empty, optimize_indexes, compact_data, remove_temp, remove_backups]):
                print("No se seleccionó ninguna tarea de depuración. Operación cancelada.")
                return
                
            # Confirmar antes de proceder
            confirm = input(f"\n¿Está seguro de que desea depurar las bases de datos del usuario '{username}'? Esta operación puede eliminar datos. (s/n): ").lower() == 's'
            if not confirm:
                print("Operación cancelada.")
                return
                
            # Configurar opciones
            options = {
                "remove_empty_collections": remove_empty,
                "optimize_indexes": optimize_indexes,
                "compact_data": compact_data,
                "remove_temp_data": remove_temp,
                "remove_old_backups": remove_backups,
                "max_backup_age_days": max_backup_age
            }
            
            print(f"\nIniciando depuración de bases de datos para el usuario '{username}'...")
            print("Este proceso puede tomar tiempo dependiendo del tamaño de las bases de datos.")
            
            results = db_manager.cleanup_user_databases(username, options)
            
            if "error" in results:
                print(f"Error durante la depuración: {results['error']}")
                return
                
            # Mostrar resultados
            print("\n" + "="*60)
            print(f"RESULTADO DE DEPURACIÓN PARA: {username}")
            print("="*60)
            
            # Resumen de operaciones
            details = results.get("details", {})
            print(f"\nResumen: {results.get('summary', 'No hay información disponible')}")
            print(f"Colecciones vacías eliminadas: {details.get('empty_collections_removed', 0)}")
            print(f"Índices optimizados: {details.get('indexes_optimized', 0)}")
            print(f"Colecciones compactadas: {details.get('collections_compacted', 0)}")
            print(f"Datos temporales eliminados: {details.get('temp_data_removed', 0)}")
            print(f"Copias de seguridad antiguas eliminadas: {details.get('backups_removed', 0)}")
            
            # Bases de datos afectadas
            if results.get("databases_affected"):
                print("\n--- BASES DE DATOS AFECTADAS ---")
                for db in results.get("databases_affected", []):
                    print(f"\nBase de datos: {db.get('name', 'N/A')}")
                    print(f"  Colecciones afectadas: {len(db.get('collections_affected', []))}")
                    if db.get("actions"):
                        for action in db.get("actions", [])[:5]:  # Mostrar primeras 5 acciones
                            print(f"  - {action}")
                        if len(db.get("actions", [])) > 5:
                            print(f"  ... y {len(db.get('actions', [])) - 5} acciones más.")
            
            # Errores
            if details.get("errors"):
                print("\n--- ERRORES DURANTE LA DEPURACIÓN ---")
                for error in details.get("errors", [])[:5]:
                    print(f"- {error}")
                if len(details.get("errors", [])) > 5:
                    print(f"... y {len(details.get('errors', [])) - 5} errores más.")
                    
            # Preguntar si se desea exportar el informe completo
            export_report = input("\n¿Desea exportar el informe completo a un archivo JSON? (s/n): ").lower() == 's'
            if export_report:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"cleanup_report_{username}_{timestamp}.json"
                try:
                    with open(os.path.join("respaldos", filename), 'w', encoding='utf-8') as f:
                        f.write(serialize_to_json(results, format_type='detailed'))
                    print(f"Informe exportado a: {os.path.join('respaldos', filename)}")
                except Exception as e:
                    print(f"Error al exportar informe: {e}")
        else:
            print("Opción no implementada o no válida.")
    except Exception as e:
        logger.error(f"Error en la opción {choice}: {e}")
        print(f"Error: {e}")

def handle_export_import(db_manager, operation):
    collection_name = input("Nombre de la colección: ")
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
    print("\n--- GESTIÓN DE USUARIOS ---")
    print("1. Listar todos los usuarios")
    print("2. Buscar usuario por ID")
    print("3. Buscar usuario por nombre")
    print("4. Editar usuario")
    print("5. Eliminar usuario")
    print("0. Volver al menú principal")
    choice = input("Seleccione una opción: ")
    try:
        if choice == "1":
            users = db_manager.find_documents("users", {}, limit=100)
            print("\nUsuarios registrados:")
            for i, user in enumerate(users, 1):
                print(f"{i}. ID: {user.get('_id')} - Nombre: {user.get('name')} - Email: {user.get('email')}")
        elif choice == "2":
            user_id = input("ID del usuario: ")
            user = db_manager.get_user_by_id(user_id)
            if user:
                print("Información del usuario:")
                print(serialize_to_json(user))
            else:
                print("Usuario no encontrado.")
        elif choice == "3":
            name = input("Nombre del usuario: ")
            users = db_manager.find_documents("users", {"name": {"$regex": name, "$options": "i"}}, limit=10)
            if users:
                print("Usuarios encontrados:")
                for i, user in enumerate(users, 1):
                    print(f"{i}. ID: {user.get('_id')} - Nombre: {user.get('name')} - Email: {user.get('email')}")
            else:
                print("No se encontraron usuarios.")
        elif choice == "4":
            user_id = input("ID del usuario a editar: ")
            user = db_manager.get_user_by_id(user_id)
            if not user:
                print("Usuario no encontrado.")
                return
            print("Datos actuales del usuario:")
            print(serialize_to_json(user))
            field = input("Campo a modificar: ")
            new_value = input(f"Nuevo valor para {field}: ")
            update = {"$set": {field: new_value}}
            modified = db_manager.update_document("users", {"_id": user.get("_id")}, update)
            if modified:
                print("Usuario actualizado correctamente.")
            else:
                print("No se pudo actualizar el usuario.")
        elif choice == "5":
            user_id = input("ID del usuario a eliminar: ")
            confirm = input(f"¿Está seguro de eliminar el usuario con ID {user_id}? (s/n): ")
            if confirm.lower() == 's':
                user = db_manager.get_user_by_id(user_id)
                if not user:
                    print("Usuario no encontrado.")
                    return
                deleted = db_manager.delete_document("users", {"_id": user.get("_id")})
                if deleted:
                    print("Usuario eliminado correctamente.")
                else:
                    print("Error al eliminar el usuario.")
        elif choice == "0":
            return
        else:
            print("Opción no válida.")
    except Exception as e:
        logger.error(f"Error en la gestión de usuarios: {e}")
        print(f"Error: {e}")

print("MONGODB_URI:", os.environ.get("MONGODB_URI"))

def main():
    try:
        parser = argparse.ArgumentParser(description="Herramienta de gestión de bases de datos MongoDB")
        parser.add_argument("--uri", type=str, help="URI de conexión a MongoDB", default=get_mongodb_uri())
        parser.add_argument("--db", type=str, help="Nombre de la base de datos a utilizar", default="test")
        parser.add_argument("--debug", action="store_true", help="Activar modo debug")
        args = parser.parse_args()
        
        db_manager = DatabaseManager(connection_uri=args.uri, database_name=args.db, debug=args.debug)
        if not db_manager.client:
            print("Error: No se pudo conectar a la base de datos.")
            sys.exit(1)
        
        while True:
            try:
                display_menu(db_manager)
                choice = input("Seleccione una opción: ").strip()
                if choice == "0":
                    print("Saliendo de la aplicación...")
                    break
                handle_choice(choice, db_manager)
                input("\nPresione Enter para continuar...")
            except EOFError:
                print("\nError de entrada/salida. Intente nuevamente.")
                continue
            except KeyboardInterrupt:
                print("\nOperación cancelada por el usuario.")
                break
    except Exception as e:
        logger.error(f"Error en la aplicación: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
