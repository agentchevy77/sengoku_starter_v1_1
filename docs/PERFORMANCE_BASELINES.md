# Performance Baselines

This log tracks the most recent latency captures so we can compare the legacy
CLI against the Textual/FastAPI prototype once it lands. Run the captures from a
clean virtual environment so results remain comparable.

```bash
source .venv/bin/activate
scripts/capture_latency_baseline.py --repeats 5 --output reports/latency-baseline.json
scripts/capture_latency_baseline.py --repeats 5 --output reports/latency-prototype.json
```

## Latest Measurements

| Command | Baseline avg (ms) | Prototype avg (ms) |
| --- | ---: | ---: |
| `sengoku recon --help` | 93.99 | 84.97 |
| `sengoku notify --help` | 86.51 | 84.00 |

- Baseline captured with the legacy ASCII CLI.
- Prototype capture taken after integrating Textual/FastAPI scaffolding.
- Variance is expected; rerun after major UI adjustments and archive the JSON
  files under `reports/` for historical analysis.

## Monitoring the Runtime Stack

Nightly CI invokes:

```bash
scripts/nightly_dependency_smoke.sh
scripts/verify_runtime_speedups.py
```

If any high-performance dependency (orjson, uvloop, aiofiles) is missing, the
job fails and surfaces the regression immediately.

For ad-hoc verification:

```bash
source .venv/bin/activate
scripts/verify_runtime_speedups.py
```

The script prints a concise report with the expected `✅ Orjson active: True`
marker so every session can confirm the fast-path runtime configuration.
