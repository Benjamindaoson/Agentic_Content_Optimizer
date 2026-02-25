"""Token 计量工具。

优先使用 tiktoken 做精确计量；若不可用则回退到轻量估算。
"""

from __future__ import annotations

import json
from typing import Any


def _to_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(payload)


def estimate_tokens(payload: Any, model: str | None = None) -> int:
    """估算 token 数。

    - 优先：tiktoken（精确）
    - 回退：中文字符 1.2 token、ASCII 字符 0.28 token 的混合估算
    """
    text = _to_text(payload)
    if not text:
        return 0

    try:
        import tiktoken

        model_name = model or "gpt-4o"
        try:
            enc = tiktoken.encoding_for_model(model_name)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # fallback: 粗略区分中英文，尽量降低误差
        cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        non_cjk_chars = max(len(text) - cjk_chars, 0)
        return max(int(cjk_chars * 1.2 + non_cjk_chars * 0.28), 1)

