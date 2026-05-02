from typing import List, Optional, Union
import numpy as np
import torch
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, util
from src.mnemonic.aggregator.schema import SearchResult
from src.mnemonic.config import config
from src.mnemonic.models import MODEL_CATALOG
import httpx

class SearchRanker:
    def __init__(self, model_name: str = config.SENTENCE_TRANSFORMER_MODEL):
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self):
        if self.model_name == "ollama-embeddings":
            self._model = "ollama" # Marker for API use
        else:
            self._model = SentenceTransformer(self.model_name)

    def update_model(self, new_model_name: str):
        if new_model_name != self.model_name:
            self.model_name = new_model_name
            self._load_model()

    def encode(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        if self.model_name == "ollama-embeddings":
            return self._encode_ollama(text)
        
        embeddings = self._model.encode(text)
        if isinstance(embeddings, np.ndarray):
            if embeddings.ndim == 1:
                return embeddings.tolist()
            return embeddings.tolist()
        return embeddings

    def _encode_ollama(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        texts = [text] if isinstance(text, str) else text
        results = []
        try:
            async def fetch():
                async with httpx.AsyncClient() as client:
                    responses = []
                    for t in texts:
                        resp = await client.post(
                            f"{config.OLLAMA_BASE_URL}/api/embeddings",
                            json={"model": config.OLLAMA_MODEL, "prompt": t}
                        )
                        responses.append(resp.json().get("embedding", []))
                    return responses
            
            # Sync wrapper for async client
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # This is a hack for when running inside an async app
                # In a real app, encode should be async
                return [] 
            return loop.run_until_complete(fetch())
        except Exception as e:
            print(f"Ollama encoding error: {e}")
            return []

    def rank_bm25(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        if not results:
            return results
            
        tokenized_corpus = [(res.title + " " + res.snippet).lower().split() for res in results]
        bm25 = BM25Okapi(tokenized_corpus)
        
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        
        # Update scores in SearchResult objects
        for i, res in enumerate(results):
            res.score = scores[i]
            
        # Re-sort results
        return sorted(results, key=lambda x: x.score, reverse=True)

    def rank_semantic(self, query: str, results: List[SearchResult], query_vector: Optional[List[float]] = None, rejected_vectors: Optional[List[List[float]]] = None) -> List[SearchResult]:
        if not results:
            return results
            
        # Use provided query embedding or encode the query
        if query_vector is not None:
            query_embedding = torch.tensor(query_vector)
        else:
            encoded = self.encode(query)
            if not encoded:
                return results
            query_embedding = torch.tensor(encoded)
        
        # Combine title and snippet for evaluation
        corpus_texts = [res.title + " " + res.snippet for res in results]
        
        # Encode corpus
        corpus_encoded = self.encode(corpus_texts)
        if not corpus_encoded:
            return results
            
        corpus_embeddings = torch.tensor(corpus_encoded)
        
        # Compute cosine similarity
        cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
        cos_scores = cos_scores.cpu().numpy()
        
        # Apply rejection penalties
        if rejected_vectors:
            for r_vec in rejected_vectors:
                r_tensor = torch.tensor(r_vec)
                # Compute similarity of all results to the rejected vector
                rejection_sims = util.cos_sim(r_tensor, corpus_embeddings)[0].cpu().numpy()
                
                # Apply penalty: subtract a portion of the similarity to the rejected vector
                # This pushes down results that are similar to what was rejected
                cos_scores -= config.REJECTION_PENALTY_WEIGHT * rejection_sims
        
        # Update scores and vectors in SearchResult objects
        for i, res in enumerate(results):
            res.score = float(cos_scores[i])
            res.vector = corpus_embeddings[i].tolist() if corpus_embeddings.ndim > 1 else corpus_embeddings.tolist()
            
        # Re-sort results
        return sorted(results, key=lambda x: x.score, reverse=True)

    def recalibrate(self, query_vec: List[float], rejected_vec: List[float], alpha: Optional[float] = None) -> List[float]:
        import numpy as np
        if alpha is None:
            alpha = config.RECALIBRATION_ALPHA
        
        q_vec = np.array(query_vec)
        r_vec = np.array(rejected_vec)
        
        # Ensure vectors are unit length
        q_vec = q_vec / np.linalg.norm(q_vec) if np.linalg.norm(q_vec) > 0 else q_vec
        r_vec = r_vec / np.linalg.norm(r_vec) if np.linalg.norm(r_vec) > 0 else r_vec
        
        # Calculate projection of q onto r
        dot_product = np.dot(q_vec, r_vec)
        projection = dot_product * r_vec
        
        # Calculate the component of q orthogonal to r
        orthogonal_component = q_vec - projection
        
        # Boost the orthogonal component to push the vector away from r
        # This increases the weight of parts of the query that are NOT like the rejected result
        new_vec = q_vec + (alpha * orthogonal_component)
        
        # Re-normalize to unit length
        norm = np.linalg.norm(new_vec)
        if norm > 0:
            new_vec = new_vec / norm
            
        return new_vec.tolist()
