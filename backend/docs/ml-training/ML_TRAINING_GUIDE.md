# ML Training System - 使用指南

## 目录

1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [数据准备](#数据准备)
4. [训练流程](#训练流程)
5. [API 使用](#api-使用)
6. [Adapter 管理](#adapter-管理)
7. [评估和监控](#评估和监控)
8. [生产部署](#生产部署)

---

## 系统概述

Growth Flywheel 2.5 ML 训练系统是一个生产级的 LLM 微调平台，支持：

- **QLoRA SFT 训练** - 平台风格学习
- **DPO 训练** - 互动率优化
- **自动数据构建** - 从真实用户反馈自动构建训练数据
- **Adapter 管理** - 多版本 adapter 管理和动态加载
- **评估系统** - 自动评估和对比
- **FastAPI 集成** - RESTful API 接口

### 架构

```
用户反馈数据 (GenerationTrace + Outcome)
    ↓
DatasetBuilder (自动构建训练数据)
    ├─ SFT Dataset (高互动内容)
    └─ DPO Dataset (偏好对)
    ↓
TrainingService
    ├─ SFT Trainer (QLoRA)
    └─ DPO Trainer (偏好优化)
    ↓
AdapterRegistry (版本管理)
    ↓
AdapterLoader (动态加载)
    ↓
生成服务 (使用 adapter 生成内容)
```

---

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements_ml.txt
```

### 2. 创建数据库表

```bash
# 创建 GenerationTrace 和 Outcome 表
python scripts/create_ml_tables.py

# 创建 AdapterRegistry 表
python scripts/create_adapter_registry_table.py
```

### 3. 准备数据

确保数据库中有足够的 `GenerationTrace` 和 `Outcome` 数据：

```python
# 最少需要:
# - SFT: 100+ 条高互动内容
# - DPO: 50+ 对偏好对
```

### 4. 运行第一次训练

```bash
# 自动训练流水线 (SFT -> DPO)
python scripts/auto_train.py \
    --platform xiaohongshu \
    --persona 学生党 \
    --niche AI工具
```

---

## 数据准备

### 数据模型

#### GenerationTrace (内容生成记录)

```python
{
    "id": "uuid",
    "platform": "xiaohongshu",
    "persona": "学生党",
    "niche": "AI工具",
    "topic": "AI 写作工具推荐",
    "prompt": "用户输入",
    "system_prompt": "系统提示",
    "output": "生成的内容",
    "title": "标题",
    "tags": ["AI", "写作"],
    "model_id": "claude-3.5-sonnet",
    "adapter_id": "xhs_student_v1",
    "created_at": "2026-02-15T10:00:00"
}
```

#### Outcome (效果数据)

```python
{
    "id": "uuid",
    "trace_id": "trace_uuid",
    "impressions": 1000,
    "clicks": 50,
    "click_rate": 0.05,
    "read_time_avg": 45.0,
    "completion_rate": 0.8,
    "likes": 20,
    "comments": 5,
    "saves": 15,
    "shares": 3,
    "engagement_score": 0.035,  # 自动计算
    "created_at": "2026-02-15T10:00:00"
}
```

### 互动分计算公式

```python
engagement_score = (
    0.45 * (saves / impressions) +
    0.25 * min(read_time_avg / 60.0, 1.0) +
    0.20 * (comments / impressions) +
    0.10 * (clicks / impressions)
)
```

### 数据质量要求

- **SFT 训练**:
  - 最少 100 条样本
  - 推荐 1,000+ 条样本
  - `engagement_score >= 0.01`

- **DPO 训练**:
  - 最少 50 对偏好对
  - 推荐 500+ 对偏好对
  - `score_diff >= 0.02`

---

## 训练流程

### 方法 1: 自动训练流水线 (推荐)

```bash
# 使用配置文件
python scripts/auto_train.py \
    --config configs/training/auto_training_example.json

# 使用命令行参数
python scripts/auto_train.py \
    --platform xiaohongshu \
    --persona 学生党 \
    --niche AI工具 \
    --sft-days 30 \
    --dpo-days 30
```

自动流水线会：
1. 训练 SFT adapter
2. 评估 SFT adapter
3. 使用 SFT adapter 作为基础训练 DPO adapter
4. 评估 DPO adapter

### 方法 2: 分步训练

#### Step 1: SFT 训练

```bash
# 使用配置文件
python scripts/train_sft.py \
    --config configs/training/sft_example.json

# 使用命令行参数
python scripts/train_sft.py \
    --platform xiaohongshu \
    --adapter-name xhs_student_ai_tools_sft_v1 \
    --base-model Qwen/Qwen2.5-7B-Instruct \
    --persona 学生党 \
    --niche AI工具 \
    --days 30 \
    --max-samples 5000 \
    --epochs 3 \
    --batch-size 4 \
    --lr 2e-4
```

#### Step 2: DPO 训练

```bash
# 使用配置文件
python scripts/train_dpo.py \
    --config configs/training/dpo_example.json

# 使用命令行参数
python scripts/train_dpo.py \
    --platform xiaohongshu \
    --adapter-name xhs_student_ai_tools_dpo_v1 \
    --base-adapter xhs_student_ai_tools_sft_v1 \
    --persona 学生党 \
    --niche AI工具 \
    --days 30 \
    --max-pairs 2000 \
    --epochs 1 \
    --batch-size 2 \
    --lr 5e-5 \
    --beta 0.1
```

### 训练配置说明

#### SFT 配置

```json
{
  "platform": "xiaohongshu",
  "adapter_name": "xhs_student_ai_tools_sft_v1",
  "base_model": "Qwen/Qwen2.5-7B-Instruct",
  "persona": "学生党",
  "niche": "AI工具",
  "days": 30,
  "min_engagement_score": 0.01,
  "max_samples": 5000,
  "num_train_epochs": 3,
  "per_device_train_batch_size": 4,
  "gradient_accumulation_steps": 4,
  "learning_rate": 2e-4,
  "eval_split": 0.1
}
```

#### DPO 配置

```json
{
  "platform": "xiaohongshu",
  "adapter_name": "xhs_student_ai_tools_dpo_v1",
  "base_adapter": "xhs_student_ai_tools_sft_v1",
  "persona": "学生党",
  "niche": "AI工具",
  "days": 30,
  "min_score_diff": 0.02,
  "max_pairs": 2000,
  "num_train_epochs": 1,
  "per_device_train_batch_size": 2,
  "gradient_accumulation_steps": 8,
  "learning_rate": 5e-5,
  "beta": 0.1,
  "eval_split": 0.1
}
```

---

## API 使用

### 启动 API 服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档: http://localhost:8000/docs

### 训练 API

#### 1. 训练 SFT Adapter

```bash
curl -X POST http://localhost:8000/api/ml/train/sft \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "xiaohongshu",
    "adapter_name": "xhs_test_sft_v1",
    "base_model": "Qwen/Qwen2.5-7B-Instruct",
    "persona": "学生党",
    "niche": "AI工具",
    "days": 30,
    "num_train_epochs": 3
  }'
```

响应:
```json
{
  "status": "accepted",
  "message": "SFT 训练任务已提交: xhs_test_sft_v1",
  "adapter_name": "xhs_test_sft_v1"
}
```

#### 2. 训练 DPO Adapter

```bash
curl -X POST http://localhost:8000/api/ml/train/dpo \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "xiaohongshu",
    "adapter_name": "xhs_test_dpo_v1",
    "base_adapter": "xhs_test_sft_v1",
    "persona": "学生党",
    "niche": "AI工具",
    "days": 30,
    "num_train_epochs": 1
  }'
```

#### 3. 自动训练流水线

```bash
curl -X POST http://localhost:8000/api/ml/train/auto \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "xiaohongshu",
    "persona": "学生党",
    "niche": "AI工具",
    "sft_days": 30,
    "dpo_days": 30
  }'
```

### Adapter 管理 API

#### 1. 列出所有 Adapters

```bash
curl http://localhost:8000/api/ml/adapters?platform=xiaohongshu
```

响应:
```json
{
  "total": 2,
  "adapters": [
    {
      "id": "uuid",
      "adapter_name": "xhs_student_ai_tools_dpo_v1",
      "adapter_type": "dpo",
      "platform": "xiaohongshu",
      "persona": "学生党",
      "niche": "AI工具",
      "status": "active",
      "is_default": true,
      "training_samples": 1500,
      "eval_metrics": {...},
      "created_at": "2026-02-15T10:00:00"
    }
  ]
}
```

#### 2. 获取 Adapter 详情

```bash
curl http://localhost:8000/api/ml/adapters/xhs_student_ai_tools_dpo_v1
```

#### 3. 设置默认 Adapter

```bash
curl -X POST http://localhost:8000/api/ml/adapters/xhs_student_ai_tools_dpo_v1/set-default
```

#### 4. 归档 Adapter

```bash
curl -X POST http://localhost:8000/api/ml/adapters/xhs_student_ai_tools_sft_v1/archive
```

### 生成 API

#### 使用 Adapter 生成内容

```bash
curl -X POST http://localhost:8000/api/ml/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "写一篇关于 AI 写作工具的小红书笔记",
    "adapter_name": "xhs_student_ai_tools_dpo_v1",
    "max_new_tokens": 512,
    "temperature": 0.7
  }'
```

响应:
```json
{
  "status": "success",
  "text": "生成的内容...",
  "adapter_name": "xhs_student_ai_tools_dpo_v1",
  "adapter_type": "dpo",
  "platform": "xiaohongshu",
  "persona": "学生党",
  "niche": "AI工具"
}
```

#### 使用默认 Adapter

```bash
curl -X POST http://localhost:8000/api/ml/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "写一篇关于 AI 写作工具的小红书笔记",
    "platform": "xiaohongshu",
    "persona": "学生党",
    "niche": "AI工具"
  }'
```

### 评估 API

#### 1. 评估 Adapter

```bash
curl -X POST http://localhost:8000/api/ml/evaluate/xhs_student_ai_tools_dpo_v1 \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_name": "xhs_student_ai_tools_dpo_v1",
    "platform": "xiaohongshu",
    "max_samples": 100
  }'
