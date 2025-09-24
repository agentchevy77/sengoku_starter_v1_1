# Nightly CI Dependency Smoke Test

This job ensures every optional Sengoku bundle remains installable and that
our dependency baselines stay in sync with `pyproject.toml`.

## Workflow Outline

1. Check out the repository and set up a fresh virtual environment.
2. Execute `scripts/nightly_dependency_smoke.sh`.
3. Persist the resulting logs/artifacts (optional) for observability.

## GitHub Actions Example

```yaml
name: nightly-smoke

on:
  schedule:
    - cron: "0 6 * * *"  # 06:00 UTC daily

jobs:
  dependency-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies, run guard, verify runtime
        run: |
          python -m venv .venv
          source .venv/bin/activate
          scripts/nightly_dependency_smoke.sh
          scripts/verify_runtime_speedups.py

# NOTE: Interactive Brokers does not publish ``ibapi`` on PyPI. The smoke script
# emits a warning when the ``ibkr`` extra cannot be installed. Provide an
# internal wheel mirror or pre-install ``ibapi`` on the runner to silence the
# warning.
```

## Jenkins Example

```groovy
pipeline {
  agent any
  triggers {
    cron('H 6 * * *')
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }
    stage('Smoke dependencies') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          scripts/nightly_dependency_smoke.sh
          scripts/verify_runtime_speedups.py
        '''
      }
    }
  }
}
```

Both pipelines rely on the script to upgrade `pip`, install every optional
extra, run `pip check`, and finally execute the dependency guard in strict mode.
