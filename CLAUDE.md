# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Context Documents

@cesimAnalyze/docs/methodology/results_analysis_method.md
@cesimAnalyze/docs/prompts/decision_making_prompt.md
@cesimAnalyze/docs/prompts/mhtml_page_parsing_prompt.md
@case_company.md
@decision_making.md

## Project Overview

Python toolkit for analyzing Cesim business simulation results and generating strategic decision guidance. Processes Excel result files across multiple rounds and produces markdown analysis reports.

## Running Scripts

```bash
# Comprehensive analysis (primary entry point)
python scripts/analyze_comprehensive_v3.py --input-dir ../results --output-dir ../analysis

# Generate detailed reports for all teams
python scripts/generate_all_team_reports.py --input-dir ../results --output-dir ../analysis

# Gap analysis for a specific team
python scripts/generate_gap_analysis.py --target-team "Blue" --input-dir ../results --output-dir ../analysis

# Single team deep-dive
python scripts/analyze_team_detail.py --team-name "Blue" --input-dir ../results --output-dir ../analysis
```

No formal test suite exists. No `requirements.txt` — dependencies are `pandas` and `numpy`.

## Architecture

- **`scripts/`** — Standalone analysis scripts, each with CLI via `argparse`
  - `analyze_comprehensive_v3.py` (1,700 lines) — Main multi-round analysis aligned with Methodology v3.0. Covers financial health, anomaly detection, competitive matrix, strategy classification, and trend projections.
  - `analyze_team_detail.py` — Single-team cross-round comparison
  - `generate_all_team_reports.py` — Batch wrapper that auto-detects teams and generates individual reports
  - `generate_gap_analysis.py` — Peer comparison with ranking and gap metrics
- **`utils/utils_data_analysis.py`** — Shared data layer: Excel reading, metric lookup (priority-based with keyword matching), structure validation, diagnostics
- **`docs/methodology/`** — Analysis methodology (6-stage framework, thresholds, deliverables)
- **`docs/prompts/`** — LLM prompts for decision-making and MHTML page parsing

## Data Format

Input: Excel files in `../results/` named `results-ir00.xls` (initial round), `results-prXX.xls` or `results-rXX.xls` (production rounds). Sheet "Results" with team names in row 4, metrics in rows 5+.

Output: Markdown reports in `../analysis/`.

## Key Conventions

- **Metrics**: All metric names and output are in English. The metric lookup system (`find_metric`, `get_metric_value`) uses keyword-based fuzzy matching with priority for global aggregates over regional breakdowns.
- **Team name mapping**: Team names map to color codes (e.g., `'Blue'`) via `TEAM_NAME_MAPPING` in `analyze_comprehensive_v3.py`.
- **Financial thresholds**: Configured as constants at the top of `analyze_comprehensive_v3.py` (cash reserves, debt ratios, EBITDA margins) — these follow Chapter 7 of the methodology doc.
- **Round detection**: Auto-scans for files matching `ir00`, `prXX`, `rXX` patterns up to 100 rounds.
