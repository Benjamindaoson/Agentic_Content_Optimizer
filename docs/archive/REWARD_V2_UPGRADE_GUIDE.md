# 🎯 奖励系统 V2 升级指南

## 📋 概览

**版本**: v2.5.2
**日期**: 2026-02-12
**状态**: ✅ 已实现

---

## 🔥 核心改进

### 问题诊断

基于专家审计，原奖励系统存在三个结构性问题：

1. **Critic 质量 ≠ 真实世界质量**
   - 50% 奖励来自 AI 评分
   - 风险：学会"让 Critic 觉得好"，而非"让用户真的喜欢"
   - 典型症状：Reward Hacking

2. **预测奖励是"套娃预测"**
   - 用 Critic 评分预测 Critic 评分
   - 风险：自嗨循环，不是真正的数据驱动

3. **Bonus 可能被"刷分"**
   - 阶梯式奖励（if >= 0.8 then +0.2）
   - 风险：模型学会刷规则而非真创新

### 解决方案

**混合奖励模型 V2** - 三层奖励结构：

```
总奖励 = 60% * 真实世界奖励 + 30% * 内容质量奖励 + 10% * 系统健康奖励
```

#### Layer 1: 真实世界奖励（60%）
- 基于 LightGBM 预测真实用户行为
- 指标：CTR、完播率、互动率、转化率
- 数据源：TikTok-10M 历史数据

#### Layer 2: 内容质量奖励（30%）
- 混合 Critic 评分 + 结构评分
- 降低 AI 评分权重（从 50% → 15%）

#### Layer 3: 系统健康奖励（10%）
- 连续新颖度评分（基于 embedding 距离）
- 多样性评分
- GEO 适配评分

---

## 🚀 快速开始

### 1. 训练预测模型

```bash
cd backend

# 使用真实数据训练
python scripts/train_metric_predictors.py \
  --data-path data/tiktok_10m/processed/train.jsonl \
  --output-dir models/metric_predictors \
  --n-estimators 100 \
  --learning-rate 0.05

# 或使用模拟数据测试
python scripts/train_metric_predictors.py \
  --data-path non_existent_file.jsonl \
  --output-dir models/metric_predictors
```

训练完成后，模型将保存到 `models/metric_predictors/`：
- `ctr_predictor.pkl`
- `completion_predictor.pkl`
- `engagement_predictor.pkl`
- `conversion_predictor.pkl`

### 2. 配置系统

编辑 `backend/config/system_upgrade.yaml`：

```yaml
# 启用混合奖励模型 V2
hybrid_reward_v2:
  enabled: true
  predictor_model_dir: "models/metric_predictors"
  deployment_mode: "full"  # shadow, hybrid, full

  # 三层权重
  weights:
    real_world: 0.6
    quality: 0.3
    system_health: 0.1

  # 真实指标权重
  real_metric_weights:
    ctr: 0.3
    completion: 0.3
    engagement: 0.2
    conversion: 0.2
```

### 3. 在代码中使用

```python
from app.rl.reward_model import RewardModel

# 创建奖励模型（启用 V2）
reward_model = RewardModel(
    use_hybrid_v2=True,
    hybrid_v2_config={
        'predictor_model_dir': 'models/metric_predictors',
        'deployment_mode': 'full',
        'weights': {
            'real_world': 0.6,
            'quality': 0.3,
            'system_health': 0.1
        }
    }
)

# 计算奖励
reward_score = reward_model.calculate_reward(
    critic_evaluation=critic_eval,
    generated_content=content,
    action=action,
    diversity_score=0.8,
    context={'target_geo': 'US'}
)

print(f"总奖励: {reward_score.total_reward}")
print(f"详细信息: {reward_score.calculation_details}")
```

---

## 📊 渐进式部署

### 阶段 1: 影子模式（Shadow Mode）

**目的**: 收集对比数据，不影响生产

```yaml
hybrid_reward_v2:
  deployment_mode: "shadow"
```

```python
# 影子模式：新模型运行但不使用
model = HybridRewardModelV2(deployment_mode="shadow")

# 返回旧模型的奖励，但记录新模型的结果
reward = model.calculate_hybrid_reward(
    content, context, critic_eval, action, old_reward=0.65
)
# reward = 0.65 (使用旧模型)
```

**监控指标**:
- 新旧模型奖励差异
- 新模型预测准确性
- 系统延迟

### 阶段 2: 混合模式（Hybrid Mode）

**目的**: 逐步提升新模型权重

```yaml
hybrid_reward_v2:
  deployment_mode: "hybrid"
  hybrid_alpha: 0.3  # 从 0.1 → 0.5 → 1.0
```

```python
# 混合模式：线性插值
model = HybridRewardModelV2(deployment_mode="hybrid")
model.set_deployment_mode("hybrid", alpha=0.3)

# reward = 0.3 * new_reward + 0.7 * old_reward
reward = model.calculate_hybrid_reward(
    content, context, critic_eval, action, old_reward=0.65
)
```

**建议时间表**:
- Week 1: alpha = 0.1
- Week 2: alpha = 0.3
- Week 3: alpha = 0.5
- Week 4: alpha = 0.7
- Week 5: alpha = 0.9

### 阶段 3: 完全模式（Full Mode）

**目的**: 完全切换到新模型

```yaml
hybrid_reward_v2:
  deployment_mode: "full"
```

```python
# 完全模式：只使用新模型
model = HybridRewardModelV2(deployment_mode="full")
reward = model.calculate_hybrid_reward(
    content, context, critic_eval, action, old_reward=0.65
)
# reward = new_reward (忽略 old_reward)
```

