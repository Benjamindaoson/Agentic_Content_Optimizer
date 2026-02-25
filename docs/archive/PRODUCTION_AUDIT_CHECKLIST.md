# 🔍 生产环境审计清单和监控系统

## 📋 上线前审计清单

**版本**: v2.5.3
**日期**: 2026-02-12
**状态**: 待审计

---

## ✅ 审计项目

### 1. Embedding 归一化一致性 ⚠️

**风险**: 零向量/NaN 导致相似度计算错误

**检查点**:
- [ ] `embed_fn` 输出是否有零向量检测
- [ ] 是否每次都做 L2 normalize
- [ ] NaN/Inf 异常处理

**修复建议**:
```python
def safe_normalize(vec: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    vec = vec.astype(np.float32)
    # 检查 NaN/Inf
    if np.any(np.isnan(vec)) or np.any(np.isinf(vec)):
        logger.warning("检测到 NaN/Inf，返回零向量")
        return np.zeros_like(vec)

    norm = np.linalg.norm(vec)
    if norm < eps:
        logger.warning("检测到零向量")
        return np.zeros_like(vec)

    return vec / norm
```

---

### 2. 参考池时间窗口策略 ⚠️

**风险**: 只看最近 N 条可能漏检长期重复

**当前实现**: 只保留最近 200 条

**改进建议**: 混合采样（70% 最近 + 30% 高分历史）

```python
def get_reference_pool(self, mode: str = "hybrid") -> List[str]:
    if mode == "recent":
        return self.ref_texts[-200:]

    elif mode == "hybrid":
        # 70% 最近
        recent = self.ref_texts[-140:]

        # 30% 高分历史（需要维护分数）
        if hasattr(self, 'ref_scores'):
            top_scored = sorted(
                zip(self.ref_texts[:-140], self.ref_scores[:-140]),
                key=lambda x: x[1],
                reverse=True
            )[:60]
            high_score = [text for text, _ in top_scored]
        else:
            high_score = []

        return recent + high_score

    return self.ref_texts[-200:]
```

---

### 3. Qdrant 距离定义对齐 ⚠️

**风险**: Qdrant 使用的距离与本地计算不一致

**检查点**:
- [ ] Qdrant collection 的 distance 配置
- [ ] 本地 `cosine_sim` 实现
- [ ] 对比测试（同一向量在两边的结果）

**验证脚本**:
```python
def verify_qdrant_alignment():
    # 测试向量
    test_vec = np.random.randn(768)
    test_vec = test_vec / np.linalg.norm(test_vec)

    # 本地计算
    local_sims = [cosine_sim(test_vec, ref) for ref in ref_vecs]

    # Qdrant 查询
    qdrant_results = qdrant_client.search(
        collection_name="diversity_pool",
        query_vector=test_vec.tolist(),
        limit=10
    )
    qdrant_sims = [hit.score for hit in qdrant_results]

    # 对比
    diff = np.abs(np.array(local_sims[:10]) - np.array(qdrant_sims))
    assert np.max(diff) < 0.01, f"距离计算不一致: max_diff={np.max(diff)}"
```

---

### 4. 近重复阈值校准 🔥

**风险**: 0.92 在不同 embedding 模型上意义不同

**当前设置**: `near_dup_threshold=0.92`

**校准方法**:
1. 收集 100 对"人工标注为重复"的样本
2. 计算相似度分布
3. 选择 95 分位数作为阈值

```python
def calibrate_threshold(duplicate_pairs: List[Tuple[str, str]]) -> float:
    """校准近重复阈值"""
    similarities = []

    for text1, text2 in duplicate_pairs:
        emb1 = embed_fn(text1)
        emb2 = embed_fn(text2)
        sim = cosine_sim(emb1, emb2)
        similarities.append(sim)

    # 使用 95 分位数
    threshold = np.percentile(similarities, 95)

    logger.info(f"校准后的阈值: {threshold:.4f}")
    logger.info(f"相似度分布: min={np.min(similarities):.4f}, "
               f"mean={np.mean(similarities):.4f}, "
               f"max={np.max(similarities):.4f}")

    return threshold
```

---

### 5. 策略频率统计粒度 ⚠️

**风险**: 只统计 triplet 可能漏检单层塌缩

**改进**: 同时统计 Hook/Body/CTA 频率

