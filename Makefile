# Growth Flywheel 2.5 - Makefile
# Common commands for development and deployment

.PHONY: help install install-ml test lint run run-ml docker-up docker-down docker-build clean eval-baseline eval-ab eval-rag load-test fault-inject slo-gate

help:
	@echo "Growth Flywheel 2.5 - Available commands:"
	@echo "  make install     - Install backend dependencies"
	@echo "  make install-ml  - Install backend + ML training dependencies"
	@echo "  make test        - Run backend tests"
	@echo "  make lint        - Run Ruff and Black"
	@echo "  make run         - Start backend API (uvicorn app.main:app)"
	@echo "  make run-ml      - Start ML API (port 8001)"
	@echo "  make docker-up   - Start all services via Docker Compose"
	@echo "  make docker-down - Stop Docker Compose services"
	@echo "  make docker-build - Build Docker images"
	@echo "  make eval-baseline - Phase 2: Run baseline evaluation"
	@echo "  make eval-ab      - Phase 2: Run A/B comparison (baseline vs current)"
	@echo "  make eval-rag     - Phase 2: Run RAG benchmark"
	@echo "  make load-test    - Run HTTP load test gate"
	@echo "  make fault-inject - Run startup fault injection checks"
	@echo "  make slo-gate     - Run readiness + load SLO gate"
	@echo "  make clean       - Remove cache and build artifacts"

install:
	cd backend && pip install -r requirements.txt

install-ml: install
	cd backend && pip install -r requirements_ml.txt 2>/dev/null || true

test:
	cd backend && pytest tests/ -v --ignore=tests/test_e2e.py --ignore=tests/test_agent_workflow_e2e.py --ignore=tests/test_real_llm_connection.py -x --tb=short -q

lint:
	cd backend && ruff check app/ && black --check app/

run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-ml:
	cd backend && python start_ml_api.py 2>/dev/null || uvicorn app.main_ml:app --reload --host 0.0.0.0 --port 8001

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

eval-baseline:
	cd backend && PYTHONPATH=. python ../scripts/eval_baseline.py --topics-file ../scripts/eval_topics.json --output ../results/baseline.json

eval-ab:
	cd backend && PYTHONPATH=. python ../scripts/eval_generation_ab.py --output ../results/eval_ab.json

eval-rag:
	cd backend && PYTHONPATH=. python ../scripts/run_rag_benchmark.py --output ../results/rag_benchmark.json

load-test:
	cd backend && python scripts/ops/load_test.py --base-url http://127.0.0.1:8000 --endpoint /health/live --duration-sec 20 --concurrency 8 --qps-per-worker 2 --max-p95-ms 800 --min-success-rate 0.995

fault-inject:
	cd backend && python scripts/ops/fault_injection_startup.py --startup-timeout-sec 25 --output-json results/ops_gate.json

slo-gate:
	cd backend && python scripts/ops/slo_gate.py --base-url http://127.0.0.1:8000 --endpoint /health/live --duration-sec 20 --concurrency 8 --qps-per-worker 2 --max-p95-ms 800 --min-success-rate 0.995 --output-json results/slo_gate.json

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
