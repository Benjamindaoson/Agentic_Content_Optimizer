# Production Hardening Validation Status

Last updated: 2026-09-21

This document records **executed validation evidence**. It intentionally separates
implemented code from credentialed third-party proof.

## P0 — Required CI: PASS

Latest required CI checks are green:

- Multimodal Slice Lint: PASS
- Ruff: PASS
- Black: PASS
- Multimodal Slice Tests: **38 passed**
- Docker Build: PASS
- Ops Scripts Smoke: PASS

Legacy repository-wide lint/test debt is kept in a separate scheduled/manual
`Legacy Repository Audit` workflow so it remains visible without pretending it
is part of the new multimodal slice's acceptance gate.

## P1 — Credentialed Real Media E2E: BLOCKED ON SECRETS

The live workflow is implemented and has been triggered. It fails closed before
paid-provider calls because the repository currently does not expose the
required GitHub Actions secrets:

- `RUNWAYML_API_SECRET`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`

When configured, the live path executes:

`Runway -> ElevenLabs -> FFmpeg -> final MP4 -> deterministic evaluation`.

No claim of a credentialed Runway/ElevenLabs E2E pass should be made until that
workflow completes and produces the retained artifact.

## P2 — Durable Storage / Recovery: PASS

A real MinIO server was launched in GitHub Actions from
`quay.io/minio/minio`.

Executed proof:

1. Generate a 2-second H.264/AAC MP4 with FFmpeg.
2. Persist it through `MinIOArtifactStore`.
3. Delete the node-local source.
4. Re-materialize it from MinIO.
5. Compare SHA-256 before/after.
6. Probe the recovered file and require both video and audio streams.

Result:

- `passed: true`
- durable URI: `s3://videos/live-minio-recovery/final/source.mp4`
- source SHA-256:
  `934d6e87b427b0853593bc029028d9fddfc64295b581250bc92461adec8e8da1`
- recovered SHA-256:
  `934d6e87b427b0853593bc029028d9fddfc64295b581250bc92461adec8e8da1`
- duration: `2.000000s`
- recovered artifact contains both audio and video streams.

The evidence artifact is retained by GitHub Actions for 7 days.

### P2 Multimodal Judge

The frame-sampled OpenAI multimodal judge implementation and deterministic mock
coverage pass in CI. A **credentialed model call** remains blocked until
`OPENAI_API_KEY` is configured.

## P3 — TikTok Publish + Metrics -> RL: BLOCKED ON TIKTOK OAUTH

The real adapter, status polling, metrics ingestion, Outcome persistence, and RL
bridge are implemented and covered by deterministic tests.

The live workflow requires:

- `TIKTOK_ACCESS_TOKEN` from an authorized TikTok user/app
- `video.publish` scope for Direct Post
- `video.list` scope for post/metrics lookup

The default live publish privacy is `SELF_ONLY`. The workflow deliberately
requires explicit invocation/user consent before the external publish side
effect.

For an unaudited TikTok client, Direct Post visibility restrictions may prevent
the public-post-ID/metrics leg from completing. In that case the workflow writes
a structured blocker report rather than claiming the RL loop passed.

## Acceptance State

| Phase | Status | Evidence |
| --- | --- | --- |
| P0 CI | PASS | 38 multimodal tests + lint + Docker + ops |
| P1 Real Video E2E | BLOCKED | external Runway/ElevenLabs credentials missing |
| P2 MinIO Durability/Recovery | PASS | real MinIO delete/recover + matching SHA-256 |
| P2 Live Multimodal Judge | BLOCKED | OpenAI API credential missing |
| P3 TikTok Direct Post | BLOCKED | TikTok OAuth token/scopes missing |
| P3 Metrics -> Outcome -> RL | BLOCKED | depends on successful real TikTok post/metrics |

The project should currently be described as **production-hardening complete at
the code and deterministic/infrastructure-validation layer, with credentialed
third-party E2E validation pending**.

## 2026-09-21 Consolidation Hardening

The repository consolidation patch adds deterministic coverage and guards for:

- same-job execution serialization and sibling-task cancellation/draining;
- transient-only retries and ambiguous-publish protection;
- cancelled-job approval rejection;
- script/storyboard schema enforcement, duplicate shot IDs and duration bounds;
- hard quality failures for incomplete scripts and duration mismatch;
- collision-resistant artifact paths;
- trace ownership, job-bound TikTok post IDs and idempotent RL synchronization;
- production Compose forwarding for media-provider settings.

Local validation passed **37 non-database multimodal tests**, Ruff and Black.
The PostgreSQL checkpoint integration test and container build remain delegated
to the required GitHub Actions run before merge; this section must not be read as
evidence that those pending checks passed.
