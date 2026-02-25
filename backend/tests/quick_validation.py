"""
简化验证脚本
Quick Validation Script

快速验证重构后的系统功能
"""

import sys
sys.path.insert(0, 'd:\\growth-flywheel-2.5\\backend')

def test_imports():
    """测试所有关键模块的导入"""
    print("=" * 80)
    print("模块导入测试")
    print("=" * 80)

    tests = []

    # 1. RAG 模块
    print("\n[1/5] 测试 RAG 模块导入...")
    try:
        from app.rag.retrievers.hybrid_retriever import HybridRetriever
        from app.rag.advanced_rag import SelfRAG, AdaptiveRAG, CorrectiveRAG
        from app.rag.embeddings.embedding_service import EmbeddingService
        print("  OK HybridRetriever")
        print("  OK SelfRAG")
        print("  OK AdaptiveRAG")
        print("  OK CorrectiveRAG (CRAG)")
        print("  OK EmbeddingService")
        tests.append(("RAG Module", True))
    except Exception as e:
        print(f"  FAIL Import error: {e}")
        tests.append(("RAG Module", False))

    # 2. Agent 模块
    print("\n[2/5] 测试 Agent 模块导入...")
    try:
        from app.agents.content.trend_agent import TrendAgent
        from app.agents.content.writer_agent import WriterAgent
        from app.agents.content.critic_agent import CriticAgent
        from app.agents.content.director_agent import DirectorAgent
        print("  ✅ TrendAgent (with CRAG)")
        print("  ✅ WriterAgent (with Dynamic RAG)")
        print("  ✅ CriticAgent (with Adaptive RAG)")
        print("  ✅ DirectorAgent")
        tests.append(("Agent 模块", True))
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        tests.append(("Agent 模块", False))

    # 3. Growth Brain 模块
    print("\n[3/5] 测试 Growth Brain 模块导入...")
    try:
        from app.growth_brain.auto_account_manager import AutoAccountManager
        from app.growth_brain.multimodal_cover_engine import MultimodalCoverEngine
        from app.growth_brain.multi_platform_engine import MultiPlatformEngine
        from app.growth_brain.causal_inference_engine import CausalInferenceEngine
        print("  ✅ AutoAccountManager (unified)")
        print("  ✅ MultimodalCoverEngine")
        print("  ✅ MultiPlatformEngine")
        print("  ✅ CausalInferenceEngine")
        tests.append(("Growth Brain 模块", True))
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        tests.append(("Growth Brain 模块", False))

    # 4. 奖励模型
    print("\n[4/5] 测试奖励模型导入...")
    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2
        print("  ✅ HybridRewardModelV2 (unified)")
        tests.append(("奖励模型", True))
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        tests.append(("奖励模型", False))

    # 5. 编排系统
    print("\n[5/5] 测试编排系统导入...")
    try:
        from app.orchestration.graphs.content_generation_graph import content_generation_graph
        from app.orchestration.nodes import (
            trend_sense_node,
            director_sample_node,
            writer_generate_node,
            critic_evaluate_node,
            policy_evolution_node
        )
        print("  ✅ content_generation_graph")
        print("  ✅ All orchestration nodes")
        tests.append(("编排系统", True))
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        tests.append(("编排系统", False))

    return tests


def test_agent_initialization():
    """测试 Agent 初始化"""
    print("\n" + "=" * 80)
    print("Agent 初始化测试")
    print("=" * 80)

    tests = []

    # 1. TrendAgent with CRAG
    print("\n[1/3] 测试 TrendAgent (CRAG)...")
    try:
        from app.agents.content.trend_agent import TrendAgent

        agent = TrendAgent(enable_crag=True)
        assert agent.enable_crag is True
        assert hasattr(agent, 'crag')
        print("  ✅ TrendAgent 初始化成功")
        print("  ✅ CRAG 已启用")
        tests.append(("TrendAgent", True))
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        tests.append(("TrendAgent", False))

    # 2. WriterAgent with Dynamic RAG
    print("\n[2/3] 测试 WriterAgent (Dynamic RAG)...")
    try:
        from app.agents.content.writer_agent import WriterAgent
        from app.agents.base import AgentConfig
        from app.ml.rl.action_space import ActionSpace
        from unittest.mock import Mock

        config = AgentConfig(name="WriterAgent", description="Test", model="test", temperature=0.8)
        llm = Mock()
        action_space = ActionSpace()

        agent = WriterAgent(config, llm, action_space, enable_dynamic_rag=True)
        assert agent.enable_dynamic_rag is True
        assert hasattr(agent, 'hybrid_retriever')
        print("  ✅ WriterAgent 初始化成功")
        print("  ✅ Dynamic RAG 已启用")
        tests.append(("WriterAgent", True))
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        tests.append(("WriterAgent", False))

    # 3. CriticAgent with Adaptive RAG
    print("\n[3/3] 测试 CriticAgent (Adaptive RAG)...")
    try:
        from app.agents.content.critic_agent import CriticAgent
        from app.agents.base import AgentConfig
        from unittest.mock import Mock

        config = AgentConfig(name="CriticAgent", description="Test", model="test", temperature=0.3)
        llm = Mock()

        agent = CriticAgent(config, llm, enable_adaptive_rag=True)
        assert agent.enable_adaptive_rag is True
        assert hasattr(agent, 'adaptive_rag')
        print("  ✅ CriticAgent 初始化成功")
        print("  ✅ Adaptive RAG 已启用")
        tests.append(("CriticAgent", True))
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        tests.append(("CriticAgent", False))

    return tests


