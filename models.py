# file: models.py
from typing import List, Optional
from pydantic import BaseModel


class SeriesMetadata(BaseModel):
    series: str  # required
    sequence: Optional[str] = None


class BookMetadata(BaseModel):
    title: str  # required
    subtitle: Optional[str] = None
    author: Optional[str] = None
    narrator: Optional[str] = None
    publisher: Optional[str] = None
    publishedYear: Optional[str] = None
    description: Optional[str] = None
    cover: Optional[str] = None  # URL to the cover image
    isbn: Optional[str] = None
    asin: Optional[str] = None
    genres: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    series: Optional[List[SeriesMetadata]] = None
    language: Optional[str] = None
    duration: Optional[int] = None  # in minutes


# Response model for the /search endpoint
class SearchResponse(BaseModel):
    matches: List[BookMetadata]


class ApiKey(BaseModel):
    key: str
    uses: int
    expires: int
    cap: int
    resetTime: Optional[int]
