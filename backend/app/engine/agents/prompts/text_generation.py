"""文案生成提示词模板

升级说明：
- 加入 Chain-of-Thought（CoT）推理链，让 LLM 先做策略分析再生成内容
- blueprint 拆分为两阶段（场景+镜头 / 风格+细节），降低单次决策负担
"""

from typing import List, Optional, Dict, Any


def build_text_generation_prompt(
    topic: str,
    platform: str,
    hook_strategy: str,
    body_strategy: str,
    cta_strategy: str,
    hook_code: str,
    body_code: str,
    cta_code: str,
    geo_keywords: List[str],
    references: List[Dict[str, Any]],
    target_audience: Optional[str] = None,
    content_style: Optional[str] = None
) -> str:
    """构建文案生成提示词（含 CoT 推理链）"""

    reference_context = ""
    if references:
        reference_context = "\n\n参考案例：\n"
        for i, ref in enumerate(references[:3], 1):
            reference_context += f"{i}. {ref.get('title', '无标题')}\n"
            reference_context += f"   内容：{ref.get('content', '')[:100]}...\n"

    platform_guides = {
        "xiaohongshu": "小红书用户喜欢真实、有用的内容，语言要亲切自然，多用emoji",
        "douyin": "抖音用户注意力短暂，前3秒必须抓眼球，节奏要快",
        "tiktok": "TikTok国际化受众，语言要简洁有力，视觉冲击力强",
        "kuaishou": "快手用户偏好接地气、真实的内容，语言要朴实"
    }

    platform_guide = platform_guides.get(platform, "")

    prompt = f"""你是一位专业的短视频文案创作者，擅长{platform}平台的内容创作。

任务：为"{topic}"创作一条高质量文案

策略要求：
- Hook策略：{hook_strategy}（{hook_code}）
- Body策略：{body_strategy}（{body_code}）
- CTA策略：{cta_strategy}（{cta_code}）

GEO关键词（必须自然融入）：{', '.join(geo_keywords)}

{f'目标受众：{target_audience}' if target_audience else ''}
{f'内容风格：{content_style}' if content_style else ''}

平台特点：{platform_guide}

{reference_context}

===== 请先完成以下推理步骤（Chain-of-Thought），然后再生成文案 =====

Step 1 - 受众心理分析：
这个话题的目标读者最可能的阅读场景是什么？他们在什么情绪状态下刷到这条内容？
他们最想看到什么（解决什么痛点 / 获得什么情绪价值）？

Step 2 - 策略落地推演：
- "{hook_strategy}"策略在这个话题上，最有效的切入角度是什么？列出 2 个候选开头。
- "{body_strategy}"策略在这个话题上，最佳的内容结构是什么？
- "{cta_strategy}"策略最自然的融入方式是什么？

Step 3 - 关键词融入规划：
GEO关键词 {', '.join(geo_keywords)} 在文案的哪些位置融入最自然？

Step 4 - 生成最终文案：
基于以上分析，选择最优方案生成文案。

===== 输出格式 =====

请按以下JSON格式输出（thinking 字段为你的推理过程，final 为最终文案）：
{{
    "thinking": {{
        "audience_insight": "受众心理分析（1-2句）",
        "hook_candidates": ["候选开头1", "候选开头2"],
        "chosen_hook_reason": "选择理由",
        "body_structure": "内容结构描述",
        "keyword_placement": "关键词融入位置规划"
    }},
    "hook": "Hook部分文案（前3秒，10-30字）",
    "body": "Body部分文案（主体内容，80-200字）",
    "cta": "CTA部分文案（行动号召，10-30字）",
    "full_text": "完整文案（包含Hook+Body+CTA，150-300字）"
}}"""

    return prompt


def build_blueprint_stage1_prompt(
    topic: str,
    platform: str,
    text_structure: str,
    references: List[Dict[str, Any]]
) -> str:
    """蓝图阶段1：场景设定 + 镜头列表（导演决策）"""

    visual_context = ""
    if references:
        visual_context = "\n\n参考案例的视觉风格：\n"
        for i, ref in enumerate(references[:2], 1):
            metadata = ref.get('metadata', {})
            visual_context += f"{i}. 场景：{metadata.get('scene', '未知')}\n"
            visual_context += f"   风格：{metadata.get('visual_style', '未知')}\n"

    platform_visual_guides = {
        "xiaohongshu": "小红书偏好清新、生活化的视觉风格，光线明亮，色调温暖",
        "douyin": "抖音需要快节奏剪辑，镜头切换频繁，视觉冲击力强",
        "tiktok": "TikTok国际化审美，注重创意和视觉特效",
        "kuaishou": "快手偏好真实、接地气的拍摄风格，不需要过度修饰"
    }

    platform_visual = platform_visual_guides.get(platform, "")

    return f"""你是一位专业的短视频导演。

任务：为以下文案设计拍摄场景和镜头（第一阶段：导演决策）

文案内容：
{text_structure}

平台视觉要求：{platform_visual}
{visual_context}

请设计：
1. 拍摄场景（具体、可执行，2-4个场景标签）
2. 3-6个镜头（每个包含 type/subject/duration_s/camera_movement）
3. 必备道具（2-5个）+ 可选道具（0-3个）
4. 与参考案例的差异化微创新点（至少10字）

JSON格式输出：
{{
    "scene": "拍摄场景",
    "scene_tags": ["标签1", "标签2"],
    "shot_list": [
        {{
            "type": "close-up/mid/wide/pov/over-shoulder",
            "subject": "拍摄主体",
            "duration_s": 5.0,
            "camera_movement": "static/pan/tilt/zoom/dolly",
            "description": "镜头描述"
        }}
    ],
    "props": ["必备道具1", "必备道具2"],
    "optional_props": ["可选道具1"],
    "micro_innovation": "差异化点（至少10字）"
}}"""


def build_blueprint_stage2_prompt(
    topic: str,
    platform: str,
    stage1_result: Dict[str, Any]
) -> str:
    """蓝图阶段2：视觉风格 + 字幕 + 节奏（摄影指导决策）"""

    scene = stage1_result.get("scene", "")
    shots = len(stage1_result.get("shot_list", []))

    return f"""基于以下已确定的场景和镜头，补充视觉风格决策。

场景：{scene}
镜头数：{shots}

请补充：
1. lighting: 自然光/暖光/冷光/霓虹
2. color_tone: 清新/复古/高级/暗黑
3. filter_preset: 滤镜预设（可选）
4. subtitle_style: 字幕风格
5. subtitle_positions: 字幕位置列表
6. pacing: slow/medium/fast
7. bgm_style: BGM风格
8. geo_text_overlay: 画面关键文字（1-3个）
9. estimated_production_time_min: 预计制作时长
10. difficulty_level: easy/medium/hard

JSON格式输出：
{{
    "lighting": "光线类型",
    "color_tone": "色调",
    "filter_preset": "滤镜预设",
    "subtitle_style": "字幕风格",
    "subtitle_positions": ["位置1", "位置2"],
    "pacing": "medium",
    "bgm_style": "BGM风格",
    "geo_text_overlay": ["GEO文本1"],
    "estimated_production_time_min": 30,
    "difficulty_level": "medium"
}}"""


def build_blueprint_generation_prompt(
    topic: str,
    platform: str,
    text_structure: str,
    references: List[Dict[str, Any]]
) -> str:
    """向后兼容：单次蓝图生成（降级方案，当两阶段调用失败时使用）"""
    return build_blueprint_stage1_prompt(topic, platform, text_structure, references)
