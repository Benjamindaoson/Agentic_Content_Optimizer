## 前端依赖安全风险接受记录（dev-only）

### 背景

在 `frontend/` 中已完成：

- **Next.js 升级至官方修复版本**：`next@15.5.10`
- `npm audit --omit=dev --audit-level=high` 结果：**0 vulnerabilities**

即：**生产运行时依赖无高危/严重漏洞**。

### 当前仍存在的告警

`npm audit --audit-level=high` 仍会报告高危漏洞，主要来自以下链路（均为 **开发期工具链**）：

- `eslint` / `eslint-config-next` / `@typescript-eslint/*`
- 传递依赖中的 `minimatch` ReDoS 相关告警

### 为什么无法“无破坏清零”

`eslint-config-next@15.5.10` 官方 peer 依赖仅支持 `eslint` 到 **v9**。
而 `npm audit` 给出的“一键清零”方案需要升级到 `eslint@10.x`，会导致与 `eslint-config-next` 的官方兼容范围冲突，属于**破坏性升级**，可能引入 CI/Lint 行为变化或直接不可用。

### 风险评估

- **影响面**：仅影响本地开发/CI lint 工具链
- **生产暴露**：不进入 Next 生产构建产物，不在浏览器/服务端运行时加载
- **结论**：接受该 dev-only 风险，优先保证与 Next 官方栈兼容与稳定

### 后续计划（可选）

- 等待 `eslint-config-next` 官方支持 `eslint@10` 后再统一升级清零
- 或在独立分支评估迁移到新 ESLint 版本并更新规则集

