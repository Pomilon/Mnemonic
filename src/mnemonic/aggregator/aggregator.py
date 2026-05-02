import os
import json
import asyncio
import time
from typing import List, Dict
from src.mnemonic.aggregator.schema import SearchResult, SearchResponse, SearchCategory
from src.mnemonic.aggregator.engines.duckduckgo import DuckDuckGoClient
from src.mnemonic.aggregator.engines.brave import BraveSearchClient
from src.mnemonic.aggregator.engines.google import GoogleSearchClient
from src.mnemonic.aggregator.engines.bing import BingSearchClient
from src.mnemonic.aggregator.engines.wikipedia import WikipediaClient
from src.mnemonic.aggregator.engines.hackernews import HackerNewsClient
from src.mnemonic.aggregator.engines.arxiv import ArXivClient
from src.mnemonic.aggregator.engines.stackoverflow import StackOverflowClient
from src.mnemonic.aggregator.engines.mock import MockSearchEngine

from src.mnemonic.config import config

class SearchAggregator:
    def __init__(self):
        self.engines = {}
        self.category_map = {cat: [] for cat in SearchCategory}
        self._load_engines()

    def _load_engines(self):
        # Clear existing
        self.engines = {}
        self.category_map = {cat: [] for cat in SearchCategory}
        
        # Map class names to actual class objects
        client_classes = {
            "DuckDuckGoClient": DuckDuckGoClient,
            "BraveSearchClient": BraveSearchClient,
            "GoogleSearchClient": GoogleSearchClient,
            "BingSearchClient": BingSearchClient,
            "WikipediaClient": WikipediaClient,
            "HackerNewsClient": HackerNewsClient,
            "ArXivClient": ArXivClient,
            "StackOverflowClient": StackOverflowClient,
            "MockSearchEngine": MockSearchEngine
        }
        
        from src.mnemonic.config import ensure_config_exists
        config_path = os.path.join(os.path.dirname(__file__), "engines.json")
        ensure_config_exists(config_path)

        if not os.path.exists(config_path):
            print(f"Warning: {config_path} not found. No engines loaded.")
            return

        try:
            with open(config_path, "r") as f:
                engines_config = json.load(f)
            
            for engine_id, cfg in engines_config.items():
                if not cfg.get("enabled", False):
                    continue
                
                class_name = cfg.get("class")
                if class_name in client_classes:
                    try:
                        engine_instance = client_classes[class_name]()
                        self.engines[engine_id] = engine_instance
                        
                        # Add to category maps
                        for cat_str in cfg.get("categories", []):
                            try:
                                cat_enum = SearchCategory(cat_str)
                                self.category_map[cat_enum].append(engine_instance)
                            except ValueError:
                                print(f"Warning: Unknown category '{cat_str}' for engine '{engine_id}'")
                    except Exception as e:
                        print(f"Error initializing engine '{engine_id}': {e}")
        except Exception as e:
            print(f"Error loading engines config: {e}")

    def reload_engines(self):
        """Reloads engines from engines.json."""
        self._load_engines()

    async def fetch_all(self, query: str, max_results_per_engine: int = config.MAX_RESULTS_PER_ENGINE, offset: int = 0, category: SearchCategory = SearchCategory.GENERAL, filters: dict = None) -> SearchResponse:
        start_time = time.perf_counter()
        if filters is None:
            filters = {}
            
        date_filter = filters.get("date")
        
        # Select clients based on category
        clients = self.category_map.get(category, [])
        if not clients and category == SearchCategory.GENERAL:
            # Fallback to all enabled engines if General is empty (shouldn't happen with default config)
            clients = list(self.engines.values())
        
        # Helper to fetch from a single engine with error handling
        async def safe_fetch(client):
            try:
                # Pass category and filters
                return await client.search(query, max_results_per_engine, offset, date_filter=date_filter, category=category)
            except Exception as e:
                print(f"Engine {client.name} failed: {e}")
                return None

        # Parallel fetch from selected engines
        if not clients:
            return SearchResponse(query=query, results=[], latency=time.perf_counter() - start_time)

        tasks = [safe_fetch(client) for client in clients]
        all_results_nested = await asyncio.gather(*tasks)
        
        # Flatten and remove empty lists, track failures
        all_results = []
        failed_engines = []
        for i, result in enumerate(all_results_nested):
            engine_name = clients[i].name
            if result is None:
                failed_engines.append(engine_name)
            elif isinstance(result, list):
                print(f"Engine {engine_name} returned {len(result)} results")
                all_results.extend(result)
        
        end_time = time.perf_counter()
        
        return SearchResponse(
            query=query,
            results=all_results,
            latency=end_time - start_time,
            failed_engines=failed_engines
        )
