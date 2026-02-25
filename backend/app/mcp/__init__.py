"""
MCP (Multi-Channel Processing) 模块

提供多平台内容适配和发布功能
"""

from app.mcp.platform_adapters import (
    PlatformAdapter,
    XiaohongshuAdapter,
    DouyinAdapter,
    WeiboAdapter,
    Platform
)
from app.mcp.multi_platform_manager import MultiPlatformManager

__all__ = [
    "PlatformAdapter",
    "XiaohongshuAdapter",
    "DouyinAdapter",
    "WeiboAdapter",
    "Platform",
    "MultiPlatformManager"
]
