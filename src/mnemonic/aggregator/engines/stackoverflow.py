import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
import hashlib

from src.mnemonic.refinement.privacy import PrivacyService

import time
class StackOverflowClient:
    def __init__(self):
        self.name = "stackoverflow"
        self.url = "https://api.stackexchange.com/2.3/search/advanced"
        self.privacy = PrivacyService()

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        try:
            # StackExchange uses page instead of offset
            page = (offset // max_results) + 1

            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": max_results,
                "page": page
            }

            headers = {"User-Agent": self.privacy.get_random_user_agent()}

            # if date_filter:
            #     # ... date logic ...

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                if response.status_code != 200:
                    return []
                
                data = response.json()
                items = data.get("items", [])
                
                results = []
                for r in items:
                    title = r.get("title", "")
                    url = r.get("link", "")
                    
                    # Clean up HTML tags from snippet if needed, but API usually provides body_markdown or similar if requested
                    # Here we just use a small snippet
                    tags = r.get("tags", [])
                    score = r.get("score")
                    is_answered = " [Answered]" if r.get("is_answered") else ""
                    
                    snippet = f"Tags: {', '.join(tags[:3])} | Score: {score}{is_answered}"
                    
                    result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                    
                    results.append(SearchResult(
                        id=result_id,
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.name,
                        source_type=SourceType.LIVE,
                        content_type=ContentType.CODE,
                        is_ad=False
                    ))
                return results
        except Exception as e:
            print(f"Error fetching from StackOverflow: {e}")
            return []
