# Project Structure

This document provides an overview of the Growth Flywheel 2.5 project structure.

## 📁 Directory Layout

```
backend/
├── app/                          # Main application code
│   ├── agents/                  # Agent system
│   │   ├── content/            # Content agents (Writer, Critic, Trend)
│   │   └── workflow/           # LangGraph workflow orchestration
│   ├── analyzers/              # Content analyzers
│   ├── core/                   # Core utilities
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # Database connection
│   │   └── tracer.py          # Generation tracing system
│   ├── crawlers/               # Web crawlers
│   ├── generators/             # Content generators
│   │   ├── viral_generator.py # Viral content generator
│   │   ├── cover_suggester.py # Cover suggestion
│   │   └── pattern_library.py # Pattern library
│   ├── growth_brain/           # Growth optimization
│   │   ├── auto_account_manager.py  # Account management
│   │   ├── multimodal_cover_engine.py
│   │   └── multi_platform_engine.py
│   ├── llm/                    # LLM integration
│   │   ├── unified.py         # Unified LLM manager
│   │   ├── model_router.py    # Model routing
│   │   └── providers/         # LLM providers
│   ├── middleware/             # Middleware
│   │   └── rate_limiter.py    # Rate limiting
│   ├── models/                 # Database models
│   │   └── generation_trace.py
│   ├── monitoring/             # Monitoring system
│   ├── persona/                # Persona management
│   ├── rag/                    # RAG system
│   │   ├── advanced_rag.py    # Advanced RAG algorithms
│   │   ├── retrievers/        # Retrieval systems
│   │   │   ├── hybrid_retriever.py  # Hybrid retrieval
│   │   │   └── qdrant_retriever.py  # Vector retrieval
│   │   └── embeddings/        # Embedding service
│   ├── rl/                     # Reinforcement learning
│   │   ├── grpo_engine.py     # GRPO algorithm
│   │   ├── ppo_engine.py      # PPO algorithm
│   │   ├── thompson_sampling.py
│   │   └── hybrid_reward_model_v2.py
│   ├── api.py                  # Main API endpoints
│   ├── api_v4_rag.py          # RAG-enhanced API
│   ├── api_v4_rl.py           # RL-enhanced API
│   └── main.py                 # Application entry point
├── tests/                      # Test suite
│   ├── test_integration.py    # Integration tests
│   ├── test_rag.py            # RAG tests
│   ├── test_rl.py             # RL tests
│   └── conftest.py            # Test fixtures
├── docs/                       # Documentation
│   ├── guides/                # User guides
│   │   └── DEPLOYMENT.md      # Deployment guide
│   ├── reports/               # Progress reports
│   ├── FINAL_COMPLETION_REPORT.md
│   └── SYSTEM_COMPLETION_REPORT.md
├── alembic/                    # Database migrations
├── migrate.py                  # Migration tool
├── verify_system.py           # System verification
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── README.md                 # Project overview
├── CHANGELOG.md              # Version history
├── CONTRIBUTING.md           # Contribution guide
└── LICENSE                   # MIT License
```

## 🎯 Key Components

### 1. API Layer (`app/api.py`)
Main API endpoints for content generation, pattern search, and monitoring.

**Key Endpoints**:
- `/api/generate/content` - Content generation
- `/api/patterns/search` - Semantic search
- `/api/patterns/trending` - Trending patterns
- `/api/monitoring/metrics` - System metrics

### 2. RAG System (`app/rag/`)
State-of-the-art retrieval-augmented generation system.

**Components**:
- `hybrid_retriever.py` - Vector + BM25 hybrid search
- `advanced_rag.py` - Self-RAG, Adaptive RAG, CRAG
- `qdrant_retriever.py` - Vector database integration

### 3. LLM Integration (`app/llm/`)
Unified interface for multiple LLM providers.

**Providers**:
- Claude (Anthropic)
- OpenAI (GPT-4.5, o1)
- DeepSeek (V3)
- Gemini (2.0)
- Dots LLM (Xiaohongshu)

### 4. Agent System (`app/agents/`)
Multi-agent content generation workflow.

