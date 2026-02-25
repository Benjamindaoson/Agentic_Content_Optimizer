#!/usr/bin/env python3
"""
Phase 2: 基线定义

基线 = 单次 LLM 调用（同 prompt 意图，无 RAG、无 Agent 编排、无 Thompson Sampling）

用于与当前系统对比，回答「比纯 LLM 好多少」。

用法：
    cd backend && python -m scripts.eval_baseline --topic "AI 提效工具推荐" [--provider claude]
    cd backend && python -m scripts.eval_baseline --topics-file scripts/eval_topics.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保 backend 在 path 中（脚本在 scripts/ 下，backend 为兄弟目录）
project_root = Path(__file__).resolve().parent.parent
backend_dir = project_root / "backend"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 中文约 1.5 字/token，英文约 4 字/token，取折中
def estimate_tokens(text: str) -> int:
    """粗略估算 token 数"""
    if not text:
        return 0
    # 混合中英文：平均约 2 字符/token
    return max(1, len(text) // 2)


BASELINE_SYSTEM = """你是一位专业的小红书文案创作者。
请为给定主题创作一条高质量文案，要求：
1. Hook（前3秒）：立即抓住注意力，10-30字
2. Body（主体）：提供价值或情感共鸣，80-200字
3. CTA（行动号召）：引导互动，10-30字
4. 总长度 150-300 字
5. 语言亲切自然，符合小红书风格

请直接输出文案内容，不要解释。"""


async def run_baseline(
    topic: str,
    platform: str = "xiaohongshu",
    provider: str = "claude",
    model: Optional[str] = None,
    evaluate: bool = True,
) -> Dict[str, Any]:
    """
    运行基线：单次 LLM 调用生成内容

    Returns:
        dict: {
            "topic": str,
            "platform": str,
            "content": str,
            "latency_ms": int,
            "input_tokens_est": int,
            "output_tokens_est": int,
            "total_tokens_est": int,
            "quality_score": float | None,  # 若 evaluate=True
        }
    """
    from app.engine.llm.unified import UnifiedLLM
    from app.engine.agents.content.critic_agent import CriticAgent
    from app.engine.agents.base import AgentConfig
    from app.engine.llm.providers.claude import ClaudeProvider

    user_prompt = f"""主题：{topic}
平台：{platform}

请创作一条符合上述要求的文案。"""

    llm = UnifiedLLM()
    messages = [{"role": "user", "content": user_prompt}]

    # 解析 provider
    provider_map = {"claude": "claude", "openai": "openai", "deepseek": "deepseek"}
    prov = provider_map.get(provider.lower(), "claude")
    model = model or ("haiku-4.5" if prov == "claude" else None)

    start = time.perf_counter()
    try:
        response = await llm.chat(
            messages=messages,
            provider=prov,
            model=model,
            system=BASELINE_SYSTEM,
            temperature=0.7,
            max_tokens=800,
        )
    except Exception as e:
        return {
            "topic": topic,
            "platform": platform,
            "content": "",
            "error": str(e),
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "input_tokens_est": estimate_tokens(BASELINE_SYSTEM + user_prompt),
            "output_tokens_est": 0,
            "total_tokens_est": 0,
            "quality_score": None,
        }

    latency_ms = int((time.perf_counter() - start) * 1000)
    content = response if isinstance(response, str) else str(response)
    input_est = estimate_tokens(BASELINE_SYSTEM + user_prompt)
    output_est = estimate_tokens(content)
    total_est = input_est + output_est

    result = {
        "topic": topic,
        "platform": platform,
        "content": content,
        "latency_ms": latency_ms,
        "input_tokens_est": input_est,
        "output_tokens_est": output_est,
        "total_tokens_est": total_est,
        "quality_score": None,
    }

    if evaluate and content:
        try:
            critic = CriticAgent(
                config=AgentConfig(name="critic", version="1.0"),
                llm_provider=ClaudeProvider(),
            )
            # 构造 Critic 需要的 generated_content 格式
            generated = {
                "text_structure": {
                    "hook": content[:50] if len(content) > 50 else content,
                    "body": content,
                    "cta": content[-50:] if len(content) > 50 else "",
                    "full_text": content,
                },
                "action": {},
            }
            resp = await critic.execute({
                "generated_content": generated,
                "platform": platform,
                "goal_metric": "engagement",
                "references": [],
                "quality_threshold": 0.7,
            })
            if resp.success and resp.data:
                eval_data = resp.data
                result["quality_score"] = eval_data.get("overall_score")
                if result["quality_score"] is not None:
                    result["quality_score"] = float(result["quality_score"])
        except Exception as e:
            result["eval_error"] = str(e)

    return result


def load_topics(path: str) -> List[Dict[str, str]]:
    """从 JSON 文件加载 topic 列表"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "topics" in data:
        return data["topics"]
    return [{"topic": str(data), "platform": "xiaohongshu"}]


