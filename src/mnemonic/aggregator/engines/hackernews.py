import httpx
import time
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
import hashlib

from src.mnemonic.refinement.privacy import PrivacyService

class HackerNewsClient:
    def __init__(self):
        self.name = "hackernews"
        self.url = "https://hn.algolia.com/api/v1/search"
        self.privacy = PrivacyService()

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        try:
            # Algolia uses page instead of offset
            page = offset // max_results

            params = {
                "query": query,
                "hitsPerPage": max_results,
                "page": page
            }
            
            headers = {"User-Agent": self.privacy.get_random_user_agent()}

            # if date_filter:
            #     now = int(time.time())
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
                hits = data.get("hits", [])
                
                results = []
                for r in hits:
                    title = r.get("title") or r.get("story_title") or "HN Discussion"
                    url = r.get("url")
                    if not url:
                        # For show HN or discussions without external links, use HN thread
                        url = f"https://news.ycombinator.com/item?id={r.get('objectID')}"
                    
                    snippet = f"Author: {r.get('author')} | Points: {r.get('points')} | Comments: {r.get('num_comments')}"
                    
                    result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                    
                    results.append(SearchResult(
                        id=result_id,
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.name,
                        source_type=SourceType.LIVE,
                        content_type=ContentType.DISCUSSION,
                        is_ad=False
                    ))
                return results
        except Exception as e:
            print(f"Error fetching from HackerNews: {e}")
            return []