```

#### 2. 在真实数据上评估

```bash
curl "http://localhost:8000/api/ml/evaluate/xhs_student_ai_tools_dpo_v1/real-data?platform=xiaohongshu&days=7&min_samples=100"
```

响应:
```json
{
  "status": "success",
  "adapter_name": "xhs_student_ai_tools_dpo_v1",
  "metrics": {
    "num_samples": 150,
    "engagement_score": {
      "mean": 0.042,
      "std": 0.015,
      "median": 0.038
    },
    "click_rate": {
      "mean": 0.055,
      "std": 0.012
    },
    "completion_rate": {
      "mean": 0.82,
      "std": 0.08
    }
  }
}
```

---

## Adapter 管理

### Adapter 命名规范

```
{platform}_{persona}_{niche}_{type}_v{version}

示例:
- xhs_student_ai_tools_sft_v1
- xhs_student_ai_tools_dpo_v1
- douyin_creator_tech_sft_v2
```

### Adapter 生命周期

1. **训练** - 使用 TrainingService 训练
2. **注册** - 自动注册到 AdapterRegistry
3. **评估** - 使用 Evaluator 评估
4. **激活** - 设置为默认 adapter
5. **使用** - 通过 AdapterLoader 加载使用
6. **归档** - 不再使用时归档
7. **删除** - 彻底删除（可选删除文件）

### 版本管理

```python
# 列出所有版本
adapters = registry.list(
    platform="xiaohongshu",
    persona="学生党",
    niche="AI工具"
)

