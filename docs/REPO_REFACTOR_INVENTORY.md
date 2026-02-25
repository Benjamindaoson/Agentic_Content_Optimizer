# Repo Refactor Inventory

This file is the single source of truth for the aggressive cleanup and migration mapping.

## Dependency And Call-Chain Map

- Backend entry: `backend/app/main.py`
- API routers: `backend/app/api/v1/*` and `backend/app/api/auth.py`
- Workflow core: `backend/app/api/v1/api_v5_langgraph.py` -> `backend/app/engine/agents/workflow/langgraph_workflow.py`
- RL core: `backend/app/ml/rl/*`
- RAG core: `backend/app/engine/rag/*`
- Frontend API client: `frontend/lib/api.ts`
- Frontend pages/components call backend with mixed prefixes (`/v1/*`, `/api/*`, `/api/v1/*`)

## Aggressive Deletion Candidates

### Delete Now
- `backend/app/rl/` (legacy compatibility layer)
- `frontend/app/dashboard-new.deprecated/` (deprecated route)
- `frontend/components/dashboard/DashboardStats.tsx` (empty component)
- `backend/htmlcov/` (generated artifact)
- `backend/results/*.json` generated gate outputs (runtime artifacts, keep out of git)

### Delete After Import Rewrite
- `backend/start_ml_api.py` (duplicate entry once `app/main_ml.py` is canonical)

## Import Rewrite Mapping

- `from app.rl.*` -> `from app.ml.rl.*`
- `import app.rl.*` -> `import app.ml.rl.*`

## API Contract Unification Mapping

- Backend canonical prefix: `/api/v1/*`
- Legacy support aliases during migration:
  - `/v1/*` remains available for backward compatibility
  - `/api/*` legacy non-version routes are removed or redirected to `/api/v1/*`

## Frontend Contract Consolidation

- New constants file: `frontend/lib/api-endpoints.ts`
- All frontend calls should use endpoint constants + `apiClient`
- Remove hardcoded hosts/ports from pages/components

## Naming Policy

- Python files/modules: `snake_case`
- React components: `PascalCase`
- Route folders: `kebab-case`
- Docs names: `UPPER_SNAKE_CASE.md`

## High-Risk Changes

- Removing `backend/app/rl/` without rewriting all imports
- Renaming backend API files without updating router registration
- Frontend endpoint migration without preserving temporary aliases

## Acceptance Baseline

- Startup:
  - `GET /health/live` -> `200`
  - `GET /health/ready` -> `200`
- Gates:
  - `backend/scripts/ops/fault_injection_startup.py`
  - `backend/scripts/ops/load_test.py`
  - `backend/scripts/ops/slo_gate.py`
