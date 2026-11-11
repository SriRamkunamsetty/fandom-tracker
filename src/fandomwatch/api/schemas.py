"""Pydantic v2 schemas for request validation, response serialization, and OpenAPI generation."""
from typing import Any, Dict, List, Optional
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Minimal fallback schema base if pydantic is not installed
    class BaseModel:
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
        def model_dump(self):
            return self.__dict__

    def Field(*a, **k):
        return None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    database: str = "connected"


class TitleResponse(BaseModel):
    id: int
    name: str
    genre: Optional[str] = None
    studio: Optional[str] = None
    release_date: Optional[str] = None
    comments: int = 0
    net_sentiment: Optional[float] = None


class CommentIngestRequest(BaseModel):
    title: str
    comment_id: str
    posted_at: str
    text: str
    likes: int = 0
    platform: str = "custom"


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ForecastResponse(BaseModel):
    title_id: int
    trend_direction: str
    alert_level: str
    days_to_threshold_breach: int
    projected_trajectory: List[Dict[str, Any]]


class CrisisBriefResponse(BaseModel):
    title: str
    severity: str
    risk_level: str
    executive_summary: str
    primary_friction_points: List[str]
    talking_points: List[str]
    immediate_actions: List[str]
    community_response_template: str
