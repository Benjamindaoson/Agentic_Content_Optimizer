# 🚀 Growth Flywheel 2.5 - Production Deployment Guide

## 📋 Phase 2: Real Data Integration & Production Deployment

**Status**: Ready for Implementation
**Last Updated**: 2026-02-13

---

## 🎯 Overview

This guide covers the transition from MVP (mock data) to production (real data + automated training).

### Key Components
1. **Real Data Collection** - XHS crawler integration
2. **Automated Training** - Celery scheduled tasks
3. **Online Metrics** - Real-time performance tracking
4. **Monitoring** - Grafana + Prometheus dashboards
5. **Production Deployment** - Docker + Kubernetes

---

## 📦 Phase 2.1: Real Data Collection

### Step 1: Configure XHS Crawler

**File**: `backend/app/crawlers/xhs_crawler.py`

The crawler is already implemented with three adapters:
- MediaCrawler (primary)
- XHS-Downloader (cover download)
- Playwright (fallback)

**Configuration**:
```python
# backend/scripts/collect_real_data.py

USE_REAL_CRAWLER = True  # Enable real crawler
CATEGORY = "美妆"
TARGET_COUNT = 1000
MIN_LIKES = 10000
```

**Run Collection**:
```bash
cd backend
python scripts/collect_real_data.py
```

**Expected Output**:
- 1,000 real viral notes collected
- Patterns extracted from real data
- Covers downloaded to `data/covers/`

---

### Step 2: Implement Analysis Service

Currently using heuristic analysis. For production, integrate LLM:

**File**: `backend/app/services/analysis_service.py`

```python
class AnalysisService:
    """
    Deep content analysis using LLM.
    """

    async def analyze_note(self, note_id: str) -> XHSAnalysis:
        """
        Analyze note structure using Claude/GPT.

        Steps:
        1. Extract text and images
        2. Prompt LLM for structure analysis
        3. Parse response into XHSAnalysis
        4. Save to database
        """
        pass
```

**LLM Prompt Template**:
```
Analyze this Xiaohongshu note:

Title: {title}
Text: {text}

Identify:
1. Hook type: question/story/shock/benefit/curiosity
2. Body structure: list/tutorial/comparison/story/tips
3. CTA type: like/collect/follow/comment/share
4. Emotion curve: [0.0-1.0 values]
5. Key topics and keywords

Return JSON format.
```

---

## 🤖 Phase 2.2: Automated Training

### Step 1: Set Up Celery Workers

**Install Celery**:
```bash
pip install celery redis
```

**Start Celery Worker**:
```bash
cd backend
celery -A app.tasks.training_tasks worker --loglevel=info --queue=training,crawl
```

**Start Celery Beat (Scheduler)**:
```bash
celery -A app.tasks.training_tasks beat --loglevel=info
```

---

### Step 2: Configure Scheduled Tasks

**File**: `backend/app/tasks/training_tasks.py`

**Schedule**:
- **2:00 AM** - Collect viral notes (100 notes/day)
- **4:00 AM** - Run GRPO training
- **Every hour** - Collect online metrics

**Monitor Tasks**:
```bash
# Check task status
celery -A app.tasks.training_tasks inspect active

# Check scheduled tasks
celery -A app.tasks.training_tasks inspect scheduled
```

---

## 📊 Phase 2.3: Online Metrics Collection

### Step 1: Implement Publishing Pipeline

**File**: `backend/app/publishing/publisher.py`

```python
class ContentPublisher:
    """
    Publish generated content to platforms.
    """

    async def publish_to_xiaohongshu(
        self,
        generation_id: str,
        account_id: str,
        schedule_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Publish content to XHS.

        Steps:
        1. Get generation content
        2. Format for XHS (title, text, images)
        3. Upload images
        4. Publish via XHS API
        5. Store published_note_id in OnlineMetrics
        6. Schedule metrics collection (24h, 48h, 7d)

        Returns:
            {
                "published_note_id": str,
                "published_url": str,
                "published_at": datetime
            }
        """
        pass
```

---

### Step 2: Implement Metrics Collector

**File**: `backend/app/rl/online_metrics_collector.py` (already exists)

**Enhance with Scheduled Collection**:

```python
@celery_app.task(name="collect_metrics_for_note")
def collect_metrics_for_note_task(generation_id: str, collection_time: str):
    """
    Collect metrics at specific time point (24h/48h/7d).
    """
    async def _collect():
        async with AsyncSessionLocal() as db:
            collector = OnlineMetricsCollector(db)
            metrics = await collector.collect_metrics_for_generation(generation_id)
            return metrics

    return run_async(_collect())
```

**Schedule Collection**:
```python
# When publishing
published_at = datetime.now()

# Schedule 24h collection
celery_app.send_task(
    "collect_metrics_for_note",
    args=(generation_id, "24h"),
    eta=published_at + timedelta(hours=24)
)

# Schedule 48h collection
celery_app.send_task(
    "collect_metrics_for_note",
    args=(generation_id, "48h"),
    eta=published_at + timedelta(hours=48)
)

# Schedule 7d collection
celery_app.send_task(
    "collect_metrics_for_note",
    args=(generation_id, "7d"),
    eta=published_at + timedelta(days=7)
)
```

---

## 📈 Phase 2.4: Monitoring & Observability

### Step 1: Set Up Prometheus

**File**: `docker-compose.monitoring.yml`

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: gf25-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: gf25-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

**Start Monitoring**:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

**Access**:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

---

### Step 2: Add Metrics to Application

