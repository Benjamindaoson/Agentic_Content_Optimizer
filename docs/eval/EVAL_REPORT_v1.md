# Growth Flywheel 2.5 评估报告 v1

**目标**：回答「比纯 LLM 好多少」

---

## 1. 评估方法论

### 1.1 基线定义

| 项目 | 说明 |
|------|------|
| 基线 | 单次 LLM 调用（同 prompt 意图，无 RAG、无 Agent 编排、无 Thompson Sampling） |
| 模型 | Claude Haiku 4.5（与主用模型一致） |
| Prompt | 简化版：为{platform}创作关于{topic}的文案，Hook/Body/CTA 结构，150-300 字 |

### 1.2 评估维度

| 维度 | 说明 | 来源 |
|------|------|------|
| 质量 | Critic 分（0-10） | CriticAgent 评估 |
| 相关性 | RAG 检索 NDCG@10、MRR | RAGEvaluator |
| 成本 | Token 数（估算） | 字符数/2 |
| 延迟 | P95 毫秒 | 实测 |

### 1.3 对比对象

| 系统 | 说明 |
|------|------|
| 基线 | 单次 LLM |
| 当前系统 | Trend→Writer→Critic 工作流 + RAG + Thompson Sampling |

---

## 2. 执行方式

```bash
# 1. 基线评估
python scripts/eval_baseline.py --topics-file scripts/eval_topics.json --output results/baseline.json

# 2. RAG Benchmark（需 Qdrant 就绪）
python scripts/run_rag_benchmark.py --output results/rag_benchmark.json

# 3. A/B 对比（需 API 运行）
python scripts/eval_generation_ab.py --output results/eval_ab.json
```

---

## 3. 结果摘要

> 运行上述脚本后，将结果填入下表。

### 3.1 生成质量对比

| 指标 | 基线 | 当前系统 | 变化 |
|------|------|----------|------|
| 平均质量分 | _待填入_ | _待填入_ | _待填入_ % |
| P95 延迟 (ms) | _待填入_ | _待填入_ | _待填入_ % |
| 平均 Token 数 | _待填入_ | _待填入_ | _待填入_ % |

### 3.2 RAG 检索质量

| 指标 | 值 |
|------|-----|
| NDCG@10 | _待填入_ |
| MRR | _待填入_ |
| 平均执行时间 (ms) | _待填入_ |

### 3.3 结论与置信度

- **结论**：_待填入（例如：当前系统在质量上较基线提升 X%，延迟增加 Y%）_
- **置信度**：_待填入（样本量、方差说明）_
- **局限**：_待填入（如：无真实用户反馈、Token 为估算值等）_

---

## 4. 附录

### 4.1 评估脚本说明

| 脚本 | 用途 |
|------|------|
| `scripts/eval_baseline.py` | 基线：单次 LLM 生成 + Critic 评估 |
| `scripts/eval_generation_ab.py` | 同一批 topic 下基线 vs 当前系统 |
| `scripts/run_rag_benchmark.py` | RAG 检索 NDCG/MRR Benchmark |
| `scripts/eval_topics.json` | 评估 topic 列表 |

### 4.2 依赖

- API 服务运行（`docker-compose up` 或 `uvicorn app.main:app`）
- Qdrant 就绪（RAG Benchmark）
- Anthropic API Key（基线 + Critic 评估）
