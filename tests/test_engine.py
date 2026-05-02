import asyncio
import os
import shutil
import pytest
from src.mnemonic.engine import MnemonicEngine
from src.mnemonic.aggregator.aggregator import SearchAggregator
from src.mnemonic.aggregator.engines.mock import MockSearchEngine
from src.mnemonic.cache.database import SemanticCache

@pytest.mark.asyncio
async def test_engine_flow():
    # Clean up old data for clean test
    if os.path.exists("./data/mnemonic_db_test"):
        shutil.rmtree("./data/mnemonic_db_test")
    
    # Initialize engine with test DB path and Mock client
    mock_aggregator = SearchAggregator()
    mock_aggregator.clients = [MockSearchEngine()]
    
    test_cache = SemanticCache(db_path="./data/mnemonic_db_test")
    engine = MnemonicEngine(aggregator=mock_aggregator, cache=test_cache)
    
    query = "python programming"
    
    print(f"--- Searching for '{query}' (Live) ---")
    response = await engine.search(query)
    print(f"Results: {len(response.results)}, From Cache: {response.from_cache}, Latency: {response.latency:.2f}s")
    assert not response.from_cache
    
    print(f"\n--- Searching for '{query}' again (Cached) ---")
    response_cached = await engine.search(query)
    print(f"Results: {len(response_cached.results)}, From Cache: {response_cached.from_cache}, Latency: {response_cached.latency:.2f}s")
    assert response_cached.from_cache
    
    print("\n--- Rejecting results ---")
    rejected_id = response.results[0].id
    await engine.feedback_rejection(query, rejected_id, response.query_vector)
    
    print(f"\n--- Searching for '{query}' after rejection (Should be Fresh with Recalibrated Vector) ---")
    # Note: Search without force_refresh will still hit cache if vector is similar, 
    # but feedback_rejection marks the OLD vector as rejected.
    response_refreshed = await engine.search(query)
    print(f"Results: {len(response_refreshed.results)}, From Cache: {response_refreshed.from_cache}, Latency: {response_refreshed.latency:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_engine_flow())
