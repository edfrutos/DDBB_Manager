"""
Verification script to:
1. Examine the contents of users_unified collection
2. Verify that fields are normalized (name, role, email)
3. Confirm users from original collections were migrated correctly
4. Generate a report of the current data structure
"""

import os
import sys
from dotenv import load_dotenv
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime
from bson import ObjectId
import json
import pprint

# Function to format MongoDB documents for pretty printing
def format_doc_for_print(doc):
    if isinstance(doc, dict):
        # Convert ObjectId to string
        if '_id' in doc and isinstance(doc['_id'], ObjectId):
            doc['_id'] = str(doc['_id'])
        # Convert any dates to strings
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
    return doc

# Connect to MongoDB
def connect_to_mongodb():
    print("Connecting to MongoDB...")
    load_dotenv()  # Load environment variables from .env file
    
    # Get connection string from environment or use default
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("Error: MONGODB_URI environment variable not found")
        sys.exit(1)
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        
        # Verify connection
        client.admin.command('ping')
        print("Connected to MongoDB successfully")
        
        # Connect to database
        db = client["app_catalogojoyero"]
        print(f"Connected to database: app_catalogojoyero")
        
        return client, db
    except ConnectionFailure as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)

# Examine collections and users
def verify_migration(db):
    print("\n--- VERIFICATION REPORT ---")
    
    # Check if collections exist
    collections = db.list_collection_names()
    print(f"Available collections: {collections}")
    
    # Check if needed collections exist
    required_collections = ["users", "usuarios", "admins", "users_unified"]
    missing_collections = [coll for coll in required_collections if coll not in collections]
    
    if missing_collections:
        print(f"Warning: Missing collections: {missing_collections}")
    
    # Count documents in each collection
    users_count = db.users.count_documents({}) if "users" in collections else 0
    usuarios_count = db.usuarios.count_documents({}) if "usuarios" in collections else 0
    admins_count = db.admins.count_documents({}) if "admins" in collections else 0
    unified_count = db.users_unified.count_documents({}) if "users_unified" in collections else 0
    
    print(f"\nDocument counts:")
    print(f"- users: {users_count} documents")
    print(f"- usuarios: {usuarios_count} documents")
    print(f"- admins: {admins_count} documents")
    print(f"- users_unified: {unified_count} documents")
    
    # Expected total
    expected_total = users_count + usuarios_count + admins_count
    if unified_count < expected_total:
        print(f"Warning: users_unified contains fewer documents ({unified_count}) than the source collections ({expected_total})")
    
    # Examine unified collection fields
    if "users_unified" in collections:
        print("\nExamining fields in users_unified:")
        
        # Get a sample document
        sample_doc = db.users_unified.find_one()
        if sample_doc:
            print("\nSample document fields:")
            for field in sample_doc.keys():
                print(f"- {field}")
            
            # Check for normalized fields
            normalized_fields = ["name", "email", "role"]
            missing_normalized = [field for field in normalized_fields if field not in sample_doc]
            
            if missing_normalized:
                print(f"\nWarning: Missing normalized fields: {missing_normalized}")
            else:
                print("\nAll expected normalized fields (name, email, role) are present")
        else:
            print("No documents found in users_unified")
    
    # Compare source collections with unified collection
    print("\nVerifying migration integrity:")
    verify_original_users(db)

def verify_original_users(db):
    # Get all users from source collections
    all_source_users = []
    
    # From users collection
    if "users" in db.list_collection_names():
        for user in db.users.find():
            user['_source_collection'] = 'users'
            all_source_users.append(user)
    
    # From usuarios collection
    if "usuarios" in db.list_collection_names():
        for user in db.usuarios.find():
            user['_source_collection'] = 'usuarios'
            all_source_users.append(user)
    
    # From admins collection
    if "admins" in db.list_collection_names():
        for user in db.admins.find():
            user['_source_collection'] = 'admins'
            all_source_users.append(user)
    
    print(f"Total source users: {len(all_source_users)}")
    
    # Check if each user has been migrated
    if "users_unified" not in db.list_collection_names():
        print("users_unified collection does not exist")
        return
    
    # Get all users from unified collection
    unified_users = list(db.users_unified.find())
    print(f"Total unified users: {len(unified_users)}")
    
    # Map original IDs to unified collection
    source_ids = [str(user['_id']) for user in all_source_users]
    unified_ids = []
    
    for user in unified_users:
        if '_original_id' in user:
            unified_ids.append(str(user['_original_id']))
        else:
            unified_ids.append(str(user['_id']))
    
    # Find missing users
    missing_users = [id for id in source_ids if id not in unified_ids]
    
    if missing_users:
        print(f"Warning: {len(missing_users)} users from original collections are missing in unified collection")
        print("Missing IDs:")
        for id in missing_users[:5]:  # Show first 5 missing IDs
            print(f"- {id}")
        if len(missing_users) > 5:
            print(f"... and {len(missing_users) - 5} more")
    else:
        print("All users from original collections have been migrated successfully")
    
    # Examine field normalization in unified collection
    if unified_users:
        field_stats = {
            "name": 0,
            "email": 0,
            "role": 0,
            "_source_collection": 0
        }
        
        for user in unified_users:
            for field in field_stats.keys():
                if field in user:
                    field_stats[field] += 1
        
        print("\nNormalized field statistics:")
        for field, count in field_stats.items():
            percentage = (count / len(unified_users)) * 100
            print(f"- {field}: {count}/{len(unified_users)} documents ({percentage:.1f}%)")
        
        # Print a few example users
        print("\nSample unified users:")
        for user in unified_users[:3]:  # Show first 3 users
            # Format the document for printing
            formatted_user = format_doc_for_print(user)
            pprint.pprint(formatted_user)

def main():
    print("User Migration Verification Tool")
    print("===============================")
    
    client, db = connect_to_mongodb()
    verify_migration(db)
    
    # Close the MongoDB connection
    client.close()
    print("\nVerification complete")

if __name__ == "__main__":
    main()

