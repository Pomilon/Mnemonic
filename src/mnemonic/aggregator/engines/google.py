import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
from src.mnemonic.config import config
import hashlib

class GoogleSearchClient:
    def __init__(self):
        self.name = "google"
        self.api_key = config.GOOGLE_API_KEY
        self.cse_id = config.GOOGLE_CSE_ID
        self.url = "https://www.googleapis.com/customsearch/v1"

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        if not self.api_key or not self.cse_id:
            return []

        params = {
            "q": query,
            "key": self.api_key,
            "cx": self.cse_id,
            "num": min(max_results, 10), # Google API limit per request
            "start": offset + 1,
        }
        
        if date_filter == "past_day": params["dateRestrict"] = "d1"
        elif date_filter == "past_week": params["dateRestrict"] = "w1"
        elif date_filter == "past_month": params["dateRestrict"] = "m1"
        elif date_filter == "past_year": params["dateRestrict"] = "y1"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    params=params,
                    timeout=10.0
                )
                if response.status_code != 200:
                    return []
                
                data = response.json()
                items = data.get("items", [])
                
                results = []
                for r in items:
                    url = r.get("link", "")
                    title = r.get("title", "")
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
            print(f"Error fetching from Google: {e}")
            return []
