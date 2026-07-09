#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, DuplicateKeyError
from dotenv import load_dotenv
from bson import ObjectId, json_util

# Configuración de normalización de campos
FIELD_MAPPINGS = {
    'nombre': 'name',  # Estandarizar a name
    'rol': 'role',     # Estandarizar a role
}

# Esquema estándar para todos los usuarios
STANDARD_SCHEMA = {
    'name': '',        # Nombre del usuario
    'email': '',       # Email (único)
    'username': '',    # Nombre de usuario (único)
    'role': 'user',    # Rol de usuario (user, admin, etc.)
    'password': None,  # Contraseña (hash)
    'last_login': None,  # Último acceso
    'created_at': None,  # Fecha de creación
    'updated_at': None,  # Fecha de actualización
}

def parse_json(data):
    """Convert MongoDB data to JSON format"""
    return json.loads(json_util.dumps(data))

def get_timestamp():
    """Get current timestamp for logging"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def normalize_user_data(user_doc, source_collection):
    """Normalize user data to standard schema"""
    # Start with standard schema
    normalized_user = dict(STANDARD_SCHEMA)
    
    # Keep original _id
    normalized_user['_id'] = user_doc.get('_id')
    
    # Source tracking for debugging/auditing
    normalized_user['_source_collection'] = source_collection
    
    # Apply field mappings and copy data
    for field, value in user_doc.items():
        if field == '_id':
            continue
            
        # Check if field needs to be mapped
        if field in FIELD_MAPPINGS:
            target_field = FIELD_MAPPINGS[field]
            # Only copy if target field is empty or source has value
            if not normalized_user[target_field] and value:
                normalized_user[target_field] = value
        elif field in STANDARD_SCHEMA:
            # Direct copy for standard fields
            normalized_user[field] = value
        else:
            # Preserve non-standard fields
            normalized_user[field] = value
    
    # Ensure we have a username if missing
    if not normalized_user.get('username') and normalized_user.get('email'):
        normalized_user['username'] = normalized_user['email'].split('@')[0]
    
    # Set timestamps if missing
    current_time = datetime.now()
    if not normalized_user.get('created_at'):
        normalized_user['created_at'] = current_time
    if not normalized_user.get('updated_at'):
        normalized_user['updated_at'] = current_time
        
    return normalized_user

def validate_migration(source_collections, target_collection, db):
    """Validate that the migration has been successful"""
    # Count documents in source collections
    source_count = sum(db[coll].count_documents({}) for coll in source_collections)
    
    # Count documents in target collection
    target_count = db[target_collection].count_documents({})
    
    print(f"\nValidating migration:")
    print(f"  - Total documents in source collections: {source_count}")
    print(f"  - Total documents in target collection: {target_count}")
    
    if target_count < source_count:
        print(f"  ⚠️ WARNING: Target collection has fewer documents than source collections")
        return False
    
    # Check for required fields
    missing_fields = []
    for doc in db[target_collection].find():
        for field in ['name', 'email', 'username', 'role']:
            if not doc.get(field):
                missing_fields.append(f"Document {doc['_id']} is missing required field '{field}'")
    
    if missing_fields:
        print(f"  ⚠️ WARNING: Found documents with missing required fields:")
        for msg in missing_fields[:5]:  # Show only first 5 to avoid overflow
            print(f"    - {msg}")
        if len(missing_fields) > 5:
            print(f"    ... and {len(missing_fields) - 5} more.")
        return False
    
    print(f"  ✅ Validation passed. All documents have been migrated correctly.")
    return True

def create_user_validation_schema(db, collection_name):
    """Create a validation schema for the users collection"""
    schema = {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "email", "username", "role"],
                "properties": {
                    "name": {
                        "bsonType": "string",
                        "description": "Nombre completo del usuario"
                    },
                    "email": {
                        "bsonType": "string",
                        "description": "Correo electrónico del usuario",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    },
                    "username": {
                        "bsonType": "string",
                        "description": "Nombre de usuario para login"
                    },
                    "role": {
                        "bsonType": "string",
                        "description": "Rol del usuario (user, admin, etc.)",
                        "enum": ["user", "admin", "editor", "viewer"]
                    },
                    "password": {
                        "bsonType": ["string", "null"],
                        "description": "Contraseña (hash)"
                    },
                    "created_at": {
                        "bsonType": ["date", "null"],
                        "description": "Fecha de creación del usuario"
                    },
                    "updated_at": {
                        "bsonType": ["date", "null"],
                        "description": "Fecha de última actualización"
                    },
                    "last_login": {
                        "bsonType": ["date", "null"],
                        "description": "Fecha de último acceso"
                    }
                }
            }
        },
        "validationLevel": "moderate"
    }
    
    try:
        # If collection already exists, use collMod, otherwise it will be created with validator
        if collection_name in db.list_collection_names():
            db.command("collMod", collection_name, **schema)
        
        print(f"Validation schema created for collection '{collection_name}'")
        return True
    except Exception as e:
        print(f"Error creating validation schema: {str(e)}")
        return False

def migrate_users(db, source_collections, target_collection, dry_run=False):
    """Migrate users from source collections to target collection with normalization"""
    temp_collection = f"{target_collection}_temp_{int(time.time())}"
    
    # Create temporary collection
    if not dry_run:
        if temp_collection in db.list_collection_names():
            db[temp_collection].drop()
        
        # Create unique indexes on the temporary collection
        db[temp_collection].create_index("email", unique=True)
        db[temp_collection].create_index("username", unique=True)
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating users to '{temp_collection if not dry_run else target_collection}'...")
    
    # Track statistics
    total_processed = 0
    total_migrated = 0
    total_errors = 0
    duplicate_emails = set()
    duplicate_usernames = set()
    
    # Process each source collection
    for source_coll in source_collections:
        if source_coll not in db.list_collection_names():
            print(f"  - Collection '{source_coll}' not found, skipping...")
            continue
            
        print(f"  - Processing '{source_coll}'...")
        count = db[source_coll].count_documents({})
        
        # Skip empty collections
        if count == 0:
            print(f"    - Collection is empty, skipping...")
            continue
            
        # Process each document
        for doc in db[source_coll].find():
            total_processed += 1
            normalized_user = normalize_user_data(doc, source_coll)
            
            # Skip inserting in dry run mode
            if dry_run:
                total_migrated += 1
                continue
                
            try:
                db[temp_collection].insert_one(normalized_user)
                total_migrated += 1
            except DuplicateKeyError as e:
                total_errors += 1
                error_msg = str(e)
                
                # Track duplicate fields for reporting
                if "email" in error_msg:
                    duplicate_emails.add(normalized_user.get("email"))
                elif "username" in error_msg:
                    duplicate_usernames.add(normalized_user.get("username"))
                
                print(f"    ⚠️ Error inserting document: {error_msg}")
                
                # Try to insert with modified fields to avoid data loss
                try:
                    if "email" in error_msg:
                        # Append source collection name to make unique
                        normalized_user["email"] = f"{normalized_user['email']}.{source_coll}"
                    if "username" in error_msg:
                        normalized_user["username"] = f"{normalized_user['username']}_{source_coll}"
                    
                    db[temp_collection].insert_one(normalized_user)
                    print(f"    ✓ Inserted with modified fields to avoid duplication")
                    total_migrated += 1
                except Exception as e2:
                    print(f"    ❌ Failed to insert even with modified fields: {str(e2)}")
    
    # Create validation schema if not dry run
    if not dry_run:
        create_user_validation_schema(db, temp_collection)
    
    # Print statistics
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migration Summary:")
    print(f"  - Total documents processed: {total_processed}")
    print(f"  - Total documents migrated: {total_migrated}")
    print(f"  - Total errors: {total_errors}")
    
    if duplicate_emails:
        print(f"  - Duplicate emails found ({len(duplicate_emails)}):")
        for email in list(duplicate_emails)[:5]:  # Show max 5
            print(f"    - {email}")
        if len(duplicate_emails) > 5:
            print(f"      ... and {len(duplicate_emails) - 5} more")
    
    if duplicate_usernames:
        print(f"  - Duplicate usernames found ({len(duplicate_usernames)}):")
        for username in list(duplicate_usernames)[:5]:  # Show max 5
            print(f"    - {username}")
        if len(duplicate_usernames) > 5:
            print(f"      ... and {len(duplicate_usernames) - 5} more")
    
    # Validate migration if not dry run
    if not dry_run:
        is_valid = validate_migration(source_collections, temp_collection, db)
        return temp_collection, is_valid
    
    return None, True

def finalize_migration(db, temp_collection, target_collection, backup_suffix="_backup"):
    """Finalize migration by replacing the target collection with the temporary one"""
    print(f"\nFinalizing migration...")
    
    # Backup existing collection if it exists
    if target_collection in db.list_collection_names():
        backup_name = f"{target_collection}{backup_suffix}_{int(time.time())}"
        print(f"  - Backing up existing '{target_collection}' to '{backup_name}'")
        
        # Rename the existing collection to backup
        db[target_collection].rename(backup_name)
    
    # Rename the temporary collection to the target name
    print(f"  - Renaming '{temp_collection}' to '{target_collection}'")
    db[temp_collection].rename(target_collection)
    
    # Create indexes on the new collection (they should already exist but to be safe)
    print(f"  - Creating indexes on '{target_collection}'")
    db[target_collection].create_index("email", unique=True)
    db[target_collection].create_index("username", unique=True)
    db[target_collection].create_index("name")
    db[target_collection].create_index("role")
    
    print(f"  ✅ Migration completed successfully.")
    return True

def main():
    # Configuration
    source_collections = ['users', 'usuarios', 'admins']  # Collections to consolidate
    target_collection = 'users_unified'  # Final collection name
    
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB connection string
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        print("Error: No se encontró la variable de entorno MONGODB_URI")
        mongo_uri = input("Introduzca la URI de MongoDB: ")
    
    try:
        # Connect to MongoDB
        print(f"{get_timestamp()} Conectando a MongoDB...")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print(f"{get_timestamp()} Conexión establecida correctamente")
        
        # Select database
        db_name = "app_catalogojoyero"  # Based on the memory rule
        db = client[db_name]
        print(f"{get_timestamp()} Base de datos: {db_name}")
        
        # Check source collections
        all_collections = db.list_collection_names()
        existing_sources = [coll for coll in source_collections if coll in all_collections]
        
        if not existing_sources:
            print(f"{get_timestamp()} No se encontraron colecciones de usuario para migrar.")
            return
            
        print(f"{get_timestamp()} Colecciones de usuario encontradas: {existing_sources}")
        
        # First do a dry run to check for issues
        print(f"\n{get_timestamp()} INICIO DE SIMULACIÓN (dry run)")
        print("="*80)
        migrate_users(db, existing_sources, target_collection, dry_run=True)
        print("="*80)
        print(f"{get_timestamp()} FIN DE SIMULACIÓN")
        
        # Ask for confirmation before proceeding
        print("\n¡ATENCIÓN! Esta operación modificará la base de datos.")
        print("Los datos originales se respaldarán, pero es recomendable tener un backup adicional.")
        
        confirm = input("\n¿Desea continuar con la migración real? (s/n): ").lower()
        if confirm != 's':
            print("Operación cancelada por el usuario.")
            return
        
        # Perform the actual migration
        print(f"\n{get_timestamp()} INICIO DE MIGRACIÓN REAL")
        print("="*80)
        
        # Do the migration
        temp_collection, is_valid = migrate_users(db, existing_sources, target_collection)
        
        if is_valid:
            print(f"\n{get_timestamp()} La migración ha sido validada correctamente.")
            
            # Ask for final confirmation before replacing collections
            final_confirm = input("\n¿Desea finalizar la migración y reemplazar la colección actual? (s/n): ").lower()
            if final_confirm != 's':
                print("Finalizando sin reemplazar las colecciones originales.")
                print(f"La colección temporal '{temp_collection}' contiene los datos migrados.")
                return
            
            # Finalize the migration
            finalize_migration(db, temp_collection, target_collection)
            print(f"\n{get_timestamp()} MIGRACIÓN COMPLETADA EXITOSAMENTE")
            print(f"Todos los usuarios han sido migrados a la colección '{target_collection}'")
        else:
            print(f"\n{get_timestamp()} ERROR: La migración no pasó la validación.")
            print(f"La colección temporal '{temp_collection}' contiene los datos migrados, pero no se reemplazarán las colecciones originales.")
            
    except ConnectionFailure as e:
        print(f"{get_timestamp()} Error de conexión a MongoDB: {str(e)}")
    except Exception as e:
        print(f"{get_timestamp()} Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if 'client' in locals():
            client.close()
            print(f"{get_timestamp()} Conexión cerrada")


if __name__ == "__main__":
    main()
