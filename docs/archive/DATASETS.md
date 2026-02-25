# 数据集使用指南

## TikTok-10M Dataset

### 数据集描述

TikTok-10M 是一个包含 1000 万条 TikTok 短视频帖子的大规模数据集，专为视频理解、多模态学习和社交媒体内容分析而设计。该数据集旨在弥合学术视频数据集与实际用户生成内容之间的差距，为研究人员提供现代短视频内容的真实模式和特征。

### 数据集结构

每个数据实例包含:

- **帖子元数据**: id, url, desc, challenges, create_time 等
- **帖子统计**: digg_count, comment_count, play_count 等
- **地理位置数据**: poi_name, address, poi_category 等
- **音乐数据**: music_name, music_album 等
- **视频数据**: vq_score, duration 等

### 使用示例

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

### 流式加载 (推荐用于大数据集)

```python
from datasets import load_dataset

# 流式加载，节省内存
dataset = load_dataset(
    "The-data-company/TikTok-10M",
    split="train",
    streaming=True
)

# 迭代处理
for i, sample in enumerate(dataset):
    if i >= 1000:  # 只处理前 1000 条
        break
    print(f"Video {i}: {sample['desc']}")
    print(f"Likes: {sample['digg_count']}")
    print(f"Views: {sample['play_count']}")
```

### 部分加载

```python
from datasets import load_dataset

# 只加载 10% 的数据
dataset = load_dataset(
    "The-data-company/TikTok-10M",
    split="train[:10%]"
)

print(f"Loaded {len(dataset)} samples")
```

### 数据集统计

- **总视频数**: 10,000,000
- **时间范围**: 2025 年春季
- **地理范围**: 美国地区
- **内容类型**: 热门趋势内容

### 在 Growth Flywheel 2.5 中的应用

#### 1. 代理分发环境 (Proxy Environment)

TikTok-10M 用作代理环境，模拟真实的内容发布和互动场景。

```python
from backend.app.rl.reward_model import RewardModel

# 初始化奖励模型
reward_model = RewardModel(data_path="./data/processed/tiktok-10m-processed.parquet")

# 计算奖励
reward = reward_model.calculate_reward(
    author_id="user_123",
    likes=1500,
    play_count=10000,
    geo_score=0.85
)

print(f"Reward: {reward:.4f}")
```

#### 2. 训练 Reward Model

```python
# 奖励计算公式
baseline(author) = median(last_10_posts_likes)
R_gain = (likes - baseline) / baseline
R_adj = R_gain * log(1 + play_count)
R_final = 0.7 * R_adj + 0.3 * GEO_score
```

#### 3. 支撑 GRPO 组内比较

```python
# GRPO 训练配置
config = GRPOTrainingConfig(
    data_path="./data/processed/tiktok-10m-processed.parquet",
    group_size=8,  # 每组 8 个样本
    learning_rate=1e-5,
    batch_size=8,
    num_epochs=3
)
```

### 数据预处理

我们的脚本会自动进行以下预处理:

```python
# 1. Same-account normalization
df = df.with_columns([
    pl.col("digg_count")
      .over("author_id")
      .rolling_median(window_size=10)
      .alias("baseline_likes"),
])

# 2. Relative gain
df = df.with_columns([
    ((pl.col("digg_count") - pl.col("baseline_likes")) / pl.col("baseline_likes"))
      .fill_null(0)
      .alias("relative_gain"),
])

# 3. Adjusted reward
df = df.with_columns([
    (pl.col("relative_gain") * (1 + pl.col("play_count")).log())
      .alias("adjusted_reward")
])
```

### 限制和偏差

- **时间偏差**: 数据集反映 2025 年春季的 TikTok 热门内容
- **地理偏差**: 仅包含美国地区的内容
- **内容偏差**: 专注于热门趋势内容
- **质量差异**: 用户生成内容的制作质量差异显著

### 数据访问

数据集通过 Hugging Face datasets 库提供。由于数据集较大 (10M 视频)，建议:

1. **使用流式加载** (streaming=True)
2. **下载特定分片** (split="train[:10%]")
3. **使用缓存** (cache_dir 参数)

