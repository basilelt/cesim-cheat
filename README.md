# Cesim Toolkit

Python + Claude Code toolkit for the [Cesim Global Challenge](https://www.cesim.com/) business simulation. Analyzes Excel results, generates strategic reports, and automates decision submission via Playwright.

## What it does

- Parses multi-round Excel result files and computes financial health, competitor behavior, and trend projections
- Generates markdown reports: comprehensive analysis, team deep-dive, and peer gap analysis
- Automates the full round cycle via Claude Code: download results → analyze → read decision pages → propose plan → submit

## Quick Start

**Prerequisites**: Python 3.10+, [uv](https://docs.astral.sh/uv/), Node.js

```bash
# Clone and install Python dependencies
cd cesimAnalyze
uv sync

# Install Playwright (for browser automation)
npm install
```

**Configure `.env`** by copying `.env_example`:

```bash
cp .env_example .env
# Edit .env with your Cesim URL, email, password, and team name
```

## Usage

### Automated (preferred)

Open Claude Code at the repo root and say:

```
run round N
```

Claude will download results, run analysis, read the current decision pages, propose a full decision plan, and — after your approval — submit decisions.

### Manual

Run scripts individually from the repo root using `uv run python`:

```bash
uv run python cesimAnalyze/scripts/analyze_comprehensive_v3.py --input-dir results --output-dir analysis
uv run python cesimAnalyze/scripts/analyze_team_detail.py --team "Blue" --input-dir results --output-dir analysis
uv run python cesimAnalyze/scripts/generate_gap_analysis.py --team "Blue" --input-dir results --output-dir analysis
uv run python cesimAnalyze/scripts/generate_all_team_reports.py --input-dir results --output-dir analysis
```

## Project Structure

```
cesim/
├── cesimAnalyze/           # Analysis toolkit
│   ├── scripts/            # Analysis scripts
│   ├── utils/              # Shared data layer
│   └── docs/               # Methodology and LLM prompts
├── results/                # Input: Excel files (results-ir00.xls, results-rXX.xls)
├── analysis/               # Output: generated markdown reports
├── .env                    # Credentials (not committed)
└── .env_example            # Template for .env
```

## Analysis Scripts

| Script | Description |
|---|---|
| `analyze_comprehensive_v3.py` | Multi-round analysis: financial health, anomaly detection, competitor matrix, strategy classification |
| `analyze_team_detail.py` | Single-team cross-round deep-dive |
| `generate_all_team_reports.py` | Batch wrapper — auto-detects teams and generates individual reports |
| `generate_gap_analysis.py` | Peer comparison with rankings and gap metrics |

## Documentation

- [`HOW_TO_USE.md`](HOW_TO_USE.md) — full walkthrough of the automated workflow
- [`case_company.md`](case_company.md) — simulation background and business context
- [`decision_making.md`](decision_making.md) — decision areas reference guide
- [`cesimAnalyze/docs/methodology/results_analysis_method.md`](cesimAnalyze/docs/methodology/results_analysis_method.md) — analysis methodology (v3.0)

## Dependencies

Managed via `cesimAnalyze/pyproject.toml`: `pandas`, `numpy`, `xlrd`.
