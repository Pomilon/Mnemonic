import json
import os
from typing import Dict, Any

DEFAULT_CATALOG = {
    "all-MiniLM-L6-v2": {
        "name": "MiniLM-L6",
        "description": "Balanced speed and quality. Small size, fast inference.",
        "dimension": 384,
        "type": "local",
        "category": "Speed"
    },
    "all-mpnet-base-v2": {
        "name": "MPNet-Base",
        "description": "High accuracy, slower inference. Better for complex semantic meaning.",
        "dimension": 768,
        "type": "local",
        "category": "Quality"
    },
    "bge-small-en-v1.5": {
        "name": "BGE-Small",
        "description": "Optimized for retrieval. Very efficient.",
        "dimension": 384,
        "type": "local",
        "category": "Balanced"
    },
    "ollama-embeddings": {
        "name": "Ollama API",
        "description": "Use your local Ollama instance for embeddings.",
        "dimension": 4096, 
        "type": "api",
        "category": "Custom"
    }
}

class ModelManager:
    def __init__(self):
        self.catalog_path = os.path.join(os.path.dirname(__file__), "aggregator", "models_catalog.json")
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, "r") as f:
                    return json.load(f)
            except:
                return DEFAULT_CATALOG
        return DEFAULT_CATALOG

    def save_catalog(self):
        os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
        with open(self.catalog_path, "w") as f:
            json.dump(self.catalog, f, indent=2)

    def add_model(self, model_id: str, name: str, description: str, dimension: int, category: str = "Custom"):
        self.catalog[model_id] = {
            "name": name,
            "description": description,
            "dimension": dimension,
            "type": "local",
            "category": category
        }
        self.save_catalog()

model_manager = ModelManager()
MODEL_CATALOG = model_manager.catalog