### 伦理考虑

- **仅公开数据**: 仅包含公开可用的数据
- **隐私保护**: 不包含超出公开分享的个人身份信息
- **内容审核**: 用户应根据使用场景实施适当的内容过滤
- **负责任使用**: 应遵守 TikTok 服务条款和适用法律

### 引用

```bibtex
@dataset{tiktok_10m_2025,
  title={TikTok-10M: A Large-Scale Short Video Dataset for Video Understanding},
  author={The Data Company},
  year={2025},
  url={https://huggingface.co/datasets/The-data-company/TikTok-10M},
  note={A dataset of 10 million TikTok posts for multimodal learning and social media analysis}
}
```

---

## JD Reviews Dataset

### 数据集描述

京东评论数据集包含大量中文商品评论，用于 L1 SFT 风格对齐训练。

### 使用示例

```python
from modelscope.msdatasets import MsDataset

# 加载数据集
dataset = MsDataset.load(
    "DAMO_NLP/jd",
    split="train"
)

# 访问样本
for item in dataset:
    print(f"Text: {item['text']}")
    print(f"Label: {item['label']}")
    break
```

### 在 Growth Flywheel 2.5 中的应用

#### L1 SFT 风格对齐

```python
# 转换为 SFT 格式
{
    "instruction": "请用口语化、有趣的方式描述这个产品",
    "input": "{product_category}",
    "output": "{review_text}"
}
```

特点:
- ✅ 口语化表达
- ✅ Emoji 使用
- ✅ 分点表达
- ✅ 情感丰富

---

## Mercari MerRec Dataset

### 数据集描述

Mercari 用户行为数据集，用于训练 User Simulator 和构建多智能体博弈环境。

### 使用示例

```python
from datasets import load_dataset

# 加载数据集
dataset = load_dataset("mercari-us/merrec")

# 访问样本
sample = dataset["train"][0]
print(f"User: {sample['user_id']}")
print(f"Item: {sample['item_id']}")
print(f"Action: {sample['action']}")
```

### 在 Growth Flywheel 2.5 中的应用

#### 用户行为模拟

```python
# 行为映射
behavior_mapping = {
    "view": "impression",
    "click": "play",
    "favorite": "like",
    "purchase": "deep_engagement"
}
```

---

## 完整下载流程

### 方法 1: 使用我们的脚本 (推荐)

```bash
# 下载所有数据集
python backend/scripts/download_datasets.py
```

这会自动:
1. 下载 TikTok-10M (~50GB)
2. 下载 JD Reviews (~5GB)
3. 下载 Mercari MerRec (~10GB)
4. 预处理所有数据
5. 保存为训练就绪格式

### 方法 2: 手动下载

```python
from datasets import load_dataset

# TikTok-10M
tiktok_dataset = load_dataset("The-data-company/TikTok-10M")

# Mercari
mercari_dataset = load_dataset("mercari-us/merrec")

# JD Reviews (需要 ModelScope)
from modelscope.msdatasets import MsDataset
jd_dataset = MsDataset.load("DAMO_NLP/jd")
```

### 方法 3: 使用镜像 (中国大陆用户)

```bash
# 设置 Hugging Face 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 然后正常下载
python backend/scripts/download_datasets.py
```

---

## 常见问题

### Q: 下载速度慢怎么办?

**A**: 使用镜像或代理:
```bash
export HF_ENDPOINT=https://hf-mirror.com
export HTTP_PROXY=http://your-proxy:port
```

### Q: 磁盘空间不足怎么办?

**A**: 使用流式加载或部分下载:
```python
dataset = load_dataset("The-data-company/TikTok-10M", split="train[:10%]")
```

### Q: 如何验证数据完整性?

**A**: 检查样本数量:
```python
print(f"TikTok-10M: {len(dataset)} samples")  # 应该是 10,000,000
```

---

## 技术支持

如有问题:
- 📖 查看 QUICKSTART.md
- 🐛 提交 GitHub Issue
- 💬 加入讨论区

---

**最后更新**: 2026-02-11
**数据集版本**: v1.0
**状态**: 生产就绪 ✅
