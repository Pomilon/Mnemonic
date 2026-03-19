from typing import List
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, util
from src.mnemonic.aggregator.schema import SearchResult

from src.mnemonic.config import config

class SearchRanker:
    def __init__(self, model_name: str = config.SENTENCE_TRANSFORMER_MODEL):
        self.model = SentenceTransformer(model_name)

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

    def rank_semantic(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        if not results:
            return results
            
        # Get query embedding
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        
        # Combine title and snippet for evaluation
        corpus_texts = [res.title + " " + res.snippet for res in results]
        corpus_embeddings = self.model.encode(corpus_texts, convert_to_tensor=True)
        
        # Compute cosine similarity
        cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
        cos_scores = cos_scores.cpu().numpy()
        
        # Update scores and vectors in SearchResult objects
        for i, res in enumerate(results):
            res.score = float(cos_scores[i])
            res.vector = corpus_embeddings[i].cpu().tolist()
            
        # Re-sort results
        return sorted(results, key=lambda x: x.score, reverse=True)

    def recalibrate(self, query_vec: List[float], rejected_vec: List[float], alpha: float = 0.15) -> List[float]:
        import numpy as np
        q_vec = np.array(query_vec)
        r_vec = np.array(rejected_vec)
        
        # Subtract the rejected vector from the query vector to shift away from it
        adjustment = alpha * r_vec
        new_vec = q_vec - adjustment
        
        # Re-normalize to unit length
        norm = np.linalg.norm(new_vec)
        if norm > 0:
            new_vec = new_vec / norm
            
        return new_vec.tolist()
