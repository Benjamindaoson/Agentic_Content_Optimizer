from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RagRuntimeConfig(BaseModel):
    mode: str = Field(default="adaptive")
    hybrid_search: bool = True
    top_k: int = Field(default=10, ge=1, le=50)
    query_expansion: bool = True
    context_compression: bool = True
    trend_quality_filter: bool = True


class LLMRuntimeConfig(BaseModel):
    provider: str = Field(default="claude")
    model: str = Field(default="claude-sonnet-4-5-20250514")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=128, le=200000)


class RlRuntimeConfig(BaseModel):
    thompson_sampling_enabled: bool = True
    exploration_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    reward_preset: str = Field(default="balanced")
    custom_reward_weights: Optional[Dict[str, float]] = None


class AgentRuntimeConfig(BaseModel):
    mode: str = Field(default="full_pipeline")  # full_pipeline | writer_critic | writer_only
    max_refinement_loops: int = Field(default=3, ge=1, le=5)
    quality_threshold_0_100: float = Field(default=75.0, ge=0.0, le=100.0)
    human_review_enabled: bool = False


class GenerationRuntimeConfig(BaseModel):
    enable_geo_keywords: bool = True
    enable_hook_strategy: bool = True
    enable_cta_strategy: bool = True


class EffectiveConfig(BaseModel):
    applied: List[str] = Field(default_factory=list)
    recorded_only: List[str] = Field(default_factory=list)
    details: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RuntimeConfig(BaseModel):
    request_id: str
    user_id: str
    rag: RagRuntimeConfig = Field(default_factory=RagRuntimeConfig)
    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    rl: RlRuntimeConfig = Field(default_factory=RlRuntimeConfig)
    agent: AgentRuntimeConfig = Field(default_factory=AgentRuntimeConfig)
    generation: GenerationRuntimeConfig = Field(default_factory=GenerationRuntimeConfig)
    effective: EffectiveConfig = Field(default_factory=EffectiveConfig)
    extra: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

