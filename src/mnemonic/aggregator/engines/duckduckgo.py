import asyncio
from typing import List
from ddgs import DDGS
from src.mnemonic.aggregator.schema import SearchResult

import hashlib
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType
from src.mnemonic.config import config

class DuckDuckGoClient:
    def __init__(self):
        self.name = "duckduckgo"

    async def search(self, query: str, max_results: int = config.MAX_RESULTS_PER_ENGINE, offset: int = 0) -> List[SearchResult]:
        loop = asyncio.get_event_loop()
        try:
            # ddgs is a blocking call, so we wrap it in a thread
            results = await loop.run_in_executor(None, self._fetch_results, query, max_results, offset)
            return results
        except Exception as e:
            print(f"Error fetching results from DuckDuckGo: {e}")
            return []

    def _fetch_results(self, query: str, max_results: int, offset: int) -> List[SearchResult]:
        with DDGS() as ddgs:
            results = []
            # Fetch slightly more than needed to skip the offset
            # DDGS generator doesn't support skipping natively in a single call easily
            # so we just iterate and skip
            count = 0
            for r in ddgs.text(query, max_results=max_results + offset):
                if count < offset:
                    count += 1
                    continue
                
                url = r.get("href", "") or ""
                title = r.get("title", "") or ""
                snippet = r.get("body", "") or ""
                
                # Generate unique ID
                result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                
                # Basic heuristic for content type
                content_type = ContentType.FACT
                if any(x in url for x in ["github.com", "gitlab.com", "stackoverflow.com"]):
                    content_type = ContentType.CODE
                elif any(x in url for x in ["youtube.com", "vimeo.com"]):
                    content_type = ContentType.VIDEO
                elif any(x in url for x in ["arxiv.org", "wikipedia.org"]):
                    content_type = ContentType.DEEP_DIVE
                elif any(x in url for x in ["reddit.com", "news.ycombinator.com"]):
                    content_type = ContentType.DISCUSSION

                results.append(SearchResult(
                    id=result_id,
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=self.name,
                    source_type=SourceType.LIVE,
                    content_type=content_type,
                    is_ad=False
                ))
                
                if len(results) >= max_results:
                    break
                    
            return results
