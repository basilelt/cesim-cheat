# Per-Round Detailed Report Prompt

## Role

You are a business simulation analyst producing a definitive post-mortem for a single Cesim round.

## Goal

Synthesize all available data for round N into a structured, exhaustive markdown report suitable for academic review and retrospective analysis.

## Input Sources (load via @-syntax)

1. `analysis/round{N}_inputs.md` — bundled dossier (Excel metrics, decisions JSON, market outlook, prior analysis MDs)
2. `analysis/comprehensive_analysis_*.md` — cross-team financial/competitive analysis
3. `analysis/team_detail_*.md` — cross-round KPI table for our team
4. `analysis/gap_analysis_*.md` — peer ranking and gap metrics

## Required Output Structure

Write to `analysis/round{N}_full_report.md`. All sections mandatory. Use English for headings, metrics, and tables.

---

### 1. Round Header

```
Round: N
Simulation date: [from data if available]
Strategic mode entering this round: Defensive / Balanced / Expansion
```

KPI snapshot table (5 columns: Metric | Our Value | Industry Avg | Rank | Delta from prior round):
- Net Sales, Net Profit, EBITDA Margin, Cash & Equivalents, Net Debt/Equity, Equity Ratio, Market Share (US/Asia/Europe), R&D Spend, Share Price, EPS.

---

### 2. Market Conditions This Round

- **Demand growth (%)** per region: USA, Asia, Europe — actual vs. pre-round forecast from market outlook
- **Technology landscape**: which tech is dominant, market coverage changes
- **Macro parameters**: tax rates by country, exchange rate assumptions, tariffs, CBAM carbon cost (if applicable)
- **Market Outlook narrative**: summarise key passages from `round{N}_market.json` prose field
- **Competitor moves detected**: price changes, new market entries, capacity additions (from comprehensive_analysis competitive section)

---

### 3. Decisions Made This Round

For each panel, produce a table: Field | Previous Round | This Round | Delta | Rationale

Panels to cover:
- **Demand** (forecasts entered, supply allocation priorities)
- **Production** (USA capacity, Asia capacity, subcontracting volumes, plant investments)
- **HR** (engineer count, salary level, training budget, utilisation target)
- **R&D** (in-house feature investments, technology licenses purchased, R&D budget total)
- **Marketing USA / Asia / Europe** (price, promotion budget, features listed, focus strategy)
- **Logistics** (supply priority per region, transport mode choices)
- **Tax** (transfer pricing multipliers USA/Asia, dividend policy)
- **Finance** (long-term debt change, share issuance/buyback, dividends declared)

If prior-round data unavailable, mark delta column as "N/A (first round)".

---

### 4. Results Diagnosis

#### 4a. Financial Health — 5-Light System

| Indicator | Value | Threshold | Status |
|-----------|-------|-----------|--------|
| Cash Reserves (mUSD) | | >50 mUSD safe | 🟢/🟡/🔴 |
| Net Debt / Equity (%) | | <60% safe | 🟢/🟡/🔴 |
| EBITDA Margin (%) | | >10% healthy | 🟢/🟡/🔴 |
| Equity Ratio (%) | | 40-60% target | 🟢/🟡/🔴 |
| R&D / Sales (%) | | 8-12% typical | 🟢/🟡/🔴 |

#### 4b. Cash Flow Attribution

Breakdown: Operating CF | Investing CF | Financing CF | Net Change. Explain what drove the largest move.

#### 4c. Regional P&L

Table: Region | Revenue | Units Sold | Avg Price | Gross Margin | Market Share. Note any region with falling share or negative margin.

#### 4d. Income Statement Summary

Revenue → Gross Profit → EBITDA → EBIT → Net Profit. Include YoY % change.

---

### 5. Competitive Position

- Ranking table: Team | Net Profit | EBITDA% | Cash | Market Share Total | Share Price | TSR cumul.
- Highlight who moved up/down significantly vs. prior round.
- Strategy classification per competitor: Aggressive / Conservative / Balanced (inferred from price levels, R&D, marketing spend).
- Detected strategic shifts: any team that changed behaviour significantly this round.

---

### 6. Forecast vs. Actual

| Decision / Assumption | What We Expected | What Happened | Variance | Root Cause |
|-----------------------|-----------------|---------------|----------|------------|

Cover: demand forecast accuracy, margin vs target, cash vs target, competitor reactions.

---

### 7. Lessons Learned & Next-Round Hooks

- **What worked**: list 2-3 decisions that had positive outcome, with evidence.
- **What failed**: list 2-3 decisions with negative outcome, root cause.
- **Surprises**: anything the market or competitors did that was unexpected.
- **Next-round priorities** (pre-fill for decision-making prompt):
  - Cash position: requires action? Y/N
  - Debt level: requires action? Y/N
  - Technology upgrade needed? Y/N + which tech
  - Market to push or retreat from?
  - Recommended strategic mode for next round

---

## Quality Rules

- Every table must have numeric values — never leave cells empty without "N/A" explanation.
- Separate confirmed facts (from Excel data) from inferences (from strategy analysis).
- Use exact metric names as they appear in the Excel / analysis reports.
- Do not invent values. If a metric is unavailable, state "not available in source data".
- Keep the report factual, dense, and useful for a 30-minute team debrief.
