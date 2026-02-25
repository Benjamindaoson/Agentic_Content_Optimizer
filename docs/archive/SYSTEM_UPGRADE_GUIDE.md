# 🚀 Growth Flywheel 2.5 - 系统升级指南

## 📋 升级概览

本次升级解决了原系统的 6 个核心问题，实现了 7 个重要功能模块。

### 解决的问题

1. ✅ **Reward 不对齐真实转化** → 混合奖励模型
2. ✅ **400 离散动作空间太死** → 层级动作空间
3. ✅ **趋势检索带来噪声** → 趋势质量过滤器
4. ✅ **Experience Pool 数据污染** → 多样性感知经验池
5. ✅ **多模型混用导致不稳定** → 模型路由器
6. ✅ **缺少可追踪性** → 生成追踪系统 + 回归测试

---

## 🎯 新增功能模块

### 1. 混合奖励模型（Hybrid Reward Model）

**位置**: `backend/app/rl/hybrid_reward_model.py`

**功能**:
- 预测真实指标（CTR、完播率、互动率、转化率）
- 质量约束（来自 Critic）
- 负奖励（同质化、合规、标题党）

**使用方法**:

```python
from app.rl.hybrid_reward_model import HybridRewardModel

# 初始化
reward_model = HybridRewardModel(
    metric_weights={'ctr': 0.2, 'completion': 0.3, 'engagement': 0.3, 'conversion': 0.2},
    quality_threshold=0.7,
    alpha=0.6,  # 预测指标权重
    beta=0.4    # 质量约束权重
)

# 计算奖励
reward_result = reward_model.calculate_reward(
    content={'hook': '...', 'body': '...', 'cta': '...'},
    context={'geo_keywords': ['关键词1', '关键词2']},
    critic_evaluation=critic_result  # 可选
)

print(f"总奖励: {reward_result['total_reward']}")
print(f"预测指标: {reward_result['predicted_metrics']}")
print(f"惩罚: {reward_result['penalties']}")
```

**配置**:

```yaml
# config/system_upgrade.yaml
hybrid_reward:
  enabled: true
  metric_weights:
    ctr: 0.2
    completion: 0.3
    engagement: 0.3
    conversion: 0.2
  quality_threshold: 0.7
  alpha: 0.6
  beta: 0.4
```

---

### 2. 生成追踪系统（Generation Tracer）

**位置**: `backend/app/core/tracer.py`

**功能**:
- 记录完整生成流程
- 追踪每个阶段的输入输出
- 记录模型版本、参数、prompt hash
- 支持查询和分析

**使用方法**:

```python
from app.core.tracer import GenerationTracer

# 初始化
tracer = GenerationTracer(db_session=db)

# 开始追踪
trace_id = tracer.start_trace(user_id="user_123", input_data={...})

# 追踪各阶段
tracer.trace_trend_retrieval(geo_keywords=[...], references=[...])
tracer.trace_strategy_selection(actions=[...], diversity_score=0.75)
tracer.trace_content_generation(action={...}, model='claude', ...)
tracer.trace_quality_evaluation(critic_scores={...}, total_reward=0.8)

# 结束追踪
await tracer.end_trace(output_data={...})
```

**分析**:

```python
from app.core.tracer import TraceAnalyzer

analyzer = TraceAnalyzer(tracer)

# 性能分析
performance = await analyzer.analyze_performance(user_id="user_123")
print(f"平均耗时: {performance['avg_duration']}s")
print(f"平均奖励: {performance['avg_reward']}")
print(f"通过率: {performance['approval_rate']}")

# 模型对比
model_perf = await analyzer.analyze_model_performance(model_name='claude')
print(f"成功率: {model_perf['success_rate']}")
print(f"平均延迟: {model_perf['avg_latency']}s")
```

---

### 3. 趋势质量过滤器（Trend Quality Filter）

**位置**: `backend/app/rag/trend_quality_filter.py`

**功能**:
- 评估趋势的新鲜度、可信度、人群匹配度、品牌适配度
- 过滤低质量趋势
- 品牌合规检查

**使用方法**:

