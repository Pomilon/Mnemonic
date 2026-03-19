import asyncio
import time
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SearchResponse
from src.mnemonic.aggregator.engines.duckduckgo import DuckDuckGoClient

from src.mnemonic.config import config

class SearchAggregator:
    def __init__(self):
        self.clients = [
            DuckDuckGoClient(),
        ]

    async def fetch_all(self, query: str, max_results_per_engine: int = config.MAX_RESULTS_PER_ENGINE, offset: int = 0) -> SearchResponse:
        start_time = time.perf_counter()
        
        # Parallel fetch from all registered engines
        tasks = [client.search(query, max_results_per_engine, offset) for client in self.clients]
        all_results_nested = await asyncio.gather(*tasks)
        
        # Flatten and remove empty lists
        all_results = [result for sublist in all_results_nested for result in sublist if result]
        
        end_time = time.perf_counter()
        
        return SearchResponse(
            query=query,
            results=all_results,
            latency=end_time - start_time
        )