**File**: `backend/app/monitoring/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Data collection metrics
notes_collected = Counter(
    'notes_collected_total',
    'Total number of notes collected',
    ['category', 'source']
)

# Training metrics
training_episodes = Counter(
    'training_episodes_total',
    'Total number of training episodes'
)

training_duration = Histogram(
    'training_duration_seconds',
    'Training episode duration'
)

pattern_success_rate = Gauge(
    'pattern_success_rate',
    'Pattern success rate',
    ['pattern_id']
)

# Generation metrics
content_generated = Counter(
    'content_generated_total',
    'Total content generated',
    ['platform', 'category']
)

generation_quality = Histogram(
    'generation_quality_score',
    'Quality score from Critic'
)

# Online metrics
published_notes = Counter(
    'published_notes_total',
    'Total notes published',
    ['platform']
)

viral_rate = Gauge(
    'viral_rate',
    'Viral rate (viral_score > 0.7)',
    ['platform', 'category']
)
```

**Instrument Code**:
```python
# In data collection
notes_collected.labels(category="美妆", source="xhs").inc()

# In training
with training_duration.time():
    result = await trainer.run_training_episode()
training_episodes.inc()

# Update pattern metrics
for pattern in patterns:
    pattern_success_rate.labels(pattern_id=pattern.pattern_id).set(
        pattern.success_rate
    )
```

---

### Step 3: Create Grafana Dashboards

**Dashboard 1: Data Collection**
- Notes collected per day
- Viral rate trend
- Crawler success rate
- Category distribution

**Dashboard 2: Training Performance**
- Training episodes per day
- Average reward trend
- Pattern success rate distribution
- Prediction accuracy (MAE, RMSE)

**Dashboard 3: Generation Quality**
- Content generated per day
- Quality score distribution
- Platform distribution
- Category performance

**Dashboard 4: Online Performance**
- Published notes per day
- Viral rate trend
- Engagement rate trend
- Top performing patterns

---

## 🐳 Phase 2.5: Production Deployment

### Step 1: Docker Configuration

**File**: `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  # Database
  postgres:
    image: postgres:16-alpine
    container_name: gf25-postgres-prod
    environment:
      POSTGRES_DB: growth_flywheel
      POSTGRES_USER: gf_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  # Redis
  redis:
    image: redis:7-alpine
    container_name: gf25-redis-prod
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: always

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: gf25-backend-prod
    environment:
      - DATABASE_URL=postgresql://gf_user:${POSTGRES_PASSWORD}@postgres:5432/growth_flywheel
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - ENVIRONMENT=production
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    restart: always

  # Celery Worker
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: gf25-celery-worker
    command: celery -A app.tasks.training_tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://gf_user:${POSTGRES_PASSWORD}@postgres:5432/growth_flywheel
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: always

  # Celery Beat
  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: gf25-celery-beat
    command: celery -A app.tasks.training_tasks beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://gf_user:${POSTGRES_PASSWORD}@postgres:5432/growth_flywheel
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: always

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: gf25-frontend-prod
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: always

volumes:
  postgres_data:
  redis_data:
```

**Deploy**:
```bash
# Set environment variables
export POSTGRES_PASSWORD=your_secure_password
export REDIS_PASSWORD=your_secure_password

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend
```

---

### Step 2: Kubernetes Deployment (Optional)

**File**: `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: growth-flywheel-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: growth-flywheel-backend
  template:
    metadata:
      labels:
        app: growth-flywheel-backend
    spec:
      containers:
      - name: backend
        image: growth-flywheel:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

**Deploy to Kubernetes**:
```bash
kubectl apply -f k8s/
kubectl get pods
kubectl logs -f deployment/growth-flywheel-backend
```

---

## 🔒 Security Checklist

### Environment Variables
- [ ] Use `.env` files (never commit to git)
- [ ] Rotate API keys regularly
- [ ] Use strong passwords for databases
- [ ] Enable SSL/TLS for all connections

### Database
- [ ] Enable PostgreSQL SSL
- [ ] Restrict database access by IP
- [ ] Regular backups (daily)
- [ ] Encrypt sensitive data

### API
- [ ] Enable CORS restrictions
- [ ] Rate limiting
- [ ] JWT token expiration
- [ ] Input validation

### Monitoring
- [ ] Set up alerts for errors
- [ ] Monitor resource usage
- [ ] Track failed tasks
- [ ] Log security events

---

## 📊 Success Metrics

### Short-term (1 month)
- [ ] 10,000+ real viral notes collected
- [ ] 100+ training episodes completed
- [ ] Prediction accuracy > 70%
- [ ] System uptime > 99%

### Medium-term (3 months)
- [ ] 100,000+ notes in database
- [ ] Viral rate improvement: +20%
- [ ] Prediction accuracy > 80%
- [ ] 1,000+ content published

### Long-term (6 months)
- [ ] 1M+ notes in database
- [ ] Viral rate improvement: +50%
- [ ] Prediction accuracy > 85%
- [ ] Multi-platform support (XHS + Douyin)

---

## 🆘 Troubleshooting

### Issue: Celery tasks not running
**Solution**:
```bash
# Check Redis connection
redis-cli -a your_password ping

# Check Celery worker status
celery -A app.tasks.training_tasks inspect active

# Restart workers
docker-compose restart celery-worker celery-beat
```

### Issue: Training fails with "no patterns"
**Solution**:
```bash
# Run data collection first
python scripts/collect_real_data.py

# Verify patterns exist
python scripts/dashboard.py
```

### Issue: High memory usage
**Solution**:
- Reduce batch size in data collection
- Increase worker memory limits
- Enable database connection pooling
- Clear old checkpoints

---

## 📞 Next Steps

1. **Week 1-2**: Implement real data collection
2. **Week 3-4**: Set up automated training
3. **Week 5-6**: Implement publishing pipeline
4. **Week 7-8**: Add monitoring and alerts
5. **Week 9-10**: Production deployment and testing

---

**Document Version**: 1.0
**Last Updated**: 2026-02-13