def test_growth_brain_initialization():
    """测试 Growth Brain 初始化"""
    print("\n" + "=" * 80)
    print("Growth Brain 初始化测试")
    print("=" * 80)

    tests = []

    print("\n[1/1] 测试 AutoAccountManager (RAG + RL)...")
    try:
        from app.growth_brain.auto_account_manager import AutoAccountManager
        from unittest.mock import Mock

        db = Mock()

        # 测试 RAG + RL
        manager = AutoAccountManager(db=db, enable_rag=True, enable_rl=True)
        assert manager.enable_rag is True
        assert manager.enable_rl is True
        assert hasattr(manager, 'retriever')
        assert hasattr(manager, 'self_rag')
        assert hasattr(manager, 'adaptive_rag')
        assert hasattr(manager, 'topic_selector')
        assert hasattr(manager, 'grpo_trainer')
        print("  ✅ AutoAccountManager 初始化成功")
        print("  ✅ RAG 组件已启用")
        print("  ✅ RL 组件已启用")

        # 测试仅 RAG
        manager_rag = AutoAccountManager(db=db, enable_rag=True, enable_rl=False)
        assert manager_rag.enable_rag is True
        assert manager_rag.enable_rl is False
        print("  ✅ RAG-only 模式正常")

        # 测试仅 RL
        manager_rl = AutoAccountManager(db=db, enable_rag=False, enable_rl=True)
        assert manager_rl.enable_rag is False
        assert manager_rl.enable_rl is True
        print("  ✅ RL-only 模式正常")

        tests.append(("AutoAccountManager", True))
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("AutoAccountManager", False))

    return tests


def verify_deleted_files():
    """验证已删除的文件"""
    print("\n" + "=" * 80)
    print("验证已删除的文件")
    print("=" * 80)

    import os

    deleted_files = {
        "Growth Brain 重复版本": [
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\auto_account_manager_rag.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\auto_account_manager_rl.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\multimodal_cover_engine_rag.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\multimodal_cover_engine_rl.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\multi_platform_engine_rag.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\multi_platform_engine_rl.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\causal_inference_engine_rag.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\growth_brain\\causal_inference_engine_rl.py",
        ],
        "奖励模型旧版本": [
            "d:\\growth-flywheel-2.5\\backend\\app\\rl\\reward_model.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\rl\\hybrid_reward_model.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\rl\\learned_reward.py",
        ],
        "未使用的功能": [
            "d:\\growth-flywheel-2.5\\backend\\app\\api_v4.py",
            "d:\\growth-flywheel-2.5\\backend\\app\\core\\config_manager.py",
        ],
        "未使用的目录": [
            "d:\\growth-flywheel-2.5\\backend\\app\\experiments",
            "d:\\growth-flywheel-2.5\\backend\\app\\observability",
        ]
    }

    for category, files in deleted_files.items():
        print(f"\n{category}:")
        for file_path in files:
            if os.path.exists(file_path):
                print(f"  ⚠️ 仍存在: {os.path.basename(file_path)}")
            else:
                print(f"  ✅ 已删除: {os.path.basename(file_path)}")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("Growth Flywheel 2.5 - 重构验证")
    print("=" * 80)

    all_tests = []

    # 1. 模块导入测试
    tests = test_imports()
    all_tests.extend(tests)

    # 2. Agent 初始化测试
    tests = test_agent_initialization()
    all_tests.extend(tests)

    # 3. Growth Brain 初始化测试
    tests = test_growth_brain_initialization()
    all_tests.extend(tests)

    # 4. 验证已删除的文件
    verify_deleted_files()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    for name, result in all_tests:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    passed = sum(1 for _, result in all_tests if result)
    total = len(all_tests)

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！重构成功！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit(main())
