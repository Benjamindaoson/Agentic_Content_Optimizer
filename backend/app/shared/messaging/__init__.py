"""
消息系统模块

提供 Agent 间通信的消息总线和相关功能
"""

from app.messaging.message_bus import MessageBus, MessageType

__all__ = ["MessageBus", "MessageType"]
