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

No setup needed. Dependencies are declared in `cesimAnalyze/pyproject.toml`. Just prefix commands with `uv run` and uv handles everything automatically:

```bash
uv run python scripts/analyze_comprehensive_v3.py --input-dir ../results --output-dir ../analysis
```

---

## LLM Provider: Claude Code

Steps 3 and 4 use **Claude Code** as the LLM. It must be started from the `cesim/` root so it picks up `CLAUDE.md`:

```bash
cd /path/to/cesim
claude
```

`CLAUDE.md` automatically loads both prompts and the methodology doc as context — no manual prompt pasting needed. Reference local files in conversation using `@` syntax:

```
@analysis/comprehensive_analysis_r01.md summarize the financial health
@mhtml/round01_demand.mhtml parse this page
```

---

## Automated Workflow

The preferred workflow for each round uses Playwright MCP to drive the browser automatically.

### Prerequisites

- **Node.js** installed (`node --version`) — required for `npx @playwright/mcp`
- **Credentials** — fill in `cesim/.env` once:
  ```
  CESIM_URL=https://...
  CESIM_EMAIL=your@email.com
  CESIM_PASSWORD=yourpassword
  CESIM_TEAM=Blue
  ```
- That's it — Playwright installs itself on first use via `npx`

### Usage

Start Claude Code from the `cesim/` root (so it picks up `.claude/settings.json`):

```bash
cd /path/to/cesim
claude
```

Then say:

```
run round 3
```

Claude will:
1. Login to Cesim using credentials from `.env`
2. Download the results Excel to `results/`
3. Run all analysis scripts
4. Navigate each decision page and extract editable fields
5. Generate a full decision plan
6. **Pause and ask for your approval** before submitting anything

Decisions are never submitted without your explicit confirmation.

### Fallback

The manual workflow (Steps 1–5 below) remains available if automation is unavailable or you prefer manual control.

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
uv run python scripts/analyze_comprehensive_v3.py \
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

Then parse each file in Claude Code (the parsing prompt is already loaded via `CLAUDE.md`):

```
@mhtml/round01_demand.mhtml parse this page
```

Replace the path with wherever you saved the file. Alternatively, paste the MHTML content directly into the chat and ask Claude to parse it.

Claude will:
1. Decode the MHTML content
2. Identify the page type
3. Extract all editable decision fields
4. Capture key reference values

Save the structured output — you will use it in Step 4.

---

### Step 4 — Generate the Decision Plan

In Claude Code (the decision-making prompt is already loaded via `CLAUDE.md`), reference the analysis reports with `@` syntax and ask for the plan:

```
@analysis/comprehensive_analysis_r01.md generate the decision plan for round 2
```

Include optional deep-dive reports for richer input:

```
@analysis/comprehensive_analysis_r01.md @analysis/team_detail_Blue_r01.md @analysis/gap_analysis_Blue_r01.md generate the decision plan for round 2
```

| Input | How to reference |
|---|---|
| Comprehensive analysis report | `@analysis/comprehensive_analysis_rXX.md` |
| Parsed MHTML page reports | Paste output from Step 3 into the conversation |
| Team detail report (optional) | `@analysis/team_detail_Blue_rXX.md` |
| Gap analysis report (optional) | `@analysis/gap_analysis_Blue_rXX.md` |

Claude will produce:
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
uv run python scripts/analyze_team_detail.py \
  --team-name "Blue" \
  --input-dir ../results \
  --output-dir ../analysis
```

**Peer comparison and gap metrics for one team:**
```bash
uv run python scripts/generate_gap_analysis.py \
  --target-team "Blue" \
  --input-dir ../results \
  --output-dir ../analysis
```

**Batch reports for all teams:**
```bash
uv run python scripts/generate_all_team_reports.py \
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
