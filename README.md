# Sengoku Decision Cockpit — Starter (v1.1, memory-safe)

This starter gives you a clean, leak-safe Python backbone plus tests and workorders for your AI team.

Quick start:

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .[dev]
pre-commit install
pytest -q
python -m optipanel.app      # demo scheduler (Ctrl+C to stop)
```
