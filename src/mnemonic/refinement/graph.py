import numpy as np
from typing import List, Dict, Any
from src.mnemonic.aggregator.schema import SearchResult
from sentence_transformers import util
import torch

class CitationGraphService:
    def __init__(self, ranker):
        self.ranker = ranker

    def compute_graph(self, results: List[SearchResult]) -> Dict[str, Any]:
        if not results:
            return {"nodes": [], "edges": []}
        
        # Extract vectors
        vectors = [res.vector for res in results if res.vector]
        if not vectors:
            return {"nodes": [], "edges": []}
            
        # Convert to tensor
        vec_tensor = torch.tensor(vectors)
        
        # Compute all-pairs cosine similarity
        sim_matrix = util.cos_sim(vec_tensor, vec_tensor).numpy()
        
        nodes = []
        edges = []
        
        # Create nodes
        for i, res in enumerate(results):
            if res.vector:
                nodes.append({
                    "id": res.id,
                    "label": res.title[:30] + "...",
                    "url": res.url,
                    "group": res.content_type
                })
        
        # Create edges for strong similarities (> 0.7)
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sim = sim_matrix[i][j]
                if sim > 0.7:
                    edges.append({
                        "from": results[i].id,
                        "to": results[j].id,
                        "weight": float(sim)
                    })
                    
        return {
            "nodes": nodes,
            "edges": edges
        }
