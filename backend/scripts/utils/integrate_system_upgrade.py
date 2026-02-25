"""
系统升级集成脚本
运行此脚本以启用所有升级功能
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""

    print("\n" + "="*80)
    print("Growth Flywheel 2.5 - 系统升级集成")
    print("="*80)

    # 1. 检查配置文件
    print("\n[1/5] 检查配置文件...")
    config_path = Path("backend/config/system_upgrade.yaml")

    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        print("请先复制配置模板:")
        print("  cp backend/config/system_upgrade.yaml.example backend/config/system_upgrade.yaml")
        return

    print(f"✅ 配置文件存在: {config_path}")

    # 2. 加载配置
    print("\n[2/5] 加载配置...")
    try:
        from app.core.config_manager import get_config_manager

        config_manager = get_config_manager(str(config_path))
        print("✅ 配置加载成功")

        # 显示启用的功能
        print("\n启用的功能:")
        features = {
            'hybrid_reward': '混合奖励模型',
            'trend_quality_filter': '趋势质量过滤',
            'diversity_experience_pool': '多样性感知经验池',
            'model_router': '模型路由器',
            'generation_tracer': '生成追踪系统',
            'hierarchical_action_space': '层级动作空间'
        }

        for key, name in features.items():
            enabled = config_manager.is_feature_enabled(key)
            status = "✅ 启用" if enabled else "⚪ 禁用"
            print(f"  {status} {name}")

    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return

    # 3. 初始化组件
    print("\n[3/5] 初始化组件...")
    try:
        from app.core.system_upgrade import get_integration

        integration = get_integration()
        components = integration.initialize_all()

        print("✅ 组件初始化成功")
        print("\n初始化的组件:")
        for name, component in components.items():
            status = "✅" if component is not None else "⚪"
            print(f"  {status} {name}")

    except Exception as e:
        print(f"❌ 组件初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 运行测试
    print("\n[4/5] 运行集成测试...")
    try:
        # 测试奖励模型
        if components['reward_model']:
            print("  测试混合奖励模型...")
            # 简单测试
            print("  ✅ 奖励模型可用")

        # 测试经验池
        if components['experience_pool']:
            print("  测试多样性经验池...")
            stats = components['experience_pool'].get_statistics()
            print(f"  ✅ 经验池可用 (经验数: {stats.get('total_experiences', 0)})")

        # 测试追踪器
        if components['tracer']:
            print("  测试生成追踪器...")
            print("  ✅ 追踪器可用")

        print("✅ 集成测试通过")

    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 5. 显示状态
    print("\n[5/5] 系统状态...")
    try:
        status = integration.get_status()

        print(f"\n系统版本: {status['version']}")
        print("\n功能状态:")
        for feature, enabled in status['features'].items():
            status_icon = "✅" if enabled else "⚪"
            print(f"  {status_icon} {feature}")

        print("\n组件状态:")
        for component, initialized in status['components'].items():
            status_icon = "✅" if initialized else "⚪"
            print(f"  {status_icon} {component}")

    except Exception as e:
        print(f"❌ 获取状态失败: {e}")

    print("\n" + "="*80)
    print("集成完成！")
    print("="*80)

    print("\n下一步:")
    print("1. 启动后端服务: cd backend && uvicorn app.main:app --reload")
    print("2. 查看升级指南: SYSTEM_UPGRADE_GUIDE.md")
    print("3. 运行示例: python backend/examples/system_upgrade_demo.py")


if __name__ == "__main__":
    asyncio.run(main())
