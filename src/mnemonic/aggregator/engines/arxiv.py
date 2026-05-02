import httpx
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
import hashlib
from src.mnemonic.refinement.privacy import PrivacyService
import xml.etree.ElementTree as ET

class ArXivClient:
    def __init__(self):
        self.name = "arxiv"
        self.url = "http://export.arxiv.org/api/query"
        self.privacy = PrivacyService()

    async def search(self, query: str, max_results: int, offset: int, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        try:
            params = {
                "search_query": f"all:{query}",
                "start": offset,
                "max_results": max_results
            }
            headers = {"User-Agent": self.privacy.get_random_user_agent()}

            # ArXiv does not support date relative filters nicely, but we can accept the param
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                if response.status_code != 200:
                    return []
                
                # ArXiv returns Atom XML
                root = ET.fromstring(response.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                results = []
                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                    url = entry.find('atom:id', ns).text
                    summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
                    authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
                    
                    snippet = f"Authors: {', '.join(authors[:3])} | {summary[:200]}..."
                    
                    result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                    
                    results.append(SearchResult(
                        id=result_id,
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.name,
                        source_type=SourceType.LIVE,
                        content_type=ContentType.ACADEMIC,
                        is_ad=False
                    ))
                return results
        except Exception as e:
            print(f"Error fetching from ArXiv: {e}")
            return []
