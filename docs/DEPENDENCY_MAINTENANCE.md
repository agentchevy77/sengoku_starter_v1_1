# Dependency Maintenance Playbook

This document explains how we keep the Sengoku Decision Cockpit aligned with its
supported dependency baselines.  The process is intentionally lightweight so it
can be executed during weekly operations reviews and before every release.

## 1. Strategic Goals

- **Security** – receive critical fixes quickly by monitoring core libraries.
- **Reproducibility** – document the minimum supported versions for tooling and
  runtime dependencies.
- **Observability** – surface outdated packages before they leak into
  production, just as we do for logging and metrics.

## 2. Automated Guardrails

1. Run the dependency guard script:

   ```bash
   source .venv/bin/activate
   python -m optipanel.ops.dependency_guard --include-dev --strict
   ```

   - Exits with code `1` when anything is missing or below the recorded floor.
   - Suitable for CI, cron, or our Grafana alerting hooks.

2. Add the command to `pre-commit` (optional) or the nightly maintenance job so
   we do not rely solely on manual checks.

## 3. Manual Verification (Monthly)

1. Review `pip list --outdated` locally to look for new major releases.
2. Update `pyproject.toml` with higher floors when we officially adopt newer
   versions.  The script will immediately enforce the new baseline.
3. Validate optional extras (`pip install -e .[async]`, `pip install -e .[ui]`,
   `pip install -e .[web]`, `pip install -e .[trading]`, `pip install -e .[caching]`,
   `pip install -e .[typing]`, `pip install -e .[testing]`, `pip install -e .[profiling]`,
   `pip install -e .[docs]`, `pip install -e .[ibkr]`) to ensure new integrations
   remain compatible.
4. Update this file with any noteworthy decisions (e.g. deferring a major bump).
   See also `docs/CI_NIGHTLY.md` for the scheduled pipeline configuration.

## 4. Reporting

- The script prints a compact table.  Boards and dashboards can ingest the
  output or capture a JSON payload by adapting the helper in
  `optipanel.ops.dependency_guard`.
- Log entries are tagged with `dependency_guard` when run from scheduled jobs
  to maintain parity with our existing operational telemetry.

## 5. Troubleshooting

| Scenario | Resolution |
| --- | --- |
| Dependency marked as `missing` | Install the package into the active
virtualenv, then re-run the guard. |
| Dependency stuck on `upgrade_required` | Verify the new floor is available on
PyPI and the mirror used in CI. |
| Unexpected parsing error | Ensure every entry in `pyproject.toml` uses
`package>=version` syntax. |

This playbook complements the wider quality strategy captured in
`docs/ARCHITECTURE.md` and `docs/TROUBLESHOOTING.md`.
