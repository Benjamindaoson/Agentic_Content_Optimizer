from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from enum import Enum


class ShotType(str, Enum):
    """镜头类型"""
    CLOSE_UP = "close-up"
    MID = "mid"
    WIDE = "wide"
    POV = "pov"
    OVER_SHOULDER = "over-shoulder"


class CameraMovement(str, Enum):
    """运镜方式"""
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    ZOOM = "zoom"
    DOLLY = "dolly"


class Shot(BaseModel):
    """单个镜头"""
    type: ShotType
    subject: str = Field(..., description="拍摄主体")
    duration_s: float = Field(..., ge=0.5, le=10, description="持续时长（秒）")
    camera_movement: Optional[CameraMovement] = Field(CameraMovement.STATIC, description="运镜方式")
    description: Optional[str] = Field(None, description="镜头描述")


class Pacing(str, Enum):
    """节奏"""
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class DifficultyLevel(str, Enum):
    """难度等级"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Blueprint(BaseModel):
    """可执行拍摄蓝图"""

    # 场景设定
    scene: str = Field(..., description="拍摄场景")
    scene_tags: List[str] = Field(default_factory=list, description="场景标签")

    # 镜头列表
    shot_list: List[Shot] = Field(..., min_items=1, max_items=10)

    # 道具清单
    props: List[str] = Field(default_factory=list, description="必备道具")
    optional_props: List[str] = Field(default_factory=list, description="可选道具")

    # 视觉风格
    lighting: str = Field(..., description="光线：自然光/暖光/冷光/霓虹")
    color_tone: str = Field(..., description="色调：清新/复古/高级/暗黑")
    filter_preset: Optional[str] = Field(None, description="滤镜预设")

    # 字幕样式
    subtitle_style: str = Field(..., description="字幕风格")
    subtitle_positions: List[str] = Field(default_factory=list, description="字幕位置")

    # 节奏控制
    pacing: Pacing = Field(Pacing.MEDIUM)
    bgm_style: Optional[str] = Field(None, description="BGM风格")

    # 微创新点（必填）
    micro_innovation: str = Field(..., min_length=10, description="与参考的差异化点")

    # GEO优化
    geo_text_overlay: Optional[List[str]] = Field(None, description="需要叠加的GEO文本")

    # 元数据
    estimated_production_time_min: int = Field(..., ge=5, description="预计制作时长（分钟）")
    difficulty_level: DifficultyLevel = Field(DifficultyLevel.MEDIUM)

    @validator('shot_list')
    def validate_shots(cls, v):
        if not v:
            raise ValueError("至少需要1个镜头")
        total_duration = sum(shot.duration_s for shot in v)
        if total_duration > 60:
            raise ValueError("总时长不能超过60秒")
        return v

    @validator('micro_innovation')
    def validate_innovation(cls, v):
        if len(v) < 10:
            raise ValueError("微创新描述不能少于10字")
        return v

    class Config:
        use_enum_values = True


class TextStructure(BaseModel):
    """文案结构"""
    hook: str = Field(..., min_length=5, description="Hook 部分")
    body: str = Field(..., min_length=20, description="Body 部分")
    cta: str = Field(..., min_length=5, description="CTA 部分")
    full_text: str = Field(..., description="完整文案")

    @validator('full_text')
    def validate_full_text(cls, v, values):
        # 验证完整文案包含各部分
        if 'hook' in values and values['hook'] not in v:
            raise ValueError("完整文案必须包含 Hook")
        if 'body' in values and values['body'] not in v:
            raise ValueError("完整文案必须包含 Body")
        if 'cta' in values and values['cta'] not in v:
            raise ValueError("完整文案必须包含 CTA")
        return v


class GeneratedContent(BaseModel):
    """生成的内容"""
    text_structure: TextStructure
    blueprint: Blueprint
    geo_keywords: List[str] = Field(..., min_items=3)
    geo_coverage: float = Field(..., ge=0, le=1)

    # 元数据
    action: dict = Field(..., description="使用的动作（H/B/C）")
    reference_id: Optional[str] = None
    generation_time_ms: Optional[int] = None
