"""
Script to create optimized indexes in the users_unified collection to improve search performance:
1. Unique indexes on email and username
2. Text index on name for partial text searches
3. Simple index on role for filtering
4. Compound index on created_at and updated_at for ordering
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, TEXT, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure

def connect_to_mongodb():
    """Connect to MongoDB and return the client and database objects"""
    print("Connecting to MongoDB...")
    load_dotenv()  # Load environment variables from .env file
    
    # Get connection string from environment
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("Error: MONGODB_URI environment variable not found")
        sys.exit(1)
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        
        # Verify connection
        client.admin.command('ping')
        print("Connected to MongoDB successfully!")
        
        # Connect to database
        db = client["app_catalogojoyero"]
        print(f"Connected to database: app_catalogojoyero")
        
        return client, db
    except ConnectionFailure as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)

def drop_existing_indexes(db, drop_all=False):
    """Drop existing indexes from the users_unified collection"""
    print("\nChecking existing indexes on users_unified collection...")
    
    if "users_unified" not in db.list_collection_names():
        print("Collection users_unified does not exist")
        return False
    
    collection = db.users_unified
    indexes = collection.index_information()
    
    # Always keep the _id index which is created by MongoDB automatically
    preserved_indexes = ["_id_"]
    
    # Define our target index names
    target_indexes = [
        "email_unique", 
        "username_unique", 
        "name_text", 
        "role_index", 
        "date_sorting_index"
    ]
    
    # List conflicting indexes (indexes on the same fields with different names)
    conflicting_indexes = []
    for idx_name, idx_info in indexes.items():
        if idx_name in preserved_indexes:
            continue
            
        # Check if we should drop this index
        should_drop = drop_all or idx_name in target_indexes
        
        # Also check for conflicting indexes on the same fields
        if not should_drop:
            # Check email index conflict
            if 'email' in [key[0] for key in idx_info.get('key', [])]:
                conflicting_indexes.append(idx_name)
                should_drop = True
            
            # Check username index conflict
            elif 'username' in [key[0] for key in idx_info.get('key', [])]:
                conflicting_indexes.append(idx_name)
                should_drop = True
                
            # Check name text index conflict
            elif any(key[0] == 'name' and key[1] == 'text' for key in idx_info.get('key', [])):
                conflicting_indexes.append(idx_name)
                should_drop = True
                
            # Check role index conflict
            elif 'role' in [key[0] for key in idx_info.get('key', [])]:
                conflicting_indexes.append(idx_name)
                should_drop = True
                
            # Check date index conflicts
            elif 'created_at' in [key[0] for key in idx_info.get('key', [])] or \
                 'updated_at' in [key[0] for key in idx_info.get('key', [])]:
                conflicting_indexes.append(idx_name)
                should_drop = True
        
        if should_drop:
            try:
                print(f"Dropping index: {idx_name}")
                collection.drop_index(idx_name)
            except Exception as e:
                print(f"Error dropping index {idx_name}: {e}")
                return False
    
    if conflicting_indexes:
        print(f"Dropped {len(conflicting_indexes)} conflicting indexes: {', '.join(conflicting_indexes)}")
    elif not drop_all:
        print("No conflicting indexes found")
    else:
        print("Dropped all existing custom indexes")
        
    return True

def create_indexes(db, recreate=False):
    """Create the specified indexes on the users_unified collection"""
    print("\nCreating optimized indexes on users_unified collection...")
    
    # Check if collection exists
    if "users_unified" not in db.list_collection_names():
        print("Error: users_unified collection does not exist")
        return False
    
    collection = db.users_unified
    
    # Check if indexes already exist and drop if recreate is True
    if recreate:
        if not drop_existing_indexes(db, drop_all=True):
            print("Failed to drop existing indexes, aborting index creation")
            return False
    else:
        # Just drop conflicting indexes
        if not drop_existing_indexes(db, drop_all=False):
            print("Failed to handle conflicting indexes, aborting index creation")
            return False
    
    # Get existing indexes after potential drops
    existing_indexes = collection.index_information().keys()
    results = []
    
    # Create indexes only if they don't exist
    try:
        # 1. Unique index on email
        if "email_unique" not in existing_indexes:
            print("Creating unique index on email field...")
            try:
                email_index = collection.create_index("email", unique=True, name="email_unique")
                results.append(("email_unique", email_index))
            except OperationFailure as e:
                print(f"Warning: Could not create email_unique index: {e}")
        else:
            print("Email index already exists, skipping...")
        
        # 1b. Unique index on username
        if "username_unique" not in existing_indexes:
            print("Creating unique index on username field...")
            try:
                username_index = collection.create_index("username", unique=True, name="username_unique")
                results.append(("username_unique", username_index))
            except OperationFailure as e:
                print(f"Warning: Could not create username_unique index: {e}")
        else:
            print("Username index already exists, skipping...")
        
        # 2. Text index on name for partial text searches
        if "name_text" not in existing_indexes:
            print("Creating text index on name field for partial text searches...")
            try:
                name_index = collection.create_index([("name", TEXT)], default_language="spanish", name="name_text")
                results.append(("name_text", name_index))
            except OperationFailure as e:
                print(f"Warning: Could not create name_text index: {e}")
        else:
            print("Name text index already exists, skipping...")
        
        # 3. Simple index on role for filtering
        if "role_index" not in existing_indexes:
            print("Creating index on role field for filtering...")
            try:
                role_index = collection.create_index("role", name="role_index")
                results.append(("role_index", role_index))
            except OperationFailure as e:
                print(f"Warning: Could not create role_index: {e}")
        else:
            print("Role index already exists, skipping...")
        
        # 4. Compound index on created_at and updated_at for sorting
        if "date_sorting_index" not in existing_indexes:
            print("Creating compound index on created_at and updated_at for sorting...")
            try:
                date_index = collection.create_index([
                    ("created_at", DESCENDING), 
                    ("updated_at", DESCENDING)
                ], name="date_sorting_index")
                results.append(("date_sorting_index", date_index))
            except OperationFailure as e:
                print(f"Warning: Could not create date_sorting_index: {e}")
        else:
            print("Date sorting index already exists, skipping...")
        
        if results:
            print(f"\nCreated {len(results)} indexes successfully!")
        else:
            print("\nNo new indexes were created")
        return True
    
    except Exception as e:
        print(f"Error creating indexes: {e}")
        return False

def verify_indexes(db):
    """Verify that the indexes were created successfully"""
    print("\nVerifying indexes on users_unified collection...")
    
    collection = db.users_unified
    indexes = collection.index_information()
    
    print("\nCurrent indexes:")
    for name, index_info in indexes.items():
        print(f"- {name}: {index_info}")
    
    # Check for expected indexes
    expected_indexes = [
        "email_unique", 
        "username_unique", 
        "name_text", 
        "role_index", 
        "date_sorting_index"
    ]
    
    missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
    
    if missing_indexes:
        print(f"\nWarning: The following indexes are missing: {missing_indexes}")
    else:
        print("\nAll expected indexes are present.")
def main():
    """Main function to create and verify indexes"""
    print("MongoDB Index Creation Tool")
    print("===========================")
    
    # Add argument parsing for more flexibility
    import argparse
    parser = argparse.ArgumentParser(description='Create optimized indexes for the users_unified collection')
    parser.add_argument('--recreate', action='store_true', help='Drop all existing indexes and recreate them')
    args = parser.parse_args()
    
    client, db = connect_to_mongodb()
    
    # Create indexes
    success = create_indexes(db, recreate=args.recreate)
    
    if success:
        # Verify indexes
        verify_indexes(db)
    
    # Close MongoDB connection
    client.close()
    print("\nIndex creation completed.")

if __name__ == "__main__":
    main()

