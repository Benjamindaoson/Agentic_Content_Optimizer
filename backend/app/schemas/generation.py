"""Generation request/response schemas"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class StreamGenerationRequest(BaseModel):
    """Streaming generation request"""
    topic: str = Field(..., description="Content topic")
    platform: str = Field(default="xiaohongshu", description="Target platform")
    goal: str = Field(default="engagement", description="Goal metric")
    action: Optional[Dict[str, Any]] = Field(None, description="Optional strategy action (hook, body, cta)")
