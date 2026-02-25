"""
环境设置脚本
检查并安装所有必需的依赖
"""

import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_python_version():
    """检查 Python 版本"""
    logger.info("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        logger.error(f"Python 3.11+ required, but found {version.major}.{version.minor}")
        return False
    logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_requirements():
    """安装依赖"""
    logger.info("Installing requirements...")

    requirements_path = Path(__file__).parent.parent / "requirements.txt"

    if not requirements_path.exists():
        logger.error(f"requirements.txt not found at {requirements_path}")
        return False

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_path)
        ])
        logger.info("✅ All requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install requirements: {e}")
        return False


def check_cuda():
    """检查 CUDA 是否可用"""
    logger.info("Checking CUDA availability...")
    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"✅ CUDA available: {torch.cuda.get_device_name(0)}")
            logger.info(f"   CUDA version: {torch.version.cuda}")
            logger.info(f"   GPU count: {torch.cuda.device_count()}")
            return True
        else:
            logger.warning("⚠️  CUDA not available. Training will be slow on CPU.")
            return False
    except ImportError:
        logger.warning("⚠️  PyTorch not installed yet")
        return False


def create_directories():
    """创建必要的目录"""
    logger.info("Creating necessary directories...")

    base_dir = Path(__file__).parent.parent.parent
    directories = [
        base_dir / "data" / "raw",
        base_dir / "data" / "processed",
        base_dir / "models" / "qwen2.5-7b-sft",
        base_dir / "models" / "qwen2.5-7b-grpo",
        base_dir / "results" / "baseline",
        base_dir / "results" / "experiment",
        base_dir / "results" / "ab_test",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"  Created: {directory}")

    logger.info("✅ All directories created")
    return True


def check_disk_space():
    """检查磁盘空间"""
    logger.info("Checking disk space...")

    import shutil
    base_dir = Path(__file__).parent.parent.parent
    stat = shutil.disk_usage(base_dir)

    free_gb = stat.free / (1024 ** 3)
    logger.info(f"  Free space: {free_gb:.2f} GB")

    if free_gb < 100:
        logger.warning(f"⚠️  Low disk space! Need at least 100GB, but only {free_gb:.2f}GB available")
        logger.warning("   TikTok-10M: ~50GB")
        logger.warning("   JD Reviews: ~5GB")
        logger.warning("   Mercari: ~10GB")
        logger.warning("   Models: ~30GB")
        return False

    logger.info("✅ Sufficient disk space")
    return True


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Growth Flywheel 2.5 - Environment Setup")
    logger.info("=" * 60)

    # 1. 检查 Python 版本
    if not check_python_version():
        logger.error("Setup failed: Python version check failed")
        sys.exit(1)

    # 2. 检查磁盘空间
    if not check_disk_space():
        logger.warning("Setup warning: Low disk space")

    # 3. 创建目录
    if not create_directories():
        logger.error("Setup failed: Directory creation failed")
        sys.exit(1)

    # 4. 安装依赖
    if not install_requirements():
        logger.error("Setup failed: Requirements installation failed")
        sys.exit(1)

    # 5. 检查 CUDA
    check_cuda()

    logger.info("=" * 60)
    logger.info("✅ Environment setup completed!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Download datasets:")
    logger.info("   python backend/scripts/download_datasets.py")
    logger.info("\n2. Train SFT model:")
    logger.info("   python backend/scripts/train_sft.py")
    logger.info("\n3. Train GRPO model:")
    logger.info("   python backend/scripts/train_grpo.py")
    logger.info("\n4. Evaluate A/B test:")
    logger.info("   python backend/scripts/evaluate_ab_test.py")


if __name__ == "__main__":
    main()