```python
class EnhancedDiversityScorer(DiversityScorer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 单层频率统计
        self.hook_counts: Dict[str, int] = defaultdict(int)
        self.body_counts: Dict[str, int] = defaultdict(int)
        self.cta_counts: Dict[str, int] = defaultdict(int)

    def update_strategy_count(self, strategy_triplet: Tuple[str, str, str]):
        super().update_strategy_count(strategy_triplet)

        hook, body, cta = strategy_triplet
        self.hook_counts[hook] += 1
        self.body_counts[body] += 1
        self.cta_counts[cta] += 1

    def get_layer_entropy(self) -> Dict[str, float]:
        """计算各层熵"""
        def calc_entropy(counts: Dict) -> float:
            total = sum(counts.values())
            if total == 0:
                return 0.0
            probs = [c / total for c in counts.values()]
            return -sum(p * np.log(p + 1e-12) for p in probs)

        return {
            'hook_entropy': calc_entropy(self.hook_counts),
            'body_entropy': calc_entropy(self.body_counts),
            'cta_entropy': calc_entropy(self.cta_counts),
            'triplet_entropy': calc_entropy(self.strategy_counts)
        }
```

---

### 6. Thompson Sampling 先验设置 ⚠️

**风险**: 冷启动偏置过大

**当前设置**: `min_pulls=3`

**改进**: 添加先验保护和置信度检查

```python
@dataclass
class ThompsonSamplingConfig:
    # ... 现有配置 ...

    # 先验参数
    prior_mean: float = 0.5  # 先验均值
    prior_std: float = 0.3   # 先验标准差
    prior_weight: float = 3.0  # 先验等效样本数

    # 置信度阈值
    confidence_threshold: float = 0.1  # 标准差阈值

def _sample_from_posterior_with_prior(self, arm: BanditArm) -> float:
    """从后验分布采样（带先验）"""

    if arm.n_pulls == 0:
        # 纯先验
        mean = self.config.prior_mean
        std = self.config.prior_std
    else:
        # 贝叶斯更新
        prior_weight = self.config.prior_weight
        data_weight = arm.n_pulls

        total_weight = prior_weight + data_weight
        mean = (prior_weight * self.config.prior_mean +
                data_weight * arm.mean) / total_weight

        # 后验方差
        std = np.sqrt(
            (prior_weight * self.config.prior_std**2 +
             data_weight * arm.variance) / total_weight
        )

    # 采样
    sampled = np.random.normal(mean, std * self.config.temperature)
    return float(sampled)
```

---

### 7. 层级采样的信用分配 ⚠️

**风险**: 同一 reward 回填三层可能导致噪声传播

**改进**: 使用折扣因子

```python
def update_hierarchical(
    self,
    action: Tuple[int, int, int],
    reward: float,
    discount_factors: Tuple[float, float, float] = (1.0, 0.9, 0.8)
):
    """
    层级更新（带折扣）

    Args:
        action: (hook_id, body_id, cta_id)
        reward: 奖励值
        discount_factors: (hook_discount, body_discount, cta_discount)
    """
    hook_id, body_id, cta_id = action
    hook_discount, body_discount, cta_discount = discount_factors

    # 更新 triplet（完整奖励）
    self.triplet_stats[action].update(reward)

    # 更新 Hook（折扣）
    self.hook_stats[hook_id].update(reward * hook_discount)

    # 更新 Body given Hook（折扣）
    self.body_given_hook_stats[(hook_id, body_id)].update(reward * body_discount)

    # 更新 CTA given Hook+Body（折扣）
    self.cta_given_hook_body_stats[(hook_id, body_id, cta_id)].update(reward * cta_discount)
```

---

### 8. 近邻泛化的错误传播 ⚠️

**风险**: 坏邻居污染

**改进**: 只共享高置信度邻居

```python
def get_neighbor_prior_with_confidence(
    self,
    action: Tuple[int, int, int],
    min_pulls: int = 5,
    max_std: float = 0.3
) -> Tuple[float, float]:
    """
    获取近邻先验（带置信度过滤）

    Args:
        action: (hook_id, body_id, cta_id)
        min_pulls: 最小尝试次数
        max_std: 最大标准差

    Returns:
        (prior_mean, prior_std)
    """
    # ... 找近邻 ...

    # 过滤低置信度邻居
    high_confidence_neighbors = [
        (dist, arm.mean)
        for dist, arm in neighbor_arms
        if arm.n_pulls >= min_pulls and arm.std <= max_std
    ]

    if not high_confidence_neighbors:
        return (0.5, 0.5)  # 默认先验

    # 加权平均
    weights = [1.0 / (d + 1e-6) for d, _ in high_confidence_neighbors]
    weights = np.array(weights) / sum(weights)
    rewards = [r for _, r in high_confidence_neighbors]

    prior_mean = float(np.dot(weights, rewards))
    prior_std = float(np.std(rewards)) if len(rewards) > 1 else 0.5

    return (prior_mean, prior_std)
```

