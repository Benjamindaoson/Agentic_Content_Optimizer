# Live Production-Hardening Validation Trigger

This marker records an explicitly requested credentialed validation run for:

- P1: Runway -> ElevenLabs -> FFmpeg real video E2E
- P2: MinIO durable persistence/delete-and-recover + OpenAI multimodal judge
- P3: TikTok Direct Post -> status/metrics -> Outcome -> RL update

Safety/side-effect constraints for the automated run:

- TikTok defaults to `SELF_ONLY` unless `TIKTOK_LIVE_PRIVACY` is explicitly configured otherwise.
- TikTok publishing is only attempted with an authorized user OAuth token.
- Generated TikTok content is marked as AIGC.
- The live provider workflow fails closed when required credentials are absent.
- No credentials are committed to the repository.


## Retry 2

Re-run requested after splitting credential-independent P2 storage validation and independent P3 credential/scope preflight.


## Retry 3

Re-run requested after replacing the retired Docker Hub MinIO image with the current official Quay AIStor image.


## Retry 4

Re-run requested after fixing Python module resolution for live validation scripts.
