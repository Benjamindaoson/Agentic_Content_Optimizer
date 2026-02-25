"""
Reference Pool Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class ReferenceUpload(BaseModel):
    """Reference upload schema"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    platform: str
    content_text: str
    tags: Optional[List[str]] = []


class ReferenceResponse(BaseModel):
    """Reference response schema"""
    id: int
    title: str
    description: Optional[str]
    platform: str
    content_text: str
    content_hash: str
    tags: List[str]
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReferenceListResponse(BaseModel):
    """Reference list response"""
    references: List[ReferenceResponse]
    total: int
    skip: int
    limit: int


class ReferenceAnalysis(BaseModel):
    """Reference analysis result"""
    reference_id: int
    detected_hook: str
    detected_body: str
    detected_cta: str
    extracted_keywords: List[str]
    structure: Dict[str, str]
    confidence: float
