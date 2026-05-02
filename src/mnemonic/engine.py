import time
from typing import List, Optional
from src.mnemonic.aggregator.aggregator import SearchAggregator
from src.mnemonic.aggregator.schema import SearchResponse, SearchResult, SearchCategory
from src.mnemonic.refinement.deduplication import DeDuplicator
from src.mnemonic.refinement.ranking import SearchRanker
from src.mnemonic.cache.database import SemanticCache
from src.mnemonic.llm import LocalLLM
from src.mnemonic.refinement.privacy import PrivacyService
from src.mnemonic.config import config

class MnemonicEngine:
    def __init__(self, aggregator=None, cache=None):
        self.aggregator = aggregator or SearchAggregator()
        self.cache = cache or SemanticCache()
        self.deduplicator = DeDuplicator()
        self.ranker = SearchRanker()
        self.privacy = PrivacyService()
        self.llm = LocalLLM()
        # Store rejected vectors per query to apply penalties
        self.rejection_registry = {} # {query: [vector1, vector2, ...]}

    async def _generate_hyde_vector(self, query: str) -> Optional[List[float]]:
        # Use existing add_log if available through a bridge or just return
        prompt = f"Please write a short, technical paragraph that would be a perfect answer to the following query: {query}. Focus on facts and key terminology."
        hypothetical_doc = await self.llm.generate(prompt)
        
        if not hypothetical_doc or "Error" in hypothetical_doc:
            return None
            
        # Embed the hypothetical document
        return self.ranker.encode(hypothetical_doc)

    async def search(self, query: str, force_refresh: bool = False, query_vector: Optional[List[float]] = None, offset: int = 0, filters: Optional[dict] = None, category: SearchCategory = SearchCategory.GENERAL) -> SearchResponse:
        start_time = time.perf_counter()
        from src.mnemonic.api.main import add_log

        # 1. Use provided vector, HyDE vector, or calculate fresh one
        if query_vector is None:
            if config.USE_HYDE and offset == 0:
                await add_log(f"HyDE: Expanding semantic intent for '{query}'...")
                hyde_vec = await self._generate_hyde_vector(query)
                if hyde_vec:
                    await add_log("HyDE: Intent expansion complete.")
                    query_vector = hyde_vec
                else:
                    await add_log("HyDE: Expansion bypassed, using base embedding.")
                    query_vector = self.ranker.encode(query)
            else:
                await add_log(f"Embed: Computing vector for '{query}'...")
                query_vector = self.ranker.encode(query)
        
        # 2. Check Cache
        if not force_refresh:
            await add_log("Cache: Checking semantic memory index...")
            cached = self.cache.query_cache(query_vector)
            if cached:
                results = cached["results"]
                # Apply filters to cached results first
                if filters:
                    await add_log(f"Cache: Applying real-time filters to cached data...")
                    results = self._apply_filters(results, filters)
                
                if offset < len(results):
                    await add_log(f"Cache: Hit! Retrieving {len(results)} nodes from memory.")
                    limit = config.MAX_RESULTS_PER_ENGINE
                    paged_results = results[offset : offset + limit]
                    
                    # Update source_type to CACHE for cached results
                    for res in paged_results:
                        res.source_type = "cache"
                    
                    # Even for cached results, apply rejection penalties if any exist
                    session_rejected_vecs = self.rejection_registry.get(query, [])
                    persistent_rejected_vecs = self.cache.get_rejection_markers(query_vector)
                    all_rejected_vecs = session_rejected_vecs + persistent_rejected_vecs
                    
                    if all_rejected_vecs:
                        await add_log(f"Refinement: Applying {len(all_rejected_vecs)} rejection penalties to cached nodes...")
                        paged_results = self.ranker.rank_semantic(
                            query, paged_results, query_vector=query_vector, rejected_vectors=all_rejected_vecs
                        )
                    
                    end_time = time.perf_counter()
                    return SearchResponse(
                        query=query,
                        results=paged_results,
                        from_cache=True,
                        latency=end_time - start_time,
                        distance=cached.get("distance"),
                        query_vector=query_vector
                    )
                await add_log("Cache: Results found, but offset requires live query.")
        
        # 3. Aggregator: Fetch from all engines with offset and category
        await add_log(f"Aggregator: Querying engines for category '{category.value}'...")
        raw_response = await self.aggregator.fetch_all(query, offset=offset, category=category, filters=filters)
        
        # 4. Refinement: Deduplicate
        await add_log("Refinement: Deduplicating response union...")
        unique_results = self.deduplicator.deduplicate(raw_response.results)
        
        # 5. Privacy: Clean URLs
        for res in unique_results:
            res.url = self.privacy.clean_url(res.url)
        
        # 6. Refinement: Apply filters
        if filters:
            await add_log(f"Refinement: Filtering {len(unique_results)} nodes...")
            unique_results = self._apply_filters(unique_results, filters)
        
        # 6. Refinement: Semantic Re-ranking with penalties
        await add_log(f"Refinement: Re-ranking {len(unique_results)} nodes using {self.ranker.model_name}...")
        # Combine session-based rejections with persistent ones from the vector store
        session_rejected_vecs = self.rejection_registry.get(query, [])
        persistent_rejected_vecs = self.cache.get_rejection_markers(query_vector)
        all_rejected_vecs = session_rejected_vecs + persistent_rejected_vecs
        
        ranked_results = self.ranker.rank_semantic(
            query, unique_results, query_vector=query_vector, rejected_vectors=all_rejected_vecs
        )
        
        # 7. Cache: Store the results (only for first page and NO filters)
        if offset == 0 and not filters:
            await add_log(f"Cache: Indexing {len(ranked_results)} nodes for future recall.")
            self.cache.add_to_cache(query, query_vector, ranked_results)
        
        end_time = time.perf_counter()
        await add_log(f"Kernel: Search cycle complete in {end_time - start_time:.2f}s.")
        
        return SearchResponse(
            query=query,
            results=ranked_results,
            from_cache=False,
            latency=end_time - start_time,
            query_vector=query_vector
        )

    def _apply_filters(self, results: List[SearchResult], filters: dict) -> List[SearchResult]:
        filtered = results
        
        # Domain Filter
        domain = filters.get("domain")
        if domain:
            filtered = [res for res in filtered if domain.lower() in res.url.lower()]
            
        # Content Type Filter
        content_type = filters.get("content_type")
        if content_type:
            filtered = [res for res in filtered if res.content_type == content_type]
            
        return filtered

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
        
        # 3. Track rejection in memory for the current session to apply penalties
        if query not in self.rejection_registry:
            self.rejection_registry[query] = []
        self.rejection_registry[query].append(rejected_res.vector)
        
        # 4. Mark rejection in cache for the OLD query vector
        self.cache.mark_rejection(query, query_vector)
        
        # 5. Perform fresh search with the NEW query vector and applied penalties
        response = await self.search(query, force_refresh=True, query_vector=new_query_vector)
        
        # Explicitly filter out the rejected item from the results
        response.results = [res for res in response.results if res.id != rejected_result_id]
        
        for res in response.results:
            res.source_type = "refined"
        return response
