# 🚀 Growth Flywheel 2.5 - Training Pipeline Design

## 📊 System Status Summary

### ✅ What's Implemented (80% Architecture)
- Complete database schema (10 tables with SSOT pattern)
- Multi-agent orchestration (LangGraph)
- RL engines (GRPO, PPO, Reward Models)
- Data crawlers (MediaCrawler, XHS-Downloader, Playwright)
- RAG system (Qdrant vector DB)
- Growth Brain v4.0 (Auto Account Manager, Cover Engine, Multi-Platform, Causal Inference)
- FastAPI backend + Next.js frontend

### ❌ What's Missing (Critical 20%)
- **Training data pipeline** (preprocessing, validation, feature engineering)
- **End-to-end training orchestration** (GRPO/PPO training loops)
- **Feedback loop closure** (generation → publish → metrics → training)
- **Real-time metrics collection** (scheduled tasks)
- **Model checkpointing and versioning**
- **Training monitoring and evaluation**

---

## 🎯 Core Problem Statement

**Current State**: System can generate content but cannot learn from real-world performance.

**Target State**: Self-evolving system that:
1. Generates content using current policy
2. Publishes to platforms (XHS/Douyin)
3. Collects real performance metrics
4. Trains policy using GRPO/PPO
5. Updates strategy selection (Thompson Sampling)
6. Repeats (Growth Flywheel)

---

## 🔄 Complete Feedback Loop Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GENERATION PHASE                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Trend Agent → Director Agent → Writer Agent       │   │
│  │ 2. Generate N candidates with different strategies   │   │
│  │ 3. Critic evaluates quality                          │   │
│  │ 4. Select best candidate                             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    PUBLISHING PHASE                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Format content for platform (XHS/Douyin)          │   │
│  │ 2. Generate/select cover image                       │   │
│  │ 3. Publish via platform API                          │   │
│  │ 4. Store: generation_id → published_note_id          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  METRICS COLLECTION PHASE                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Wait 24h/48h/7d for metrics to stabilize          │   │
│  │ 2. Crawl published note metrics                      │   │
│  │ 3. Calculate: viral_score, engagement_rate, velocity │   │
│  │ 4. Store in OnlineMetrics table                      │   │
│  │ 5. Compare predicted vs actual performance           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     TRAINING PHASE                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Group metrics by pattern (Hook/Body/CTA)          │   │
│  │ 2. Calculate relative rewards (GRPO)                 │   │
│  │ 3. Update pattern success rates (Bayesian)           │   │
│  │ 4. Update Thompson Sampling priors (α, β)            │   │
│  │ 5. Retrain reward model (optional)                   │   │
│  │ 6. Save checkpoint                                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    (Loop back to GENERATION)
```

---

## 📦 Phase 1: Data Collection Pipeline

### 1.1 Historical Data Collection (Bootstrap)

**Objective**: Collect 10,000+ viral notes to initialize patterns and reward model.

**Implementation**:
```python
# backend/app/training/data_collection/historical_crawler.py

class HistoricalDataCollector:
    """
    Collects historical viral content for initial training.
    """

    async def collect_bootstrap_data(
        self,
        platform: str = "xiaohongshu",
        categories: List[str] = ["美妆", "穿搭", "美食", "旅行"],
        min_viral_score: float = 0.7,
        target_count: int = 10000,
        time_window_days: int = 90
    ) -> Dict[str, Any]:
        """
        Collect historical viral notes for bootstrapping.

        Steps:
        1. For each category, crawl top notes from last 90 days
        2. Filter by viral_score >= 0.7
        3. Download covers
        4. Run XHSAnalysis on each note
        5. Extract patterns
        6. Store in database

        Returns:
            {
                "total_collected": int,
                "by_category": Dict[str, int],
                "patterns_extracted": int,
                "avg_viral_score": float
            }
        """
        pass
```

**Celery Task**:
```python
# backend/app/tasks/data_collection_tasks.py

@celery_app.task(name="collect_historical_data", queue="crawl")
def collect_historical_data_task(
    platform: str,
    categories: List[str],
    min_viral_score: float,
    target_count: int
):
    """
    Scheduled task to collect historical data.
    Runs once during system initialization.
    """
    collector = HistoricalDataCollector()
    result = await collector.collect_bootstrap_data(
        platform=platform,
        categories=categories,
        min_viral_score=min_viral_score,
        target_count=target_count
    )
    return result