```python
from app.rag.trend_quality_filter import TrendQualityFilter, BrandGuidelines

# 配置品牌指南
brand_guidelines = BrandGuidelines({
    'tone_keywords': ['专业', '可信', '创新'],
    'forbidden_words': ['低俗', '色情', '暴力'],
    'target_audience': {'age_range': [18, 35], 'interests': ['短视频']}
})

# 初始化过滤器
filter = TrendQualityFilter(brand_guidelines=brand_guidelines)

# 过滤趋势
filtered_trends = filter.filter_trends(
    trends=raw_trends,
    threshold=0.6,
    max_results=10
)

# 查看质量评分
for trend in filtered_trends:
    print(f"趋势: {trend['id']}, 质量分数: {trend['quality_score']}")
    print(f"详细: {trend['quality_details']}")
```

**配置**:

```yaml
trend_quality_filter:
  enabled: true
  threshold: 0.6
  max_results: 10
  weights:
    freshness: 0.2
    credibility: 0.2
    audience_match: 0.3
    brand_fit: 0.3
```

---

### 4. 多样性感知经验池（Diversity-Aware Experience Pool）

**位置**: `backend/app/rl/diversity_experience_pool.py`

**功能**:
- 追踪动作分布和新颖度
- 多样性感知采样（平衡质量和探索）
- 防止自我强化

**使用方法**:

```python
from app.rl.diversity_experience_pool import DiversityAwareExperiencePool

# 初始化
pool = DiversityAwareExperiencePool(
    max_size=1000,
    max_episodes=100,
    novelty_decay=0.95
)

# 添加经验
pool.add_episode(episode)

# 采样经验（多种策略）
sampled = pool.sample_experiences(
    n=10,
    strategy='balanced',  # random, best, balanced, diverse, epsilon_greedy
    filter_approved=True
)

# 获取多样性统计
stats = pool.get_diversity_stats()
print(f"动作熵: {stats['action_entropy']}")
print(f"平均新颖度: {stats['avg_novelty']}")
print(f"Top动作: {stats['top_actions']}")
```

**采样策略**:
- `random`: 随机采样
- `best`: 只采样高奖励的
- `diverse`: 优先采样新颖的
- `balanced`: 平衡质量和多样性（50/50）
- `epsilon_greedy`: ε-贪心（ε 概率探索）

---

### 5. 模型路由器（Model Router）

**位置**: `backend/app/llm/model_router.py`

**功能**:
- 智能路由（根据任务类型选择最佳模型）
- 灰度发布（新模型逐步放量）
- 自动降级（失败时切换到备用模型）
- 性能监控（延迟、成功率、成本）

**使用方法**:

```python
from app.llm.model_router import ModelRouter, ModelConfig, RoutingRule, TaskType

# 配置模型
models = {
    'claude': ModelConfig(name='claude', provider='claude', version='...', cost_per_1k_tokens=0.015),
    'deepseek': ModelConfig(name='deepseek', provider='deepseek', version='...', cost_per_1k_tokens=0.001)
}

# 配置路由规则
routing_rules = [
    RoutingRule(
        task_type=TaskType.CONTENT_GENERATION,
        primary_model='deepseek',
        fallback_models=['claude']
    )
]

# 初始化路由器
router = ModelRouter(models=models, routing_rules=routing_rules)

# 注册模型实例
router.register_model_instance('claude', claude_instance)
router.register_model_instance('deepseek', deepseek_instance)

# 路由请求
result = await router.route(
    task_type=TaskType.CONTENT_GENERATION,
    prompt="生成内容...",
    temperature=0.7
)

# 获取指标
metrics = router.get_metrics()
print(f"Claude 成功率: {metrics['claude']['success_rate']}")
print(f"DeepSeek 平均延迟: {metrics['deepseek']['avg_latency']}s")
```

**灰度发布**:

```python
# 启用灰度
router.canary_config.enabled = True
router.canary_config.canary_model = 'gemini'
router.canary_config.traffic_percent = 10.0

# 检查灰度健康
health = router.check_canary_health()
if health['recommendation'] == 'promote':
    router.promote_canary()  # 提升为主模型
elif health['recommendation'] == 'rollback':
    router.rollback_canary()  # 回滚
```

