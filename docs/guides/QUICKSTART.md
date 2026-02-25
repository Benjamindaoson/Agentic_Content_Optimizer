# 快速开始指南 - 数据集下载和模型微调

## 前置要求

### 硬件要求
- **GPU**: 4x NVIDIA A100 (80GB) 或同等算力
- **内存**: 256GB+ RAM
- **存储**: 100GB+ 可用空间
  - TikTok-10M: ~50GB
  - JD Reviews: ~5GB
  - Mercari MerRec: ~10GB
  - 模型权重: ~30GB

### 软件要求
- Python 3.11+
- CUDA 11.8+
- PyTorch 2.1+

## 步骤 1: 环境设置

```bash
cd growth-flywheel-2.5/backend

# 运行环境设置脚本
python scripts/setup_environment.py
```

这个脚本会:
- ✅ 检查 Python 版本
- ✅ 检查磁盘空间 (需要 100GB+)
- ✅ 创建必要的目录
- ✅ 安装所有依赖 (包括 polars, datasets, transformers, trl 等)
- ✅ 检查 CUDA 是否可用

## 步骤 2: 下载数据集

### 方法 1: 使用我们的脚本 (推荐)

```bash
python scripts/download_datasets.py
```

这个脚本会自动下载并预处理:
1. **TikTok-10M** (50GB, ~2-3小时)
2. **JD Reviews** (5GB, ~30分钟)
3. **Mercari MerRec** (10GB, ~1小时)

### 方法 2: 手动下载 TikTok-10M

```python
from datasets import load_dataset

# 加载完整数据集
dataset = load_dataset("The-data-company/TikTok-10M")

# 访问训练集
train_dataset = dataset["train"]

# 查看样本
sample = train_dataset[0]
print(f"description: {sample['desc']}")
print(f"likes: {sample['digg_count']}")
print(f"url: {sample['url']}")
```

### 方法 3: 流式加载 (节省内存)

```python
from datasets import load_dataset

# 流式加载，不下载全部数据
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

## 步骤 3: 数据预处理

下载完成后，脚本会自动进行预处理:

### TikTok-10M 预处理
```python
# 1. Same-account normalization
baseline = median(last_10_posts_likes)

# 2. Relative gain
r_gain = (likes - baseline) / baseline

# 3. Adjusted reward
r_adj = r_gain * log(1 + play_count)

# 4. Final reward
reward = 0.7 * r_adj + 0.3 * geo_score
```

### JD Reviews 预处理
```python
# 转换为 SFT 格式
{
    "instruction": "请用口语化、有趣的方式描述这个产品",
    "input": "{product_category}",
    "output": "{review_text}"
}
```

## 步骤 4: L1 SFT 训练 (风格对齐)

```bash
# 生成训练配置
python scripts/train_sft.py

# 启动训练 (需要 6-8 小时)
bash models/qwen2.5-7b-sft/train_sft.sh

# 或使用 LLaMA-Factory Web UI
llamafactory-cli webui
```

**训练配置**:
- 模型: Qwen2.5-7B
- LoRA: rank=16, alpha=32
- Batch size: 4
- Gradient accumulation: 8
- Learning rate: 5e-5
- Epochs: 3

**预期时间**: 6-8 小时 (4x A100)

## 步骤 5: GRPO 训练 (策略优化)

```bash
# 启动 GRPO 训练 (需要 12-16 小时)
python scripts/train_grpo.py
```

**训练配置**:
- 基础模型: Qwen2.5-7B-SFT (上一步的输出)
- Group size: 8
- Learning rate: 1e-5
- Batch size: 8
- Epochs: 3

**预期时间**: 12-16 小时 (4x A100)

## 步骤 6: A/B 测试评估

```bash
python scripts/evaluate_ab_test.py \
  --baseline ./results/baseline/generated_contents.jsonl \
  --experiment ./results/experiment/generated_contents.jsonl \
  --output ./results/ab_test
```

**评估指标**:
1. 高分区覆盖率 (>= 0.8)
2. GEO 引用成功率 (>= 0.7)
3. 结构多样性 (熵)

## 常见问题

### Q1: ModuleNotFoundError: No module named 'polars'

**解决方案**:
```bash
pip install polars pandas datasets tqdm transformers trl peft torch
```

或运行:
```bash
python scripts/setup_environment.py
```

### Q2: 磁盘空间不足

**解决方案**:
- 使用流式加载 (streaming=True)
- 只下载部分数据 (split="train[:10%]")
- 清理缓存 (~/.cache/huggingface)

### Q3: CUDA out of memory

**解决方案**:
- 减小 batch size
- 使用 gradient checkpointing
- 使用 8-bit 量化 (load_in_8bit=True)

### Q4: 下载速度慢

**解决方案**:
```bash
# 设置 Hugging Face 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 或使用代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

## 监控训练进度

### TensorBoard
```bash
tensorboard --logdir=./models/qwen2.5-7b-sft/checkpoints
```

### Weights & Biases
```bash
# 登录 W&B
wandb login

# 查看实验
wandb project growth-flywheel-2.5
```

## 验证安装

```bash
# 检查 Python 版本
python --version  # 应该 >= 3.11

# 检查 CUDA
python -c "import torch; print(torch.cuda.is_available())"  # 应该输出 True

# 检查依赖
python -c "import polars, datasets, transformers, trl, peft"  # 不应该报错

# 检查磁盘空间
df -h  # 应该有 100GB+ 可用空间
```

## 时间估算

| 步骤 | 时间 | 硬件 |
|------|------|------|
| 环境设置 | 10-15 分钟 | - |
| 下载 TikTok-10M | 2-3 小时 | 网速依赖 |
| 下载 JD Reviews | 30 分钟 | 网速依赖 |
| 下载 Mercari | 1 小时 | 网速依赖 |
| 数据预处理 | 1-2 小时 | CPU |
| L1 SFT 训练 | 6-8 小时 | 4x A100 |
| GRPO 训练 | 12-16 小时 | 4x A100 |
| A/B 测试评估 | 30 分钟 | CPU |
| **总计** | **24-32 小时** | - |

## 成本估算

### 云服务器 (AWS p4d.24xlarge)
- 配置: 8x A100 (40GB), 1152GB RAM
- 价格: ~$32/小时
- 总成本: $768 - $1024 (24-32 小时)

### 云服务器 (Google Cloud A2)
- 配置: 4x A100 (80GB), 680GB RAM
- 价格: ~$15/小时
- 总成本: $360 - $480 (24-32 小时)

## 下一步

完成训练后:
1. 启动后端服务: `uvicorn app.main:app --reload`
2. 启动前端服务: `cd frontend && npm run dev`
3. 访问内容驾驶舱: http://localhost:3000/cockpit
4. 开始生成内容！

## 技术支持

如有问题，请查看:
- 📖 完整文档: `docs/`
- 🐛 问题反馈: GitHub Issues
- 💬 讨论区: GitHub Discussions
