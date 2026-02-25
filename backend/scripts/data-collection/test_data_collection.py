"""
测试数据收集系统

验证数据库表创建成功，并测试基本的 CRUD 操作
"""

import sys
from pathlib import Path
import uuid
import time

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog


def test_content_generation_log():
    """测试内容生成日志"""
    print("\n" + "=" * 80)
    print("📝 测试内容生成日志")
    print("=" * 80)

    db = SessionLocal()

    try:
        # 创建测试数据
        content = ContentGenerationLog(
            id=str(uuid.uuid4()),
            user_id="test_user_001",
            session_id="session_001",
            platform="xiaohongshu",
            topic="AI 写作工具推荐",
            persona="学生党",
            keywords=["AI", "写作", "效率"],
            model_version="claude-3.5-sonnet",
            rag_enabled=True,
            rl_enabled=True,
            generated_content="🤖 学生党必备！这款 AI 写作工具太好用了...\n\n作为一名大学生，每天都要写各种作业和论文...",
            title="学生党必备的 AI 写作神器",
            tags=["AI工具", "学习效率", "写作助手"],
            generation_time_ms=8500,
            token_count=450,
            cost_usd=0.015,
            quality_score=0.85,
            platform_fit_score=0.92,
            viral_potential_score=0.78
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        print(f"✅ 内容生成日志创建成功")
        print(f"   ID: {content.id}")
        print(f"   平台: {content.platform}")
        print(f"   主题: {content.topic}")
        print(f"   模型: {content.model_version}")
        print(f"   质量评分: {content.quality_score}")

        # 查询验证
        count = db.query(ContentGenerationLog).count()
        print(f"\n📊 数据库中共有 {count} 条内容生成日志")

        return content.id

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def test_user_feedback_log(content_id: str):
    """测试用户反馈日志"""
    print("\n" + "=" * 80)
    print("👍 测试用户反馈日志")
    print("=" * 80)

    db = SessionLocal()

    try:
        # 创建多个反馈
        feedbacks = [
            UserFeedbackLog(
                id=str(uuid.uuid4()),
                content_id=content_id,
                user_id="user_001",
                event_type="view",
                event_timestamp=int(time.time() * 1000)
            ),
            UserFeedbackLog(
                id=str(uuid.uuid4()),
                content_id=content_id,
                user_id="user_001",
                event_type="like",
                event_timestamp=int(time.time() * 1000) + 5000,
                rating=5,
                feedback_text="内容很有帮助！"
            ),
            UserFeedbackLog(
                id=str(uuid.uuid4()),
                content_id=content_id,
                user_id="user_002",
                event_type="save",
                event_timestamp=int(time.time() * 1000) + 10000
            ),
            UserFeedbackLog(
                id=str(uuid.uuid4()),
                content_id=content_id,
                user_id="user_003",
                event_type="share",
                event_timestamp=int(time.time() * 1000) + 15000
            ),
        ]

        db.add_all(feedbacks)
        db.commit()

        print(f"✅ 用户反馈日志创建成功")
        print(f"   创建了 {len(feedbacks)} 条反馈记录")

        # 查询验证
        all_feedbacks = db.query(UserFeedbackLog).filter_by(content_id=content_id).all()
        print(f"\n📊 该内容共有 {len(all_feedbacks)} 条反馈")

        # 按事件类型统计
        event_types = {}
        for f in all_feedbacks:
            event_types[f.event_type] = event_types.get(f.event_type, 0) + 1

        print("\n事件类型分布:")
        for event_type, count in event_types.items():
            print(f"   {event_type}: {count}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        db.rollback()
    finally:
        db.close()


def test_ab_test_log(content_id: str):
    """测试 A/B 测试日志"""
    print("\n" + "=" * 80)
    print("🧪 测试 A/B 测试日志")
    print("=" * 80)

    db = SessionLocal()

    try:
        # 创建 A/B 测试记录
        ab_test = ABTestLog(
            id=str(uuid.uuid4()),
            experiment_id="exp_model_comparison_001",
            variant_id="claude-3.5",
            content_id=content_id,
            user_id="test_user_001",
            experiment_config={
                "name": "模型对比测试",
                "variants": ["claude-3.5", "gpt-4", "deepseek"],
                "traffic_split": [0.33, 0.33, 0.34],
                "start_date": "2026-02-15",
                "end_date": "2026-02-22"
            },
            outcome="success",
            outcome_value=0.85
        )

        db.add(ab_test)
        db.commit()
        db.refresh(ab_test)

        print(f"✅ A/B 测试日志创建成功")
        print(f"   实验 ID: {ab_test.experiment_id}")
        print(f"   变体 ID: {ab_test.variant_id}")
        print(f"   结果: {ab_test.outcome}")
        print(f"   结果值: {ab_test.outcome_value}")

        # 查询验证
        count = db.query(ABTestLog).count()
        print(f"\n📊 数据库中共有 {count} 条 A/B 测试日志")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        db.rollback()
    finally:
        db.close()


def test_query_with_relationships():
    """测试关联查询"""
    print("\n" + "=" * 80)
    print("🔗 测试关联查询")
    print("=" * 80)

    db = SessionLocal()

    try:
        # 查询内容及其反馈
        contents = db.query(ContentGenerationLog).limit(5).all()

        for content in contents:
            print(f"\n内容 ID: {content.id}")
            print(f"主题: {content.topic}")
            print(f"反馈数量: {len(content.feedbacks)}")

            if content.feedbacks:
                print("反馈详情:")
                for feedback in content.feedbacks[:3]:  # 只显示前3条
                    print(f"  - {feedback.event_type} by {feedback.user_id}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
    finally:
        db.close()


def main():
    """运行所有测试"""
    print("=" * 80)
    print("🧪 数据收集系统测试")
    print("=" * 80)

    # 测试 1: 内容生成日志
    content_id = test_content_generation_log()

    if content_id:
        # 测试 2: 用户反馈日志
        test_user_feedback_log(content_id)

        # 测试 3: A/B 测试日志
        test_ab_test_log(content_id)

        # 测试 4: 关联查询
        test_query_with_relationships()

    print("\n" + "=" * 80)
    print("✅ 所有测试完成！")
    print("=" * 80)

    print("\n下一步：")
    print("1. 启动 API 服务: uvicorn app.main:app --reload")
    print("2. 访问 API 文档: http://localhost:8000/docs")
    print("3. 测试数据收集 API 端点")


if __name__ == "__main__":
    main()
