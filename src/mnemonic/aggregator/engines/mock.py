import asyncio
import hashlib
from typing import List
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
from src.mnemonic.config import config

class MockSearchEngine:
    def __init__(self, name: str = "mock-engine"):
        self.name = name

    async def search(self, query: str, max_results: int = config.MAX_RESULTS_PER_ENGINE, offset: int = 0, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        # Simulate network latency
        await asyncio.sleep(0.1)
        
        results = []
        for i in range(offset, offset + max_results):
            url = f"https://mock-{self.name}.com/result/{i}"
            title = f"Mock Result {i} for '{query}' from {self.name}"
            snippet = f"This is a mock result {i} from {self.name} for the category {category}. It provides simulated information for testing purposes."
            
            # Use content type based on category
            content_type = ContentType.FACT
            thumbnail = None
            
            if category == SearchCategory.IMAGES:
                content_type = ContentType.IMAGE
                thumbnail = f"https://picsum.photos/seed/{self.name}{i}/200/200"
            elif category == SearchCategory.IT:
                content_type = ContentType.CODE
            elif category == SearchCategory.SCIENCE:
                content_type = ContentType.ACADEMIC
            elif category == SearchCategory.NEWS:
                content_type = ContentType.NEWS
            elif category == SearchCategory.SOCIAL:
                content_type = ContentType.DISCUSSION

            result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
            
            results.append(SearchResult(
                id=result_id,
                title=title,
                url=url,
                snippet=snippet,
                source=self.name,
                source_type=SourceType.LIVE,
                content_type=content_type,
                thumbnail=thumbnail,
                is_ad=False,
                score=1.0 - (i * 0.01)
            ))
        return results
