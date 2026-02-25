# Growth Flywheel 2.5 文件结构说明

## 📁 目录结构

```
D:\growth-flywheel-2.5\
├── backend/                    # 后端代码
│   ├── app/                   # 应用代码
│   ├── scripts/               # 脚本文件（已分类）
│   │   ├── ml-training/      # ML 训练相关脚本
│   │   ├── data-collection/  # 数据收集脚本
│   │   ├── deployment/       # 部署脚本
│   │   ├── testing/          # 测试脚本
│   │   └── utils/            # 工具脚本
│   ├── data/                 # 数据文件
│   │   └── databases/        # 数据库文件
│   │       ├── growth_flywheel.db  # 主数据库（正在使用）
│   │       └── archive/      # 历史测试数据库
│   ├── docs/                 # 后端文档
│   │   └── ml-training/      # ML 训练文档
│   ├── start_ml_api.py       # ML API 启动脚本
│   └── README.md             # 后端说明
│
├── frontend/                  # 前端代码
│
├── docs/                      # 项目文档（已分类）
│   ├── ml-training/          # ML 训练相关文档
│   │   ├── ML_DEPLOYMENT_COMPLETE.md
│   │   ├── ML_SYSTEM_SUMMARY.md
│   │   ├── DATA_COLLECTION_DESIGN.md
│   │   ├── DATA_COLLECTION_QUICKSTART.md
│   │   ├── FINETUNE_*.md
│   │   ├── DPO_FINETUNE_GUIDE.md
│   │   └── 完整微调流程详解.md
│   │
│   ├── implementation-reports/  # 实施报告
│   │   ├── Phase1_完成报告.md
│   │   ├── Phase2_完成报告.md
│   │   ├── Phase3_完成报告.md
│   │   ├── Phase4_完成报告.md
│   │   ├── Phase5_完成报告.md
│   │   ├── Phase6_完成报告.md
│   │   ├── Phase7_完成报告_最终版.md
│   │   ├── Phase8_完成报告.md
│   │   ├── IMPLEMENTATION_STATUS.md
│   │   └── PHASE1_IMPLEMENTATION_SUMMARY.md
│   │
│   └── archive/              # 历史文档归档
│       ├── 改进计划_Phase7.md
│       ├── 改进计划执行指南.md
│       ├── 系统完成度检查报告.md
│       ├── 总体进度报告.md
│       ├── 总体进度报告_最终版.md
│       ├── 项目总览.md
│       ├── 项目整理完成报告.md
│       └── 真实功能实现清单.md
│
├── data/                      # 数据目录
├── models/                    # 模型目录
├── results/                   # 结果目录
├── rednote_data/             # 小红书数据
├── monitoring/               # 监控配置
├── venv/                     # Python 虚拟环境
│
├── .env                      # 环境变量
├── .env.example              # 环境变量示例
├── docker-compose.yml        # Docker 配置
├── docker-compose.db.yml     # 数据库 Docker 配置
└── README.md                 # 项目说明

```

## 📝 主要文档说明

### ML 训练系统文档
- **ML_DEPLOYMENT_COMPLETE.md** - ML 系统部署完成报告（最新）
- **ML_SYSTEM_SUMMARY.md** - ML 系统总结
- **DATA_COLLECTION_QUICKSTART.md** - 数据收集快速开始
- **FINETUNE_QUICKSTART.md** - 微调快速开始

### 后端 ML 文档
- **backend/docs/ml-training/ML_TRAINING_GUIDE.md** - ML 训练完整指南
- **backend/docs/ml-training/ML_QUICKSTART.md** - ML 快速开始
- **backend/docs/ml-training/ML_INTEGRATION_COMPLETE.md** - ML 集成完成报告

### 实施报告
- **Phase1-8_完成报告.md** - 各阶段实施报告
- **IMPLEMENTATION_STATUS.md** - 当前实施状态

## 🗂️ 脚本分类

### ML 训练脚本 (backend/scripts/ml-training/)
- `auto_train.py` - 自动训练流程
- `train_sft.py` - SFT 训练
- `train_dpo.py` - DPO 训练
- `create_ml_tables_sqlite.py` - 创建 ML 数据库表
- `test_ml_system_sqlite.py` - 测试 ML 系统
- `test_ml_feedback_api.py` - 测试反馈 API
- `test_content_generation_logging.py` - 测试内容生成日志

### 数据收集脚本 (backend/scripts/data-collection/)
- `download_*.py` - 各种数据下载脚本
- `build_knowledge_base.py` - 构建知识库

### 部署脚本 (backend/scripts/deployment/)
- `deploy_vllm.py` - 部署 vLLM
- `deploy_dots_llm.py` - 部署 Dots LLM

### 测试脚本 (backend/scripts/testing/)
- `test_*.py` - 各种测试脚本
- `demo_*.py` - 演示脚本

### 工具脚本 (backend/scripts/utils/)
- `init_*.py` - 初始化脚本
- 其他工具脚本

## 🗄️ 数据库文件

### 主数据库
- **backend/growth_flywheel.db** - 主数据库（正在使用，包含 ML 训练数据）

### 归档数据库 (backend/data/databases/archive/)
- `demo_mvp_*.db` - 历史测试数据库
- `mvp_demo_*.db` - MVP 演示数据库
- `e2e_test_*.db` - 端到端测试数据库

## 🚀 快速开始

### 启动 ML API 服务
```bash
cd backend
python start_ml_api.py
```

### 查看 API 文档
- http://localhost:8001/docs

### 测试系统
```bash
cd backend
python scripts/testing/test_ml_feedback_api.py
```

## 📊 当前状态

- ✅ ML 训练系统已部署
- ✅ 数据收集 API 已集成
- ✅ 内容生成流程已集成日志记录
- ⏳ 等待收集真实用户数据

## 🔗 相关链接

- [ML 部署完成报告](docs/ml-training/ML_DEPLOYMENT_COMPLETE.md)
- [ML 系统总结](docs/ml-training/ML_SYSTEM_SUMMARY.md)
- [后端 README](backend/README.md)
