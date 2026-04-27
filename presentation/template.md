---
marp: true
theme: default
paginate: true
header: 'Cesim Global Challenge — Mobile Inc.'
footer: 'Sgehle-Maillot Team · 2025-2026'
style: |
  :root {
    --color-accent: #1a56db;
    --color-warn: #e3a008;
    --color-danger: #f05252;
    --color-ok: #0e9f6e;
  }
  section {
    font-size: 1.05em;
    font-family: 'Segoe UI', Arial, sans-serif;
  }
  section.lead {
    text-align: center;
    background: #1e3a5f;
    color: white;
  }
  section.lead h1 {
    font-size: 2.2em;
    color: white;
  }
  section.lead h2 {
    color: #9ec8f5;
    font-size: 1.2em;
    font-weight: normal;
  }
  section.kpi {
    background: #f8fafc;
  }
  table {
    font-size: 0.82em;
    width: 100%;
  }
  th {
    background: #1e3a5f;
    color: white;
  }
  h1 { color: #1e3a5f; font-size: 1.6em; border-bottom: 2px solid #1a56db; padding-bottom: 0.2em; }
  h2 { color: #1a56db; font-size: 1.3em; }
  blockquote {
    border-left: 4px solid #1a56db;
    background: #eff6ff;
    padding: 0.5em 1em;
    font-style: italic;
  }
---

<!--
TEMPLATE FILE — DO NOT PRESENT DIRECTLY.
Use this frontmatter + style when generating cesim_journey.md.

Reusable slide patterns below (copy as needed into cesim_journey.md):
-->

---

<!-- PATTERN: KPI Dashboard slide -->
# Round N — Results

| Metric | Value | vs Prior | Status |
|--------|-------|----------|--------|
| Net Sales (mUSD) | | +X% | 🟢 |
| EBITDA Margin | | +X pp | 🟢 |
| Cash (mUSD) | | | 🟡 |
| Market Share | | | 🟢 |
| Share Price (USD) | | | 🔴 |

> **Verdict:** One sentence on this round's outcome.

---

<!-- PATTERN: Decision table slide -->
# Round N — Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| R&D | | |
| Production | | |
| Marketing | | |
| Finance | | |

**Bold moves:** decision 1, decision 2

---

<!-- PATTERN: Market conditions slide -->
# Round N — Market & Context

**Demand growth:** USA X% | Asia X% | Europe X%

**Strategic mode entering:** Balanced / Defensive / Expansion

**Key macro change:** [one line]

**Competitor moves:** [2-3 bullet points]

---

<!-- PATTERN: Financial trajectory Mermaid -->
# Financial Trajectory

```mermaid
xychart-beta
  title "Net Profit (mUSD) by Round"
  x-axis ["R1", "R2", "R3", "R4", "R5", "R6"]
  y-axis "Net Profit (mUSD)"
  line [0, 0, 0, 0, 0, 0]
```

---

<!-- PATTERN: Competitive quadrant -->
# Competitive Landscape

```mermaid
quadrantChart
  title Teams — Market vs Financial Position
  x-axis Low Aggressiveness --> High Aggressiveness
  y-axis Weak Financials --> Strong Financials
  quadrant-1 Leaders
  quadrant-2 Financially Strong
  quadrant-3 Cautious
  quadrant-4 Aggressive Risk-Takers
  Team A: [0.5, 0.6]
  Team B: [0.7, 0.4]
  Our Team: [0.5, 0.7]
```
