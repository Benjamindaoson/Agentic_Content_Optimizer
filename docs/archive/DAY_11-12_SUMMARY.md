# Day 11-12: Critic Agent + Reward Model - 实现总结

## 完成时间
2026-02-11

## 实现概述
完成了 Critic Agent 的深度实现，包括多维度质量评估、审批决策、改进建议生成，以及完整的 Reward Model 用于计算奖励分数，为 GRPO 策略进化提供信号。

## 核心文件

### 1. 数据模型层
**`backend/app/schemas/evaluation.py`**
- `EvaluationDimension`: 评估维度枚举
  - creativity: 创意性
  - executability: 可执行性
  - geo_optimization: GEO优化
  - platform_fit: 平台适配
  - engagement_potential: 互动潜力

- `ApprovalStatus`: 审批状态枚举
  - approved: 通过
  - rejected: 拒绝
  - needs_revision: 需要修改

- `DimensionScore`: 单个维度评分
  - dimension, score (0-1), reasoning, suggestions

- `CriticEvaluation`: Critic 评估结果
  - dimension_scores: 5个维度评分
  - overall_score: 综合评分
  - approval_status: 审批决策
  - summary: 评估摘要
  - critical_issues: 关键问题
  - highlights: 内容亮点
  - improvement_suggestions: 改进建议
  - 验证器：所有维度必须存在，综合评分与维度平均分一致

- `RewardComponents`: 奖励组成部分
  - quality_reward: 质量奖励（来自 Critic）
  - predicted_engagement/completion/conversion: 预测指标
  - diversity_bonus: 多样性奖励
  - geo_bonus: GEO优化奖励
  - innovation_bonus: 创新奖励

- `RewardScore`: 奖励分数
  - components: 奖励组成
  - total_reward: 总奖励（0-2）
  - goal_weights: 目标权重
  - calculation_details: 计算详情
  - 验证器：总奖励计算一致性

- `CriticResult`: Critic 完整结果
  - content_id, evaluation, reward, approved, action

### 2. Agent 层
**`backend/app/agents/content/critic_agent.py`**
- `CriticAgent`: 评估生成内容质量的智能体
  - `execute()`: 主执行方法
    1. 多维度评估
    2. 计算综合评分
    3. 审批决策
    4. 生成评估摘要
    5. 提取关键问题和亮点
    6. 生成改进建议
    7. 组装评估结果

  - `_evaluate_dimensions()`: 多维度评估
    - 使用 LLM 对5个维度进行评分
    - 提供评分理由和改进建议
    - JSON 解析 + 容错处理
    - 返回 List[DimensionScore]

  - `_make_approval_decision()`: 审批决策
    - 检查是否有严重问题（score < 0.5）
    - 检查综合评分是否达标
    - 返回 approved/needs_revision/rejected

  - `_generate_summary()`: 生成评估摘要
    - 找出最高分和最低分维度
    - 生成简洁的摘要文本

  - `_extract_critical_issues()`: 提取关键问题
    - 收集低分维度（score < 0.6）的问题

  - `_extract_highlights()`: 提取内容亮点
    - 收集高分维度（score >= 0.8）的亮点

  - `_generate_improvement_suggestions()`: 生成改进建议
    - 收集低分维度的建议（最多5条）

### 3. Reward Model 层
**`backend/app/rl/reward_model.py`**
- `RewardModel`: 奖励模型类
  - `__init__()`: 初始化
    - goal_weights: 目标权重配置
    - historical_stats: 历史数据统计

  - `calculate_reward()`: 计算奖励分数
    1. 质量奖励（来自 Critic）
    2. 预测奖励（基于历史数据或启发式）
    3. 多样性奖励
    4. GEO 优化奖励
    5. 创新奖励
    6. 计算总奖励

  - `_predict_performance()`: 预测内容表现
    - 如果有历史数据，直接使用
    - 否则基于 Critic 评估进行启发式预测
    - 互动率 = engagement_potential * 0.6 + creativity * 0.4
    - 完播率 = platform_fit * 0.5 + executability * 0.3 + creativity * 0.2
    - 转化率 = engagement_potential * 0.5 + geo_optimization * 0.3 + platform_fit * 0.2
    - 添加随机噪声（模拟真实环境）

  - `_calculate_diversity_bonus()`: 计算多样性奖励
    - diversity_score * 0.2（最多0.2）

  - `_calculate_geo_bonus()`: 计算 GEO 优化奖励
    - coverage >= 0.8: 0.2
    - coverage >= 0.6: 0.1
    - 否则: 0.0

  - `_calculate_innovation_bonus()`: 计算创新奖励
    - creativity >= 0.8 且 micro_innovation >= 20字: 0.2
    - creativity >= 0.7 且 micro_innovation >= 15字: 0.1
    - 否则: 0.0

  - `_calculate_total_reward()`: 计算总奖励
    - 质量奖励 * 0.5 + 预测奖励 * 0.5 + 各种奖励

  - `update_historical_stats()`: 更新历史统计
    - 使用指数移动平均（EMA）在线学习
    - 更新均值和标准差

### 4. 提示词模板层
**`backend/app/agents/prompts/critic_evaluation.py`**
- `build_critic_evaluation_prompt()`: Critic 评估提示词
  - 完整的文案和拍摄蓝图展示
  - 5个维度的详细评估标准
  - 评分指南（0.9-1.0优秀，0.8-0.9良好，...）
  - 参考案例对比
  - 目标指标说明
  - 结构化输出要求（JSON）

- `_format_shot_list()`: 格式化镜头列表
  - 将镜头列表转换为易读格式

