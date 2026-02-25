# 🔧 奖励系统升级方案

## 📋 问题诊断

基于专家审计，当前奖励系统存在三个结构性问题：

### ⚠️ 问题 1: Critic 质量 ≠ 真实世界质量
- **现状**: 50% 奖励来自 Critic 评分（AI 的看法）
- **风险**: 学会"让 Critic 觉得好"，而非"让用户真的喜欢"
- **典型症状**: Reward Hacking - 优化审稿标准而非真实效果

### ⚠️ 问题 2: 预测奖励是"套娃预测"
- **现状**: 用 Critic 评分预测 Critic 评分
- **风险**: 自嗨循环，不是真正的数据驱动
- **缺失**: 真实用户行为预测模型

### ⚠️ 问题 3: Bonus 可能被"刷分"
- **现状**: 阶梯式奖励（if >= 0.8 then +0.2）
- **风险**: 模型学会刷规则而非真创新
- **改进**: 需要连续奖励函数

---

## 🎯 升级方案

### 方案 A: 渐进式升级（推荐）
**适用场景**: 现有系统平滑升级，降低风险

#### 阶段 1: 添加真实指标预测器（1-2周）
1. 训练轻量级预测模型
   - Engagement Predictor (CTR/互动率)
   - Completion Predictor (完播率)
   - Conversion Predictor (转化率)

2. 数据来源
   - 使用 TikTok-10M 历史数据
   - 特征: Hook/Body/CTA 类型 + 文本 embedding
   - 模型: XGBoost/LightGBM（快速迭代）

3. 集成方式
   - 先作为辅助指标（权重 0.1）
   - 逐步提升权重（0.1 → 0.3 → 0.5）
   - A/B 测试验证效果

#### 阶段 2: 调整奖励权重（1周）
```python
# 当前
total_reward = 0.5 * quality + 0.5 * predicted + bonus

# 升级后
total_reward = 0.3 * quality + 0.6 * real_predicted + 0.1 * bonus
```

#### 阶段 3: 改进 Bonus 机制（1周）
- 从阶梯式改为连续式
- 添加 novelty_score（embedding 距离）
- 防止规则刷分

---

### 方案 B: 激进式重构（高风险高收益）
**适用场景**: 有充足时间和资源，追求最优效果

#### 新奖励架构
```python
# 三层结构
total_reward = 0.6 * real_world_reward      # 真实用户行为
             + 0.3 * content_quality_reward  # 内容质量
             + 0.1 * system_health_reward    # 系统健康
```

---

## 📊 具体实现方案

### 1. 真实指标预测器

#### 数据准备
```python
# 特征工程
features = {
    'hook_type': one_hot_encoding(hook_id),
    'body_type': one_hot_encoding(body_id),
    'cta_type': one_hot_encoding(cta_id),
    'text_embedding': get_embedding(content),
    'length_features': {
        'hook_length': len(hook),
        'body_length': len(body),
        'total_length': len(hook + body + cta)
    },
    'structural_features': {
        'has_numbers': bool,
        'has_emoji': bool,
        'has_question': bool,
        'sentence_count': int
    }
}

# 标签
labels = {
    'engagement_rate': likes / views,
    'completion_rate': complete_views / views,
    'conversion_rate': conversions / views
}
```

#### 模型训练
```python
# 使用 LightGBM（快速 + 可解释）
import lightgbm as lgb

# 训练三个独立模型
engagement_model = lgb.LGBMRegressor(
    n_estimators=100,
    learning_rate=0.05,
    max_depth=6
)

completion_model = lgb.LGBMRegressor(...)
conversion_model = lgb.LGBMRegressor(...)

# 训练
engagement_model.fit(X_train, y_engagement)
completion_model.fit(X_train, y_completion)
conversion_model.fit(X_train, y_conversion)
```

#### 在线预测
```python
def predict_real_metrics(content, action):
    features = extract_features(content, action)

    return {
        'engagement': engagement_model.predict(features),
        'completion': completion_model.predict(features),
        'conversion': conversion_model.predict(features)
    }
```

---

### 2. 改进的奖励计算

