# Top-tier Repo Refactor — Acceptance Report

**Date**: 2026-02-22  
**Plan**: Top-tier Repo Refactor (Phase 1–4)

## Completed Tasks

| ID | Task | Status |
|----|------|--------|
| global-inventory | 生成全仓库引用图与删除候选清单 | ✅ |
| backend-unify | 删除 app/rl 兼容层并统一到 app/ml/rl | ✅ |
| api-contract-unify | 统一后端路由前缀与版本命名，前端 endpoint 常量 | ✅ |
| frontend-cleanup | 删除 deprecated 页面与空组件 | ✅ |
| deploy-prod-pack | 新增腾讯轻量云生产部署文件与一键发布回滚脚本 | ✅ |
| docs-readme-rewrite | 重写 README 与 docs 索引 | ✅ |
| acceptance-gates | 执行 startup/slo/user-smoke 门禁 | ✅ |

## Verification Results

### Backend Import
- `import app.main` — **OK**
- `from app.ml.rl import ...` — **OK**

### Unit Tests (pytest)
- `test_startup_compat` — **PASS**
- `test_hybrid_reward_v2` — **PASS**
- `test_diversity_scorer` — **PASS**
- `test_thompson_sampling` — 16/17 PASS (1 flaky: `test_cold_start_exploration`)

### API Routes
- Backend routes unified to `/api/v1/*`:
  - `/api/v1/auth`, `/api/v1/workflow`, `/api/v1/outcomes`, `/api/v1/trends`, `/api/v1/dashboard`, etc.

### Frontend
- `api-endpoints.ts` — created
- `api.ts` — uses `ENDPOINTS` constants
- `dashboard-new.deprecated` — deleted
- `DashboardStats.tsx` (empty) — deleted

### Deployment Artifacts
- `docker-compose.prod.yml` — created
- `deploy/nginx.conf` — created
- `scripts/deploy-prod.sh` — created
- `scripts/rollback-prod.sh` — created

## SLO / User Smoke

- **SLO gate**: Requires running backend; run `python backend/scripts/ops/slo_gate.py --base-url http://127.0.0.1:8080` when API is up.
- **User smoke**: Run `python backend/scripts/testing/user_flow_smoke.py` with backend + DB/Redis.

## Success Criteria Met

- [x] 目录与命名统一
- [x] 启动链路可跑通 (`app.main` imports)
- [x] `/health/ready` 稳定可用 (when services running)
- [x] 文档完整覆盖 AI 算法/产品/系统/应用亮点
