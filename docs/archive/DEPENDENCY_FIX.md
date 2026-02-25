# 依赖安装问题解决方案

## 问题描述

用户在运行 `download_datasets.py` 时遇到错误:

```
ModuleNotFoundError: No module named 'polars'
```

## 根本原因

`download_datasets.py` 脚本需要多个 Python 包，但这些包没有被安装:
- `polars` - 高性能数据处理库
- `datasets` - Hugging Face 数据集库
- `transformers` - Transformer 模型库
- `trl` - 强化学习训练库
- `peft` - 参数高效微调库
- 等等...

## 解决方案

### 方法 1: 使用安装脚本 (推荐 - Windows)

```bash
# 在项目根目录运行
install.bat
```

这个脚本会:
1. ✅ 检查 Python 版本 (需要 3.11+)
2. ✅ 检查磁盘空间 (需要 100GB+)
3. ✅ 创建所有必要的目录
4. ✅ 安装所有依赖 (包括 polars)
5. ✅ 检查 CUDA 是否可用

### 方法 2: 使用 Python 脚本

```bash
cd backend
python scripts/setup_environment.py
```

这个脚本会:
1. ✅ 检查 Python 版本
2. ✅ 检查磁盘空间
3. ✅ 创建目录结构
4. ✅ 自动安装 requirements.txt 中的所有依赖
5. ✅ 检查 CUDA

### 方法 3: 手动安装

```bash
cd backend
pip install -r requirements.txt
```

或者只安装数据处理相关的包:

```bash
pip install polars pandas datasets tqdm transformers trl peft torch
```

## 已更新的文件

### 1. `backend/requirements.txt`
添加了所有必需的依赖:
- 数据处理: polars, pandas, numpy, datasets
- ML/RL: torch, transformers, trl, peft, bitsandbytes
- 评估: scipy, scikit-learn, matplotlib, seaborn
- 监控: wandb, tensorboard
- 训练: llmtuner (LLaMA-Factory)

### 2. `backend/scripts/setup_environment.py` (新建)
自动化环境设置脚本:
- 检查 Python 版本
- 检查磁盘空间
- 创建目录结构
- 安装所有依赖
- 检查 CUDA

### 3. `install.bat` (新建)
Windows 一键安装脚本:
- 用户友好的安装流程
- 自动检查和安装
- 提供下一步指引

### 4. `QUICKSTART.md` (新建)
完整的快速开始指南:
- 详细的环境要求
- 分步安装说明
- 数据集下载指南
- 训练流程说明
- 常见问题解答
- 时间和成本估算

### 5. `DATASETS.md` (新建)
数据集使用指南:
- TikTok-10M 详细说明
- 使用示例 (包括用户提供的代码)
- 流式加载方法
- 在 Growth Flywheel 2.5 中的应用
- JD Reviews 和 Mercari 说明
- 完整下载流程

### 6. `README.md` (更新)
更新了快速开始部分:
- 添加了指向 QUICKSTART.md 和 DATASETS.md 的链接
- 添加了数据集下载步骤
- 添加了模型训练步骤
- 更清晰的安装流程

## 验证安装

运行以下命令验证所有依赖已正确安装:

```bash
# 检查 Python 版本
python --version  # 应该 >= 3.11

# 检查关键依赖
python -c "import polars; print('polars:', polars.__version__)"
python -c "import datasets; print('datasets:', datasets.__version__)"
python -c "import transformers; print('transformers:', transformers.__version__)"
python -c "import trl; print('trl:', trl.__version__)"
python -c "import peft; print('peft:', peft.__version__)"

# 检查 CUDA
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## 下一步

安装完成后，可以开始下载数据集:

```bash
python backend/scripts/download_datasets.py
```

**注意**:
- TikTok-10M: ~50GB, 需要 2-3 小时
- JD Reviews: ~5GB, 需要 30 分钟
- Mercari MerRec: ~10GB, 需要 1 小时
- 总计: ~65GB, 需要 3-4 小时

## 关于数据集下载

### TikTok-10M 使用方法 (来自官方文档)

```python
from datasets import load_dataset

# 加载完整数据集
dataset = load_dataset("The-data-company/TikTok-10M")

# 访问训练集
train_dataset = dataset["train"]

# 访问样本
sample = train_dataset[0]
print(f"description: {sample['desc']}")
print(f"likes: {sample['digg_count']}")
print(f"url: {sample['url']}")
```

### 流式加载 (节省内存)

```python
from datasets import load_dataset

# 流式加载
dataset = load_dataset(
    "The-data-company/TikTok-10M",
    split="train",
    streaming=True
)

# 迭代处理
for i, sample in enumerate(dataset):
    if i >= 1000:  # 只处理前 1000 条
        break
    print(sample['desc'])
```

## 技术支持

如有问题:
- 📖 查看 [QUICKSTART.md](../QUICKSTART.md)
- 📊 查看 [DATASETS.md](../DATASETS.md)
- 🐛 提交 GitHub Issue
- 💬 加入讨论区

## 总结

✅ **问题已解决**: 所有必需的依赖现在都包含在 `requirements.txt` 中

✅ **自动化安装**: 提供了 3 种安装方法 (install.bat, setup_environment.py, 手动)

✅ **完整文档**: 创建了 QUICKSTART.md 和 DATASETS.md 提供详细指导

✅ **用户友好**: 提供了清晰的错误信息和解决方案

✅ **生产就绪**: 所有脚本都经过测试和验证

---

**创建时间**: 2026-02-11
**状态**: 已解决 ✅
**影响范围**: 数据集下载和模型训练
