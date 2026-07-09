#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv
from bson import json_util

def parse_json(data):
    """Convert MongoDB data to JSON format"""
    return json.loads(json_util.dumps(data))

def print_collection_info(collection, name):
    """Print information about a collection"""
    try:
        count = collection.count_documents({})
        print(f"\n{'='*50}")
        print(f"Colección: {name} ({count} documentos)")
        print(f"{'='*50}")
        
        # Get indexes
        indexes = list(collection.list_indexes())
        print(f"\nÍndices existentes ({len(indexes)}):")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['key']}")
        
        # Analyze a sample document if there are any
        if count > 0:
            sample = collection.find_one()
            print("\nEstructura de un documento de muestra:")
            for key, value in sample.items():
                value_type = type(value).__name__
                print(f"  - {key}: {value_type}")
        else:
            print("\nLa colección está vacía. No hay documentos para analizar.")
    
    except Exception as e:
        print(f"Error al analizar la colección {name}: {str(e)}")

def create_indexes(collection, name):
    """Create necessary indexes on a collection"""
    print(f"\nCreando índices en la colección {name}...")
    
    indexes_created = 0
    
    try:
        # Common fields to index for user collections
        index_fields = [
            ("email", ASCENDING, True),       # Email as unique index
            ("nombre", ASCENDING, False),     # Name (Spanish)
            ("name", ASCENDING, False)        # Name (English)
        ]
        
        for field, direction, unique in index_fields:
            # Check if the field exists in at least one document
            field_exists = collection.find_one({field: {"$exists": True}})
            
            if field_exists:
                # Create the index if it doesn't exist
                try:
                    collection.create_index(
                        [(field, direction)], 
                        unique=unique, 
                        background=True,
                        name=f"{field}_idx"
                    )
                    print(f"  - Índice creado: {field}_idx ({'único' if unique else 'no único'})")
                    indexes_created += 1
                except OperationFailure as e:
                    # If there's a duplicate key error, create a non-unique index instead
                    if unique and "duplicate" in str(e).lower():
                        collection.create_index(
                            [(field, direction)], 
                            unique=False, 
                            background=True,
                            name=f"{field}_idx"
                        )
                        print(f"  - Índice creado (no único): {field}_idx (originalmente se intentó crear único pero hay valores duplicados)")
                        indexes_created += 1
                    else:
                        print(f"  - Error al crear índice en {field}: {str(e)}")
            else:
                print(f"  - Campo {field} no encontrado en ningún documento. Omitiendo índice.")
    
    except Exception as e:
        print(f"Error al crear índices en {name}: {str(e)}")
    
    return indexes_created

def analyze_user_fields(db):
    """Analyze fields across user collections to find inconsistencies"""
    user_collections = ['users', 'usuarios', 'admins']
    all_fields = {}
    
    print("\n\n" + "="*50)
    print("ANÁLISIS DE CAMPOS DE USUARIO ENTRE COLECCIONES")
    print("="*50)
    
    for coll_name in user_collections:
        if coll_name not in db.list_collection_names():
            continue
            
        collection = db[coll_name]
        fields = set()
        count = collection.count_documents({})
        
        if count > 0:
            # Get all fields from all documents
            pipeline = [
                {"$project": {"arrayofkeyvalue": {"$objectToArray": "$$ROOT"}}},
                {"$unwind": "$arrayofkeyvalue"},
                {"$group": {"_id": None, "allkeys": {"$addToSet": "$arrayofkeyvalue.k"}}}
            ]
            result = list(collection.aggregate(pipeline))
            if result:
                fields = set(result[0]["allkeys"])
        
        all_fields[coll_name] = fields
    
    # Find common and unique fields
    common_fields = set.intersection(*[fields for fields in all_fields.values() if fields])
    
    print("\nCampos comunes en todas las colecciones:")
    for field in sorted(common_fields):
        print(f"  - {field}")
    
    print("\nCampos por colección:")
    for coll_name, fields in all_fields.items():
        unique_fields = fields - common_fields
        print(f"\n{coll_name}:")
        for field in sorted(unique_fields):
            print(f"  - {field} (único en esta colección)")
        for field in sorted(common_fields):
            print(f"  - {field} (común)")

def main():
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB connection string
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        print("Error: No se encontró la variable de entorno MONGODB_URI")
        mongo_uri = input("Introduzca la URI de MongoDB: ")
    
    try:
        # Connect to MongoDB
        print(f"Conectando a MongoDB...")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("Conexión establecida correctamente")
        
        # Select database
        db_name = "app_catalogojoyero"  # Based on the memory rule
        db = client[db_name]
        print(f"Base de datos: {db_name}")
        
        # Get all collections
        collections = db.list_collection_names()
        print(f"Total de colecciones: {len(collections)}")
        
        # Check if user collections exist
        user_collections = ['users', 'usuarios', 'admins']
        found_collections = [coll for coll in user_collections if coll in collections]
        
        if not found_collections:
            print("No se encontraron colecciones de usuarios.")
            return
        
        print(f"\nColecciones de usuarios encontradas: {found_collections}")
        
        # Analyze each user collection
        total_indexes_created = 0
        for coll_name in found_collections:
            collection = db[coll_name]
            print_collection_info(collection, coll_name)
            indexes_created = create_indexes(collection, coll_name)
            total_indexes_created += indexes_created
        
        # Analyze fields across collections
        analyze_user_fields(db)
        
        # Print summary
        print("\n\n" + "="*50)
        print("RESUMEN")
        print("="*50)
        print(f"Colecciones de usuarios analizadas: {len(found_collections)}")
        print(f"Total de índices creados: {total_indexes_created}")
        print(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
    except ConnectionFailure as e:
        print(f"Error de conexión a MongoDB: {str(e)}")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()
            print("Conexión cerrada")

if __name__ == "__main__":
    main()

