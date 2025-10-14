# Git & Documentation Workflow

This repo treats Git history as a first-class documentation asset while layering formal docs on top. Please follow the workflow below so change rationale, API expectations, and user guidance stay in sync with the codebase.

## Commit Hygiene
- Use Conventional Commit prefixes (`feat|fix|chore|refactor|docs|test|perf|build`). Keep the subject line under 72 characters and describe the behavior change, not the file list.
- Describe *why* the change is needed in the body when it is not obvious. Link related workorders or issues.
- Group related changes in focused commits. Avoid mixing functional work with formatting or generated artifacts.

## Documentation Expectations
- Update Markdown or other docs whenever a change affects runtime behavior, CLI surface area, APIs, or operational runbooks.
- When adding new features, include a short usage snippet and list any new config flags, environment variables, or outputs.
- For bug fixes, note the remediation in the relevant doc (`docs/`, `README.md`, or module-level docstrings) so future engineers understand root cause and guardrails.

## Pull Request Checklist
Before opening a PR:
1. Ensure the commit history tells the story—no “WIP” or “tmp” commits on the branch.
2. Re-read the docs you touched (or should have touched). Confirm they still reflect current behavior.
3. Run `pytest -o addopts=''` and the golden ASCII snapshot test to keep pipelines trustworthy.
4. If you captured diagnostics (profiling `.run` files, logs, etc.), delete them or store them outside the repo—the `.gitignore` covers most cases now.

## Future Enhancements
- When we stand up a richer doc site (Sphinx / MkDocs), the same expectations will feed an automated changelog and API reference. Until then, disciplined commits + Markdown are our source of truth.

Keeping the Git log meaningful and the docs refreshed is part of “definition of done” for every workorder.
