import lancedb
import os
import pandas as pd
import pyarrow as pa
from typing import List, Optional
from datetime import datetime
from src.mnemonic.aggregator.schema import SearchResult
from src.mnemonic.config import config

class SemanticCache:
    def __init__(self, db_path: str = config.DATABASE_URI, table_name: str = config.CACHE_TABLE_NAME):
        self.db_path = db_path
        self.table_name = table_name
        self._ensure_db_exists()
        self.db = lancedb.connect(self.db_path)
        self.table = self._get_or_create_table()

    def _ensure_db_exists(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _get_or_create_table(self):
        if self.table_name in self.db.table_names():
            return self.db.open_table(self.table_name)
        
        # Initial schema definition
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), 384)),
            pa.field("query", pa.string()),
            pa.field("results_json", pa.string()), 
            pa.field("rejection_score", pa.int32()),
            pa.field("timestamp", pa.timestamp('ms')),
            pa.field("metadata", pa.string())
        ])
        
        return self.db.create_table(self.table_name, schema=schema)

    def add_to_cache(self, query: str, vector: List[float], results: List[SearchResult], metadata: str = "{}"):
        import json
        
        # Convert SearchResult objects to dicts for JSON storage
        results_json = json.dumps([res.model_dump() for res in results])
        
        data = {
            "vector": vector,
            "query": query,
            "results_json": results_json,
            "rejection_score": 0,
            "timestamp": datetime.now(),
            "metadata": metadata
        }
        
        self.table.add([data])

    def mark_rejection(self, query: str, vector: List[float]):
        # Find the most recent entry for this query/vector and increment rejection score
        # In LanceDB, we might need to overwrite or just add a new entry with high rejection
        # For simplicity in this prototype, we'll update the most recent one if possible, 
        # but LanceDB table.update is more complex. We'll just add a new "negative" entry or 
        # increment rejection_score for matches.
        
        # Actually, let's just find the ID or use a filter
        results = self.table.search(vector).limit(1).to_pandas()
        if not results.empty:
            # We can't easily 'update' a single row by index in a simple way with LanceDB's basic API
            # without a primary key. Let's assume we use the query string as a semi-unique identifier for now
            # or just filter by distance.
            
            # For this prototype, we'll use the 'delete and re-add' pattern if we want to update
            escaped_query = query.replace("'", "''")
            self.table.delete(f"query = '{escaped_query}'")
            
            # Re-add with incremented rejection score
            import json
            data = {
                "vector": vector,
                "query": query,
                "results_json": results.iloc[0]["results_json"],
                "rejection_score": int(results.iloc[0]["rejection_score"]) + 1,
                "timestamp": datetime.now(),
                "metadata": results.iloc[0]["metadata"]
            }
            self.table.add([data])

    def get_results_by_vector(self, vector: List[float]):
        results = self.table.search(vector).limit(1).to_pandas()
        if results.empty:
            return None
            
        import json
        cached_results_raw = json.loads(results.iloc[0]["results_json"])
        return [SearchResult(**res) for res in cached_results_raw]

    def clear_cache(self):
        # Create a new table with the same schema to clear it
        schema = self.table.schema
        self.db.drop_table(self.table_name)
        self.table = self.db.create_table(self.table_name, schema=schema)

    def query_cache(self, vector: List[float], distance_threshold: float = config.CACHE_DISTANCE_THRESHOLD, rejection_threshold: int = config.CACHE_REJECTION_THRESHOLD, ttl_days: int = config.CACHE_TTL_DAYS):
        # Search for the nearest query
        results = self.table.search(vector).limit(1).to_pandas()
        
        if results.empty:
            return None
            
        # Check distance
        distance = results.iloc[0]["_distance"]
        if distance > distance_threshold:
            return None
            
        # Check rejection score
        if int(results.iloc[0]["rejection_score"]) >= rejection_threshold:
            return None
            
        # Check TTL
        timestamp = results.iloc[0]["timestamp"]
        # Convert timestamp to datetime if it's not already
        if isinstance(timestamp, pd.Timestamp):
            age = (datetime.now() - timestamp.to_pydatetime()).days
        else:
            age = (datetime.now() - timestamp).days
            
        if age > ttl_days:
            return None
            
        import json
        cached_results_raw = json.loads(results.iloc[0]["results_json"])
        
        # Convert back to SearchResult objects
        cached_results = [SearchResult(**res) for res in cached_results_raw]
        
        return {
            "query": results.iloc[0]["query"],
            "results": cached_results,
            "distance": float(distance)
        }
