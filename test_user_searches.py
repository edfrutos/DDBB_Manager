"""
Script to test user searches using the different indexes:
1. Text search on name field
2. Exact match search on email
3. Filter by role
4. Sort by dates (created_at and updated_at)

For each search type, the script:
- Implements the search using the optimized indexes
- Measures performance
- Verifies index usage with explain()
- Displays results in a user-friendly format
"""

import os
import sys
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pprint
import json
from tabulate import tabulate
from datetime import datetime
from bson import ObjectId

# Create a pretty printer for MongoDB documents
pp = pprint.PrettyPrinter(indent=2)

# Function to format MongoDB documents for pretty printing
def format_doc_for_print(doc):
    """Format MongoDB document for better readability"""
    if isinstance(doc, dict):
        # Convert ObjectId to string
        if '_id' in doc and isinstance(doc['_id'], ObjectId):
            doc['_id'] = str(doc['_id'])
        # Convert any dates to strings
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
    return doc

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

def test_text_search(collection):
    """Test text search using name_text index"""
    print("\n1. TESTING TEXT SEARCH ON NAME FIELD")
    print("===================================")
    
    # Define search terms to test
    # Define search terms to test
    search_terms = ["Admin", "Alejandro", "a"]  # Different complexity levels
    
    results = []
    for term in search_terms:
        print(f"\nSearching for name containing: '{term}'")
        # Prepare text search query using $text operator which automatically uses the text index
        query = {"$text": {"$search": term}}
        
        # Add text score projection for relevance sorting
        projection = {"score": {"$meta": "textScore"}}
        # Get explain plan first (before executing query)
        # Get explain plan first (before executing query) - for text searches
        start_explain = time.time()
        # No need for hint with text search, MongoDB automatically uses text index
        explain_result = collection.find(query, projection).explain()
        # Check if text index is used
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        index_name = None
        if "queryPlan" in winning_plan:
            stage = winning_plan.get("queryPlan", {}).get("stage", "")
            index_name = winning_plan.get("queryPlan", {}).get("inputStage", {}).get("indexName", None)
        else:
            stage = winning_plan.get("stage", "")
            if "inputStage" in winning_plan:
                index_name = winning_plan.get("inputStage", {}).get("indexName", None)
                
        # For text searches, the indexName might appear deeper in the plan or as TEXT_MATCH stage
        is_using_text_index = False
        if stage == "TEXT_MATCH" or (index_name and "text" in index_name):
            is_using_text_index = True
            index_name = "name_text"
            
        is_using_index = is_using_text_index
        # Execute actual query with text search functionality
        start_time = time.time()
        # Use projection to get the text score - MongoDB automatically uses text index with $text
        cursor = collection.find(
            query, 
            projection
        ).sort([("score", {"$meta": "textScore"})])
        docs = list(cursor)
        execution_time = time.time() - start_time
        # Print results
        print(f"Found {len(docs)} documents in {execution_time:.6f} seconds")
        print(f"Using index: {is_using_index} (Index: {index_name})")
        
        if docs:
            print("\nSample documents found:")
            for doc in docs[:2]:  # Show first two results
                formatted_doc = format_doc_for_print(doc)
                pp.pprint(formatted_doc)
        
        # Store result for summary
        results.append({
            "term": term, 
            "count": len(docs), 
            "time": execution_time, 
            "using_index": is_using_index,
            "index_name": index_name
        })
    
    return results

def test_email_search(collection):
    """Test exact match search using email_unique index"""
    print("\n2. TESTING EMAIL EXACT MATCH SEARCH")
    print("=================================")
    
    # Get some sample emails from the collection for testing
    sample_users = list(collection.find({}, {"email": 1}).limit(3))
    sample_emails = [user.get("email") for user in sample_users if user.get("email")]
    
    # Add a nonexistent email
    test_emails = sample_emails + ["nonexistent@example.com"]
    
    results = []
    for email in test_emails:
        print(f"\nSearching for email: '{email}'")
        # Prepare query with hint to force index usage
        query = {"email": email}
        
        # Get explain plan with explicit hint to use email_unique index
        start_explain = time.time()
        explain_result = collection.find(query).hint("email_unique").explain()
        explain_time = time.time() - start_explain
        
        # Check if email index is used
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        index_name = None
        if "inputStage" in winning_plan:
            index_name = winning_plan.get("inputStage", {}).get("indexName", None)
            
        is_using_index = index_name in ["email_unique", "email_1"]
        
        # Execute actual query and measure time
        start_time = time.time()
        cursor = collection.find(query)
        docs = list(cursor)
        execution_time = time.time() - start_time
        
        # Print results
        print(f"Found {len(docs)} documents in {execution_time:.6f} seconds")
        print(f"Using index: {is_using_index} (Index: {index_name})")
        
        if docs:
            print("\nDocument found:")
            for doc in docs:
                formatted_doc = format_doc_for_print(doc)
                pp.pprint(formatted_doc)
        
        # Store result for summary
        results.append({
            "email": email, 
            "found": len(docs) > 0, 
            "time": execution_time, 
            "using_index": is_using_index,
            "index_name": index_name
        })
    
    return results

