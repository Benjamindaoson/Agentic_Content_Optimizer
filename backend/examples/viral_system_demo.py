"""
病毒式内容系统演示

展示 Phase 1 (Viral Tracker) + Phase 2 (Pattern Library) 如何与 GRPO 系统集成
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import numpy as np
from datetime import datetime, timedelta
from app.viral import (
    ViralContentTracker,
    ViralCriteria,
    ViralContent,
    PatternLibrary,
    ViralPattern
)


def simple_embed(text: str) -> np.ndarray:
    """简单的 embedding 函数（演示用）"""
    # 实际应该使用真实的 embedding 模型
    np.random.seed(hash(text) % (2**32))
    return np.random.randn(768).astype(np.float32)


def demo_phase1_viral_tracking():
    """演示 Phase 1: 病毒式内容追踪"""
    print("=" * 80)
    print("Phase 1: 病毒式内容追踪演示")
    print("=" * 80)

    # 创建追踪器
    tracker = ViralContentTracker(
        criteria=ViralCriteria(
            min_views=100000,
            min_likes=5000,
            min_shares=1000,
            min_comments=500,
            min_viral_score=0.75
        ),
        platforms=["tiktok", "xiaohongshu", "douyin"]
    )

    # 模拟追踪内容
    test_contents = [
        {
            'content_id': 'tk_001',
            'platform': 'tiktok',
            'content_type': 'video',
            'text': '限时优惠！这个产品改变了我的生活。立即购买，不要错过！',
            'url': 'https://tiktok.com/tk_001',
            'author_id': 'author_001',
            'created_at': datetime.now() - timedelta(hours=12),
            'metrics': {
                'views': 250000,
                'likes': 15000,
                'shares': 3000,
                'comments': 1200,
                'saves': 800
            },
            'category': 'ecommerce',
            'tags': ['限时优惠', '产品推荐', '生活方式']
        },
        {
            'content_id': 'xhs_002',
            'platform': 'xiaohongshu',
            'content_type': 'note',
            'text': '科学验证的护肤方法，皮肤科医生推荐。30天见效，真实案例分享。',
            'url': 'https://xiaohongshu.com/xhs_002',
            'author_id': 'author_002',
            'created_at': datetime.now() - timedelta(hours=24),
            'metrics': {
                'views': 180000,
                'likes': 12000,
                'shares': 2500,
                'comments': 800,
                'saves': 1500
            },
            'category': 'beauty',
            'tags': ['护肤', '科学', '医生推荐']
        },
        {
            'content_id': 'dy_003',
            'platform': 'douyin',
            'content_type': 'video',
            'text': '普通内容，播放量不高',
            'url': 'https://douyin.com/dy_003',
            'author_id': 'author_003',
            'created_at': datetime.now() - timedelta(hours=6),
            'metrics': {
                'views': 5000,
                'likes': 200,
                'shares': 50,
                'comments': 30,
                'saves': 10
            },
            'category': 'lifestyle',
            'tags': ['日常']
        }
    ]

    # 追踪内容
    print("\n追踪内容中...\n")
    viral_count = 0
    for content_data in test_contents:
        is_viral, viral_score, content = tracker.track_content(**content_data)

        print(f"内容 ID: {content.content_id}")
        print(f"  平台: {content.platform}")
        print(f"  播放量: {content.views:,}")
        print(f"  互动率: {content.engagement_rate:.2%}")
        print(f"  爆款分数: {viral_score:.3f}")
        print(f"  是否爆款: {'🔥 是' if is_viral else '❌ 否'}")
        print()

        if is_viral:
            viral_count += 1

    # 获取统计
    stats = tracker.get_statistics()
    print("\n追踪统计:")
    print(f"  总追踪数: {stats['total_tracked']}")
    print(f"  爆款数量: {stats['total_viral']}")
    print(f"  爆款率: {stats['viral_rate']:.2%}")
    print(f"  平台分布: {stats['platform_distribution']}")
    print(f"  平均爆款分数: {stats['average_viral_score']:.3f}")
    print(f"  平均播放量: {stats['average_views']:,.0f}")

    # 获取爆款内容
    viral_contents = tracker.get_viral_contents(sort_by="viral_score", limit=10)
    print(f"\nTop 爆款内容 ({len(viral_contents)} 条):")
    for i, content in enumerate(viral_contents, 1):
        print(f"  {i}. {content.content_id} - 分数: {content.viral_score:.3f}, 播放: {content.views:,}")

    return tracker


def demo_phase2_pattern_library(tracker: ViralContentTracker):
    """演示 Phase 2: 爆款模式库"""
    print("\n" + "=" * 80)
    print("Phase 2: 爆款模式库演示")
    print("=" * 80)

    # 创建模式库
    library = PatternLibrary(
        storage_path="data/viral/pattern_library_demo.json",
        embed_fn=simple_embed
    )

    # 从爆款内容中提取模式
    viral_contents = tracker.get_viral_contents(limit=10)

    print("\n从爆款内容中提取模式...\n")

    # 提取 Hook 模式
    hook_pattern = ViralPattern(
        pattern_id="hook_urgency_001",
        pattern_type="hook",
        name="紧迫感开场",
        description="使用限时、稀缺等词汇制造紧迫感",
        template="限时{优惠类型}！{产品/服务}改变了{目标}。{行动号召}",
        examples=[
            "限时优惠！这个产品改变了我的生活。立即购买",
            "限时折扣！这项服务改变了我的工作效率。马上体验"
        ],
        keywords=["限时", "优惠", "改变", "立即"],
        platforms=["tiktok", "xiaohongshu", "douyin"],
        categories=["ecommerce", "service"],
        tags=["urgency", "scarcity", "action"]
    )

    # 提取 Body 模式
    body_pattern = ViralPattern(
        pattern_id="body_authority_001",
        pattern_type="body",
        name="权威背书",
        description="使用专家、科学、数据等权威元素增强可信度",
        template="{权威来源}验证的{方法/产品}，{专业人士}推荐。{效果承诺}",
        examples=[
            "科学验证的护肤方法，皮肤科医生推荐。30天见效",
            "临床验证的减肥方案，营养师推荐。2周见效"
        ],
        keywords=["科学", "验证", "医生", "推荐", "见效"],
        platforms=["xiaohongshu", "douyin"],
        categories=["beauty", "health"],
        tags=["authority", "credibility", "results"]
    )

    # 提取 CTA 模式
    cta_pattern = ViralPattern(
        pattern_id="cta_fomo_001",
        pattern_type="cta",
        name="FOMO 行动号召",
        description="使用错过恐惧心理促进行动",
        template="{行动动词}，不要错过{机会/优惠}！",
        examples=[
            "立即购买，不要错过！",
            "马上体验，限量供应！"
        ],
        keywords=["立即", "马上", "不要错过", "限量"],
        platforms=["tiktok", "xiaohongshu", "douyin"],
        categories=["ecommerce", "service"],
        tags=["fomo", "urgency", "action"]
    )

    # 添加模式到库
    patterns = [hook_pattern, body_pattern, cta_pattern]
    for pattern in patterns:
        library.add_pattern(pattern)
        print(f"✅ 添加模式: {pattern.pattern_id} ({pattern.name})")

    # 模拟使用模式并更新性能
    print("\n模拟使用模式并更新性能...\n")
    for pattern in patterns:
        # 模拟 10 次使用
        for i in range(10):
            is_success = np.random.random() > 0.3  # 70% 成功率
            viral_score = np.random.uniform(0.6, 0.95) if is_success else np.random.uniform(0.3, 0.6)
            views = int(np.random.uniform(80000, 300000)) if is_success else int(np.random.uniform(10000, 80000))
            engagement_rate = np.random.uniform(0.05, 0.15) if is_success else np.random.uniform(0.01, 0.05)

            pattern.update_performance(is_success, viral_score, views, engagement_rate)

        print(f"模式: {pattern.name}")
        print(f"  使用次数: {pattern.total_uses}")
        print(f"  成功率: {pattern.success_rate:.2%}")
        print(f"  平均爆款分数: {pattern.avg_viral_score:.3f}")
        print(f"  平均播放量: {pattern.avg_views:,.0f}")
        print()

    # 相似度搜索
    print("\n相似度搜索演示:\n")
    query = "如何快速提升销量？专家建议"
    results = library.search_by_similarity(
        query_text=query,
        top_k=3,
        min_similarity=0.5
    )

    print(f"查询: '{query}'")
    print(f"找到 {len(results)} 个相似模式:\n")
    for pattern, similarity in results:
        print(f"  - {pattern.name} (相似度: {similarity:.3f})")
        print(f"    模板: {pattern.template}")
        print(f"    成功率: {pattern.success_rate:.2%}")
        print()

    # 性能搜索
    print("\n性能搜索演示:\n")
    top_patterns = library.search_by_performance(
        sort_by="success_rate",
        top_k=3
    )

    print("Top 3 高成功率模式:\n")
    for i, pattern in enumerate(top_patterns, 1):
        print(f"  {i}. {pattern.name}")
        print(f"     成功率: {pattern.success_rate:.2%}")
        print(f"     平均爆款分数: {pattern.avg_viral_score:.3f}")
        print(f"     使用次数: {pattern.total_uses}")
        print()

    # 趋势分析
    print("\n趋势分析:\n")
    trending = library.get_trending_patterns(top_k=3)

    print("Top 3 趋势模式:\n")
    for i, (pattern, trend_score) in enumerate(trending, 1):
        print(f"  {i}. {pattern.name}")
        print(f"     趋势分数: {trend_score:.3f}")
        print(f"     成功率: {pattern.success_rate:.2%}")
        print()

    # 统计信息
    stats = library.get_statistics()
    print("\n模式库统计:")
    print(f"  总模式数: {stats['total_patterns']}")
    print(f"  按类型分布: {stats['by_type']}")
    print(f"  平均成功率: {stats['avg_success_rate']:.2%}")
    print(f"  平均使用次数: {stats['avg_uses']:.1f}")

    # 保存模式库
    library.save_to_file()
    print(f"\n✅ 模式库已保存到 {library.storage_path}")

    return library


def demo_integration_with_grpo(tracker: ViralContentTracker, library: PatternLibrary):
    """演示与 GRPO 系统的集成"""
    print("\n" + "=" * 80)
    print("Phase 1+2 与 GRPO 系统集成演示")
    print("=" * 80)

    print("\n集成架构:")
    print("""
    [ Viral Tracker ] → 追踪爆款内容
            ↓
    [ Pattern Library ] → 提取可复用模式
            ↓
    [ Pattern Retrieval ] → 检索相关模式（作为 GRPO 的冷启动先验）
            ↓
    [ LLM Generator ] → 基于模式生成候选内容
            ↓
    [ Reward Model V2 ] → 评分（真实指标 + 质量 + 多样性）
            ↓
    [ Thompson Sampling ] → 智能选择动作
            ↓
    [ GRPO Training ] → 长期进化优化
            ↺ 反馈优化
    """)

    print("\n关键集成点:\n")

    # 1. 冷启动先验
    print("1. 冷启动先验（Pattern Library → Thompson Sampling）")
    print("   - Pattern Library 提供高成功率模式作为先验")
    print("   - Thompson Sampling 使用这些先验加速收敛")
    print("   - 示例：")

    top_patterns = library.search_by_performance(sort_by="success_rate", top_k=3)
    for pattern in top_patterns:
        print(f"     模式: {pattern.name}, 成功率: {pattern.success_rate:.2%}")
        print(f"     → 可作为 Thompson Sampling 的先验均值: {pattern.avg_viral_score:.3f}")

    # 2. 实时反馈
    print("\n2. 实时反馈（GRPO → Pattern Library）")
    print("   - GRPO 生成的内容如果成为爆款，自动提取新模式")
    print("   - Pattern Library 持续更新和演化")
    print("   - 示例：")
    print("     新爆款内容 → 提取模式 → 添加到库 → 下次生成时使用")

    # 3. 多样性保证
    print("\n3. 多样性保证（Pattern Library + Diversity Scorer）")
    print("   - Pattern Library 提供多样化的模式选择")
    print("   - Diversity Scorer 防止过度使用单一模式")
    print("   - 示例：")
    print("     检索到 10 个相似模式 → 随机采样 → 避免策略塌缩")

    # 4. 性能追踪
    print("\n4. 性能追踪（全链路）")
    print("   - Viral Tracker: 追踪真实爆款数据")
    print("   - Pattern Library: 追踪模式使用效果")
    print("   - Reward Model V2: 预测真实指标")
    print("   - Production Monitor: 监控系统健康")

    print("\n✅ 集成完成！系统现在具备:")
    print("   1. 自动追踪爆款（Viral Tracker）")
    print("   2. 提取可复用模式（Pattern Library）")
    print("   3. 智能冷启动（Pattern → Thompson Sampling）")
    print("   4. 长期进化（GRPO 闭环）")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("病毒式内容系统 v2.6 演示")
    print("Phase 1 (Viral Tracker) + Phase 2 (Pattern Library)")
    print("=" * 80)

    # Phase 1: 病毒式内容追踪
    tracker = demo_phase1_viral_tracking()

    # Phase 2: 爆款模式库
    library = demo_phase2_pattern_library(tracker)

    # 集成演示
    demo_integration_with_grpo(tracker, library)

    print("\n" + "=" * 80)
    print("演示完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
