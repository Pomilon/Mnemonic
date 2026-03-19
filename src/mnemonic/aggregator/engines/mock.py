import hashlib
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType

from src.mnemonic.config import config

class MockSearchClient:
    def __init__(self):
        self.name = "mock"

    async def search(self, query: str, max_results: int = config.MAX_RESULTS_PER_ENGINE) -> List[SearchResult]:
        results = [
            SearchResult(
                id=hashlib.md5(f"mock1{query}".encode()).hexdigest(),
                title=f"Mock Result 1 for {query}",
                url=f"https://example.com/mock1?q={query}",
                snippet=f"This is a mock snippet for {query} to test the engine without hitting real APIs.",
                source=self.name,
                source_type=SourceType.LIVE,
                content_type=ContentType.FACT
            ),
            SearchResult(
                id=hashlib.md5(f"mock2{query}".encode()).hexdigest(),
                title=f"Mock Result 2 for {query}",
                url=f"https://example.com/mock2?q={query}",
                snippet=f"Another mock result to verify de-duplication and ranking. {query} is a great topic.",
                source=self.name,
                source_type=SourceType.LIVE,
                content_type=ContentType.DISCUSSION
            )
        ]
        return results