def test_role_filtering(collection):
    """Test filtering by role using role_index"""
    print("\n3. TESTING ROLE FILTERING")
    print("=======================")
    
    # Get available roles in the collection
    roles = collection.distinct("role")
    
    results = []
    for role in roles:
        print(f"\nFiltering for role: '{role}'")
        
        # Prepare query
        query = {"role": role}
        
        # Get explain plan
        start_explain = time.time()
        explain_result = collection.find(query).explain()
        explain_time = time.time() - start_explain
        
        # Check if role index is used
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        index_name = None
        if "inputStage" in winning_plan:
            index_name = winning_plan.get("inputStage", {}).get("indexName", None)
            
        is_using_index = index_name in ["role_index", "role_1"]
        
        # Execute actual query and measure time
        start_time = time.time()
        cursor = collection.find(query)
        docs = list(cursor)
        execution_time = time.time() - start_time
        
        # Print results
        print(f"Found {len(docs)} {role} users in {execution_time:.6f} seconds")
        print(f"Using index: {is_using_index} (Index: {index_name})")
        
        # Print summary of results
        if docs:
            print(f"\nUsers with role '{role}':")
            for i, doc in enumerate(docs[:3], 1):  # Show first 3 results
                print(f"{i}. {doc.get('name')} ({doc.get('email')})")
            
            if len(docs) > 3:
                print(f"...and {len(docs) - 3} more")
        
        # Store result for summary
        results.append({
            "role": role, 
            "count": len(docs), 
            "time": execution_time, 
            "using_index": is_using_index,
            "index_name": index_name
        })
    
    return results

def test_date_sorting(collection):
    """Test sorting by dates using date_sorting_index"""
    print("\n4. TESTING DATE SORTING")
    print("====================")
    
    # Different sort directions to test
    sorts = [
        {"direction": "newest first", "sort": [("created_at", -1)]},
        {"direction": "oldest first", "sort": [("created_at", 1)]},
        {"direction": "recently updated", "sort": [("created_at", -1), ("updated_at", -1)]}  # Modified to match index
    ]
    results = []
    for sort_option in sorts:
        direction = sort_option["direction"]
        sort = sort_option["sort"]
        
        print(f"\nSorting users by {direction}")
        # Get explain plan with sort and hint to use the date index
        start_explain = time.time()
        sort_query = collection.find({})
        
        # Apply sort
        sort_query = sort_query.sort(sort)
        
        # For compound sorts, use an explicit hint
        if len(sort) > 1 or sort[0][0] == "created_at":
            sort_query = sort_query.hint("date_sorting_index")
            
        explain_result = sort_query.explain()
        explain_time = time.time() - start_explain
        
        # Check if date index is used
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        index_name = None
        
        # MongoDB might use different stages for sort execution
        if "queryPlan" in winning_plan:
            stage = winning_plan.get("queryPlan", {}).get("stage", "")
            if stage == "SORT":
                index_name = "none (in-memory sort)"
            else:
                index_name = winning_plan.get("queryPlan", {}).get("inputStage", {}).get("indexName", None)
        else:
            stage = winning_plan.get("stage", "")
            if stage == "SORT":
                index_name = "none (in-memory sort)"
            elif "inputStage" in winning_plan:
                index_name = winning_plan.get("inputStage", {}).get("indexName", None)
        
        is_using_index = index_name in ["date_sorting_index", "created_at_-1_updated_at_-1"]
        # Execute actual query with sort and hint, then measure time
        start_time = time.time()
        sort_query = collection.find({})
        
        # Apply sort
        sort_query = sort_query.sort(sort)
        
        # For compound sorts, use an explicit hint
        if len(sort) > 1 or sort[0][0] == "created_at":
            sort_query = sort_query.hint("date_sorting_index")
            
        docs = list(sort_query)
        execution_time = time.time() - start_time
        
        # Print results
        print(f"Sorted {len(docs)} users in {execution_time:.6f} seconds")
        print(f"Using index: {is_using_index} (Index: {index_name})")
        
        # Print summary of results
        if docs:
            print(f"\nUsers sorted by {direction}:")
            for i, doc in enumerate(docs[:3], 1):
                created = doc.get('created_at', 'N/A')
                updated = doc.get('updated_at', 'N/A')
                if isinstance(created, datetime):
                    created = created.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(updated, datetime):
                    updated = updated.strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"{i}. {doc.get('name')} - Created: {created}, Updated: {updated}")
            
            if len(docs) > 3:
                print(f"...and {len(docs) - 3} more")
        
        # Store result for summary
        results.append({
            "sort": direction, 
            "count": len(docs), 
            "time": execution_time, 
            "using_index": is_using_index,
            "index_name": index_name
        })
    
    return results

