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
