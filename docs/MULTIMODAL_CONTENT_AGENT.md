# Multimodal Content Creation Agent

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
4. **Classified transient-error retry with exponential backoff and error history**.
5. **Parallel visual generation with bounded concurrency**.
6. **Multimodal quality gate before human approval and release**.
7. **Explicit Human-in-the-loop release control**.
8. Provider protocols that can be backed by cloud APIs, local models, MCP tools, or deterministic test doubles.

The in-memory checkpoint store is intentionally for tests/local development. A production deployment should bind the same interface to PostgreSQL/Redis/object storage.

A structured LLM planner and existing-platform publishing bridge are implemented in `multimodal_content_adapters.py`. Concrete media providers live in `multimodal_media.py`: Runway task-based video generation, ElevenLabs TTS, and FFmpeg assembly with subtitles and configurable brand templates. `multimodal_persistence.py` adds PostgreSQL checkpoints; `multimodal_artifacts.py` adds MinIO/S3-compatible artifact persistence and rematerialization; `multimodal_eval.py` adds deterministic ffprobe checks plus an optional frame-sampled OpenAI multimodal judge; and `api_multimodal_production.py` exposes submit/status/approve/cancel/resume plus explicit TikTok publish/status/feedback controls. `multimodal_publishers.py` implements TikTok creator-info validation, Direct Post initialization, chunk upload, status polling, and video-metrics retrieval.

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

The evaluator combines deterministic checks and an optional model-based review layer, including:

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

Publishing is intentionally stricter than ordinary generation tools: the runtime
persists a publish-attempt marker before the external side effect. If the remote
platform may have accepted a request but the response is lost, the same job is
not published again automatically; an operator must first reconcile the platform
result. The standard Compose deployment uses one API worker until active jobs are
moved to a distributed worker/queue.

This is the core behavior required for long-running content production to be reliable rather than merely generative.

## Remaining Engineering Steps

The hardening modules above are implemented and deterministic CI coverage exists. What remains is operational validation and scale hardening:

1. **Credentialed live-provider validation** — manually run the guarded Runway + ElevenLabs E2E workflow and preserve generated artifacts/traces.
2. **Live object-storage validation** — verify MinIO/S3 persistence, rematerialization, lifecycle, and retention against a real deployment.
3. **Live TikTok validation** — configure OAuth/scopes and run an explicitly consented Direct Post through creator info -> init -> upload -> status; platform audit is required for normal public distribution.
4. **Live multimodal-judge calibration** — enable GPT-based frame judging, build a fixed regression set, and calibrate decision thresholds against human review.
5. **Production outcome validation** — ingest real TikTok post metrics, persist Outcome records, and verify the downstream RL update against production traces.
6. **Distributed execution** — replace in-process asyncio active tasks with queue/worker execution so running jobs survive API process loss and horizontal scaling.
7. **Webhook/event completion** — use platform completion callbacks where available instead of relying only on polling.

## Resume / Portfolio Positioning

For portfolio/resume use, distinguish implemented engineering from live deployment evidence. The current codebase can be described as:

> **Multimodal Content Creation Agent** — Built a long-horizon multimodal agent that turns content briefs into scripts, storyboards, generated media, voice, assembled short-form videos, quality-reviewed releases, and performance-feedback loops, with checkpointed execution, bounded concurrency, failure recovery, human approval, and multi-platform delivery.

Do not describe Runway/ElevenLabs/TikTok as production-deployed integrations until the credentialed live E2E and platform-posting runs are actually completed.