---

### 9. GRPO 组内归一化交互 ⚠️

**风险**: Bonus 改变 reward 分布，影响 GRPO 的 mean/std

**监控**: 记录每项 reward component 的直方图

```python
class RewardDistributionMonitor:
    """奖励分布监控器"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.components_history = {
            'quality': [],
            'predicted': [],
            'diversity': [],
            'geo': [],
            'innovation': [],
            'total': []
        }

    def record(self, reward_score: RewardScore):
        """记录奖励"""
        self.components_history['quality'].append(reward_score.components.quality_reward)
        self.components_history['predicted'].append(
            reward_score.components.predicted_engagement * 0.4 +
            reward_score.components.predicted_completion * 0.3 +
            reward_score.components.predicted_conversion * 0.3
        )
        self.components_history['diversity'].append(reward_score.components.diversity_bonus)
        self.components_history['geo'].append(reward_score.components.geo_bonus)
        self.components_history['innovation'].append(reward_score.components.innovation_bonus)
        self.components_history['total'].append(reward_score.total_reward)

        # 保持窗口大小
        for key in self.components_history:
            if len(self.components_history[key]) > self.window_size:
                self.components_history[key] = self.components_history[key][-self.window_size:]

    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """获取统计信息"""
        stats = {}
        for component, values in self.components_history.items():
            if not values:
                continue

            stats[component] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'p25': np.percentile(values, 25),
                'p50': np.percentile(values, 50),
                'p75': np.percentile(values, 75)
            }

        return stats

    def check_distribution_health(self) -> Dict[str, bool]:
        """检查分布健康度"""
        stats = self.get_statistics()
        health = {}

        for component, stat in stats.items():
            # 检查标准差是否过小（塌缩）或过大（不稳定）
            std_healthy = 0.05 < stat['std'] < 0.5

            # 检查均值是否在合理范围
            mean_healthy = 0.0 <= stat['mean'] <= 2.0

            health[component] = std_healthy and mean_healthy

        return health
```

---

### 10. 优雅降级路径验证 ✅

**检查点**:
- [ ] embed_fn 不可用时的降级逻辑
- [ ] Qdrant 不可用时的降级逻辑
- [ ] 所有异常路径的测试覆盖

**测试脚本**:
```python
def test_graceful_degradation():
    """测试优雅降级"""

    # 测试 1: embed_fn 返回 None
    def broken_embed_fn(text: str) -> np.ndarray:
        return None

    try:
        scorer = DiversityScorer(embed_fn=broken_embed_fn)
        score = scorer.compute_diversity_score("test", ("h", "b", "c"))
        assert score == 1.0, "应该降级到默认值"
        print("✅ embed_fn=None 降级测试通过")
    except Exception as e:
        print(f"❌ embed_fn=None 降级测试失败: {e}")

    # 测试 2: Qdrant 连接失败
    scorer = DiversityScorer(
        embed_fn=simple_embed,
        use_qdrant=True,
        qdrant_client=None  # 模拟连接失败
    )

    try:
        score = scorer.compute_diversity_score("test", ("h", "b", "c"))
        print("✅ Qdrant 降级测试通过")
    except Exception as e:
        print(f"❌ Qdrant 降级测试失败: {e}")

    # 测试 3: 空参考池
    scorer = DiversityScorer(embed_fn=simple_embed)
    score = scorer.compute_diversity_score("test", ("h", "b", "c"))
    assert score == 1.0, "空参考池应返回 1.0"
    print("✅ 空参考池测试通过")
```

---

## 📊 生产监控指标

### 核心指标（6个）

#### 1. 重复率监控

```python
class DuplicationMonitor:
    """重复率监控"""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.daily_stats = defaultdict(lambda: {'total': 0, 'duplicates': 0})

    def record(self, similarity: float, date: str):
        """记录相似度"""
        self.daily_stats[date]['total'] += 1
        if similarity >= self.threshold:
            self.daily_stats[date]['duplicates'] += 1

    def get_duplication_rate(self, date: str) -> float:
        """获取重复率"""
        stats = self.daily_stats[date]
        if stats['total'] == 0:
            return 0.0
        return stats['duplicates'] / stats['total']
```