# 获取默认版本
default_adapter = registry.get_default(
    platform="xiaohongshu",
    persona="学生党",
    niche="AI工具"
)

# 切换版本
registry.set_default("xhs_student_ai_tools_dpo_v2")
```

---

## 评估和监控

### 评估指标

#### 自动指标

- **Distinct-1/2** - 文本多样性
- **BLEU** - 与参考文本的相似度
- **ROUGE-L** - 最长公共子序列
- **Platform Fit** - 平台适配度
- **Engagement Potential** - 互动潜力

#### 真实指标

- **Engagement Score** - 综合互动分
- **Click Rate** - 点击率
- **Completion Rate** - 完成率
- **Conversion Rate** - 转化率

### 监控

#### TensorBoard

```bash
tensorboard --logdir ./outputs/sft/xhs_student_ai_tools_sft_v1
```

#### Weights & Biases

```bash
export WANDB_PROJECT="growth-flywheel-2.5"
export WANDB_RUN_NAME="xhs_student_ai_tools_sft_v1"
```

---

## 生产部署

### 部署架构

```
Load Balancer
    ↓
FastAPI (Uvicorn) x N
    ↓
AdapterLoader (缓存)
    ↓
GPU Inference (vLLM)
```

### 部署步骤

#### 1. 准备环境

```bash
# 安装依赖
pip install -r requirements_ml.txt