#### 新的混合奖励模型 v2
```python
class HybridRewardModelV2:
    """
    升级版混合奖励模型

    改进:
    1. 真实指标预测器（数据驱动）
    2. 降低 Critic 权重
    3. 连续 Bonus 函数
    """

    def __init__(self):
        # 加载预测模型
        self.engagement_predictor = load_model('engagement')
        self.completion_predictor = load_model('completion')
        self.conversion_predictor = load_model('conversion')

        # 权重配置
        self.weights = {
            'real_world': 0.6,      # 真实指标
            'quality': 0.3,         # 内容质量
            'system_health': 0.1    # 系统健康
        }

    def calculate_reward(self, content, context, critic_eval):
        # 1. 真实世界奖励（数据驱动）
        real_metrics = self._predict_real_metrics(content, context)
        real_reward = (
            0.4 * real_metrics['engagement'] +
            0.4 * real_metrics['completion'] +
            0.2 * real_metrics['conversion']
        )

        # 2. 内容质量奖励（混合）
        quality_reward = (
            0.5 * critic_eval.overall_score +  # AI 评分
            0.5 * self._calculate_structure_score(content)  # 结构评分
        )

        # 3. 系统健康奖励（连续函数）
        system_health = (
            0.4 * self._calculate_diversity_score(content) +
            0.4 * self._calculate_novelty_score(content) +
            0.2 * self._calculate_geo_score(content)
        )

        # 总奖励
        total = (
            self.weights['real_world'] * real_reward +
            self.weights['quality'] * quality_reward +
            self.weights['system_health'] * system_health
        )

        return {
            'total_reward': total,
            'real_reward': real_reward,
            'quality_reward': quality_reward,
            'system_health': system_health,
            'real_metrics': real_metrics
        }

    def _calculate_novelty_score(self, content):
        """连续新颖度评分（基于 embedding 距离）"""
        current_emb = self.get_embedding(content)

        # 与历史内容的平均距离
        if not self.history_embeddings:
            return 1.0

        distances = [
            cosine_distance(current_emb, hist_emb)
            for hist_emb in self.history_embeddings[-50:]
        ]

        avg_distance = np.mean(distances)

        # 归一化到 [0, 1]
        novelty = min(avg_distance / 0.5, 1.0)

        return novelty
```

---

### 3. 渐进式部署策略

#### 阶段 1: 影子模式（1周）
```python
# 同时运行新旧模型，但只用旧模型的奖励
old_reward = old_model.calculate_reward(...)
new_reward = new_model.calculate_reward(...)

# 记录对比数据
log_comparison(old_reward, new_reward)

# 使用旧奖励
return old_reward
```

#### 阶段 2: 混合模式（2周）
```python
# 线性插值
alpha = 0.3  # 逐步从 0.1 → 0.5 → 1.0
final_reward = alpha * new_reward + (1 - alpha) * old_reward
```

#### 阶段 3: 完全切换（1周）
```python
# 完全使用新模型
return new_reward
```

---

## 📈 预期效果

### 短期（1-2周）
- ✅ 真实指标预测器上线
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

## 🔧 实施优先级

### P0 - 立即执行（本周）
1. ✅ 准备训练数据（TikTok-10M）
2. ✅ 训练初版预测模型
3. ✅ 实现影子模式

### P1 - 近期执行（2周内）
1. ✅ 实现 HybridRewardModelV2
2. ✅ 改进 Bonus 为连续函数
3. ✅ A/B 测试验证

### P2 - 中期优化（1月内）
1. ✅ 优化预测模型
2. ✅ 建立在线学习机制
3. ✅ 完善监控和告警

---

## 🎯 成功指标

### 技术指标
- 预测模型 R² > 0.6
- 奖励相关性 > 0.7
- 系统延迟 < 100ms

### 业务指标
- 真实 CTR 提升 > 15%
- 完播率提升 > 20%
- 转化率提升 > 10%

### 系统指标
- 内容多样性保持 > 0.8
- Reward Hacking 检测 < 5%
- 模型稳定性 > 95%

---

## 📚 参考资料

### 学术论文
- "Learning to Summarize from Human Feedback" (OpenAI, 2020)
- "Training Language Models with Human Preferences" (Anthropic, 2022)
- "Constitutional AI" (Anthropic, 2022)

### 工业实践
- YouTube 推荐系统的多目标优化
- TikTok 内容质量评估体系
- Meta 的 Reward Modeling 实践

---

**最后更新**: 2026-02-12
**方案制定**: Claude Sonnet 4.5
**状态**: 待实施
