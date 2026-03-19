from pydantic import BaseModel
from typing import List, Optional

from enum import Enum

class ContentType(str, Enum):
    FACT = "fact"
    CODE = "code"
    DEEP_DIVE = "deep_dive"
    VIDEO = "video"
    DISCUSSION = "discussion"
    TUTORIAL = "tutorial"
    DATASET = "dataset"
    NEWS = "news"
    DIAGRAM = "diagram"
    AUDIO = "audio"

class SourceType(str, Enum):
    CACHE = "cache"
    LIVE = "live"

class SearchResult(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    source: str
    source_type: SourceType
    content_type: ContentType = ContentType.FACT
    score: float = 0.0
    is_ad: bool = False
    metadata: dict = {} # Extra info like duration, tags, language
    vector: Optional[List[float]] = None # To support recalibration

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    from_cache: bool = False
    latency: float = 0.0
    distance: Optional[float] = None
    query_vector: Optional[List[float]] = None # To return to frontend for subsequent rejections
