# Multimodal Content Production & Growth Agent

> A production-oriented agent system for turning content briefs into researched, generated, reviewed, and publishable social content — with long-horizon execution, recovery, evaluation, human approval, and feedback-driven optimization.

This repository started as **Growth Flywheel**, an AI content-generation and growth-optimization system. It is now being evolved into a **Multimodal Content Production & Growth Agent** that treats content production as a stateful execution problem rather than a one-shot generation call.

## Why this project

Most content-generation demos stop at:

```text
prompt -> text
```

A production content agent has to manage a much longer loop:

```text
brief
  -> research / trend signals
  -> strategy
  -> script
  -> storyboard
  -> media generation
  -> voice
  -> assembly
  -> quality / safety evaluation
  -> human approval
  -> platform publishing
  -> performance feedback
  -> strategy optimization
```

The engineering problem is therefore not only generation quality. It is also **orchestration, durable state, tool execution, recovery, evaluation, permissions, and feedback**.

## Current architecture

```text
                         Content Brief
                              |
                              v
                    Trend / Reference Layer
                 RAG + crawlers + trend analysis
                              |
                              v
                     Agent Orchestration
          Trend -> Director -> Writer -> Critic -> Refine
                              |
                              v
                   Production Runtime
       Script -> Storyboard -> Visuals -> Voice -> Assembly
                              |
                              v
                  Quality / Safety Gate
                              |
                              v
                     Human Approval
                              |
                              v
                  Platform Adaptation
              XHS / Douyin / other adapters
                              |
                              v
                   Outcome Feedback
          engagement / ranking / RL / evaluation
```

## Agent runtime

The new multimodal production runtime lives at:

`backend/app/engine/agents/workflow/multimodal_content_workflow.py`

It provides:

- **long-horizon execution** across multiple production stages;
- **checkpoint after every completed stage**;
- **resume by job ID** without replaying completed work;
- **bounded parallel generation** for storyboard shots;
- **retry with exponential backoff** for transient provider/tool failures;
- **error history** with stage and attempt metadata;
- **quality gate** before release;
- **Human-in-the-loop approval** for publish actions;
- provider-neutral interfaces for LLMs, image/video models, TTS, assemblers, MCP tools, and publishers.

### Production flow

```text
Brief
  |
  v
Script
  |
  v
Storyboard
  |
  +-----------------------------+
  |                             |
  v                             v
Visual / Video Assets       Voice / Audio
  |                             |
  +--------------+--------------+
                 |
                 v
           Final Assembly
                 |
                 v
          Multimodal Eval
                 |
                 v
          Human Approval
                 |
                 v
             Publish
```

If a provider fails halfway through a long task, completed artifacts remain checkpointed. A resumed job continues from the latest valid state rather than starting over.

## Existing capabilities reused by the multimodal agent

### Agent orchestration

The repository already includes:

- LangGraph-based workflow orchestration;
- Trend, Director, Writer, Critic, and refinement components;
- conditional routing and iterative generation;
- task state and workflow tracing;
- multi-agent collaboration components.

Relevant code:

- `backend/app/engine/agents/workflow/`
- `backend/app/engine/agents/content/`
- `backend/app/engine/agents/planning/`

### RAG and content intelligence

The system contains retrieval and reference-content infrastructure for:

- hybrid retrieval;
- adaptive retrieval strategies;
- reference-content filtering;
- trend and viral-pattern analysis;
- content-quality signals.

Relevant code:

- `backend/app/engine/rag/`
- `backend/app/data/analyzers/`
- `backend/app/data/crawlers/`

### Video-oriented platform adaptation

The existing platform layer already supports video-oriented content structures, including:

- Douyin video-script formatting;
- content-type and video-path models;
- multi-platform adaptation;
- publishing abstractions;
- platform performance feedback.

Relevant code:

- `backend/app/mcp/platform_adapters.py`
- `backend/app/engine/growth_brain/multi_platform_engine.py`