**Agents**:
- `Writer Agent` - Content generation
- `Critic Agent` - Quality evaluation
- `Trend Agent` - Trend analysis

### 5. Growth Brain (`app/growth_brain/`)
Intelligent growth optimization system.

**Features**:
- Smart topic discovery
- Performance monitoring
- Optimal scheduling
- Multi-platform support

### 6. RL System (`app/rl/`)
Reinforcement learning for content optimization.

**Algorithms**:
- GRPO (Group Relative Policy Optimization)
- PPO (Proximal Policy Optimization)
- Thompson Sampling
- Hybrid Reward Model V2

### 7. Monitoring (`app/core/tracer.py`)
Complete generation tracing and monitoring.

**Features**:
- Workflow tracking
- Performance analysis
- Database persistence
- Smart alerts

## 📊 Data Flow

```
User Request
    ↓
API Layer (FastAPI)
    ↓
Agent System (LangGraph)
    ↓
┌─────────┬─────────┬─────────┐
│ Writer  │ Critic  │ Trend   │
│ Agent   │ Agent   │ Agent   │
└─────────┴─────────┴─────────┘
    ↓         ↓         ↓
┌─────────┬─────────┬─────────┐
│   RAG   │   LLM   │   RL    │
│ System  │ Manager │ System  │
└─────────┴─────────┴─────────┘
    ↓         ↓         ↓
┌─────────┬─────────┬─────────┐
│ Qdrant  │ Claude  │ GRPO    │
│ Vector  │ OpenAI  │ PPO     │
└─────────┴─────────┴─────────┘
    ↓
Response + Tracing
```

## 🔧 Configuration Files

### Environment Variables (`.env`)
```env
# Core
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql://...
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Security
JWT_SECRET=your-secret-key
CORS_ORIGINS=http://localhost:3000

# LLM APIs
ANTHROPIC_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

### Requirements (`requirements.txt`)
Main dependencies:
- `fastapi` - Web framework
- `sqlalchemy` - ORM
- `qdrant-client` - Vector database
- `anthropic` - Claude API
- `openai` - OpenAI API
- `langchain` - LLM framework
- `langgraph` - Agent workflow

## 📝 Documentation Files

### User Documentation
- `README.md` - Project overview and quick start
- `docs/guides/DEPLOYMENT.md` - Deployment guide
- `CONTRIBUTING.md` - Contribution guidelines
- `CHANGELOG.md` - Version history

### Technical Documentation
- `docs/SYSTEM_COMPLETION_REPORT.md` - System evaluation
- `docs/FINAL_COMPLETION_REPORT.md` - Project summary
- `docs/reports/` - Progress reports

## 🧪 Testing Structure

```
tests/
├── conftest.py              # Test fixtures
├── test_integration.py      # Integration tests
├── test_rag.py             # RAG system tests
├── test_rl.py              # RL system tests
├── test_agents.py          # Agent tests
└── test_api.py             # API tests
```

## 🚀 Deployment Files

- `migrate.py` - Database migration tool
- `verify_system.py` - System verification
- `docker-compose.yml` - Docker deployment
- `Dockerfile` - Container image
- `.env.example` - Environment template

## 📦 Package Structure

The application follows a modular architecture:

1. **Core Layer**: Configuration, database, utilities
2. **Data Layer**: Models, database operations
3. **Service Layer**: Business logic, algorithms
4. **API Layer**: HTTP endpoints, request handling
5. **Integration Layer**: External services, LLMs

## 🔐 Security

Security-related files:
- `app/core/config.py` - Configuration validation
- `app/middleware/rate_limiter.py` - Rate limiting
- `.env.example` - Secure defaults

## 📈 Monitoring

Monitoring components:
- `app/core/tracer.py` - Generation tracing
- `app/monitoring/` - System monitoring
- `app/models/generation_trace.py` - Trace storage

---

For more details, see:
- [README.md](../README.md) - Project overview
- [DEPLOYMENT.md](guides/DEPLOYMENT.md) - Deployment guide
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guide
