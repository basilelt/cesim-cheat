# Marp Presentation Prompt

## Role

You are a business strategy presenter. Produce a Marp markdown slide deck telling the story of our Cesim simulation journey.

## Goal

Create `presentation/cesim_journey.md` — a polished ~30-slide Marp deck for class final presentation (instructor + peers audience). Tone: professional, narrative, data-backed.

## Input Sources

Load all per-round full reports:
- `analysis/round{1..N}_full_report.md` for each round that exists
- `analysis/comprehensive_analysis_*.md` (latest cross-team analysis)
- `case_company.md` (background on the simulation)

## Output File

Write to `presentation/cesim_journey.md`.

After writing, run: `npm run slides` to render HTML and PDF.

## Marp Frontmatter

Start the file with:

```yaml
---
marp: true
theme: default
paginate: true
header: 'Cesim Global Challenge — Mobile Inc.'
footer: 'Sgehle-Maillot Team · 2025-2026'
style: |
  section {
    font-size: 1.1em;
  }
  section.lead {
    text-align: center;
  }
  table {
    font-size: 0.85em;
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1em;
  }
---
```

Each slide starts with `---` separator.

## Slide Structure (~30 slides)

### Act 1 — Context (slides 1-4)

1. **Cover** — Title: "Cesim Global Challenge", subtitle: team name, members, course, academic year. Big text, centered.

2. **The Game** — What is Cesim? 3 bullet points max. One Mermaid diagram showing the value chain: R&D → Production → Marketing → Revenue → Finance.

3. **Our Starting Position** — Table: initial KPIs (cash, equity, sales, market share). 1 sentence on our initial strategy thesis.

4. **Competition** — List of teams. Table: initial snapshot of all teams (share price, cash). Highlight us.

### Act 2 — The Journey, Round by Round (3 slides per round × N rounds)

For **each round N**, produce exactly 3 slides:

**Slide A — Market & Context (Round N)**
- Left column: market conditions (demand growth %, key macro change)
- Right column: competitor moves detected
- Small callout: "Our entering strategic mode: [Defensive/Balanced/Expansion]"

**Slide B — Our Decisions (Round N)**
- Compact table: Decision Area | Key Choice | Rationale
- Highlight 2 bold decisions that defined the round

**Slide C — Results (Round N)**
- KPI dashboard: Net Sales | EBITDA% | Cash | Market Share | Share Price — this round vs prior
- 1-sentence verdict: "Round N was a [win/struggle/pivot] because..."
- Traffic light 🟢/🟡/🔴 per KPI

### Act 3 — Big Picture (slides after per-round arc)

**Financial Trajectory** — Mermaid xychart-beta (or a markdown table if data is complex):
- X: round number
- Y: Net Profit, Market Share, Share Price
- Show our line vs industry average

**Competitive Landscape Final** — Mermaid quadrant chart:
- X-axis: Market Aggressiveness (low → high)
- Y-axis: Financial Health (low → high)
- Place each team in a quadrant

**Our Strategy Arc** — Timeline slide. Show how our strategic mode evolved: Balanced → Defensive → Expansion → etc. Annotate with "why we switched".

**Wins & Losses** — Two-column slide: "What worked" (3 items with evidence) | "What we'd redo" (3 items with rationale).

**Lessons Learned** — 5 clear lessons. Format: lesson title (bold) + 1-line explanation.

**If We Did It Again** — 3 concrete strategic changes we'd make from round 1. Be specific (e.g., "Invest in Tech 2 by round 2 instead of round 4").

**Q&A / Discussion** — Simple closing slide with team name and "Thank you".

## Quality Rules

- Every data point on slides must come from the round reports — no invented numbers.
- Charts use Mermaid syntax — test that the syntax is valid before writing.
- Tables max 5 columns for readability.
- Avoid walls of text: max 5 bullet points per slide, max 1 line each.
- Slides must tell a story arc: setup → journey → reflection → lessons.
- Keep the per-round slides factual and tight; save analysis for the "big picture" section.
- After writing the file, run `npm run slides` and report the output path.
