import random
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

class PrivacyService:
    def __init__(self):
        self.tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid', '_hsenc', '_hsmi',
            '__hssc', '__hstc', '__hsfp', 'rb_clickid', 's_kwcid', 'pict_id'
        }
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1"
        ]

    def clean_url(self, url: str) -> str:
        """Removes tracking parameters from a URL."""
        try:
            parsed = urlparse(url)
            query_params = parse_qsl(parsed.query)
            clean_params = [
                (k, v) for k, v in query_params 
                if k.lower() not in self.tracking_params
            ]
            
            new_query = urlencode(clean_params)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            return url

    def get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)
