from typing import List, Protocol
from src.mnemonic.aggregator.schema import SearchResult

class SearchEngine(Protocol):
    name: str
    async def search(self, query: str, max_results: int, offset: int) -> List[SearchResult]:
        ...
