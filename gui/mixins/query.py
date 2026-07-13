import json
import re
import traceback

from PyQt6.QtWidgets import QMessageBox


class QueryMixin:
    """Métodos de ejecución de consultas MongoDB para MainWindow."""

    def execute_query(self):
        """Execute a MongoDB query from the query editor."""
        if self.db is None:
            QMessageBox.warning(self, "Advertencia", "No hay conexión a la base de datos")
            return

        self.record_activity("execute_query")

        query_text = self.query_editor.toPlainText().strip()

        if not query_text:
            self.results_view.setPlainText("No query to execute")
            return

        try:
            match = re.search(r"db\.(\w+)\.(\w+)\((.*)\)", query_text)

            if not match:
                self.results_view.setPlainText("Invalid query format. Use: db.collection.operation(params)")
                return

            collection_name = match.group(1)
            operation = match.group(2)
            params_str = match.group(3).strip()

            collection = self.db[collection_name]

            if operation == "find":
                if params_str:
                    try:
                        if "," in params_str:
                            query_part, projection_part = params_str.split(",", 1)
                            query = json.loads(query_part)
                            projection = json.loads(projection_part)
                            results = collection.find(query, projection)
                        else:
                            query = json.loads(params_str)
                            results = collection.find(query)
                    except json.JSONDecodeError:
                        self.results_view.setPlainText(f"Invalid JSON in query parameters: {params_str}")
                        return
                else:
                    results = collection.find()

                results_list = list(results)
                if results_list:
                    formatted_results = json.dumps(results_list, indent=2, default=str)
                    self.results_view.setPlainText(formatted_results)
                    self.show_status_message(f"Found {len(results_list)} documents")
                else:
                    self.results_view.setPlainText("No documents found matching the query")
                    self.show_status_message("No documents found")

            elif operation == "insertOne":
                try:
                    document = json.loads(params_str)
                    result = collection.insert_one(document)
                    self.results_view.setPlainText(f"Document inserted with ID: {result.inserted_id}")
                    self.show_status_message("Document inserted successfully")
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON document: {params_str}")

            elif operation == "insertMany":
                try:
                    documents = json.loads(params_str)
                    if not isinstance(documents, list):
                        self.results_view.setPlainText("insertMany requires an array of documents")
                        return
                    result = collection.insert_many(documents)
                    self.results_view.setPlainText(f"Inserted {len(result.inserted_ids)} documents")
                    self.show_status_message(f"Inserted {len(result.inserted_ids)} documents")
                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON array: {params_str}")

            elif operation == "updateOne" or operation == "updateMany":
                try:
                    if "," not in params_str:
                        self.results_view.setPlainText(f"{operation} requires filter and update documents")
                        return

                    filter_part, update_part = params_str.split(",", 1)
                    filter_doc = json.loads(filter_part)
                    update_doc = json.loads(update_part)

                    if operation == "updateOne":
                        result = collection.update_one(filter_doc, update_doc)
                        matched = result.matched_count
                        modified = result.modified_count
                    else:
                        result = collection.update_many(filter_doc, update_doc)
                        matched = result.matched_count
                        modified = result.modified_count

                    self.results_view.setPlainText(f"Matched: {matched}, Modified: {modified}")
                    self.show_status_message(f"Updated {modified} of {matched} matching documents")

                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON in parameters: {params_str}")

            elif operation == "deleteOne" or operation == "deleteMany":
                try:
                    filter_doc = json.loads(params_str)

                    if operation == "deleteOne":
                        result = collection.delete_one(filter_doc)
                        deleted = result.deleted_count
                    else:
                        result = collection.delete_many(filter_doc)
                        deleted = result.deleted_count

                    self.results_view.setPlainText(f"Deleted {deleted} document(s)")
                    self.show_status_message(f"Deleted {deleted} document(s)")

                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON filter: {params_str}")

            elif operation == "aggregate":
                try:
                    pipeline = json.loads(params_str)
                    if not isinstance(pipeline, list):
                        self.results_view.setPlainText("Aggregate requires a pipeline array")
                        return

                    results = list(collection.aggregate(pipeline))
                    if results:
                        formatted_results = json.dumps(results, indent=2, default=str)
                        self.results_view.setPlainText(formatted_results)
                    else:
                        self.results_view.setPlainText("No results from aggregation pipeline")
                    self.show_status_message(f"Aggregation returned {len(results)} results")

                except json.JSONDecodeError:
                    self.results_view.setPlainText(f"Invalid JSON pipeline: {params_str}")

            else:
                self.results_view.setPlainText(
                    "Operation not supported: "
                    f"{operation}\n\nSupported operations: find, insertOne, insertMany, updateOne, updateMany, deleteOne, deleteMany, aggregate"
                )

        except Exception as e:
            self.results_view.setPlainText(f"Error executing query: {str(e)}")
            self.show_status_message(f"Error: {str(e)}", error=True)
