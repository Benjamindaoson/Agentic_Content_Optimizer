# Growth Flywheel 2.5 — Documentation Index

## Quick Links

- [README](../README.md) — Project overview, quick start, architecture
- [REPO_REFACTOR_INVENTORY](REPO_REFACTOR_INVENTORY.md) — Refactor mapping and deletion candidates

## AI Highlights

### AI Algorithms
- **RAG**: Self-RAG, Adaptive RAG, CRAG, Graph RAG (see `backend/app/engine/rag/`)
- **RL**: Thompson Sampling, GRPO, Hybrid Reward Model V2, Contextual Bandit (see `backend/app/ml/rl/`)
- **Agent**: LangGraph workflow (Trend → Director → Writer → Critic → Refinement)

### AI Application Development
- Structured output (Pydantic schemas)
- tiktoken-based token budgeting
- Prompt template versioning (PostgreSQL-backed)
- Cost-aware model routing

### AI System Design
- Health endpoints: `/health/live`, `/health/ready`
- Prometheus `/metrics`
- ProductionMonitor, AlertNotifier (Slack/PagerDuty)
- Startup fault injection, SLO gates

### AI Product
- End-to-end: 选题 → 生成 → 评估 → 发布 → 回流
- WebSocket real-time workflow visualization
- Outcome scraper for XHS compliance

## Deployment

- **Local**: `docker compose up -d`
- **Production (Tencent Cloud)**: `./scripts/deploy-prod.sh`, `docker-compose.prod.yml`
- **Nginx**: `deploy/nginx.conf`

## Ops Scripts

- `backend/scripts/ops/load_test.py` — HTTP load test
- `backend/scripts/ops/fault_injection_startup.py` — Startup failure simulation
- `backend/scripts/ops/slo_gate.py` — Combined readiness + load gate
