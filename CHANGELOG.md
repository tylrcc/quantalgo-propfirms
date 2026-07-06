# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-04

Complete rewrite into an installable, tested Python package.

### Added
- `src/quantalgo` package with single-responsibility modules: `config`, `data`,
  `strategy`, `backtest`, `montecarlo`, `execution`, `reporting`, `cli`.
- Typed, env-overridable configuration via dataclasses (`quantalgo.config`).
- Deterministic synthetic data generator so the full pipeline runs offline.
- Event-driven backtester with correct position sizing and Topstep-style risk rules
  (daily loss limit, trailing drawdown, profit target).
- Bootstrap Monte-Carlo challenge pass-rate simulator with EV and percentile outputs.
- Broker abstraction with an in-memory `PaperBroker` and an async `TradovateBroker`.
- `quantalgo` CLI (`backtest`, `montecarlo`, `info`) with banner and text reports.
- Pytest test-suite, GitHub Actions CI (Python 3.10-3.12), MIT license, packaging
  (`pyproject.toml`), `Makefile`, and `.env.example`.

### Fixed
- Backtester crashes (`.idx.get_loc`, calling `.cummax()` on a NumPy array, chained
  boolean indexing) that prevented the original from running.
- Monte-Carlo array-size mismatch and invalid probability vector.
- `main.py` referencing an unimported `API_CONFIG` and an undefined `df`.
- `MONTEN_CARLO` config typo.

### Changed
- Vectorised, O(n) per-session signal logic replacing the original O(n²) row loops.
