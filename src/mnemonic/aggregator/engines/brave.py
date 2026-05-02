import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
from src.mnemonic.config import config
import hashlib

class BraveSearchClient:
    def __init__(self):
        self.name = "brave"
        self.api_key = config.BRAVE_API_KEY
        self.url = "https://api.search.brave.com/res/v1/web/search"

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        if not self.api_key:
            return []

        freshness = None
        if date_filter == "past_day": freshness = "pd"
        elif date_filter == "past_week": freshness = "pw"
        elif date_filter == "past_month": freshness = "pm"
        elif date_filter == "past_year": freshness = "py"
        
        params = {
            "q": query,
            "count": max_results,
            "offset": offset,
        }
        if freshness:
            params["freshness"] = freshness

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    params=params,
                    headers={"X-Subscription-Token": self.api_key},
                    timeout=10.0
                )
                if response.status_code != 200:
                    return []
                
                data = response.json()
                web_results = data.get("web", {}).get("results", [])
                
                results = []
                for r in web_results:
                    url = r.get("url", "")
                    title = r.get("title", "")
                    snippet = r.get("description", "")
                    
                    result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                    
                    results.append(SearchResult(
                        id=result_id,
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.name,
                        source_type=SourceType.LIVE,
                        content_type=ContentType.FACT,
                        is_ad=False
                    ))
                return results
        except Exception as e:
            print(f"Error fetching from Brave: {e}")
            return []
