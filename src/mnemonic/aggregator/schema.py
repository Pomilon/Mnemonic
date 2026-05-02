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
    ACADEMIC = "academic"
    IMAGE = "image"
    DIAGRAM = "diagram"
    AUDIO = "audio"

class SearchCategory(str, Enum):
    GENERAL = "general"
    IT = "it"
    SCIENCE = "science"
    NEWS = "news"
    SOCIAL = "social"
    IMAGES = "images"

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
    thumbnail: Optional[str] = None
    metadata: dict = {} # Extra info like duration, tags, language
    vector: Optional[List[float]] = None # To support recalibration

# ... (rest of the file)
class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    from_cache: bool = False
    latency: float = 0.0
    distance: Optional[float] = None
    query_vector: Optional[List[float]] = None # To return to frontend for subsequent rejections
    failed_engines: List[str] = []

ICON_MAP = {
    ContentType.FACT: "book-open",
    ContentType.CODE: "code",
    ContentType.DEEP_DIVE: "layout",
    ContentType.VIDEO: "video",
    ContentType.DISCUSSION: "message-square",
    ContentType.TUTORIAL: "graduation-cap",
    ContentType.DATASET: "database",
    ContentType.NEWS: "newspaper",
    ContentType.ACADEMIC: "library",
    ContentType.IMAGE: "image-plus",
    ContentType.DIAGRAM: "image",
    ContentType.AUDIO: "audio-lines"
}

COLOR_MAP = {
    ContentType.FACT: ("text-emerald-400", "bg-emerald-400/10", "border-emerald-400/20"),
    ContentType.CODE: ("text-cyan-400", "bg-cyan-400/10", "border-cyan-400/20"),
    ContentType.DEEP_DIVE: ("text-indigo-400", "bg-indigo-400/10", "border-indigo-400/20"),
    ContentType.VIDEO: ("text-rose-400", "bg-rose-400/10", "border-rose-400/20"),
    ContentType.DISCUSSION: ("text-amber-400", "bg-amber-400/10", "border-amber-400/20"),
    ContentType.TUTORIAL: ("text-orange-400", "bg-orange-400/10", "border-orange-400/20"),
    ContentType.DATASET: ("text-fuchsia-400", "bg-fuchsia-400/10", "border-fuchsia-400/20"),
    ContentType.NEWS: ("text-blue-400", "bg-blue-400/10", "border-blue-400/20"),
    ContentType.ACADEMIC: ("text-slate-300", "bg-slate-300/10", "border-slate-300/20"),
    ContentType.IMAGE: ("text-pink-400", "bg-pink-400/10", "border-pink-400/20"),
    ContentType.DIAGRAM: ("text-violet-400", "bg-violet-400/10", "border-violet-400/20"),
    ContentType.AUDIO: ("text-lime-400", "bg-lime-400/10", "border-lime-400/20")
}

