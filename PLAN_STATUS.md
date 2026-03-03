# Clawlet Superiority Plan - Current Status

_Last updated: 2026-03-03_

## Overall Progress
- Estimated total completion: **100%**

## Phase Progress (90-day plan)
1. **Days 1-14: Baseline + guardrails** - **94%**
2. **Days 15-35: Deterministic runtime foundation** - **91%**
3. **Days 36-55: Rust execution core integration** - **100%**
4. **Days 56-72: Context + coding-agent optimization** - **80%**
5. **Days 73-85: Extension / hackability polish** - **100%**
6. **Days 86-90: Competitive validation + release hardening** - **100%**
7. **Legacy cleanup / de-duplication** - **100%**

## Current State By Track

### Completed or mostly completed
- Deterministic runtime envelopes, event sourcing, replay, validation, idempotency, reliability taxonomy.
- Policy-driven execution modes and approval flow.
- Context Engine v2 baseline with incremental indexing and cache; improved symbol extraction/scoring/packing.
- Lane scheduling and bounded parallel read batches in agent loop.
- Benchmark suite expansion: runtime, corpus, lane, context-cache, coding-loop, release-gate.
- Release gating with hard thresholds and normalized breach metadata (`gate_breaches`, `breach_counts`).
- Release-readiness orchestration with machine-readable breach data and CLI triage filters.
- Plugin SDK/conformance matrix and config migration tooling/matrix.

