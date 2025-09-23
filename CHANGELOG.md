# Changelog

## [0.7.0] - 2025-09-23

### Added
- Feature: Sustainment dials (`sustainability`, `fakeout_risk`) in recon and Command Room
- Feature: Supply narratives in Command Room panel and recon CLI/JSON outputs
- Feature: Optional supply enrichment for alerts/notify pipelines
- Feature: Health diagnostics CLI subcommand for system monitoring
- Feature: Readiness meters with attack/defense scoring
- Recon ↔ Command Room parity for READY meters, microchips (M15/H1/D1), and bundle normalization

### Changed
- Improved TTLCache implementation with tombstone pattern for proper entry invalidation
- Enhanced thread safety with locks for concurrent access
- Configurable heap compaction with environmental overrides
- Better metrics instrumentation throughout the codebase

### Fixed
- **Critical**: IBKR thread leak on connection failure - daemon threads now properly cleaned up
- Price validation now handles NaN/Inf values correctly
- Fixed race condition in TTLCache entry invalidation
- Corrected type hints and MyPy errors across multiple modules
- Fixed import sorting and formatting issues

### Performance
- Optimized heap compaction in TTLCache reducing memory overhead
- IBKR live path validated with TTL/LRU caching for improved response times
- Reduced unnecessary heap operations with prune-before-compact pattern

### Documentation
- Added comprehensive release process documentation
- Created schema validation report for API compliance
- Updated bug report with prioritized findings