```

**Database Schema** (Already exists):
- `XHSNote`: Raw note data
- `XHSMetrics`: Performance metrics
- `XHSCover`: Cover images
- `XHSAnalysis`: Multi-dimensional analysis
- `Pattern`: Extracted patterns
- `PatternSample`: Pattern-to-note mapping

---

### 1.2 Real-Time Metrics Collection

**Objective**: Continuously collect performance metrics for published content.

**Implementation**:
```python
# backend/app/training/data_collection/realtime_metrics_collector.py

class RealtimeMetricsCollector:
    """
    Collects real-time metrics for published content.
    """

    async def collect_metrics_for_generation(
        self,
        generation_id: str,
        collection_schedule: List[int] = [24, 48, 168]  # hours
    ) -> List[OnlineMetrics]:
        """
        Collect metrics at multiple time points.

        Args:
            generation_id: ID of the generation
            collection_schedule: Hours after publish to collect metrics

        Returns:
            List of OnlineMetrics records
        """
        # 1. Get published_note_id from OnlineMetrics
        # 2. For each time point in schedule:
        #    - Crawl current metrics
        #    - Calculate viral_score, engagement_rate, velocity
        #    - Store in OnlineMetrics
        #    - Compare with predicted metrics
        pass

    async def batch_collect_pending_metrics(
        self,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Collect metrics for all pending published notes.

        Steps:
        1. Query OnlineMetrics where next_collection_at <= now
        2. Batch crawl metrics
        3. Update records
        4. Schedule next collection

        Returns:
            {
                "collected": int,
                "failed": int,
                "avg_accuracy": float
            }
        """
        pass
```

**Celery Scheduled Task**:
```python
# backend/app/tasks/metrics_collection_tasks.py

@celery_app.task(name="collect_realtime_metrics", queue="crawl")
def collect_realtime_metrics_task():
    """
    Runs every hour to collect metrics for published content.
    """
    collector = RealtimeMetricsCollector()
    result = await collector.batch_collect_pending_metrics(batch_size=100)
    return result

# Schedule in celery beat
celery_app.conf.beat_schedule = {
    'collect-realtime-metrics': {
        'task': 'collect_realtime_metrics',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

---

### 1.3 Data Validation and Quality Control

**Implementation**:
```python
# backend/app/training/data_collection/data_validator.py

class TrainingDataValidator:
    """
    Validates data quality before training.
    """

    def validate_training_batch(
        self,
        online_metrics: List[OnlineMetrics]
    ) -> Tuple[List[OnlineMetrics], List[str]]:
        """
        Validate training data quality.

        Checks:
        1. Metrics are within reasonable ranges
        2. No missing critical fields
        3. Sufficient time has passed for metrics to stabilize
        4. Pattern information is complete
        5. No duplicate entries

        Returns:
            (valid_metrics, error_messages)
        """
        valid = []
        errors = []

        for metric in online_metrics:
            # Check 1: Metrics range
            if not (0 <= metric.engagement_rate <= 1):
                errors.append(f"Invalid engagement_rate: {metric.engagement_rate}")
                continue

            # Check 2: Required fields
            if not metric.generation_id or not metric.published_note_id:
                errors.append(f"Missing required fields")
                continue

            # Check 3: Time stability (at least 24h)
            hours_since_publish = (datetime.now() - metric.published_at).total_seconds() / 3600
            if hours_since_publish < 24:
                errors.append(f"Metrics too fresh: {hours_since_publish}h")
                continue

            # Check 4: Pattern info
            generation = metric.generation
            if not generation or not generation.best_content:
                errors.append(f"Missing generation data")
                continue

            valid.append(metric)

        return valid, errors
```

---

## 🧠 Phase 2: Training Pipeline

### 2.1 GRPO Training Loop

**Objective**: Train policy using Group Relative Policy Optimization.

**Implementation**:
```python
# backend/app/training/grpo_training_loop.py

class GRPOTrainingLoop:
    """
    End-to-end GRPO training orchestration.
    """

    def __init__(self):
        self.trainer = GRPOTrainer()
        self.validator = TrainingDataValidator()
        self.reward_model = HybridRewardModelV2()

    async def run_training_episode(
        self,
        min_samples: int = 50,
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """
        Run one training episode.

        Steps:
        1. Collect online metrics from last N days
        2. Validate data quality
        3. Group by pattern (Hook/Body/CTA)
        4. Calculate relative rewards
        5. Update pattern success rates (Bayesian)
        6. Update Thompson Sampling priors
        7. Save checkpoint
        8. Evaluate prediction accuracy

        Returns:
            {
                "episode_id": str,
                "samples_used": int,
                "patterns_updated": int,
                "avg_reward": float,
                "prediction_accuracy": Dict[str, float],
                "checkpoint_path": str
            }
        """
        # 1. Collect data
        online_metrics = await self.trainer.collect_online_metrics(
            lookback_days=lookback_days
        )

        if len(online_metrics) < min_samples:
            return {"status": "insufficient_data", "samples": len(online_metrics)}

        # 2. Validate
        valid_metrics, errors = self.validator.validate_training_batch(online_metrics)

        if len(valid_metrics) < min_samples:
            return {"status": "insufficient_valid_data", "errors": errors}

        # 3. Group by pattern
        pattern_groups = self._group_by_pattern(valid_metrics)

        # 4. Calculate relative rewards
        relative_rewards = {}
        for pattern_key, metrics in pattern_groups.items():
            rewards = [self.reward_model.calculate_reward(m) for m in metrics]
            mean_reward = np.mean(rewards)
            std_reward = np.std(rewards)
            relative_rewards[pattern_key] = [
                (r - mean_reward) / (std_reward + 1e-8) for r in rewards
            ]

        # 5. Update patterns
        patterns_updated = 0
        for pattern_key, rel_rewards in relative_rewards.items():
            pattern = await self._get_pattern(pattern_key)
            if pattern:
                # Bayesian update
                successes = sum(1 for r in rel_rewards if r > 0)
                failures = len(rel_rewards) - successes

                pattern.thompson_alpha += successes
                pattern.thompson_beta += failures
                pattern.success_rate = pattern.thompson_alpha / (
                    pattern.thompson_alpha + pattern.thompson_beta
                )
                pattern.sample_size += len(rel_rewards)

                await self.db.commit()
                patterns_updated += 1

        # 6. Save checkpoint
        checkpoint_path = await self._save_checkpoint(
            episode_id=str(uuid.uuid4()),
            patterns_updated=patterns_updated,
            metrics=valid_metrics
        )

        # 7. Evaluate
        accuracy = await self.trainer.evaluate_prediction_accuracy(valid_metrics)

        return {
            "status": "success",
            "episode_id": checkpoint_path.split("/")[-1],
            "samples_used": len(valid_metrics),
            "patterns_updated": patterns_updated,
            "avg_reward": np.mean([r for rewards in relative_rewards.values() for r in rewards]),
            "prediction_accuracy": accuracy,
            "checkpoint_path": checkpoint_path
        }

    def _group_by_pattern(self, metrics: List[OnlineMetrics]) -> Dict[str, List[OnlineMetrics]]:
        """Group metrics by (hook, body, cta) pattern."""
        groups = {}
        for metric in metrics:
            generation = metric.generation
            if not generation or not generation.best_content:
                continue

            content = generation.best_content
            pattern_key = f"{content.get('hook_type')}_{content.get('body_type')}_{content.get('cta_type')}"

            if pattern_key not in groups:
                groups[pattern_key] = []
            groups[pattern_key].append(metric)

        return groups

    async def _save_checkpoint(self, episode_id: str, patterns_updated: int, metrics: List[OnlineMetrics]) -> str:
        """Save training checkpoint."""
        checkpoint_dir = Path("checkpoints") / episode_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Save patterns
        patterns = await self.db.query(Pattern).all()
        patterns_data = [
            {
                "id": p.id,
                "hook_template": p.hook_template,
                "body_structure": p.body_structure,
                "cta_template": p.cta_template,
                "success_rate": p.success_rate,
                "thompson_alpha": p.thompson_alpha,
                "thompson_beta": p.thompson_beta,
                "sample_size": p.sample_size
            }
            for p in patterns
        ]

        with open(checkpoint_dir / "patterns.json", "w") as f:
            json.dump(patterns_data, f, indent=2)

        # Save metadata
        metadata = {
            "episode_id": episode_id,
            "timestamp": datetime.now().isoformat(),
            "patterns_updated": patterns_updated,
            "samples_used": len(metrics),
            "avg_success_rate": np.mean([p["success_rate"] for p in patterns_data])
        }

        with open(checkpoint_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return str(checkpoint_dir)
```

**Celery Scheduled Task**:
```python
# backend/app/tasks/training_tasks.py

@celery_app.task(name="run_grpo_training", queue="training")
def run_grpo_training_task():
    """
    Runs GRPO training episode.
    Scheduled to run daily or when sufficient new data is available.
    """
    loop = GRPOTrainingLoop()
    result = await loop.run_training_episode(
        min_samples=50,
        lookback_days=7
    )
    return result

# Schedule in celery beat
celery_app.conf.beat_schedule = {
    'run-grpo-training': {
        'task': 'run_grpo_training',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

---

### 2.2 Reward Model Training

**Objective**: Train reward model to predict viral_score from content features.

**Implementation**:
```python
# backend/app/training/reward_model_training.py

class RewardModelTrainer:
    """
    Trains reward model to predict performance.
    """

    async def train_reward_model(
        self,
        training_data: List[OnlineMetrics],
        model_type: str = "gradient_boosting"
    ) -> Dict[str, Any]:
        """
        Train reward model on real performance data.

        Features:
        - Content structure (hook/body/cta types)
        - Text features (length, sentiment, keywords)
        - Visual features (cover layout, colors)
        - Timing features (publish time, day of week)
        - Account features (follower count, historical performance)

        Target:
        - viral_score (regression)

        Returns:
            {
                "model_path": str,
                "metrics": {
                    "mae": float,
                    "rmse": float,
                    "r2": float
                },
                "feature_importance": Dict[str, float]
            }
        """
        pass
```

---

## 🔗 Phase 3: Feedback Loop Closure

### 3.1 Publishing Pipeline

**Objective**: Publish generated content to platforms.

**Implementation**:
```python
# backend/app/publishing/publisher.py

class ContentPublisher:
    """
    Publishes content to platforms.
    """

    async def publish_to_xiaohongshu(
        self,
        generation_id: str,
        account_id: str,
        schedule_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Publish content to Xiaohongshu.

        Steps:
        1. Get generation content
        2. Format for XHS (title, text, images)
        3. Generate/select cover
        4. Publish via XHS API
        5. Store published_note_id in OnlineMetrics
        6. Schedule metrics collection

        Returns:
            {
                "published_note_id": str,
                "published_url": str,
                "published_at": datetime,
                "next_collection_at": datetime
            }
        """
        pass
```

---

### 3.2 End-to-End Orchestration

**Implementation**:
```python
# backend/app/training/orchestrator.py

class TrainingOrchestrator:
    """
    Orchestrates the complete feedback loop.
    """

    async def run_complete_cycle(
        self,
        topic: str,
        platform: str = "xiaohongshu",
        account_id: str = None,
        auto_publish: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete cycle: generate → publish → collect → train.

        Steps:
        1. Generate content
        2. (Optional) Publish to platform
        3. Schedule metrics collection
        4. When metrics available, trigger training

        Returns:
            {
                "generation_id": str,
                "published": bool,
                "published_note_id": Optional[str],
                "metrics_scheduled": bool,
                "training_scheduled": bool
            }
        """
        # 1. Generate
        generation_result = await self.generation_service.generate(
            topic=topic,
            platform=platform
        )

        generation_id = generation_result["generation_id"]

        # 2. Publish (if auto_publish)
        published_note_id = None
        if auto_publish and account_id:
            publish_result = await self.publisher.publish_to_xiaohongshu(
                generation_id=generation_id,
                account_id=account_id
            )
            published_note_id = publish_result["published_note_id"]

        # 3. Schedule metrics collection
        if published_note_id:
            await self._schedule_metrics_collection(
                generation_id=generation_id,
                published_note_id=published_note_id,
                collection_schedule=[24, 48, 168]  # hours
            )

        return {
            "generation_id": generation_id,
            "published": published_note_id is not None,
            "published_note_id": published_note_id,
            "metrics_scheduled": published_note_id is not None,
            "training_scheduled": True
        }
```

---

## 📈 Phase 4: Monitoring and Evaluation

### 4.1 Training Metrics Dashboard

**Metrics to Track**:
1. **Data Collection**:
   - Notes collected per day
   - Crawl success rate
   - Data quality score

2. **Training**:
   - Episodes completed
   - Samples per episode
   - Patterns updated
   - Average reward trend
   - Prediction accuracy (MAE, RMSE, R²)

3. **Policy Performance**:
   - Success rate by pattern
   - Thompson Sampling exploration rate
   - Strategy diversity
   - Viral rate trend

4. **System Health**:
   - API latency
   - Task queue length
   - Error rate
   - Database size

**Implementation**:
```python
# backend/app/monitoring/training_monitor.py

class TrainingMonitor:
    """
    Monitors training progress and system health.
    """

    async def get_training_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive training metrics.
        """
        return {
            "data_collection": await self._get_data_collection_metrics(),
            "training": await self._get_training_metrics(),
            "policy_performance": await self._get_policy_metrics(),
            "system_health": await self._get_system_health()
        }
```

---

## 🚀 Implementation Roadmap

### Week 1: Data Collection Infrastructure
- [ ] Implement `HistoricalDataCollector`
- [ ] Implement `RealtimeMetricsCollector`
- [ ] Implement `TrainingDataValidator`
- [ ] Set up Celery scheduled tasks
- [ ] Test data collection pipeline

### Week 2: Training Loop
- [ ] Implement `GRPOTrainingLoop`
- [ ] Implement checkpoint saving/loading
- [ ] Implement `RewardModelTrainer`
- [ ] Test training on sample data
- [ ] Verify pattern updates

### Week 3: Publishing Pipeline
- [ ] Implement `ContentPublisher` for XHS
- [ ] Integrate with XHS API
- [ ] Test publishing flow
- [ ] Implement metrics scheduling

### Week 4: Feedback Loop Closure
- [ ] Implement `TrainingOrchestrator`
- [ ] Connect all components
- [ ] End-to-end testing
- [ ] Deploy to staging

### Week 5: Monitoring and Optimization
- [ ] Implement `TrainingMonitor`
- [ ] Build training dashboard
- [ ] Set up alerts
- [ ] Performance tuning

### Week 6: Production Deployment
- [ ] Load testing
- [ ] Security audit
- [ ] Documentation
- [ ] Production deployment

---

## 🎯 Success Metrics

### Short-term (1 month)
- ✅ 10,000+ viral notes collected
- ✅ 100+ training episodes completed
- ✅ Prediction accuracy > 70%
- ✅ Feedback loop latency < 48h

### Medium-term (3 months)
- ✅ Viral rate improvement: +20%
- ✅ Prediction accuracy > 80%
- ✅ Strategy diversity maintained
- ✅ 1,000+ published notes tracked

### Long-term (6 months)
- ✅ Viral rate improvement: +50%
- ✅ Prediction accuracy > 85%
- ✅ Fully autonomous operation
- ✅ Multi-platform support

---

## 🔧 Technical Requirements

### Infrastructure
- PostgreSQL 13+ (with 100GB+ storage)
- Redis 6+ (with persistence)
- Qdrant (with 50GB+ storage)
- Celery workers (4+ workers)
- GPU for model training (optional but recommended)

### API Access
- Xiaohongshu API credentials
- Douyin API credentials (future)
- LLM API keys (Claude, GPT, Gemini)

### Monitoring
- Prometheus + Grafana
- Sentry for error tracking
- ELK stack for logging

---

## 🚨 Risk Mitigation

### Data Quality
- **Risk**: Low-quality training data
- **Mitigation**: Multi-stage validation, outlier detection, manual review

### Platform Changes
- **Risk**: Platform API changes break crawlers
- **Mitigation**: Multi-crawler fallback, compliance caching, monitoring

### Training Instability
- **Risk**: Policy collapse, reward hacking
- **Mitigation**: Clipped updates, diversity bonuses, human oversight

### System Overload
- **Risk**: Too many concurrent tasks
- **Mitigation**: Rate limiting, queue management, auto-scaling

---

## 📚 Next Steps

1. **Review this design** with team
2. **Prioritize features** based on business needs
3. **Set up development environment**
4. **Start with Week 1 tasks**
5. **Iterate based on results**

---

**Document Version**: 1.0
**Last Updated**: 2026-02-13
**Author**: Growth Flywheel Team
