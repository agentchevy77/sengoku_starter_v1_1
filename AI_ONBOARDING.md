# AI Onboarding — Updated Guidelines

Welcome to the Sengoku Decision Cockpit repo. These instructions replace the
legacy single–work order workflow and reflect how we operate today.

## Planning & Scope

- Coordinate with the Lead Architect before you start. A branch may cover
  multiple work orders, but document which WOs you are touching in your changelog
  entry and PR description.
- Follow each work order’s **Allowed paths**; if you need to stray, call it out
  explicitly in the PR for review.
- Capture a lightweight plan (checklist or steps) before large changes so the
  team can follow your intent.

## Coding Standards

- Python 3.12+ codebase; prefer type annotations and deterministic, pure
  functions when feasible.
- Long-running or periodic async work must go through `PeriodicTask` and be
  registered with `AsyncResourceRegistry`.
- Use `TTLCache` for caching with explicit bounds, and honour
  `BudgetMeter.backoff_active` in schedulers or loops.
- Keep comments concise and only where they add clarity.

## Tooling Workflow

1. Activate the project virtualenv (`source .venv/bin/activate`).
2. Install/upgrade developer tooling as needed (`pip install --upgrade pip
   setuptools wheel`).
3. Run formatters/linters via `pre-commit run --all-files`.
4. Execute `pytest -q` (or relevant subsets). Ensure coverage stays above the
   configured threshold; rerun after fixing issues.
5. When touching CLI or runtime behaviour, include integration tests where
   practical. Use existing fixtures and the sandbox adapter—no new live network
   calls in automated tests.

## Deliverables & Reporting

- Provide unified diffs through git commits. Commit early and often; squash
  later if needed.
- Final hand-off message should summarize:
  - Objective
  - Key changes with file references
  - Tests/commands run (and results)
  - Follow-up actions or risks
- Keep responses concise but complete—clarity over brevity.

## Housekeeping

- Update `CHANGELOG.md` under the **Unreleased** section when you add notable
  features, tests, or tooling.
- Ensure `pre-commit`, `pytest`, and coverage hooks are clean before requesting
  review.
- If you detect inconsistent state or unexpected local changes, stop and sync
  with the team before proceeding.

These practices keep the repo healthy while allowing richer, multi-scope work.
