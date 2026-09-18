# Multimodal Content Production & Growth Agent

## Positioning

This project is being extended from an AI content-generation and growth-optimization system into a **recoverable multimodal content production agent** for short-form video and social content.

The target is not a one-shot "prompt -> video" demo. The system should execute a long-running production workflow with explicit state, tool boundaries, quality gates, human approval, failure recovery, and post-publication feedback.

## Target Workflow

```text
Campaign / Content Brief
        |
        v
Trend & Topic Research
        |
        v
Script Planning
        |
        v
Storyboard
        |
        +--------------------+
        |                    |
        v                    v
Visual / Video Assets     Voice / Audio
        |                    |
        +---------+----------+
                  |
                  v
            Video Assembly
                  |
                  v
      Multimodal Quality Gate
                  |
                  v
           Human Approval
                  |
                  v
        Platform Publishing
                  |
                  v
      Performance Feedback
                  |
                  v
       Strategy / RL Update
```

## What Already Exists

The repository already contains reusable foundations for this direction:

- LangGraph-based agent workflow and state management.
- Trend, Writer, Critic, Director, and refinement flows.
- RAG and retrieval infrastructure for reference content.
- Douyin/TikTok-oriented video-script adaptation.
- Multimodal cover generation and A/B testing.
- Multi-platform content adaptation and publishing abstractions.
- SFT/DPO/GRPO and online-feedback related components.
- Observability, deployment, queue, and monitoring infrastructure.

## Phase 1 Implemented

The first production-runtime slice is implemented in:

`backend/app/engine/agents/workflow/multimodal_content_workflow.py`

It adds a provider-neutral long-horizon orchestration layer with:

1. **Script -> storyboard -> media -> assembly -> evaluation -> approval -> publish** execution.
2. **Durable checkpoints after every completed stage**.
3. **Resume by job ID** without replaying completed work.
4. **Per-stage retry with exponential backoff and error history**.
5. **Parallel visual generation with bounded concurrency**.
6. **Multimodal quality gate before human approval and release**.
7. **Explicit Human-in-the-loop release control**.
8. Provider protocols that can be backed by cloud APIs, local models, MCP tools, or deterministic test doubles.

The in-memory checkpoint store is intentionally for tests/local development. A production deployment should bind the same interface to PostgreSQL/Redis/object storage.

A structured LLM planner and existing-platform publishing bridge are implemented in `backend/app/engine/agents/workflow/multimodal_content_adapters.py`. Concrete media providers are implemented in `multimodal_media.py`: Runway task-based video generation, ElevenLabs TTS, and FFmpeg assembly. `multimodal_persistence.py` adds PostgreSQL checkpoints, `multimodal_eval.py` adds the evaluation harness, and `api_multimodal_production.py` exposes submit/status/approve/cancel/resume controls.

## Provider Boundaries

The orchestration layer does not hard-code a model vendor.

### Content Planner

Responsible for:

- campaign brief -> script;
- script -> storyboard;
- shot duration, narration, and visual prompts.

### Media Toolkit

Responsible for:

- image/video generation or retrieval;
- TTS / voice generation;
- final video assembly.

Candidate implementations can wrap:

- existing image-generation infrastructure;
- external video generation providers;
- local generation services;
- FFmpeg-based assembly;
- MCP-exposed media tools.

A provider should only be documented as implemented once a tested adapter exists in the repository.

### Quality Evaluator

The evaluator should eventually combine deterministic checks and model-based review, including:

- script/storyboard consistency;
- narration/visual alignment;
- duration and aspect-ratio constraints;
- subtitle/audio completeness;
- brand and factual consistency;
- platform policy and safety checks;
- final artifact integrity.

### Approval Gate

High-impact actions such as publishing remain behind explicit human approval.

## Recovery Semantics

A production job is treated as a stateful execution, not a chain of disposable model calls.

Examples:

- If shot 7 fails, completed shots 1-6 remain checkpointed.
- If assembly fails, script/storyboard/generated assets are reused.
- If a job waits for approval, approval can be recorded and the same job resumes from the release stage.
- Tool/provider failures are recorded with stage, attempt, error type, and message.

This is the core behavior required for long-running content production to be reliable rather than merely generative.

## Remaining Engineering Steps

The next production-hardening slice is:

1. **Credentialed live-provider validation** for Runway and ElevenLabs, including quota/rate-limit failure cases.
2. **Durable media artifact storage** in MinIO/S3 instead of node-local files.
3. **Subtitle and brand-template rendering** in the FFmpeg assembly stage.
4. **Model-based multimodal judge** layered on top of deterministic artifact checks.
5. **Real platform publishing** replacing the repository's existing simulated publishing paths.
6. **Feedback ingestion** connecting real completion/engagement/conversion metrics back to strategy/RL components.
7. **Distributed job execution** so long-running tasks survive API process restarts and horizontal scaling.

## Resume / Portfolio Positioning

Once the real media adapters and end-to-end tests are complete, the project can be described as:

> **Multimodal Content Production & Growth Agent** — Built a long-horizon multimodal agent that turns content briefs into scripts, storyboards, generated media, voice, assembled short-form videos, quality-reviewed releases, and performance-feedback loops, with checkpointed execution, bounded concurrency, failure recovery, human approval, and multi-platform delivery.

Until those adapters are implemented and verified, the repository should be described more conservatively as a content-generation/growth system with a recoverable multimodal production runtime under active development.
