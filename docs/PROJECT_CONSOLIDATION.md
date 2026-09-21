# Project Consolidation Record

## Canonical project

This repository is the canonical codebase for **Multimodal Content Creation
Agent**. It upgrades the original Agentic Content Optimizer / Growth Flywheel
repository in place so the existing Git history remains traceable.

## Source boundaries

| Source | Decision |
| --- | --- |
| Agentic Content Optimizer feature branch | Merge into the canonical main branch after CI and review gates pass |
| Original Growth Flywheel main branch | Preserve as `legacy-growth-optimizer-v1`; do not present old marketing metrics as current evidence |
| `haole-mas` | Keep independent as a general multi-agent workspace; reuse only clearly applicable contracts or patterns |
| `reward-modeling-lab` and `RewardLens` | Keep independent research projects; expose integration boundaries rather than copying their implementations |
| Private multimodal research | Describe research direction only; do not publish private code or inaccessible links |

## Rules

1. One canonical repository owns the content-production runtime, provider
   adapters, media assembly, evaluation, approval and publishing interfaces.
2. Related flagship repositories are not copied into this repository merely to
   increase apparent scope.
3. Implemented code, deterministic validation, infrastructure validation and
   credentialed live proof are reported as separate evidence levels.
4. External publishing remains explicit and human-authorized.
5. The legacy branch is reference material, not proof of current product impact.

## Historical continuity

The repository rename is a project-positioning change, not a claim that all old
Growth Flywheel experiments are part of the current validated system. Current
public claims must be supported by the default branch and its retained evidence.
