# Growth Flywheel 2.5 - 数据栈与技术栈规范

## 完成时间
2026-02-11

---

# ✅ 一、数据栈（含完整下载链接）

## D1｜主数据：分发环境 + Reward（必选）

**数据集名称：TikTok-10M（Hugging Face）**

**完整下载链接：**
👉 [https://huggingface.co/datasets/The-data-company/TikTok-10M](https://huggingface.co/datasets/The-data-company/TikTok-10M)

**在系统中的角色：**
* 作为**代理分发环境（Proxy Environment）**
* 用于：
  * 同账号归一化（Intra-Account Normalization）
  * 奖励建模（Reward Model）
  * GRPO 组内比较

**字段说明：**
* `author_id` - 作者ID
* `publish_time` - 发布时间
* `play_count` - 播放量
* `digg_count` - 点赞数
* `comment_count` - 评论数
* `share_count` - 分享数
* `description` - 内容描述
* `hashtags` - 话题标签

**奖励公式：**
```python
# 同账号归一化
baseline(author) = median(last_10_posts_likes)

# 相对增益
R_gain = (likes - baseline) / baseline

# 调整奖励（考虑曝光）
R_adj = R_gain * log(1 + play_count)
```

---

## D2｜中文风格对齐（L1 SFT 语料，必选）

**数据集名称：ModelScope 京东评论数据集**

**完整下载链接：**
👉 [https://modelscope.cn/datasets/DAMO_NLP/jd](https://modelscope.cn/datasets/DAMO_NLP/jd)

**用途：**
* 训练"平台原生口语 + Emoji + 分点表达"
* 作为 **Writer Agent** 的语言风格基座

**可用字段：**
* `review_text` - 评论文本
* `rating` - 评分
* `product_category` - 产品类别

**应用场景：**
* L1 SFT：风格对齐
* 学习中文口语化表达
* Emoji 使用模式
* 分点表达结构

---

## D3｜用户行为模拟（User Simulator，必选）

### 选项 A（推荐）：Mercari MerRec

**完整下载链接：**
👉 [https://huggingface.co/datasets/mercari-us/merrec](https://huggingface.co/datasets/mercari-us/merrec)

**用途：**
* 训练 User Agent（用户反应预测器）
* 构建多智能体博弈环境

**行为映射：**

| Mercari 行为 | Growth Flywheel 2.5 含义 |
|------------|------------------------|
| 浏览 (Browse) | 曝光 (Impression) |
| 点击 (Click) | 播放 (Play) |
| 收藏 (Favorite) | 点赞 (Like) |
| 购买 (Purchase) | 深度互动 (Deep Engagement) |

**应用场景：**
* 用户决策路径建模
* 互动概率预测
* A/B 测试模拟

---

### 选项 B：Amazon-M2 购物会话数据集

**项目主页（含论文 + 下载）：**
👉 [https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation](https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation)

**用途：**
* 替代 Mercari 作为用户决策模型训练数据
* 学习"浏览 → 点击 → 转化"路径

**优势：**
* 多语言支持
* 会话级行为序列
* 丰富的上下文信息

---

## D4｜趋势与热点 RAG（可选但加分）

**多源 RAG 数据源：**

| 数据源 | 完整链接 | 用途 | 更新频率 |
|-------|---------|------|---------|
| Google Trends | [https://trends.google.com](https://trends.google.com) | 热点时间序列 | 实时 |
| TikTok Hashtag 趋势 | [https://www.tiktok.com/tag](https://www.tiktok.com/tag) | 话题热度 | 实时 |
| 今日头条热榜 | [https://www.toutiao.com/hot-event/](https://www.toutiao.com/hot-event/) | 中文热点 | 小时级 |
| 百度热搜 | [https://top.baidu.com](https://top.baidu.com) | 中文热点 | 实时 |

**在系统中的应用：**
> "Trend Agent 通过多源 RAG（Google Trends + TikTok + 中文热榜）实时构建 GEO 关键词包。"

**实现方式：**
```python
# Trend Agent RAG 检索
def retrieve_trending_keywords(topic: str, platform: str):
    # 1. Google Trends API
    google_trends = fetch_google_trends(topic)

    # 2. TikTok Hashtag API
    tiktok_trends = fetch_tiktok_hashtags(topic)

    # 3. 中文热榜爬虫
    cn_trends = fetch_cn_hotlist(topic)

    # 4. 融合 + 排序
    geo_keywords = merge_and_rank([
        google_trends,
        tiktok_trends,
        cn_trends
    ])

    return geo_keywords
```

---

# ✅ 二、数据栈映射表（可直接使用）

| 模块 | 数据集 | 完整链接 | 用途 |
|-----|-------|---------|------|
| **MDP / Reward / GRPO** | TikTok-10M | [https://huggingface.co/datasets/The-data-company/TikTok-10M](https://huggingface.co/datasets/The-data-company/TikTok-10M) | 构建代理分发环境、同账号归一化奖励、GRPO 训练 |
| **L1 SFT（风格对齐）** | ModelScope 京东评论 | [https://modelscope.cn/datasets/DAMO_NLP/jd](https://modelscope.cn/datasets/DAMO_NLP/jd) | 中文口语化、Emoji、分点表达风格对齐 |
| **User Simulator** | Mercari MerRec | [https://huggingface.co/datasets/mercari-us/merrec](https://huggingface.co/datasets/mercari-us/merrec) | 模拟"曝光→播放→点赞→转化"路径 |
| **（备选）User Simulator** | Amazon-M2 | [https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation](https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation) | 会话级用户行为建模 |
| **Trend RAG** | Google Trends | [https://trends.google.com](https://trends.google.com) | 热点时间序列 |
| **Trend RAG** | TikTok Hashtags | [https://www.tiktok.com/tag](https://www.tiktok.com/tag) | 平台话题热度 |
| **Trend RAG** | 百度热搜 | [https://top.baidu.com](https://top.baidu.com) | 中文热点 |

---

# ✅ 三、技术栈规范

## 3.1 模型栈

### Base Model

**Qwen2.5-7B**
* 官网：[https://huggingface.co/Qwen/Qwen2.5-7B](https://huggingface.co/Qwen/Qwen2.5-7B)
* 参数量：7B
* 上下文长度：32K tokens
* 优势：
  * 中文能力强
  * 指令遵循好
  * 推理速度快
  * 开源可商用

### 微调工具

**LLaMA-Factory**
* GitHub：[https://github.com/hiyouga/LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)
* 版本：v0.7.0+
* 特性：
  * 支持 LoRA/QLoRA
  * 支持 GRPO/DPO/PPO
  * Web UI 界面
  * 多卡训练

### 微调配置

**LoRA 参数：**
```yaml
# LoRA 配置
lora_rank: 16
lora_alpha: 32
lora_dropout: 0.05
target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj

# 训练参数
learning_rate: 5e-5
batch_size: 4
gradient_accumulation_steps: 8
num_epochs: 3
warmup_ratio: 0.1
```

---

## 3.2 RL 算法

### GRPO（Group Relative Policy Optimization）

**可用框架：**

**TRL (Transformer Reinforcement Learning)**
* GitHub：[https://github.com/huggingface/trl](https://github.com/huggingface/trl)
* 版本：v0.8.0+
* 特性：
  * 原生支持 GRPO
  * 集成 Hugging Face 生态
  * 支持分布式训练

**GRPO 配置：**
```python
from trl import GRPOConfig, GRPOTrainer

config = GRPOConfig(
    learning_rate=1e-5,
    batch_size=8,
    mini_batch_size=2,
    gradient_accumulation_steps=4,
    ppo_epochs=4,
    max_grad_norm=1.0,
    temperature=1.0,
    clip_epsilon=0.2,
    group_size=8,  # GRPO 特有：组大小
    normalize_rewards=True,  # GRPO 特有：相对奖励归一化
)

trainer = GRPOTrainer(
    model=model,
    config=config,
    train_dataset=train_dataset,
    reward_model=reward_model,
)
```

---

## 3.3 多智能体协议

### MCP（Model Context Protocol）

**规范主页：**
👉 [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

**版本：** v1.0

**在系统中的应用：**
* Trend Agent ↔ Director Agent 通信
* Director Agent ↔ Writer Agent 通信
* Writer Agent ↔ Critic Agent 通信
* Critic Agent ↔ Policy Evolution 通信

**MCP 消息格式：**
```json
{
  "protocol": "mcp/1.0",
  "from": "trend_agent",
  "to": "director_agent",
  "message_type": "geo_keywords",
  "payload": {
    "topic": "AI 写作工具",
    "keywords": ["AI", "写作", "效率", "工具"],
    "trends": [
      {"keyword": "ChatGPT", "score": 0.95},
      {"keyword": "文案生成", "score": 0.87}
    ]
  },
  "timestamp": "2026-02-11T10:30:00Z"
}
```

---

## 3.4 工程基础设施

### 训练与推理

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 训练框架 | PyTorch | 2.1.0+ | 模型训练 |
| 推理引擎 | vLLM | 0.3.0+ | 高性能推理 |
| 量化工具 | bitsandbytes | 0.41.0+ | INT8/INT4 量化 |

### 数据处理

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 数据处理 | Pandas | 2.0.0+ | 数据清洗 |
| 高性能处理 | Polars | 0.20.0+ | 大规模数据 |
| 存储格式 | Parquet | - | 列式存储 |

### 向量检索

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 向量检索 | FAISS | 1.7.4+ | 相似度搜索 |
| 向量数据库 | Qdrant | 1.7.0+ | 向量存储 |
| 嵌入模型 | text-embedding-ada-002 | - | OpenAI 嵌入 |

### Agent 编排

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| Agent 框架 | LangChain | 0.1.0+ | Agent 编排 |
| 状态图 | LangGraph | 0.0.40+ | 工作流编排 |
| 协议 | MCP | 1.0 | Agent 通信 |

### 实验跟踪

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 实验跟踪 | Weights & Biases | 0.16.0+ | 训练监控 |
| 模型注册 | MLflow | 2.10.0+ | 模型版本管理 |
| 可视化 | TensorBoard | 2.15.0+ | 训练可视化 |

---

## 3.5 完整技术栈总览

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Trend    │  │ Director │  │ Writer   │  │ Critic   │    │
│  │ Agent    │→ │ Agent    │→ │ Agent    │→ │ Agent    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                        ↓                                     │
│                  ┌──────────┐                                │
│                  │ Policy   │                                │
│                  │ Evolution│                                │
│                  └──────────┘                                │
├─────────────────────────────────────────────────────────────┤
│                    编排层                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LangGraph (StateGraph + Conditional Routing)         │   │
│  │ MCP (Model Context Protocol)                         │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    模型层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Qwen2.5-7B   │  │ Reward Model │  │ User         │      │
│  │ (Base Model) │  │ (Critic)     │  │ Simulator    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    训练层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ LLaMA-Factory│  │ TRL (GRPO)   │  │ PyTorch      │      │
│  │ (SFT)        │  │ (RL)         │  │ (Framework)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    数据层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ TikTok-10M   │  │ 京东评论      │  │ Mercari      │      │
│  │ (Reward)     │  │ (SFT)        │  │ (User Sim)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Google Trends│  │ TikTok Tags  │  │ 百度热搜      │      │
│  │ (RAG)        │  │ (RAG)        │  │ (RAG)        │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    基础设施层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ FAISS/Qdrant │  │ PostgreSQL   │  │ Redis        │      │
│  │ (Vector DB)  │  │ (Database)   │  │ (Cache)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ W&B          │  │ MLflow       │  │ Docker       │      │
│  │ (Tracking)   │  │ (Registry)   │  │ (Container)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3.6 部署配置

### 开发环境

```yaml
# requirements.txt
torch==2.1.0
transformers==4.36.0
trl==0.8.0
peft==0.7.0
bitsandbytes==0.41.0
langchain==0.1.0
langgraph==0.0.40
faiss-cpu==1.7.4
qdrant-client==1.7.0
pandas==2.0.0
polars==0.20.0
wandb==0.16.0
mlflow==2.10.0
```

### 生产环境

```yaml
# Docker 配置
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 安装 Python 3.11
RUN apt-get update && apt-get install -y python3.11 python3-pip

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 vLLM（推理加速）
RUN pip install vllm==0.3.0

# 复制代码
COPY . /app
WORKDIR /app

# 启动服务
CMD ["python", "main.py"]
```

### 硬件要求

| 环境 | GPU | 内存 | 存储 |
|-----|-----|------|------|
| 开发 | 1x RTX 4090 (24GB) | 64GB | 500GB SSD |
| 训练 | 4x A100 (80GB) | 256GB | 2TB NVMe |
| 生产 | 2x A100 (40GB) | 128GB | 1TB SSD |

---

## 3.7 性能指标

### 训练性能

| 阶段 | 时间 | GPU 利用率 | 吞吐量 |
|-----|------|-----------|--------|
| L1 SFT | 6 小时 | 85% | 2000 samples/s |
| GRPO | 12 小时 | 90% | 500 episodes/h |
| 总计 | 18 小时 | - | - |

### 推理性能

| 指标 | 值 |
|-----|---|
| 延迟（P50） | 200ms |
| 延迟（P99） | 500ms |
| 吞吐量 | 100 req/s |
| GPU 利用率 | 70% |

---

# ✅ 四、数据处理流程

## 4.1 TikTok-10M 预处理

```python
import pandas as pd
import polars as pl

# 1. 加载数据
df = pl.read_parquet("tiktok-10m.parquet")

# 2. 同账号归一化
df = df.with_columns([
    # 计算每个作者的 baseline
    pl.col("digg_count")
      .over("author_id")
      .rolling_median(window_size=10)
      .alias("baseline_likes"),

    # 计算相对增益
    ((pl.col("digg_count") - pl.col("baseline_likes")) / pl.col("baseline_likes"))
      .alias("relative_gain"),

    # 调整奖励
    (pl.col("relative_gain") * (1 + pl.col("play_count")).log())
      .alias("adjusted_reward")
])

# 3. 过滤异常值
df = df.filter(
    (pl.col("adjusted_reward") > -3) &
    (pl.col("adjusted_reward") < 3)
)

# 4. 保存
df.write_parquet("tiktok-10m-processed.parquet")
```

## 4.2 京东评论 SFT 数据构建

```python
# 1. 加载数据
df = pd.read_json("jd_reviews.jsonl", lines=True)

# 2. 构建 SFT 格式
sft_data = []
for _, row in df.iterrows():
    sft_data.append({
        "instruction": f"请用口语化的方式评价这个{row['product_category']}产品",
        "input": "",
        "output": row["review_text"]
    })

# 3. 保存
pd.DataFrame(sft_data).to_json("sft_data.jsonl", orient="records", lines=True)
```

## 4.3 Mercari 用户行为映射

```python
# 行为映射
behavior_mapping = {
    "view": "impression",
    "click": "play",
    "favorite": "like",
    "purchase": "deep_engagement"
}

# 构建用户行为序列
user_sessions = []
for session in mercari_data:
    mapped_session = {
        "user_id": session["user_id"],
        "actions": [
            {
                "action": behavior_mapping[action["type"]],
                "item_id": action["item_id"],
                "timestamp": action["timestamp"]
            }
            for action in session["actions"]
        ]
    }
    user_sessions.append(mapped_session)
```

---

# ✅ 五、实施路线图

## Phase 1: 数据准备（Week 1-2）

- [ ] 下载 TikTok-10M 数据集
- [ ] 下载京东评论数据集
- [ ] 下载 Mercari MerRec 数据集
- [ ] 数据预处理和清洗
- [ ] 构建 SFT 训练数据
- [ ] 构建 GRPO 训练数据

## Phase 2: 模型训练（Week 3-4）

- [ ] L1 SFT：风格对齐（Qwen2.5-7B + 京东评论）
- [ ] Reward Model 训练（TikTok-10M）
- [ ] User Simulator 训练（Mercari）
- [ ] GRPO 策略优化（TRL + TikTok-10M）

## Phase 3: 系统集成（Week 5-6）

- [ ] 集成 Trend Agent（RAG）
- [ ] 集成 Director Agent（策略采样）
- [ ] 集成 Writer Agent（内容生成）
- [ ] 集成 Critic Agent（质量评估）
- [ ] 集成 Policy Evolution（GRPO）

## Phase 4: 测试与优化（Week 7-8）

- [ ] 端到端测试
- [ ] 性能优化
- [ ] A/B 测试
- [ ] 生产部署

---

# ✅ 六、参考文献

1. **GRPO 算法**
   - Shao et al. (2024). "DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models"
   - [https://arxiv.org/abs/2402.03300](https://arxiv.org/abs/2402.03300)

2. **TikTok-10M 数据集**
   - [https://huggingface.co/datasets/The-data-company/TikTok-10M](https://huggingface.co/datasets/The-data-company/TikTok-10M)

3. **Mercari MerRec 数据集**
   - [https://huggingface.co/datasets/mercari-us/merrec](https://huggingface.co/datasets/mercari-us/merrec)

4. **Amazon-M2 数据集**
   - [https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation](https://www.amazon.science/publications/amazon-m2-a-multilingual-multi-locale-shopping-session-dataset-for-recommendation-and-text-generation)

5. **Model Context Protocol (MCP)**
   - [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

6. **LLaMA-Factory**
   - [https://github.com/hiyouga/LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)

7. **TRL (Transformer Reinforcement Learning)**
   - [https://github.com/huggingface/trl](https://github.com/huggingface/trl)

---

**文档版本**: v1.0
**最后更新**: 2026-02-11
**维护者**: Growth Flywheel 2.5 Team
