import time
from typing import List, Optional
from src.mnemonic.aggregator.aggregator import SearchAggregator
from src.mnemonic.aggregator.schema import SearchResponse, SearchResult
from src.mnemonic.refinement.deduplication import DeDuplicator
from src.mnemonic.refinement.ranking import SearchRanker
from src.mnemonic.cache.database import SemanticCache

class MnemonicEngine:
    def __init__(self, aggregator=None, cache=None):
        self.aggregator = aggregator or SearchAggregator()
        self.cache = cache or SemanticCache()
        self.deduplicator = DeDuplicator()
        self.ranker = SearchRanker()

    async def search(self, query: str, force_refresh: bool = False, query_vector: Optional[List[float]] = None, offset: int = 0) -> SearchResponse:
        start_time = time.perf_counter()
        
        # 1. Use provided vector or calculate fresh one
        if query_vector is None:
            query_vector = self.ranker.model.encode(query).tolist()
        
        # 2. Check Cache (only for first page to avoid complex paging in cache for this prototype)
        if not force_refresh and offset == 0:
            cached = self.cache.query_cache(query_vector)
            if cached:
                # Update source_type to CACHE for cached results
                for res in cached["results"]:
                    res.source_type = "cache"
                
                end_time = time.perf_counter()
                return SearchResponse(
                    query=query,
                    results=cached["results"],
                    from_cache=True,
                    latency=end_time - start_time,
                    distance=cached.get("distance"),
                    query_vector=query_vector
                )
        
        # 3. Aggregator: Fetch from all engines with offset
        raw_response = await self.aggregator.fetch_all(query, offset=offset)
        
        # 4. Refinement: Deduplicate
        unique_results = self.deduplicator.deduplicate(raw_response.results)
        
        # 5. Refinement: Semantic Re-ranking
        ranked_results = self.ranker.rank_semantic(query, unique_results)
        
        # 6. Cache: Store the results (only for first page)
        if offset == 0:
            self.cache.add_to_cache(query, query_vector, ranked_results)
        
        end_time = time.perf_counter()
        
        return SearchResponse(
            query=query,
            results=ranked_results,
            from_cache=False,
            latency=end_time - start_time,
            query_vector=query_vector
        )

    async def feedback_rejection(self, query: str, rejected_result_id: str, query_vector: List[float]) -> SearchResponse:
        # 1. Find the rejected result to get its vector
        cached_results = self.cache.get_results_by_vector(query_vector)
        if not cached_results:
            return await self.search(query, force_refresh=True)

        rejected_res = next((r for r in cached_results if r.id == rejected_result_id), None)
        if not rejected_res or not rejected_res.vector:
            return await self.search(query, force_refresh=True)

        # 2. Recalibrate the query vector
        new_query_vector = self.ranker.recalibrate(query_vector, rejected_res.vector)
        
        # 3. Mark rejection in cache for the OLD query vector
        self.cache.mark_rejection(query, query_vector)
        
        # 4. Perform fresh search with the NEW query vector
        response = await self.search(query, force_refresh=True, query_vector=new_query_vector)
        for res in response.results:
            res.source_type = "refined"
        return response
