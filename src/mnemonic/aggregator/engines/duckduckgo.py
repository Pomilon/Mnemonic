import asyncio
from typing import List
from ddgs import DDGS
from src.mnemonic.aggregator.schema import SearchResult

import hashlib
from src.mnemonic.aggregator.schema import SearchResult, SourceType, ContentType, SearchCategory
from src.mnemonic.refinement.privacy import PrivacyService
from src.mnemonic.config import config

class DuckDuckGoClient:
    def __init__(self):
        self.name = "duckduckgo"
        self.privacy = PrivacyService()

    async def search(self, query: str, max_results: int = config.MAX_RESULTS_PER_ENGINE, offset: int = 0, date_filter: str = None, category: SearchCategory = SearchCategory.GENERAL) -> List[SearchResult]:
        loop = asyncio.get_event_loop()
        try:
            if category == SearchCategory.IMAGES:
                results = await loop.run_in_executor(None, self._fetch_images, query, max_results, offset)
            elif category == SearchCategory.NEWS:
                results = await loop.run_in_executor(None, self._fetch_news, query, max_results, offset, date_filter)
            else:
                results = await loop.run_in_executor(None, self._fetch_results, query, max_results, offset, date_filter)
            return results
        except Exception as e:
            print(f"Error fetching results from DuckDuckGo: {e}")
            return []

    def _fetch_news(self, query: str, max_results: int, offset: int, date_filter: str = None) -> List[SearchResult]:
        ua = self.privacy.get_random_user_agent()
        timelimit = None
        if date_filter == "past_day": timelimit = "d"
        elif date_filter == "past_week": timelimit = "w"
        elif date_filter == "past_month": timelimit = "m"
        
        with DDGS() as ddgs:
            results = []
            count = 0
            for r in ddgs.news(query, max_results=max_results + offset, timelimit=timelimit):
                if count < offset:
                    count += 1
                    continue
                
                url = r.get("url", "")
                title = r.get("title", "")
                snippet = r.get("body", "")
                source = r.get("source", self.name)
                
                result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                
                results.append(SearchResult(
                    id=result_id,
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                    source_type=SourceType.LIVE,
                    content_type=ContentType.NEWS,
                    is_ad=False
                ))
                
                if len(results) >= max_results:
                    break
            return results

    def _fetch_images(self, query: str, max_results: int, offset: int) -> List[SearchResult]:
        ua = self.privacy.get_random_user_agent()
        with DDGS() as ddgs:
            results = []
            count = 0
            # ddgs doesn't take headers in constructor anymore in latest versions, 
            # but we can try to use it if supported or rely on internal rotation if it has any.
            # However, the user said image search is not working.
            for r in ddgs.images(query, max_results=max_results + offset):
                if count < offset:
                    count += 1
                    continue
                
                url = r.get("image", "")
                title = r.get("title", "")
                thumbnail = r.get("thumbnail", "")
                source_url = r.get("url", "")
                
                result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                
                results.append(SearchResult(
                    id=result_id,
                    title=title,
                    url=source_url,
                    snippet=f"Image from {url}",
                    source=self.name,
                    source_type=SourceType.LIVE,
                    content_type=ContentType.IMAGE,
                    thumbnail=thumbnail,
                    is_ad=False
                ))
                
                if len(results) >= max_results:
                    break
            return results

    def _fetch_results(self, query: str, max_results: int, offset: int, date_filter: str = None) -> List[SearchResult]:
        ua = self.privacy.get_random_user_agent()
        timelimit = None
        if date_filter == "past_day": timelimit = "d"
        elif date_filter == "past_week": timelimit = "w"
        elif date_filter == "past_month": timelimit = "m"
        elif date_filter == "past_year": timelimit = "y"
        
        with DDGS() as ddgs:
            results = []
            # Fetch slightly more than needed to skip the offset
            # DDGS generator doesn't support skipping natively in a single call easily
            # so we just iterate and skip
            count = 0
            for r in ddgs.text(query, max_results=max_results + offset, timelimit=timelimit):
                if count < offset:
                    count += 1
                    continue
                
                url = r.get("href", "") or ""
                title = r.get("title", "") or ""
                snippet = r.get("body", "") or ""
                
                # Generate unique ID
                result_id = hashlib.md5(f"{url}{title}".encode()).hexdigest()
                
                # Enhanced heuristic for content type
                content_type = ContentType.FACT
                url_lower = url.lower()
                
                DOMAIN_MAP = {
                    ContentType.CODE: ["github.com", "gitlab.com", "stackoverflow.com", "bitbucket.org", "codepen.io", "gist.github.com"],
                    ContentType.VIDEO: ["youtube.com", "vimeo.com", "dailymotion.com", "twitch.tv"],
                    ContentType.DEEP_DIVE: ["arxiv.org", "wikipedia.org", "scholar.google.com", "britannica.com", "nature.com", "science.org"],
                    ContentType.DISCUSSION: ["reddit.com", "news.ycombinator.com", "quorum.com", "stackexchange.com"],
                    ContentType.NEWS: ["reuters.com", "apnews.com", "bbc.com", "nytimes.com", "wsj.com", "theguardian.com"],
                    ContentType.TUTORIAL: ["medium.com", "dev.to", "tutorialspoint.com", "geeksforgeeks.org", "w3schools.com"],
                    ContentType.DATASET: ["kaggle.com", "datasetsearch.google.com", "uci.edu", "huggingface.co/datasets"],
                }
                
                for c_type, domains in DOMAIN_MAP.items():
                    if any(domain in url_lower for domain in domains):
                        content_type = c_type
                        break

                results.append(SearchResult(
                    id=result_id,
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=self.name,
                    source_type=SourceType.LIVE,
                    content_type=content_type,
                    is_ad=False
                ))
                
                if len(results) >= max_results:
                    break
                    
            return results
