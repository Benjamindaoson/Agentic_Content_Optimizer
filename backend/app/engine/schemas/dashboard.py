"""
Dashboard Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProjectCreate(BaseModel):
    """Project creation schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    platform: str = Field(..., description="Target platform (tiktok, xiaohongshu, etc)")
    target_audience: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Project update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    platform: Optional[str] = None
    target_audience: Optional[str] = None


class ProjectResponse(BaseModel):
    """Project response schema"""
    id: int
    name: str
    description: Optional[str]
    platform: str
    target_audience: Optional[str]
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Project list response"""
    projects: List[ProjectResponse]
    total: int
    skip: int
    limit: int


class ProjectStats(BaseModel):
    """Project statistics"""
    project_id: int
    total_episodes: int
    successful_episodes: int
    success_rate: float
    average_reward: float
    recent_episodes: int


class DashboardOverview(BaseModel):
    """Dashboard overview"""
    total_projects: int
    total_episodes: int
    successful_episodes: int
    success_rate: float
    average_reward: float
    recent_episodes: int