#### 2. 策略熵监控

```python
def calculate_strategy_entropy(strategy_counts: Dict) -> float:
    """计算策略熵"""
    total = sum(strategy_counts.values())
    if total == 0:
        return 0.0

    probs = [count / total for count in strategy_counts.values()]
    entropy = -sum(p * np.log(p + 1e-12) for p in probs)

    # 归一化到 [0, 1]
    max_entropy = np.log(len(strategy_counts))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

    return normalized_entropy
```

#### 3. 层级熵监控

```python
def monitor_layer_entropy(scorer: EnhancedDiversityScorer) -> Dict[str, float]:
    """监控各层熵"""
    return scorer.get_layer_entropy()
```

#### 4. Thompson Sampling 探索率

```python
def calculate_exploration_rate(selector: ThompsonSamplingSelector) -> float:
    """计算探索率"""
    stats = selector.get_statistics()
    return stats['exploration_rate']
```

#### 5. Reward 分解监控

```python
def monitor_reward_components(monitor: RewardDistributionMonitor) -> Dict:
    """监控奖励分解"""
    return monitor.get_statistics()
```

#### 6. Top-K 策略稳定性

```python
class TopKStabilityMonitor:
    """Top-K 策略稳定性监控"""

    def __init__(self, k: int = 10):
        self.k = k
        self.daily_topk = {}

    def record(self, date: str, top_strategies: List[Tuple]):
        """记录每日 Top-K"""
        self.daily_topk[date] = set(s[0] for s in top_strategies[:self.k])

    def calculate_stability(self, date1: str, date2: str) -> float:
        """计算两天的重合度"""
        if date1 not in self.daily_topk or date2 not in self.daily_topk:
            return 0.0

        set1 = self.daily_topk[date1]
        set2 = self.daily_topk[date2]

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0
```

---

## 🚨 告警规则

### 1. 重复率告警

```python
if duplication_rate > 0.3:
    alert("重复率过高", severity="warning")
if duplication_rate > 0.5:
    alert("重复率严重", severity="critical")
```

### 2. 熵塌缩告警

```python
if strategy_entropy < 0.3:
    alert("策略熵过低，可能塌缩", severity="warning")
if strategy_entropy < 0.1:
    alert("策略严重塌缩", severity="critical")
```

### 3. 探索率告警

```python
if exploration_rate < 0.2:
    alert("探索率过低", severity="warning")
if exploration_rate > 0.8:
    alert("探索率过高，收敛慢", severity="info")
```

### 4. Reward 分布告警

```python
health = monitor.check_distribution_health()
for component, is_healthy in health.items():
    if not is_healthy:
        alert(f"{component} 分布异常", severity="warning")
```

---

## 🎯 发布说明补充

### 风险提示

⚠️ **阈值校准**: `near_dup_threshold=0.92` 需要根据实际 embedding 模型校准。建议：
1. 收集 100 对人工标注的重复样本
2. 计算相似度分布
3. 使用 95 分位数作为阈值

⚠️ **先验设置**: Thompson Sampling 的先验参数（`prior_mean`, `prior_std`, `prior_weight`）需要根据业务场景调整。

⚠️ **Qdrant 对齐**: 确保 Qdrant collection 的 distance 配置与本地计算一致（cosine）。

### 回滚开关

✅ **Feature Flags**:
```yaml
# system_upgrade.yaml
diversity_scorer:
  enabled: true  # 可快速关闭

thompson_sampling:
  enabled: true  # 可快速关闭

# 灰度配置
rollout:
  diversity_scorer_traffic: 0.1  # 10% 流量
  thompson_sampling_traffic: 0.1  # 10% 流量
```

### 评估方法

✅ **离线回放**:
```bash
# 使用历史数据回放
python scripts/replay_evaluation.py \
  --data-path data/historical_logs.jsonl \
  --use-diversity-scorer \
  --use-thompson-sampling
```

✅ **线上 A/B 测试**:
- 对照组: 原有系统
- 实验组: 新系统（10% 流量）
- 观察指标: 重复率、策略熵、转化率

---

**审计日期**: 2026-02-12
**审计人员**: Claude Sonnet 4.5
**状态**: 待执行
