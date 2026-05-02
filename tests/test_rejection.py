import asyncio
import numpy as np
import torch
from sentence_transformers import util
from src.mnemonic.engine import MnemonicEngine
from src.mnemonic.aggregator.aggregator import SearchAggregator
from src.mnemonic.aggregator.engines.mock import MockSearchEngine
from src.mnemonic.cache.database import SemanticCache
import os
import shutil

async def verify_rejection_logic():
    print("--- Verifying Rejection Logic Impact ---")
    
    # Setup
    if os.path.exists("./data/mnemonic_db_rejection_test"):
        shutil.rmtree("./data/mnemonic_db_rejection_test")
        
    mock_aggregator = SearchAggregator()
    mock_aggregator.clients = [MockSearchEngine("test-engine")]
    test_cache = SemanticCache(db_path="./data/mnemonic_db_rejection_test")
    engine = MnemonicEngine(aggregator=mock_aggregator, cache=test_cache)
    
    query = "artificial intelligence"
    
    # 1. Initial Search
    print(f"Initial search for: {query}")
    res1 = await engine.search(query)
    q_vec1 = res1.query_vector
    
    # Identify item to reject
    rejected_item = res1.results[0]
    rejected_id = rejected_item.id
    rejected_vec = rejected_item.vector
    
    # 2. Perform Rejection
    print(f"Rejecting top result: {rejected_id}")
    res2 = await engine.feedback_rejection(query, rejected_id, q_vec1)
    
    # 3. Verify Impact
    # Check if rejected item is gone
    item_ids = [r.id for r in res2.results]
    assert rejected_id not in item_ids, "Rejected item should be filtered out!"
    print("Success: Rejected item explicitly filtered out.")
    
    # Verify ranking change
    # Note: MockSearchEngine returns deterministic results based on index.
    # The ranker penalty should have shifted things.
    if res2.results[0].id != res1.results[1].id:
        # If it's not just the next item in line, the ranking shifted
        print(f"Rank shift detected: New top item is {res2.results[0].id}")
    
    # Cleanup
    shutil.rmtree("./data/mnemonic_db_rejection_test")
    print("Rejection logic verified successfully.")

if __name__ == "__main__":
    asyncio.run(verify_rejection_logic())
