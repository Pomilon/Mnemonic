from typing import List
from urllib.parse import urlparse, urlunparse
from src.mnemonic.aggregator.schema import SearchResult

class DeDuplicator:
    def __init__(self):
        # Tracking parameters to strip for normalization
        self.tracking_params = [
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "gclid", "fbclid", "msclkid", "_ga", "_gid"
        ]

    def normalize_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            # Standardize scheme and netloc to lowercase
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Remove www.
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # Reconstruct without tracking parameters
            # and without fragment
            query = "&".join(
                [p for p in parsed.query.split("&") if p.split("=")[0].lower() not in self.tracking_params]
            )
            
            normalized = urlunparse((scheme, netloc, parsed.path, parsed.params, query, ""))
            return normalized.rstrip("/")
        except:
            return url

    def deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        unique_results = {}
        for result in results:
            normalized_url = self.normalize_url(result.url)
            
            if normalized_url not in unique_results:
                unique_results[normalized_url] = result
            else:
                # Keep the result from the source with higher priority or better snippet length
                # For now, just keep the first one we saw
                pass
                
        return list(unique_results.values())