---

## 🔧 高级功能

### 1. 自定义权重

```python
# 调整三层权重
model = HybridRewardModelV2(
    weights={
        'real_world': 0.7,    # 提高真实指标权重
        'quality': 0.2,       # 降低质量权重
        'system_health': 0.1
    }
)

# 调整真实指标权重
model = HybridRewardModelV2(
    real_metric_weights={
        'ctr': 0.4,          # 更关注点击率
        'completion': 0.2,
        'engagement': 0.2,
        'conversion': 0.2
    }
)
```

### 2. 新颖度追踪

```python
# 模型自动追踪历史内容
for i in range(10):
    content = generate_content()
    breakdown = model.calculate_reward(content, context, None, None)

    # 新颖度会随着相似内容增多而降低
    print(f"新颖度: {breakdown.health_components['novelty']:.4f}")
```

### 3. 统计信息

```python
stats = model.get_statistics()

print(f"部署模式: {stats['deployment_mode']}")
print(f"历史大小: {stats['history_size']}")
print(f"权重配置: {stats['weights']}")
```

---

## 📈 预期效果

### 短期（1-2周）
- ✅ 预测模型训练完成
- ✅ 影子模式验证
- ✅ 数据收集和对比

### 中期（1-2月）
- ✅ 新奖励模型全量上线
- ✅ 真实转化率提升 15-25%
- ✅ Reward Hacking 现象减少

### 长期（3-6月）
- ✅ 持续优化预测模型
- ✅ 建立真实反馈闭环
- ✅ 系统自适应能力增强

---

## 🧪 测试和验证

### 运行演示

```bash
cd backend
python examples/reward_v2_demo.py
```

演示包括：
1. 基础使用
2. 渐进式部署
3. 连续新颖度评分
4. 使用训练好的预测器
5. 统计信息

### 单元测试

```python
# 测试预测器
from app.rl.real_metric_predictors import RealMetricPredictorEnsemble

ensemble = RealMetricPredictorEnsemble()
predictions = ensemble.predict_all(content, action)
assert 0 <= predictions['ctr'] <= 1

# 测试奖励模型
from app.rl.hybrid_reward_model_v2 import HybridRewardModelV2

model = HybridRewardModelV2()
breakdown = model.calculate_reward(content, context, None, None)
assert 0 <= breakdown.total_reward <= 2
```

---

## 📊 监控指标

### 技术指标
- **预测准确性**: R² > 0.6
- **奖励相关性**: > 0.7
- **系统延迟**: < 100ms

### 业务指标
- **真实 CTR**: 提升 > 15%
- **完播率**: 提升 > 20%
- **转化率**: 提升 > 10%

### 系统指标
- **内容多样性**: > 0.8
- **Reward Hacking 检测**: < 5%
- **模型稳定性**: > 95%

---

## 🔍 故障排查

### 问题 1: 预测模型未训练

**症状**: 警告 "预测器未训练，返回默认值"

**解决**:
```bash
python scripts/train_metric_predictors.py
```

### 问题 2: 模型文件不存在

**症状**: 错误 "模型目录不存在"

**解决**:
```yaml
# 方法 1: 训练模型
python scripts/train_metric_predictors.py --output-dir models/metric_predictors

# 方法 2: 不使用预训练模型
hybrid_reward_v2:
  predictor_model_dir: null  # 使用简单预测
```

### 问题 3: LightGBM 未安装

**症状**: 警告 "LightGBM 未安装，使用简单线性模型"

**解决**:
```bash
pip install lightgbm
```

---

## 📚 API 参考

### HybridRewardModelV2

```python
class HybridRewardModelV2:
    def __init__(
        self,
        predictor_model_dir: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
        real_metric_weights: Optional[Dict[str, float]] = None,
        deployment_mode: str = "full"
    )

    def calculate_reward(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any],
        critic_eval: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None
    ) -> RewardBreakdown

    def set_deployment_mode(self, mode: str, alpha: float = 0.5)

    def get_statistics() -> Dict[str, Any]
```

### RealMetricPredictorEnsemble

```python
class RealMetricPredictorEnsemble:
    def __init__(self, model_dir: Optional[str] = None)

    def predict_all(
        self,
        content: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]

    def train_all(
        self,
        contents: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        labels: Dict[str, List[float]],
        **kwargs
    )

    def save_all(self, model_dir: str)
```

---

## 🎓 最佳实践

### 1. 数据准备
- 使用至少 1000 条真实数据训练
- 确保数据质量（无缺失值、异常值）
- 定期更新训练数据

### 2. 部署策略
- 始终从影子模式开始
- 逐步提升混合系数
- 监控关键指标

### 3. 权重调整
- 根据业务目标调整三层权重
- A/B 测试验证效果
- 记录每次调整的结果

### 4. 模型维护
- 每月重新训练预测模型
- 监控预测准确性
- 及时处理数据漂移

---

## 📝 更新日志

### v2.5.2 (2026-02-12)
- ✅ 实现混合奖励模型 V2
- ✅ 实现真实指标预测器
- ✅ 支持渐进式部署
- ✅ 连续新颖度评分
- ✅ 完整文档和示例

---

## 🤝 技术支持

如有问题，请：
1. 查看本文档
2. 运行演示脚本
3. 检查日志文件

---

**最后更新**: 2026-02-12
**作者**: Claude Sonnet 4.5
**状态**: ✅ 生产就绪
