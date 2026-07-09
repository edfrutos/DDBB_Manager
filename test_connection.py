#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MongoDB Connection Test Script
This script verifies the connection to MongoDB using the URI from the .env file.
"""

import os
import sys
import traceback
from dotenv import load_dotenv

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    print("PyMongo is required. Install it using: pip install pymongo")
    sys.exit(1)

def test_mongodb_connection():
    """Test MongoDB connection using environment variables"""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get MongoDB URI from environment variables
    mongodb_uri = os.environ.get("MONGODB_URI")
    
    if not mongodb_uri:
        print("ERROR: MONGODB_URI environment variable not found in .env file")
        print("Make sure you have a .env file with a valid MONGODB_URI variable")
        return False
    
    # Mask password in URI for safe display
    display_uri = mongodb_uri
    if "@" in mongodb_uri:
        parts = mongodb_uri.split("@")
        auth_part = parts[0]
        if ":" in auth_part:
            user_part = auth_part.split(":")[0]
            display_uri = f"{user_part}:****@{parts[1]}"
    
    print(f"Connection URI: {display_uri}")
    
    try:
        # Create a MongoDB client with a 5-second timeout
        print("\nAttempting to connect to MongoDB...")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        
        # Verify connection with ping
        print("Verifying connection with server ping...")
        client.admin.command('ping')
        print("✓ Server ping successful")
        
        # Get server info
        server_info = client.server_info()
        print(f"✓ Connected to MongoDB server version: {server_info.get('version', 'unknown')}")
        
        # Connect to the database
        db_name = "app_catalogojoyero"
        print(f"\nConnecting to database '{db_name}'...")
        db = client[db_name]
        
        # List collections
        print("Listing collections...")
        collections = db.list_collection_names()
        if collections:
            print(f"✓ Found {len(collections)} collections:")
            for i, coll in enumerate(collections, 1):
                count = db[coll].count_documents({})
                print(f"  {i}. {coll} ({count} documents)")
        else:
            print("No collections found in the database")
        
        # Test a simple query
        if collections:
            test_collection = collections[0]
            print(f"\nTesting query on '{test_collection}'...")
            docs = list(db[test_collection].find().limit(1))
            if docs:
                print(f"✓ Successfully retrieved 1 document from '{test_collection}'")
                print(f"  Document fields: {', '.join(docs[0].keys())}")
            else:
                print(f"Collection '{test_collection}' is empty")
        
        print("\n✓ CONNECTION TEST SUCCESSFUL")
        return True
        
    except ServerSelectionTimeoutError as e:
        print("\n❌ SERVER SELECTION ERROR")
        print(f"Failed to connect to MongoDB server: {str(e)}")
        print("\nPossible causes:")
        print("1. Server is not running")
        print("2. Network connectivity issues")
        print("3. Firewall blocking the connection")
        print("4. Incorrect hostname or port")
        print(f"\nDetailed error: {e}")
        return False
        
    except ConnectionFailure as e:
        print("\n❌ CONNECTION FAILURE")
        print(f"Failed to connect to MongoDB: {str(e)}")
        print("\nPossible causes:")
        print("1. Authentication failed (incorrect username/password)")
        print("2. SSL/TLS certificate issues")
        print("3. Connection string format is incorrect")
        print(f"\nDetailed error: {e}")
        return False
        
    except Exception as e:
        print("\n❌ UNEXPECTED ERROR")
        print(f"An unexpected error occurred: {str(e)}")
        print("\nError details:")
        traceback.print_exc()
        return False
        
    finally:
        if 'client' in locals():
            print("\nClosing MongoDB connection...")
            client.close()
            print("Connection closed")

if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Connection Test")
    print("=" * 60)
    
    success = test_mongodb_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All connection tests PASSED")
    else:
        print("❌ Connection tests FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