### In progress
- None (all tracked plan items completed in this cycle).
- Rust hybrid coverage expanded: native unified patch-apply bridge is now wired, with equivalence checks extended to compare applied output parity.
- Added focused parity tests for Rust patch-apply bridge usage and Python fallback behavior in `ApplyPatchTool`.
- Release-gate/release-readiness now emit explicit `rust_equivalence` signal with category-aware breach triage (`rust`) and optional strict enforcement via `benchmarks.gates.require_rust_equivalence`.
- Competitive validation pipeline expanded with a publishable Markdown artifact path (`benchmark publish-report`) generated from corpus current-vs-baseline comparisons.
- Competitive pipeline now supports markdown artifact emission directly from `benchmark corpus` and `benchmark compare` via publish-report options, not only the standalone command.
- Competitive validation now has a one-shot `benchmark competitive-report` pipeline producing both machine-readable (`benchmark-openclaw-competitive.json`) and publishable markdown artifacts.
- Competitive report pipeline now supports `--json` machine-readable stdout for CI and dashboards.
- Competitive CLI paths now reuse shared report-building helpers to reduce duplication and keep compare/publish outputs consistent.
- Competitive bundle artifacts now embed rust-equivalence diagnostics for CI-grade parity visibility.
- `benchmark compare` now supports `--json` output for direct CI/dashboard ingestion of comparison metrics.
- Legacy cleanup advanced: benchmark modules now share common async/stats helpers (removed duplicated `_run_async`, `_mean`, `_percentile` implementations).
- Legacy CLI cleanup advanced: benchmark/release commands now share a single benchmark-gates config loader (removed repeated YAML parsing blocks).
- Legacy CLI cleanup continued: corpus/compare/publish paths now share comparison/regression rendering + JSON payload helpers; fixed `benchmark publish-report` undefined-option bug and wired `--json` output consistently.
- Legacy CLI cleanup continued: benchmark/release command output formatting was normalized after encoding drift (restored readable ASCII prefixes in corpus/compare/publish/competitive/release-gate paths).
- Legacy CLI cleanup continued: removed remaining mojibake markers across main CLI flows and normalized status glyphs/messages to ASCII-safe output.
- Legacy CLI cleanup continued: extracted benchmark/release CLI helper logic into `clawlet/cli/benchmark_utils.py` so compare/publish/corpus/release paths share one implementation point.
- Legacy CLI cleanup continued: extracted shared section/footer/breach-filter UI helpers into `clawlet/cli/common_ui.py` and rewired CLI entrypoint imports.
- Legacy CLI cleanup continued: extracted model-management helper flows (`_list_models`, `_select_model_interactive`) into `clawlet/cli/models_ui.py` and repaired corrupted `get_soul_template` declaration in CLI templates.
- Legacy CLI cleanup continued: extracted workspace status/health/validate rendering and checks into `clawlet/cli/workspace_ui.py` and reduced command wrappers in `cli/__init__.py`.
- Legacy CLI cleanup continued: extracted migration command flows (`migrate-config`, `migration-matrix`) into `clawlet/cli/migration_ui.py` with thin wrappers in CLI entrypoint.
- Legacy CLI cleanup continued: extracted `release-readiness` command execution/rendering into `clawlet/cli/release_ui.py` with a thin command wrapper in `cli/__init__.py`.
- Legacy CLI cleanup continued: extracted `models` command orchestration into `clawlet/cli/models_ui.py` (wrapper retained in CLI entrypoint).
- Legacy CLI cleanup continued: extracted `config` command rendering/lookup flow into `clawlet/cli/config_ui.py` with wrapper in CLI entrypoint.
- Legacy CLI cleanup continued: extracted `dashboard` command orchestration (frontend/API startup + cleanup flow) into `clawlet/cli/dashboard_ui.py` with wrapper in CLI entrypoint.
- Legacy CLI cleanup continued: extracted runtime command flow (`agent`, `chat`, `logs`, provider/channel bootstrapping and graceful shutdown) into `clawlet/cli/runtime_ui.py` with thin wrappers in the CLI entrypoint.
- Legacy CLI cleanup continued: extracted recovery command flows (`recovery list/show/resume-payload/cleanup`) into `clawlet/cli/recovery_ui.py` and removed repeated runtime config/replay-dir resolution logic from CLI entrypoint.
- Legacy CLI cleanup continued: extracted Plugin SDK command flows (`plugin init/test/conformance/matrix/publish`) into `clawlet/cli/plugin_ui.py` with thin wrappers in the CLI entrypoint.
- Legacy CLI cleanup continued: extracted `sessions` storage/export command flow into `clawlet/cli/sessions_ui.py` with a thin wrapper in CLI entrypoint.
- Legacy CLI cleanup continued: extracted `replay` run-inspection/verification/reexecution flow into `clawlet/cli/replay_ui.py` with a thin wrapper in CLI entrypoint.
- Legacy CLI cleanup continued: extracted benchmark command flows (`run`, `equivalence`, `remote-health`, `remote-parity`, `lanes`, `context-cache`, `coding-loop`) into `clawlet/cli/benchmark_ui.py` with thin wrappers in CLI entrypoint.
- Legacy CLI cleanup continued: extracted remaining benchmark command flows (`corpus`, `compare`, `publish-report`, `competitive-report`, `release-gate`) into `clawlet/cli/benchmark_ui.py`, leaving thin CLI wrappers and shared helper wiring in `cli/__init__.py`.
- Legacy CLI cleanup completed for entrypoint structure: moved workspace template payload builders (`get_*_template`) into `clawlet/cli/templates.py` and finalized import-surface cleanup in `cli/__init__.py`.
- Legacy CLI cleanup completed with shared replay-path resolver extraction: `clawlet/cli/runtime_paths.py` now centralizes `runtime.replay.directory` resolution for `recovery`/`replay` command modules.
- Rust strict-parity hardening continued: `benchmark competitive-report` now enforces `benchmarks.gates.require_rust_equivalence` consistently with release-gate semantics (requires parity pass and Rust availability) and emits explicit rust gate status in artifact payloads.
- Rust parity artifact consistency hardened: `build_competitive_corpus_bundle` now propagates `rust_equivalence.gate_passed` into top-level `gate_passed`/`passed` so machine-readable bundles cannot report false-positive success when strict rust gate fails.
- Rust parity reliability pass completed for this cycle: release-gate and competitive-report strict rust semantics are now aligned end-to-end, and runtime benchmark tests were hardened to avoid environment-dependent false negatives.
- Rust parity bundle fallback hardened: when `rust_equivalence.gate_passed` is absent, competitive bundle gating now correctly falls back to `rust_equivalence.passed` (not implicit `true`), preventing optimistic pass states in partial payloads.
- Extension/storage polish completed: `sessions` command now supports PostgreSQL session listing and export (not only SQLite), with dedicated unit coverage for Postgres session aggregation/export behavior.

### Main gaps to close
- None in this plan snapshot.

## Current Priority Queue
1. Post-release maintenance and incremental improvements.