async def main():
    parser = argparse.ArgumentParser(description="Phase 2: 基线评估")
    parser.add_argument("--topic", type=str, help="单个 topic")
    parser.add_argument("--topics-file", type=str, help="topic 列表 JSON 文件")
    parser.add_argument("--platform", type=str, default="xiaohongshu")
    parser.add_argument("--provider", type=str, default="claude")
    parser.add_argument("--no-evaluate", action="store_true", help="不调用 Critic 评估")
    parser.add_argument("--output", type=str, help="输出 JSON 文件路径")
    args = parser.parse_args()

    topics = []
    if args.topic:
        topics = [{"topic": args.topic, "platform": args.platform}]
    elif args.topics_file:
        topics = load_topics(args.topics_file)
    else:
        # 默认 5 个 topic
        topics = [
            {"topic": "AI 提效工具推荐", "platform": "xiaohongshu"},
            {"topic": "如何提高工作效率", "platform": "xiaohongshu"},
            {"topic": "适合新手的 AI 绘画工具", "platform": "xiaohongshu"},
            {"topic": "2024年内容创作趋势", "platform": "xiaohongshu"},
            {"topic": "如何用 AI 打造个人 IP", "platform": "xiaohongshu"},
        ]

    print("=" * 60)
    print("Phase 2: 基线评估（单次 LLM，无 RAG/Agent）")
    print("=" * 60)
    print(f"Topics: {len(topics)}")
    print(f"Provider: {args.provider}")

    results = []
    for i, t in enumerate(topics):
        topic = t.get("topic", t) if isinstance(t, dict) else t
        platform = t.get("platform", args.platform) if isinstance(t, dict) else args.platform
        print(f"\n[{i+1}/{len(topics)}] {topic}")
        r = await run_baseline(
            topic=topic,
            platform=platform,
            provider=args.provider,
            evaluate=not args.no_evaluate,
        )
        results.append(r)
        q = r.get("quality_score")
        print(f"  latency={r['latency_ms']}ms, tokens_est={r['total_tokens_est']}, quality={q}")

    # 汇总
    valid = [r for r in results if "error" not in r]
    summary = {
        "baseline": "single_llm_no_rag_no_agent",
        "provider": args.provider,
        "num_topics": len(topics),
        "num_success": len(valid),
        "avg_latency_ms": sum(r["latency_ms"] for r in valid) / len(valid) if valid else 0,
        "avg_tokens_est": sum(r["total_tokens_est"] for r in valid) / len(valid) if valid else 0,
        "avg_quality_score": None,
    }
    scores = [r["quality_score"] for r in valid if r.get("quality_score") is not None]
    if scores:
        summary["avg_quality_score"] = round(sum(scores) / len(scores), 4)

    output = {"summary": summary, "results": results}
    print("\n" + "=" * 60)
    print("Summary:", json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Saved to {args.output}")

    return output


if __name__ == "__main__":
    asyncio.run(main())