---

### 6. 回归测试系统（Regression Test Suite）

**位置**: `backend/app/testing/regression_suite.py`

**功能**:
- 加载固定测试集
- 执行回归测试
- 评估质量
- 对比基线

**使用方法**:

```python
from app.testing.regression_suite import RegressionTestSuite

# 初始化
test_suite = RegressionTestSuite(
    test_cases_path="./tests/regression/test_cases.json",
    baseline_path="./tests/regression/baseline.json"
)

# 运行回归测试
report = await test_suite.run_regression(
    system_version="v2.5.1",
    generation_func=your_generation_function,
    evaluation_func=your_evaluation_function
)

# 查看报告
print(f"通过率: {report.pass_rate:.1%}")
print(f"平均质量: {report.avg_quality_score}")

# 对比基线
if report.comparison_with_baseline:
    comparison = report.comparison_with_baseline
    print(f"相比基线: {comparison['overall_diff']:+.3f}")
    print(f"建议: {comparison['recommendation']}")

# 保存报告
test_suite.save_report(report, "./tests/regression/report_v2.5.1.json")

# 设为新基线
test_suite.set_as_baseline(report)
```

---

### 7. 层级动作空间（Hierarchical Action Space）

**位置**: `backend/app/rl/hierarchical_action_space.py`

**功能**:
- 两层结构：策略（Strategy）+ 实现（Implementation）
- 可扩展：新增策略不需要重构
- 可学习：每个策略的实现可以独立优化

**使用方法**:

```python
from app.rl.hierarchical_action_space import HierarchicalActionSpace, StrategyType

# 初始化
action_space = HierarchicalActionSpace()

# 采样动作
action = action_space.sample_action(
    context={
        'platform': 'xiaohongshu',
        'target_audience': {'age_range': [18, 35]}
    }
)

print(f"策略: {action['strategy']['name']}")
print(f"实现: {action['implementation']['id']}")
print(f"Hook模式: {action['implementation']['hook_pattern']}")
print(f"Body模式: {action['implementation']['body_pattern']}")
print(f"CTA模式: {action['implementation']['cta_pattern']}")

# 指定策略类型
action = action_space.sample_action(
    strategy_type=StrategyType.EMOTIONAL_RESONANCE
)

# 更新表现
action_space.update_performance(
    implementation_id='ER_001',
    performance_score=0.85
)

# 添加新策略
from app.rl.hierarchical_action_space import StrategyConfig, ImplementationTemplate

new_strategy = StrategyConfig(
    type=StrategyType.CURIOSITY_GAP,
    name="好奇缺口",
    description="制造信息缺口引发好奇",
    platforms=['douyin', 'tiktok']
)
action_space.add_strategy(new_strategy)

# 添加新实现
new_impl = ImplementationTemplate(
    id='CG_003',
    strategy_type=StrategyType.CURIOSITY_GAP,
    hook_pattern='悬念设置 + 反转预告',
    body_pattern='层层递进 + 意外揭秘',
    cta_pattern='悬念延续',
    description='制造信息缺口'
)
action_space.add_implementation(new_impl)
```

**内置策略**:
1. 情绪共鸣（Emotional Resonance）
2. 知识权威（Knowledge Authority）
3. 社交证明（Social Proof）
4. 问题解决（Problem Solution）
5. 好奇缺口（Curiosity Gap）
6. 价值主张（Value Proposition）
7. 故事叙述（Storytelling）
8. 数据驱动（Data Driven）

---

## 🔧 集成到现有系统

### 步骤 1: 更新依赖

```bash
cd backend
pip install -r requirements.txt
```

### 步骤 2: 配置文件

复制配置模板：

```bash
cp config/system_upgrade.yaml.example config/system_upgrade.yaml
```

编辑配置文件，根据需要调整参数。

### 步骤 3: 修改现有代码

#### 3.1 替换奖励模型

**原代码** (`app/rl/reward_model.py`):
```python
from app.rl.reward_model import RewardModel
reward_model = RewardModel()
```

