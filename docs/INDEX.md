# Growth Flywheel 2.5 — Documentation Index

## Quick Links

- [README](../README.md) — Project overview, quick start, architecture
- [Multimodal Content Agent](MULTIMODAL_CONTENT_AGENT.md) — Long-horizon short-video/content production runtime, recovery semantics, and roadmap
- [Production Hardening Status](PRODUCTION_HARDENING_STATUS.md) — Executed P0–P3 validation evidence, live blockers, and acceptance state
- [REPO_REFACTOR_INVENTORY](REPO_REFACTOR_INVENTORY.md) — Refactor mapping and deletion candidates

## AI Highlights

### AI Algorithms
- **RAG**: Self-RAG, Adaptive RAG, CRAG, Graph RAG (see `backend/app/engine/rag/`)
- **RL**: Thompson Sampling, GRPO, Hybrid Reward Model V2, Contextual Bandit (see `backend/app/ml/rl/`)
- **Agent**: LangGraph workflow (Trend → Director → Writer → Critic → Refinement)
- **Multimodal Agent Runtime**: Script → Storyboard → Media → Assembly → Quality Gate → Approval → Publish, with checkpoint/resume and failure recovery

### AI Application Development
- Structured output (Pydantic schemas)
- tiktoken-based token budgeting
- Prompt template versioning (PostgreSQL-backed)
- Cost-aware model routing
- Provider-neutral media/tool interfaces for multimodal production

### AI System Design
- Health endpoints: `/health/live`, `/health/ready`
- Prometheus `/metrics`
- ProductionMonitor, AlertNotifier (Slack/PagerDuty)
- Startup fault injection, SLO gates
- Recoverable long-running jobs with per-stage checkpoints and bounded parallel media generation

### AI Product
- End-to-end: 选题 → 生成 → 评估 → 发布 → 回流
- Multimodal production: brief → script → storyboard → media → assembly → review → publish
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
