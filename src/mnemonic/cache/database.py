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
        # Instead of deleting, we just add a high-rejection entry for this vector
        # This acts as a 'negative' marker in the vector space
        import json
        # We don't need results here, just the marker
        data = {
            "vector": vector,
            "query": query,
            "results_json": "[]", 
            "rejection_score": 10, # High score to indicate a strong rejection
            "timestamp": datetime.now(),
            "metadata": "rejection_marker"
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

    def get_rejection_markers(self, vector: List[float], limit: int = 5) -> List[List[float]]:
        # Search for nearby rejections
        # We filter for rejection_score > 0
        results = self.table.search(vector).where("rejection_score > 0").limit(limit).to_pandas()
        if results.empty:
            return []
        
        return results["vector"].tolist()

    def query_cache(self, vector: List[float], distance_threshold: float = config.CACHE_DISTANCE_THRESHOLD, rejection_threshold: int = config.CACHE_REJECTION_THRESHOLD, ttl_days: int = config.CACHE_TTL_DAYS):
        # Search for the top few nearest queries to check for rejections
        results = self.table.search(vector).limit(5).to_pandas()
        
        if results.empty:
            return None
            
        # Check if any of the nearest entries are strong rejections
        for _, row in results.iterrows():
            if int(row["rejection_score"]) >= rejection_threshold:
                return None
        
        # Now check the closest entry for actual results
        closest = results.iloc[0]
        distance = closest["_distance"]
        if distance > distance_threshold:
            return None
            
        # Check TTL
        timestamp = closest["timestamp"]
        if isinstance(timestamp, pd.Timestamp):
            age = (datetime.now() - timestamp.to_pydatetime()).days
        else:
            age = (datetime.now() - timestamp).days
            
        if age > ttl_days:
            return None
            
        import json
        cached_results_raw = json.loads(closest["results_json"])
        if not cached_results_raw:
            return None
        
        # Convert back to SearchResult objects
        cached_results = [SearchResult(**res) for res in cached_results_raw]
        
        return {
            "query": closest["query"],
            "results": cached_results,
            "distance": float(distance)
        }
