import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
from src.mnemonic.config import config
import hashlib

class BingSearchClient:
    def __init__(self):
        self.name = "bing"
        self.api_key = config.BING_API_KEY
        self.url = "https://api.bing.microsoft.com/v7.0/search"

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        if not self.api_key:
            return []

        params = {
            "q": query,
            "count": max_results,
            "offset": offset,
        }
        
        if date_filter == "past_day": params["freshness"] = "Day"
        elif date_filter == "past_week": params["freshness"] = "Week"
        elif date_filter == "past_month": params["freshness"] = "Month"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    params=params,
                    headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    timeout=10.0
                )
                if response.status_code != 200:
                    return []
                
                data = response.json()
                web_pages = data.get("webPages", {}).get("value", [])
                
                results = []
                for r in web_pages:
                    url = r.get("url", "")
                    title = r.get("name", "")
                    snippet = r.get("snippet", "")
                    
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
            print(f"Error fetching from Bing: {e}")
            return []
