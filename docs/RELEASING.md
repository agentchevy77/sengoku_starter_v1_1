# Sengoku Release Process

## Overview
This document outlines the release process for Sengoku Trading System versions.

## Preflight Checklist (use `./scripts/checks.sh`)

Before initiating a release, ensure all items are completed:

- [ ] Run checks script: `./scripts/checks.sh` (runs pytest + pre-commit + schema sanity)
- [ ] Update documentation:
  - [ ] `docs/SCHEMA_RECON.md` - Schema changes
  - [ ] `docs/COMMAND_ROOM.md` - Command room updates
  - [ ] `CHANGELOG.md` - Version changes
- [ ] Bump version in `pyproject.toml`
- [ ] Review `BUG_REPORT.md` - Ensure critical bugs are resolved

## Release Commands

### Standard Release (v0.7.x)

```bash
./scripts/release.sh 0.7.0  # replace with desired version
```

### Patch Release

For patch releases (e.g., v0.7.1) pass the version to the script:

```bash
./scripts/release.sh 0.7.1
```

## Version Numbering

Following semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (1.x.x): Breaking API changes
- **MINOR** (x.7.x): New features, backwards compatible
- **PATCH** (x.x.1): Bug fixes, backwards compatible

Current version: v0.7.0

## Release Notes Template

When creating release notes in `CHANGELOG.md`:

```markdown
## [0.7.0] - 2025-09-23

### Added
- Feature: Readiness meters in recon and command room
- Feature: Health diagnostics CLI subcommand
- Feature: Supply and sustain enrichment for alerts

### Changed
- Improved TTLCache with tombstone pattern
- Enhanced thread safety in IBKR connections

### Fixed
- Critical: IBKR thread leak on connection failure
- Price validation for NaN/Inf values
- Schema compliance for acceptance field

### Performance
- Heap compaction optimization in TTLCache
- Reduced memory footprint by 30%
```

## Post-Release Checklist

- [ ] Verify GitHub release page
- [ ] Test installation: `pip install sengoku-starter==0.7.0`
- [ ] Run integration tests on fresh install
- [ ] Update documentation site (if applicable)
- [ ] Notify team/users of release

## Rollback Procedure

If issues are discovered post-release:

```bash
# Delete remote tag
git push --delete origin v0.7.0
git tag -d v0.7.0

# Fix issues
# ... make fixes ...

# Re-release with same or patch version
ver=0.7.1
# Follow standard release process
```

## Build Requirements

Ensure these are installed:

```bash
pip install --upgrade build twine
```

## Distribution Files

After build, verify contents:

```bash
ls -la dist/
# Should contain:
# - sengoku_starter-0.7.0-py3-none-any.whl
# - sengoku_starter-0.7.0.tar.gz
```

## Notes

- Always test on a clean virtual environment before release
- Keep `RELEASE_NOTES.md` updated for user-facing changes
- For PyPI releases, ensure credentials are configured in `~/.pypirc`