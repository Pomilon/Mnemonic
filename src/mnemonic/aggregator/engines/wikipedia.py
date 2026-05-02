import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
import hashlib

from src.mnemonic.refinement.privacy import PrivacyService

class WikipediaClient:
    def __init__(self):
        self.name = "wikipedia"
        self.url = "https://en.wikipedia.org/w/api.php"
        self.privacy = PrivacyService()

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results,
                "sroffset": offset
            }
            
            headers = {"User-Agent": self.privacy.get_random_user_agent()}
            
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
                search_results = data.get("query", {}).get("search", [])
                
                results = []
                for r in search_results:
                    title = r.get("title", "")
                    # Construct URL from title
                    url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    snippet = r.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
                    
                    result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                    
                    results.append(SearchResult(
                        id=result_id,
                        title=title,
                        url=url,
                        snippet=snippet + "...",
                        source=self.name,
                        source_type=SourceType.LIVE,
                        content_type=ContentType.ACADEMIC,
                        is_ad=False
                    ))
                return results
        except Exception as e:
            print(f"Error fetching from Wikipedia: {e}")
            return []