### 5. 编排层
**`backend/app/orchestration/nodes.py`**
- `critic_evaluate_node()`: Critic Agent 节点（已从占位符升级为完整实现）
  - 初始化 Critic Agent 和 Reward Model
  - 根据 goal_metric 调整目标权重
  - 为每个生成的内容进行评估
  - 计算奖励分数
  - 组装 CriticResult
  - 收集通过的内容
  - 更新状态：critic_results, approved_contents

### 6. 前端组件
**`frontend/components/evaluation/EvaluationCard.tsx`**
- 评估结果展示卡片组件
  - 审批状态（通过/拒绝/需要修改）
  - 综合评分和摘要
  - 5个维度评分（进度条 + 评分理由）
  - 内容亮点（高分维度）
  - 关键问题（低分维度）
  - 改进建议
  - 奖励分数详情
    - 质量奖励、预测指标
    - 奖励加成（多样性、GEO、创新）

## 技术亮点

### 1. 深度实现（非占位符）
- 完整的多维度评估系统
- 真实的 LLM 调用（Claude）
- 启发式预测算法
- 奖励计算公式
- 在线学习机制（EMA）

### 2. 科学的评估体系
- 5个维度全面覆盖内容质量
- 评分标准清晰、可解释
- 审批决策逻辑合理
- 改进建议可操作

### 3. 灵活的奖励模型
- 多目标优化（互动率、完播率、转化率）
- 目标权重可配置
- 多种奖励加成机制
- 历史数据学习能力

### 4. 容错处理
- JSON 解析失败时正则提取
- LLM 响应异常处理
- 数据验证（Pydantic）
- 详细的错误日志

### 5. 用户体验
- 可视化评分进度条
- 颜色编码（绿/黄/红）
- 分类展示（亮点/问题/建议）
- 奖励分数透明化

## 数据流

```
Writer Agent 生成内容
  ↓
Critic Agent 评估
  ├─ 多维度评估（5个维度）
  │   ├─ 构建评估提示词
  │   ├─ 调用 LLM
  │   └─ 解析 JSON → DimensionScore[]
  ├─ 计算综合评分
  ├─ 审批决策（approved/needs_revision/rejected）
  ├─ 生成摘要
  ├─ 提取问题和亮点
  └─ 生成改进建议
  ↓
Reward Model 计算奖励
  ├─ 质量奖励（来自 Critic）
  ├─ 预测奖励（启发式或历史数据）
  ├─ 多样性奖励
  ├─ GEO 优化奖励
  ├─ 创新奖励
  └─ 计算总奖励
  ↓
组装 CriticResult
  ├─ evaluation: CriticEvaluation
  ├─ reward: RewardScore
  ├─ approved: bool
  └─ action: H/B/C
  ↓
收集通过的内容 → approved_contents
  ↓
GRPO 策略进化（待实现，Day 13-14）
```

## 奖励计算公式

### 总奖励
```
total_reward = quality_reward * 0.5
             + predicted_reward * 0.5
             + diversity_bonus
             + geo_bonus
             + innovation_bonus
```

### 预测奖励
```
predicted_reward = predicted_engagement * weight_engagement
                 + predicted_completion * weight_completion
                 + predicted_conversion * weight_conversion
```

### 预测指标（启发式）
```
predicted_engagement = engagement_potential * 0.6 + creativity * 0.4
predicted_completion = platform_fit * 0.5 + executability * 0.3 + creativity * 0.2
predicted_conversion = engagement_potential * 0.5 + geo_optimization * 0.3 + platform_fit * 0.2
```

### 奖励加成
```
diversity_bonus = min(diversity_score * 0.2, 0.2)

geo_bonus = 0.2 if geo_coverage >= 0.8
          = 0.1 if geo_coverage >= 0.6
          = 0.0 otherwise

innovation_bonus = 0.2 if creativity >= 0.8 and innovation_length >= 20
                 = 0.1 if creativity >= 0.7 and innovation_length >= 15
                 = 0.0 otherwise
```

## 审批决策逻辑

```python
if any(dimension.score < 0.5):
    return REJECTED  # 有严重问题

if overall_score >= quality_threshold:
    return APPROVED  # 达标

if overall_score >= quality_threshold - 0.1:
    return NEEDS_REVISION  # 接近阈值，需要修改

return REJECTED  # 综合评分过低
```

## 验证要点

### CriticEvaluation 验证
- ✅ 所有5个维度必须存在
- ✅ 综合评分与维度平均分偏差 < 10%
- ✅ reasoning 长度 >= 10字
- ✅ 评分范围 0-1

### RewardScore 验证
- ✅ 总奖励与计算值偏差 < 5%
- ✅ 总奖励范围 0-2
- ✅ 各组件范围合法

## 下一步（Day 13-14）

1. **GRPO 策略进化引擎**
   - Group Relative Policy Optimization 实现
   - 策略梯度计算
   - 相对奖励归一化
   - 策略更新机制

2. **经验池管理**
   - 保存 episode 数据
   - 构建 experience pool
   - 采样和重放机制

3. **策略网络**
   - 动作概率分布
   - 策略参数更新
   - 探索-利用平衡

## 文件清单

### 新增文件
- `backend/app/schemas/evaluation.py`
- `backend/app/agents/content/critic_agent.py`
- `backend/app/rl/reward_model.py`
- `backend/app/agents/prompts/critic_evaluation.py`
- `frontend/components/evaluation/EvaluationCard.tsx`

### 修改文件
- `backend/app/orchestration/nodes.py`

## 代码统计
- 新增代码：~1000 行
- Python: ~800 行
- TypeScript: ~200 行
- 模块数：4 个
- 组件数：1 个

---

**实现状态**: ✅ 完成
**质量等级**: 深度实现（非占位符）
**测试状态**: 待集成测试
**关键创新**: 多维度评估 + 启发式预测 + 在线学习