### Multimodal cover generation

The repository includes a multimodal cover engine with:

- cover candidate generation;
- image-provider abstraction;
- CTR-oriented scoring;
- A/B testing support.

Relevant code:

- `backend/app/engine/growth_brain/multimodal_cover_engine.py`

### Post-training and optimization

The repository also contains model/strategy optimization components around:

- SFT;
- DPO;
- GRPO;
- Thompson Sampling;
- contextual bandits;
- reward and outcome feedback;
- online-learning related workflows.

Relevant code:

- `backend/app/ml/`
- `backend/scripts/ml-training/`

## What is implemented vs. next

### Implemented

- content and agent workflow foundations;
- LangGraph orchestration;
- video-script/platform adaptation;
- multimodal cover generation;
- RAG / reference-content infrastructure;
- RL / post-training components;
- publishing abstractions;
- recoverable multimodal production runtime;
- checkpoint/resume;
- retry and bounded concurrency;
- quality and approval gates;
- deterministic runtime tests.

### Next adapters

The following should only be treated as implemented after tested adapters land in the repository:

1. structured storyboard planner backed by the existing LLM layer;
2. real text/image-to-video provider adapter;
3. TTS provider adapter;
4. FFmpeg-based deterministic video assembly;
5. persistent database/object-store checkpoint implementation;
6. multimodal evaluation harness;
7. submit/status/approve/cancel/resume production-job API;
8. end-to-end feedback ingestion from published short videos.

See [Multimodal Content Agent Architecture](docs/MULTIMODAL_CONTENT_AGENT.md).

## Reliability model

The runtime treats each content job as a durable state machine.

Examples:

- a failed shot can be retried without regenerating successful shots;
- a failed assembly step reuses existing script, storyboard, visuals, and audio;
- a job can stop at human approval and resume later;
- unsafe or low-quality output can be blocked before publication;
- provider-specific failures remain isolated behind tool interfaces.

This separation keeps the **agent runtime** independent from individual model vendors.

## Testing

The new runtime has deterministic tests for:

- full production-flow completion;
- transient visual-provider retry;
- checkpoint and resume after human approval;
- quality-gate blocking before publish.

Run the focused test suite from `backend/`:

```bash
pytest tests/test_workflow/test_multimodal_content_workflow.py -q
```

The repository CI also runs lint, tests, Docker build validation, and ops smoke checks.

## Technology

Core technologies already present in the repository include:

- Python / FastAPI
- LangGraph / LangChain
- PostgreSQL / Redis
- Qdrant
- Celery
- Docker / Kubernetes manifests
- Prometheus
- OpenAI / Anthropic / Google model integrations
- Pillow / OpenCV
- RAG, post-training, RL, and evaluation components

The multimodal runtime intentionally uses **protocol-based tool boundaries**, so future video/TTS/assembly providers can be replaced without rewriting orchestration logic.

## Project direction

The intended portfolio positioning is:

> **Multimodal Content Production & Growth Agent** — a long-horizon agent system for research, script and storyboard planning, multimodal asset generation, quality-controlled assembly, human-approved publishing, and performance-feedback optimization.

The differentiator is not simply that the system can generate content. The goal is to demonstrate how an agent can **plan, call tools, preserve state, recover from failure, pass evaluation gates, obtain approval, and complete a real multimodal production workflow**.

## Documentation

- [Documentation Index](docs/INDEX.md)
- [Multimodal Content Agent Architecture](docs/MULTIMODAL_CONTENT_AGENT.md)
- [Repository Refactor Inventory](docs/REPO_REFACTOR_INVENTORY.md)
- [Technical Documentation](TECHNICAL_DOCUMENTATION.md)

## Status

Active engineering refactor. The multimodal production runtime is implemented; real video-generation, TTS, and deterministic video-assembly adapters are the next delivery slice.