**新代码**:
```python
from app.rl.hybrid_reward_model import HybridRewardModel
reward_model = HybridRewardModel(
    metric_weights={'ctr': 0.2, 'completion': 0.3, 'engagement': 0.3, 'conversion': 0.2},
    quality_threshold=0.7
)
```

#### 3.2 替换经验池

**原代码** (`app/rl/experience_pool.py`):
```python
from app.rl.experience_pool import ExperiencePool
pool = ExperiencePool()
```

**新代码**:
```python
from app.rl.diversity_experience_pool import DiversityAwareExperiencePool
pool = DiversityAwareExperiencePool(max_size=1000, max_episodes=100)
```

#### 3.3 添加追踪

在生成流程中添加追踪：

```python
from app.core.tracer import GenerationTracer

tracer = GenerationTracer(db_session=db)

# 在生成开始时
trace_id = tracer.start_trace(user_id=user_id, input_data=input_data)

# 在各个阶段
tracer.trace_trend_retrieval(...)
tracer.trace_strategy_selection(...)
tracer.trace_content_generation(...)
tracer.trace_quality_evaluation(...)

# 在生成结束时
await tracer.end_trace(output_data=output_data)
```

#### 3.4 添加趋势过滤

在 Trend Agent 中添加过滤：

```python
from app.rag.trend_quality_filter import TrendQualityFilter, BrandGuidelines

# 初始化（在 TrendAgent.__init__ 中）
self.quality_filter = TrendQualityFilter(brand_guidelines=brand_guidelines)

# 在检索后过滤（在 TrendAgent.execute 中）
raw_trends = await self.qdrant.search(...)
filtered_trends = self.quality_filter.filter_trends(raw_trends, threshold=0.6)
```

---

## 📊 运行示例

```bash
cd backend
python examples/system_upgrade_demo.py
```

这将运行所有 7 个功能模块的示例。

---

## 🧪 运行回归测试

```bash
cd backend
python -m pytest tests/regression/
```

或使用回归测试脚本：

```bash
python scripts/run_regression_test.py --version v2.5.1
```

---

## 📈 监控和分析

### 查看追踪数据

```python
from app.core.tracer import GenerationTracer, TraceAnalyzer

tracer = GenerationTracer(db_session=db)
analyzer = TraceAnalyzer(tracer)

# 性能分析
performance = await analyzer.analyze_performance(user_id="user_123")

# 模型对比
model_perf = await analyzer.analyze_model_performance(model_name='claude')

# 策略对比
comparison = await analyzer.compare_strategies('strategy_a', 'strategy_b')
```

### 查看模型指标

```python
from app.llm.model_router import ModelRouter

router = ModelRouter(...)

# 获取所有模型指标
metrics = router.get_metrics()

# 获取特定模型指标
claude_metrics = router.get_metrics('claude')
```

### 查看多样性统计

```python
from app.rl.diversity_experience_pool import DiversityAwareExperiencePool

pool = DiversityAwareExperiencePool(...)

# 获取多样性统计
diversity_stats = pool.get_diversity_stats()
print(f"动作熵: {diversity_stats['action_entropy']}")
print(f"平均新颖度: {diversity_stats['avg_novelty']}")
```

---

## 🚨 注意事项

1. **向后兼容**: 所有新模块都是可选的，不会破坏现有功能
2. **性能影响**: 追踪系统会增加少量开销（<5%），可通过配置禁用
3. **数据库**: 追踪系统需要数据库支持，确保数据库连接正常
4. **模型实例**: 模型路由器需要注册模型实例才能工作
5. **测试用例**: 回归测试需要预先准备测试用例

---

## 📚 更多资源

- [API 文档](./API_DOCS.md)
- [架构设计](./ARCHITECTURE.md)
- [性能优化](./PERFORMANCE.md)
- [故障排查](./TROUBLESHOOTING.md)

---

## 🤝 贡献

如果你发现问题或有改进建议，请提交 Issue 或 Pull Request。

---

**最后更新**: 2026-02-12
**版本**: v2.5.1
**作者**: Growth Flywheel Team
