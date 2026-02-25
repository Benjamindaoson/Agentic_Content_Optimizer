from app.engine.agents.prompts.text_generation import (
    build_text_generation_prompt,
    build_blueprint_stage1_prompt,
    build_blueprint_stage2_prompt,
)


def test_text_generation_prompt_contains_cot_steps_and_json_fields():
    prompt = build_text_generation_prompt(
        topic="AI 提效",
        platform="xiaohongshu",
        hook_strategy="数字冲击",
        body_strategy="分点教学",
        cta_strategy="互动提问",
        hook_code="H03",
        body_code="B02",
        cta_code="C01",
        geo_keywords=["效率", "工具"],
        references=[{"title": "样例", "content": "内容示例"}],
        target_audience="职场人",
        content_style="专业",
    )

    assert "Step 1 - 受众心理分析" in prompt
    assert "Step 2 - 策略落地推演" in prompt
    assert "Step 3 - 关键词融入规划" in prompt
    assert "Step 4 - 生成最终文案" in prompt
    assert '"hook"' in prompt
    assert '"body"' in prompt
    assert '"cta"' in prompt
    assert '"full_text"' in prompt


def test_blueprint_stage1_prompt_contains_required_sections():
    prompt = build_blueprint_stage1_prompt(
        topic="AI 工具",
        platform="xiaohongshu",
        text_structure="Hook + Body + CTA",
        references=[{"metadata": {"scene": "办公室", "visual_style": "清新"}}],
    )

    assert "第一阶段：导演决策" in prompt
    assert '"scene"' in prompt
    assert '"shot_list"' in prompt
    assert '"props"' in prompt
    assert '"micro_innovation"' in prompt


def test_blueprint_stage2_prompt_contains_required_sections():
    prompt = build_blueprint_stage2_prompt(
        topic="AI 工具",
        platform="xiaohongshu",
        stage1_result={"scene": "办公室", "shot_list": [{"type": "mid"}]},
    )

    assert "补充视觉风格决策" in prompt
    assert '"lighting"' in prompt
    assert '"subtitle_style"' in prompt
    assert '"estimated_production_time_min"' in prompt
    assert '"difficulty_level"' in prompt

