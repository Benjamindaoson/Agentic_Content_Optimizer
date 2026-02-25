# Ops Gates

用于上线前的三类门禁：

1. `load_test.py`：接口压测 + 延迟/成功率阈值门禁  
2. `fault_injection_startup.py`：启动链路故障注入（Redis / Postgres 不可用）  
3. `slo_gate.py`：先检查 `/health/ready`，再执行压测门禁

## 快速使用

```bash
cd backend
python scripts/ops/load_test.py --base-url http://127.0.0.1:8000 --endpoint /health/live
python scripts/ops/fault_injection_startup.py --startup-timeout-sec 25
python scripts/ops/slo_gate.py --base-url http://127.0.0.1:8000
```

## Makefile 一键命令

- `make load-test`
- `make fault-inject`
- `make slo-gate`

## 报告产物

- `results/ops_gate.json`：启动故障注入结果
- `results/slo_gate.json`：SLO 门禁结果
