# How to Use the Cesim Analysis Toolkit

This guide covers the end-to-end workflow for one simulation round: downloading results, running analysis, parsing decision pages, and generating a decision plan ready to submit.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (`pip install uv` or `brew install uv`)
- Directory layout (relative to this file):
  ```
  cesim/
  ├── results/          ← place downloaded Excel files here
  ├── analysis/         ← generated reports appear here
  ├── cesimAnalyze/     ← scripts, docs, pyproject.toml
  └── HOW_TO_USE.md     ← this file
  ```

## Installation

From the `cesimAnalyze/` directory:

```bash
uv venv
uv sync
```

This creates a `.venv/` and installs `pandas`, `numpy`, and `xlrd` (required for `.xls` files).

**Activate the environment** (optional — needed if calling `python` directly):
```bash
source .venv/bin/activate
```

**Or skip activation** and prefix commands with `uv run`:
```bash
uv run python scripts/analyze_comprehensive_v3.py --input-dir ../results --output-dir ../analysis
```

---

## Each Round: Step by Step

### Step 1 — Download Results Excel

After the round resolves in Cesim, download the Excel results file and place it in `results/`.

Expected filename pattern:
- `results-ir00.xls` — initial round
- `results-pr01.xls` or `results-r01.xls` — production rounds (number matches round)

The scripts auto-detect all files matching these patterns, so no renaming is needed.

---

### Step 2 — Run Comprehensive Analysis

From the `cesimAnalyze/` directory:

```bash
python scripts/analyze_comprehensive_v3.py \
  --input-dir ../results \
  --output-dir ../analysis
```

This is the primary analysis script. It produces a markdown report in `../analysis/` covering:
- Financial health diagnosis (cash, margins, leverage, equity)
- Anomaly detection across rounds
- Competitive matrix for all teams
- Strategy classification and trend projections

Wait for it to complete before moving to the next step.

---

### Step 3 — Export and Parse MHTML Decision Pages

In Cesim, navigate to each decision page (demand, production, pricing, marketing, R&D, logistics, tax, finance). Use your browser's **Save as MHTML** (or "Save as Webpage, Single File") to export each page.

Then feed each MHTML file to an LLM using the prompt in:

```
cesimAnalyze/docs/prompts/mhtml_page_parsing_prompt.md
```

The prompt instructs the LLM to:
1. Decode the MHTML content
2. Identify the page type
3. Extract all editable decision fields
4. Capture key reference values

Save the structured output — you will use it in Step 4.

---

### Step 4 — Generate the Decision Plan

Feed the following into an LLM using the prompt in `cesimAnalyze/docs/prompts/decision_making_prompt.md`:

| Input | Source |
|---|---|
| Comprehensive analysis report | `../analysis/` (from Step 2) |
| Parsed MHTML page reports | Output from Step 3 |
| Team detail report (optional) | See Optional Deep-Dives below |
| Gap analysis report (optional) | See Optional Deep-Dives below |

The prompt instructs the LLM to produce:
1. Executive summary and current status diagnosis
2. Strategic mode (defensive / balanced / expansion)
3. Complete decision table with numeric values for every field
4. Risk register
5. Pre-submit checklist

Review the decision plan for internal consistency (capacity vs. demand, spending vs. cash) before submitting.

---

### Step 5 — Submit Decisions

Enter the values from the decision plan into Cesim and submit before the round deadline.

---

## Optional Deep-Dives

Run these before Step 4 if you want richer input for the decision plan.

**Single-team cross-round comparison:**
```bash
python scripts/analyze_team_detail.py \
  --team-name "Blue" \
  --input-dir ../results \
  --output-dir ../analysis
```

**Peer comparison and gap metrics for one team:**
```bash
python scripts/generate_gap_analysis.py \
  --target-team "Blue" \
  --input-dir ../results \
  --output-dir ../analysis
```

**Batch reports for all teams:**
```bash
python scripts/generate_all_team_reports.py \
  --input-dir ../results \
  --output-dir ../analysis
```

Replace `"Blue"` with your team's color code. Available codes are defined in `TEAM_NAME_MAPPING` at the top of `analyze_comprehensive_v3.py`.

---

## Understanding the Outputs

All outputs land in `../analysis/` as markdown files.

| Report | Contents |
|---|---|
| Comprehensive analysis | Financial health, anomaly flags, competitive matrix, strategy classification, trend projections |
| Team detail | Cross-round KPI table for one team |
| Gap analysis | Ranking and gap metrics vs. peers |
| Per-team batch | One report per team (same format as team detail) |

---

## Extending the Codebase

If you are adding new scripts or metrics to `cesimAnalyze/scripts/`, consider using **spec-kit** (GitHub's Spec-Driven Development toolkit) to structure the work: specify → plan → implement. It fits naturally when extending the Python codebase.

For the analysis workflow itself (running scripts, parsing MHTML, generating decision plans), spec-kit adds no value — the methodology docs and prompts already serve that role:

| Spec-Kit concept | Already covered by |
|---|---|
| Constitution (principles) | `case_company.md` + `decision_making.md` |
| Specify (requirements) | `docs/methodology/results_analysis_method.md` |
| Plan (strategy) | `docs/prompts/decision_making_prompt.md` |
| Implement | Running the Python scripts |