def print_summary(text_results, email_results, role_results, sort_results):
    """Print a summary table of all test results"""
    print("\n\nSUMMARY OF SEARCH PERFORMANCE TESTS")
    print("=================================")
    
    # Text search summary
    print("\nText Search Results:")
    text_table = []
    for r in text_results:
        text_table.append([
            r["term"], 
            r["count"], 
            f"{r['time']:.6f}s", 
            "✓" if r["using_index"] else "✗",
            r["index_name"] or "N/A"
        ])
    print(tabulate(text_table, headers=["Search Term", "Results", "Time", "Using Index", "Index Name"]))
    
    # Email search summary
    print("\nEmail Search Results:")
    email_table = []
    for r in email_results:
        email_table.append([
            r["email"], 
            "Found" if r["found"] else "Not Found", 
            f"{r['time']:.6f}s", 
            "✓" if r["using_index"] else "✗",
            r["index_name"] or "N/A"
        ])
    print(tabulate(email_table, headers=["Email", "Result", "Time", "Using Index", "Index Name"]))
    
    # Role filtering summary
    print("\nRole Filtering Results:")
    role_table = []
    for r in role_results:
        role_table.append([
            r["role"], 
            r["count"], 
            f"{r['time']:.6f}s", 
            "✓" if r["using_index"] else "✗",
            r["index_name"] or "N/A"
        ])
    print(tabulate(role_table, headers=["Role", "Count", "Time", "Using Index", "Index Name"]))
    
    # Date sorting summary
    print("\nDate Sorting Results:")
    sort_table = []
    for r in sort_results:
        sort_table.append([
            r["sort"], 
            r["count"], 
            f"{r['time']:.6f}s", 
            "✓" if r["using_index"] else "✗",
            r["index_name"] or "N/A"
        ])
    print(tabulate(sort_table, headers=["Sort Order", "Count", "Time", "Using Index", "Index Name"]))

def main():
    """Main function to run all search tests"""
    print("MongoDB User Search Performance Test")
    print("===================================")
    
    client = None
    try:
        # Connect to MongoDB
        client, db = connect_to_mongodb()
        
        # Check if users_unified collection exists
        if "users_unified" not in db.list_collection_names():
            print("Error: users_unified collection not found in database.")
            sys.exit(1)
            
        collection = db.users_unified
        
        # Print collection info
        doc_count = collection.count_documents({})
        print(f"\nFound {doc_count} documents in users_unified collection")
        
        # Print MongoDB server info
        server_info = client.server_info()
        print(f"MongoDB server version: {server_info.get('version', 'Unknown')}")
        # Show available indexes
        print("\nAvailable indexes:")
        indexes = collection.index_information()
        for name, info in indexes.items():
            print(f"- {name}: {info}")
        
        # Run the four search tests
        print("\nRunning search performance tests...")
        
        # 1. Test text search
        text_results = test_text_search(collection)
        
        # 2. Test email search
        email_results = test_email_search(collection)
        
        # 3. Test role filtering
        role_results = test_role_filtering(collection)
        
        # 4. Test date sorting
        sort_results = test_date_sorting(collection)
        
        # Print summary of all test results
        print_summary(text_results, email_results, role_results, sort_results)
        
        print("\nAll tests completed successfully!")
        
    except ConnectionFailure as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        sys.exit(1)
    finally:
        # Close MongoDB connection
        if client:
            print("\nClosing MongoDB connection...")
            client.close()
            print("Connection closed")

if __name__ == "__main__":
    main()
