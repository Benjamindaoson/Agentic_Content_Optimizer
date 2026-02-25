"""Critic 评估提示词模板"""

from typing import List, Dict, Any


def build_critic_evaluation_prompt(
    text_structure: Dict[str, str],
    blueprint: Dict[str, Any],
    geo_keywords: List[str],
    geo_coverage: float,
    platform: str,
    goal_metric: str,
    references: List[Dict[str, Any]]
) -> str:
    """构建 Critic 评估提示词"""

    # 构建参考案例上下文
    reference_context = ""
    if references:
        reference_context = "\n\n【参考案例对比】\n"
        for i, ref in enumerate(references[:2], 1):
            reference_context += f"{i}. {ref.get('title', '无标题')}\n"
            reference_context += f"   表现：{ref.get('performance', '未知')}\n"

    # 目标指标说明
    goal_descriptions = {
        "engagement": "互动率（点赞、评论、分享）",
        "completion": "完播率（视频完整观看）",
        "conversion": "转化率（引导行动）"
    }
    goal_desc = goal_descriptions.get(goal_metric, goal_metric)

    prompt = f"""你是一位专业的内容评审专家，擅长评估短视频内容的质量。

请对以下内容进行多维度评估：

【文案】
Hook（前3秒）: {text_structure["hook"]}
Body（主体内容）: {text_structure["body"]}
CTA（行动号召）: {text_structure["cta"]}

完整文案:
{text_structure["full_text"]}

【拍摄蓝图】
场景: {blueprint["scene"]}
场景标签: {', '.join(blueprint.get("scene_tags", []))}
镜头数: {len(blueprint["shot_list"])}
镜头详情:
{_format_shot_list(blueprint["shot_list"])}

道具:
- 必备: {', '.join(blueprint["props"])}
- 可选: {', '.join(blueprint.get("optional_props", []))}

视觉风格:
- 光线: {blueprint["lighting"]}
- 色调: {blueprint["color_tone"]}
- 滤镜: {blueprint.get("filter_preset", "无")}

字幕: {blueprint["subtitle_style"]}
节奏: {blueprint["pacing"]}
BGM: {blueprint.get("bgm_style", "无")}

微创新点: {blueprint["micro_innovation"]}

预计制作时长: {blueprint["estimated_production_time_min"]} 分钟
难度等级: {blueprint["difficulty_level"]}

【GEO优化】
关键词: {', '.join(geo_keywords)}
覆盖率: {geo_coverage * 100:.0f}%

【目标】
平台: {platform}
目标指标: {goal_desc}

{reference_context}

请从以下5个维度进行评估（每个维度0-1分）：

1. **creativity（创意性）** - 评估标准：
   - 内容是否新颖、有创意、能引发兴趣
   - Hook 是否有吸引力
   - 微创新点是否有效且可行
   - 与参考案例相比是否有差异化

2. **executability（可执行性）** - 评估标准：
   - 拍摄蓝图是否清晰、具体、可执行
   - 镜头设计是否合理（时长、类型、运镜）
   - 道具和场景是否容易获取
   - 制作难度是否与预估时长匹配

3. **geo_optimization（GEO优化）** - 评估标准：
   - 关键词融入是否自然、不生硬
   - 覆盖率是否达标（>=0.6为合格，>=0.8为优秀）
   - 是否有利于搜索引擎优化
   - GEO文本叠加是否合理

4. **platform_fit（平台适配）** - 评估标准：
   - 是否符合{platform}平台的内容特点
   - 语言风格是否匹配平台用户习惯
   - 内容长度是否合适（150-300字）
   - 视觉风格是否符合平台审美

5. **engagement_potential（互动潜力）** - 评估标准：
   - Hook 是否能在前3秒抓住注意力
   - Body 是否提供价值或情感共鸣
   - CTA 是否明确、有效、能引导互动
   - 整体内容是否能激发用户点赞、评论、分享

评分指南：
- 0.9-1.0: 优秀，超出预期
- 0.8-0.9: 良好，达到高标准
- 0.7-0.8: 合格，符合基本要求
- 0.6-0.7: 一般，需要改进
- 0.5-0.6: 较差，有明显问题
- 0.0-0.5: 不合格，严重问题

请按以下JSON格式输出：
{{
    "dimensions": [
        {{
            "dimension": "creativity",
            "score": 0.85,
            "reasoning": "评分理由（至少10字，要具体说明优点或问题）",
            "suggestions": ["改进建议1", "改进建议2"]
        }},
        {{
            "dimension": "executability",
            "score": 0.75,
            "reasoning": "评分理由...",
            "suggestions": ["建议..."]
        }},
        {{
            "dimension": "geo_optimization",
            "score": 0.80,
            "reasoning": "评分理由...",
            "suggestions": ["建议..."]
        }},
        {{
            "dimension": "platform_fit",
            "score": 0.78,
            "reasoning": "评分理由...",
            "suggestions": ["建议..."]
        }},
        {{
            "dimension": "engagement_potential",
            "score": 0.82,
            "reasoning": "评分理由...",
            "suggestions": ["建议..."]
        }}
    ]
}}

注意：
1. 必须包含所有5个维度
2. 每个维度的 reasoning 必须具体、有针对性
3. suggestions 应该是可操作的改进建议
4. 评分要客观、一致，避免过高或过低"""

    return prompt


def _format_shot_list(shot_list: List[Dict[str, Any]]) -> str:
    """格式化镜头列表"""
    formatted = []
    for i, shot in enumerate(shot_list, 1):
        formatted.append(
            f"  {i}. {shot['type']} - {shot['subject']} "
            f"({shot['duration_s']}s, {shot['camera_movement']})"
        )
    return "\n".join(formatted)