# 创建数据库表
python scripts/create_ml_tables.py
python scripts/create_adapter_registry_table.py
```

#### 2. 训练 Adapters

```bash
# 训练多个 adapter
python scripts/auto_train.py --platform xiaohongshu --persona 学生党 --niche AI工具
python scripts/auto_train.py --platform xiaohongshu --persona 职场人 --niche 效率工具
python scripts/auto_train.py --platform douyin --persona 创作者 --niche 科技数码
```

#### 3. 启动服务

```bash
# 单进程
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 多进程
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

#### 4. 配置负载均衡

```nginx
upstream ml_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name api.example.com;

    location /api/ml/ {
        proxy_pass http://ml_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 性能优化

#### 1. Adapter 缓存

```python
# AdapterLoader 自动缓存已加载的 adapter
loader = AdapterLoader(registry)
model, tokenizer, adapter = loader.load("xhs_student_ai_tools_dpo_v1")
# 第二次加载会从缓存读取
```

#### 2. 批量推理

```python
# 使用 vLLM 进行批量推理
from vllm import LLM, SamplingParams

llm = LLM(model="./outputs/dpo/xhs_student_ai_tools_dpo_v1")
prompts = [...]
outputs = llm.generate(prompts, sampling_params)
```

#### 3. 量化

```python
# 使用 4-bit 量化减少显存
config = SFTConfig(
    use_4bit=True,
    bnb_4bit_compute_dtype="bfloat16",
    bnb_4bit_quant_type="nf4"
)
```

---

## 故障排查

### 问题 1: CUDA out of memory

**解决方案**:
```python
# 减少批次大小
per_device_train_batch_size = 2

# 增加梯度累积
gradient_accumulation_steps = 8

# 启用梯度检查点
gradient_checkpointing = True
```

### 问题 2: 训练速度慢

**解决方案**:
```python
# 启用混合精度
bf16 = True

# 增加批次大小
per_device_train_batch_size = 8

# 使用多 GPU
# CUDA_VISIBLE_DEVICES=0,1,2,3 python scripts/train_sft.py ...
```

### 问题 3: 数据集为空

**解决方案**:
```bash
# 检查数据库中的数据
python -c "
from app.core.database import SessionLocal
from app.ml.training.schemas import GenerationTrace, Outcome

db = SessionLocal()
traces = db.query(GenerationTrace).count()
outcomes = db.query(Outcome).count()
print(f'Traces: {traces}, Outcomes: {outcomes}')
"
```

### 问题 4: Adapter 加载失败

**解决方案**:
```bash
# 检查 adapter 路径
ls -la ./outputs/sft/xhs_student_ai_tools_sft_v1/

# 检查 adapter 配置
cat ./outputs/sft/xhs_student_ai_tools_sft_v1/adapter_config.json
```

---

## 最佳实践

### 1. 数据质量

- 定期清理低质量数据
- 确保 `engagement_score` 计算准确
- 平衡不同平台/人设/领域的数据

### 2. 训练策略

- 先训练 SFT，再训练 DPO
- 使用小数据集快速验证
- 定期评估和对比不同版本

### 3. 版本管理

- 使用语义化版本号
- 保留历史版本用于回滚
- 记录每个版本的训练配置和指标

### 4. 监控和告警

- 监控训练进度和损失
- 监控推理延迟和吞吐量
- 设置告警阈值

---

## 参考资料

- [QLoRA 论文](https://arxiv.org/abs/2305.14314)
- [DPO 论文](https://arxiv.org/abs/2305.18290)
- [Transformers 文档](https://huggingface.co/docs/transformers)
- [PEFT 文档](https://huggingface.co/docs/peft)
- [TRL 文档](https://huggingface.co/docs/trl)

---

**最后更新**: 2026-02-15
**版本**: 1.0.0
