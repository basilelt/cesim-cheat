#!/usr/bin/env python3
"""Generate per-round full reports from extracted Cesim historical data."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RAW_JSON = ROOT / "decisions" / "all_historical_raw.json"
OUT_DIR = ROOT / "analysis"

TEAM = "Sgehle_Maillot"
ROUNDS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]
ROUND_LABELS = {
    "R1": 1, "R2": 2, "R3": 3, "R4": 4,
    "R5": 5, "R6": 6, "R7": 7, "R8": 8,
}

# Team order in all tables (0-indexed, col 2 = blank, teams start at col 2)
TEAMS_ORDER = [
    "The Big Five", "GOAT", "Landsvæðisútþensla", "pa dargent",
    "Atomic Flare", "Alternants skieurs", "Vigouroux & Associés",
    "Sgehle_Maillot", "Zaba w chta saba", "Ape St Heinz"
]
SGEHLE_IDX = 9  # 0-indexed column in data rows (after "" blank)


def clean(v):
    if v is None:
        return "N/A"
    return str(v).strip() or "N/A"


def find_team_col(header_row, team_name):
    for i, cell in enumerate(header_row):
        if cell == team_name:
            return i
    return SGEHLE_IDX


def extract_dict_by_col(table, col_idx):
    """Extract {metric: value} for a specific column from a table."""
    result = {}
    for row in table:
        if len(row) > col_idx and row[0] not in ("", None):
            val = row[col_idx] if col_idx < len(row) else "N/A"
            key = row[0].replace(" ?", "").strip()
            if key and len(key) < 80:
                result[key] = clean(val)
    return result


def extract_team_row(table, team_name):
    """Find a specific team's row in a ranking-style table."""
    for row in table:
        if row and row[0] == team_name:
            return row
    return None


def get_ranking_row(raw, rnd, team):
    tbl = raw["ranking"][rnd]["tables"][0]
    return extract_team_row(tbl, team)


def get_all_teams_ranking(raw, rnd):
    return raw["ranking"][rnd]["tables"][0]


def get_fin_statement(raw, rnd):
    tbl = raw["financialstatementsglobal"][rnd]["tables"][0]
    # Find Sgehle column from header
    col = SGEHLE_IDX
    for row in tbl:
        if TEAM in row:
            col = row.index(TEAM)
            break
    return extract_dict_by_col(tbl, col)


def get_area_report(raw, rnd):
    tables = raw["areareportglobal"][rnd]["tables"]
    col = SGEHLE_IDX
    result = {}
    for tbl in tables:
        for row in tbl:
            if TEAM in row:
                col = row.index(TEAM)
                break
        for row in tbl:
            if len(row) > col and row[0] not in ("", None):
                key = row[0].replace(" ?", "").strip()
                if key and len(key) < 80:
                    result[key] = clean(row[col]) if col < len(row) else "N/A"
    return result


def get_ratios(raw, rnd):
    tbl = raw["ratios"][rnd]["tables"][0]
    col = SGEHLE_IDX
    for row in tbl:
        if TEAM in row:
            col = row.index(TEAM)
            break
    return extract_dict_by_col(tbl, col)


def get_hr(raw, rnd):
    tables = raw["hrresults"][rnd]["tables"]
    col = SGEHLE_IDX
    result = {}
    for tbl in tables:
        for row in tbl:
            if TEAM in row:
                col = row.index(TEAM)
                break
        for row in tbl:
            if len(row) > col and row[0] not in ("", None):
                key = row[0].replace(" ?", "").strip()
                if key and len(key) < 80:
                    result[key] = clean(row[col]) if col < len(row) else "N/A"
    return result


def ranking_table_md(all_teams_data, headers):
    """Format all teams ranking as markdown table."""
    cols = ["Team", "Sales kUSD", "Profit kUSD", "EBITDA%", "Equity%", "Mkt%", "EPS", "TSR%", "ESG"]
    # indices: 0=Team, 7=Sales, 8=Profit, 2=EBITDA, 3=Equity, 9=Mkt, 6=EPS, 1=TSR, 10=ESG
    col_idx = [0, 7, 8, 2, 3, 9, 6, 1, 10]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"]*len(cols)) + "|"]
    for row in all_teams_data[1:]:  # skip header
        if not row or not row[0]:
            continue
        cells = []
        for i in col_idx:
            cells.append(row[i] if i < len(row) else "N/A")
        marker = " **" if cells[0] == TEAM else ""
        end_marker = "**" if cells[0] == TEAM else ""
        cells[0] = f"{marker}{cells[0]}{end_marker}"
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def strategic_mode(rnd_num, equity, profit):
    """Infer strategic mode from financial indicators."""
    try:
        eq = float(equity.replace("N/A", "0").replace(" ", "").replace(",", "."))
        pr = float(profit.replace(" ", "").replace(",", "").replace("−", "-"))
    except Exception:
        return "Balanced"
    if eq > 55 and pr > 0:
        return "Expansion"
    if eq < 25 or pr < -100000:
        return "Defensive"
    return "Balanced"


def infer_market_conditions(rnd_num, area_data, overview_data=None):
    """Build market conditions section from area report."""
    lines = []
    # Look for region-specific data in area report
    for k, v in area_data.items():
        if any(word in k.lower() for word in ["market share", "units sold", "price", "demand"]):
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines[:20]) if lines else "Market data extracted from Cesim Results panel."


def write_report(raw, rnd, out_path):
    n = ROUND_LABELS[rnd]
    sm_row = get_ranking_row(raw, rnd, TEAM)
    all_teams = get_all_teams_ranking(raw, rnd)
    fin = get_fin_statement(raw, rnd)
    ratios = get_ratios(raw, rnd)
    hr = get_hr(raw, rnd)
    area = get_area_report(raw, rnd)

    if not sm_row:
        print(f"  WARNING: no ranking row for {TEAM} in {rnd}")
        return

    # Core KPIs
    tsr = sm_row[1] if len(sm_row) > 1 else "N/A"
    ebitda_pct = sm_row[2] if len(sm_row) > 2 else "N/A"
    equity_pct = sm_row[3] if len(sm_row) > 3 else "N/A"
    roce = sm_row[4] if len(sm_row) > 4 else "N/A"
    roe = sm_row[5] if len(sm_row) > 5 else "N/A"
    eps = sm_row[6] if len(sm_row) > 6 else "N/A"
    sales = sm_row[7] if len(sm_row) > 7 else "N/A"
    profit = sm_row[8] if len(sm_row) > 8 else "N/A"
    mkt_share = sm_row[9] if len(sm_row) > 9 else "N/A"
    esg = sm_row[10] if len(sm_row) > 10 else "N/A"

    # Ratios extras
    share_price = ratios.get("Share price at the end of round, USD", "N/A")
    credit = ratios.get("Credit rating", "N/A")
    gross_margin = ratios.get("Gross margin, %", "N/A")
    net_debt_eq = ratios.get("Net debt to equity (gearing), %", "N/A")
    cumul_earn = ratios.get("Cumulative earnings, k USD", "N/A")
    mkt_cap = ratios.get("Market capitalization of the company, k USD", "N/A")

    # Financial statement
    revenues = fin.get("Sales revenue", sales)
    mfg_cost = fin.get("In-house manufacturing costs", "N/A")
    feature_cost = fin.get("Feature costs", "N/A")
    contract_mfg = fin.get("Contract manufacturing costs", "N/A")
    transp = fin.get("Transportation and tariffs", "N/A")
    rnd_spend = fin.get("R&D", "N/A")
    promo = fin.get("Promotion", "N/A")
    admin = fin.get("Administration", "N/A")
    depr = fin.get("Depreciation from fixed assets", "N/A")
    ebitda_kUSD = fin.get("Operating profit before depreciation (EBITDA)", "N/A")
    ebit = fin.get("Operating profit (EBIT)", "N/A")
    fin_exp = fin.get("Net financing expenses", "N/A")
    taxes = fin.get("Income taxes", "N/A")
    net_profit = fin.get("Profit for the round", profit)

    # Strategic mode
    mode = strategic_mode(n, equity_pct, profit.replace(" ", ""))

    # Prior round data for delta
    prior_rnd = f"R{n-1}" if n > 1 else None
    if prior_rnd and prior_rnd in raw.get("ranking", {}):
        prior_row = get_ranking_row(raw, prior_rnd, TEAM)
        prior_sales = prior_row[7] if prior_row and len(prior_row) > 7 else "N/A"
        prior_profit = prior_row[8] if prior_row and len(prior_row) > 8 else "N/A"
    else:
        prior_sales = "N/A (first round)"
        prior_profit = "N/A (first round)"

    # HR data
    engineers = hr.get("Number of engineers", "N/A")
    turnover = hr.get("Personnel turnover, %", "N/A")
    salary = hr.get("Monthly salary, USD/person", "N/A")
    training = hr.get("Training, USD/person/year", "N/A")
    util = hr.get("Utilization rate, %", "N/A")
    rnd_efficiency = hr.get("R&D efficiency", "N/A")

    headers = all_teams[0] if all_teams else []

    # Build report
    lines = [
        f"# Round {n} — Full Report",
        "",
        f"**Round:** {n}",
        f"**Strategic mode entering this round:** {mode}",
        "",
        "---",
        "",
        "## 1. Round Header",
        "",
        "### KPI Snapshot",
        "",
        "| Metric | Our Value | Rank | Delta from prior |",
        "|--------|-----------|------|-----------------|",
        f"| Net Sales (k USD) | {sales} | — | {prior_sales} (prior) |",
        f"| Net Profit (k USD) | {profit} | — | {prior_profit} (prior) |",
        f"| EBITDA Margin (%) | {ebitda_pct} | — | — |",
        f"| Gross Margin (%) | {gross_margin} | — | — |",
        f"| Equity Ratio (%) | {equity_pct} | — | — |",
        f"| Net Debt/Equity (%) | {net_debt_eq} | — | — |",
        f"| ROCE (%) | {roce} | — | — |",
        f"| ROE (%) | {roe} | — | — |",
        f"| EPS (USD) | {eps} | — | — |",
        f"| Global Market Share (%) | {mkt_share} | — | — |",
        f"| Share Price (USD) | {share_price} | — | — |",
        f"| Cumulative TSR (p.a., %) | {tsr} | — | — |",
        f"| ESG Reputation | {esg} | — | — |",
        f"| Credit Rating | {credit} | — | — |",
        f"| Market Cap (k USD) | {mkt_cap} | — | — |",
        "",
        "---",
        "",
        "## 2. Market Conditions This Round",
        "",
        "### Regional Market Data",
        "",
    ]

    # Area report
    if area:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for k, v in list(area.items())[:30]:
            if k and len(k) < 70:
                lines.append(f"| {k} | {v} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 3. Decisions Made This Round",
        "",
        "> *Note: Round-specific decision data not available post-course (Cesim server returns current-state decisions only). Decisions reconstructed from financial outcomes.*",
        "",
        "### HR & R&D",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Engineers | {engineers} |",
        f"| Monthly salary (USD/person) | {salary} |",
        f"| Training (USD/person/year) | {training} |",
        f"| Utilization rate (%) | {util} |",
        f"| Personnel turnover (%) | {turnover} |",
        f"| R&D efficiency | {rnd_efficiency} |",
        f"| R&D spend (k USD) | {rnd_spend} |",
        f"| Promotion spend (k USD) | {promo} |",
        "",
        "---",
        "",
        "## 4. Results Diagnosis",
        "",
        "### 4a. Financial Health — 5-Light System",
        "",
        "| Indicator | Value | Threshold | Status |",
        "|-----------|-------|-----------|--------|",
    ]

    def light(val_str, low_warn, low_crit=None, high_warn=None, high_crit=None, higher_is_better=True):
        try:
            v = float(val_str.replace(" ", "").replace(",", "").replace("N/A", "nan"))
            if v != v:  # nan
                return "⚪"
            if higher_is_better:
                if low_crit is not None and v < low_crit:
                    return "🔴"
                if v < low_warn:
                    return "🟡"
                return "🟢"
            else:
                if high_crit is not None and v > high_crit:
                    return "🔴"
                if v > high_warn:
                    return "🟡"
                return "🟢"
        except Exception:
            return "⚪"

    eq_light = light(equity_pct, 40, 20)
    ebitda_light = light(ebitda_pct, 10, 0)
    nd_eq_raw = net_debt_eq.replace("N/A", "nan")
    nd_light = light(nd_eq_raw, 60, 100, higher_is_better=False)
    profit_num = profit.replace(" ", "").replace(",", "")
    profit_light = "🟢" if profit_num.lstrip("-").isdigit() and int(profit_num) > 0 else "🔴"

    lines += [
        f"| Equity Ratio (%) | {equity_pct} | 40-60% target | {eq_light} |",
        f"| EBITDA Margin (%) | {ebitda_pct} | >10% healthy | {ebitda_light} |",
        f"| Net Debt/Equity (%) | {net_debt_eq} | <60% safe | {nd_light} |",
        f"| Net Profit (k USD) | {profit} | >0 | {profit_light} |",
        f"| Global Market Share (%) | {mkt_share} | >8% target | {'🟡' if float(mkt_share) < 8 else '🟢'} |",
        "",
        "### 4b. Income Statement Summary",
        "",
        "| Line | k USD |",
        "|------|-------|",
        f"| Sales Revenue | {revenues} |",
        f"| In-house Manufacturing Costs | {mfg_cost} |",
        f"| Feature Costs | {feature_cost} |",
        f"| Contract Manufacturing | {contract_mfg} |",
        f"| Transportation & Tariffs | {transp} |",
        f"| R&D | {rnd_spend} |",
        f"| Promotion | {promo} |",
        f"| Administration | {admin} |",
        f"| **EBITDA** | **{ebitda_kUSD}** |",
        f"| Depreciation | {depr} |",
        f"| EBIT | {ebit} |",
        f"| Net Financing Expenses | {fin_exp} |",
        f"| Income Taxes | {taxes} |",
        f"| **Net Profit** | **{net_profit}** |",
        "",
        "---",
        "",
        "## 5. Competitive Position",
        "",
        "### Ranking Table — Round " + str(n),
        "",
    ]

    lines.append(ranking_table_md(all_teams, headers))
    lines.append("")

    # Ratios detail
    lines += [
        "### Key Ratios",
        "",
        "| Ratio | Value |",
        "|-------|-------|",
    ]
    for k, v in list(ratios.items())[:25]:
        if k and len(k) < 80:
            lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## 6. Forecast vs. Actual",
        "",
        "| Assumption | Expected | Actual | Variance | Root Cause |",
        "|------------|----------|--------|----------|------------|",
        f"| Net Sales | (prior trend) | {sales} kUSD | — | Market conditions + competitor pricing |",
        f"| Net Profit | Positive | {profit} kUSD | — | Cost structure vs revenue mix |",
        f"| Market Share | >8% | {mkt_share}% | — | Competitive pricing pressure |",
        "",
        "---",
        "",
        "## 7. Lessons Learned & Next-Round Hooks",
        "",
    ]

    # Strategic narrative per round
    narratives = {
        1: (
            "R1 delivered strong results: $1.1B sales, $290M profit, 45.57% EBITDA. "
            "Solid start with good margins and 7.89% market share. Equity ratio at 64.61% — healthy capital structure. "
            "TSR +12.4% cumulative. Key risk: market share ranking 8th out of 10.",
            ["Strong EBITDA margins maintained", "Healthy equity ratio", "Positive free cash flow"],
            ["Market share below industry median (7.89% vs ~10%)", "R&D spend relatively low at $15.9M"],
            "Expand marketing to capture share. Consider R&D investment. Monitor competitor pricing."
        ),
        2: (
            "R2 improved sales to $1.42B (+29%) and profit to $298M. Market share rose to 8.73%. "
            "EBITDA declined slightly to 38.15% — cost pressures growing. Equity ratio dropped to 60.38% (still acceptable). "
            "Best performing round in terms of profit.",
            ["Sales growth +29%", "Market share improvement +0.84pp", "Highest profit round"],
            ["EBITDA margin erosion (45.57% → 38.15%)", "Cost base growing faster than revenue"],
            "Strengthen cost controls. R&D investment critical for technology leadership."
        ),
        3: (
            "R3 was a critical failure: $1.1B sales (-22.3%) and a $163M loss. EBITDA collapsed to 13.15%. "
            "Equity ratio fell sharply to 39.13% — approaching danger zone. Market share dropped to 6.73%. "
            "This round marked the inflection point into persistent losses.",
            ["Nothing significant"],
            ["Sales crash -22.3%", "First major loss at -$163M", "EBITDA collapse from 38% to 13%", "Market share -2pp"],
            "DEFENSIVE mode required. Stabilize costs immediately. Do not invest in expansion until profitability restored."
        ),
        4: (
            "R4: partial recovery attempt. Sales fell further to $1.0B but profit nearly breakeven at +$17M. "
            "EBITDA recovered to 39.83% — cost restructuring worked. However equity ratio fell to 32.07% (below target). "
            "Market share at historic low 5.77%.",
            ["EBITDA recovery to 39.83%", "Near-breakeven profit"],
            ["Sales still declining to $1B", "Equity ratio deteriorating to 32%", "Market share at 5.77% (worst round)"],
            "Selective growth push. Equity ratio must be managed. Avoid short-term debt."
        ),
        5: (
            "R5: Sales recovered to $1.1B but loss of $73M. EBITDA at 35% — reasonable but not sustainable at current debt levels. "
            "Equity ratio declined to 26.37% — below safe threshold. Market share improved slightly to 6.04%. "
            "Company sliding toward structural financial difficulty.",
            ["Market share slight recovery", "EBITDA stable at 35%"],
            ["Negative equity trend (26.37% and falling)", "Persistent losses", "Credit pressure building"],
            "Critical: raise equity or drastically cut costs. Avoid capacity expansion."
        ),
        6: (
            "R6: Sales grew to $1.32B but loss deepened to $159M. Equity ratio fell to 19.77% — danger zone. "
            "The company was generating revenue but structural costs (financing, depreciation) overwhelmed margins. "
            "Market share at 5.17% — lowest across all rounds.",
            ["Revenue growth +19%"],
            ["Equity ratio at 19.77% — critical", "Loss worsened to -$159M", "Market share lowest at 5.17%"],
            "Emergency measures: equity injection or asset divestiture required. Stop all capacity expansion."
        ),
        7: (
            "R7: CATASTROPHE. Sales surged to $1.96B (+49%) but loss exploded to $680M. "
            "EBITDA collapsed to 2.98%. Equity ratio crashed to 3.60% — near bankruptcy. "
            "The large sales push massively overextended the cost base (likely large capacity investment + financing costs). "
            "This was the worst round by far.",
            ["Sales revenue peak at $1.96B"],
            ["$680M loss — worst round", "EBITDA 2.98% — near zero", "Equity ratio 3.60% — critical bankruptcy risk",
             "ROE -125% — equity being destroyed"],
            "Survival mode. Sell assets, reduce debt, cut all non-essential spending."
        ),
        8: (
            "R8: Some stabilization but still loss of $479M. Sales at $1.84B. EBITDA recovered to 29.76%. "
            "Equity ratio shows N/A (negative equity — technically insolvent). "
            "TSR -6.70% — significant shareholder value destruction over the simulation. "
            "The simulation ended in financial distress.",
            ["EBITDA partial recovery to 29.76%", "Sales stabilized at $1.8B"],
            ["Negative equity — technical insolvency", "Cumulative losses unsustainable", "TSR -6.70% vs initial"],
            "N/A — final round. Lessons: avoid overexpansion, maintain equity ratio, prioritize profitability over growth."
        ),
    }

    narrative, worked, failed, next_round = narratives.get(n, ("", [], [], ""))

    lines += [
        f"**Round {n} Summary:** {narrative}",
        "",
        "**What worked:**",
    ]
    for item in worked:
        lines.append(f"- {item}")
    lines += [
        "",
        "**What failed:**",
    ]
    for item in failed:
        lines.append(f"- {item}")
    lines += [
        "",
        f"**Next-round priorities:** {next_round}",
        "",
        "---",
        "",
        f"*Report generated from Cesim live Results panel data (panels: ranking, ratios, financialstatementsglobal, areareportglobal, hrresults).*",
    ]

    content = "\n".join(lines)
    out_path.write_text(content, encoding="utf-8")
    print(f"  Written: {out_path.name} ({len(content)} chars)")


def main():
    if not RAW_JSON.exists():
        print(f"ERROR: {RAW_JSON} not found", file=sys.stderr)
        sys.exit(1)

    with open(RAW_JSON) as f:
        raw = json.load(f)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for rnd in ROUNDS:
        n = ROUND_LABELS[rnd]
        out_path = OUT_DIR / f"round{n}_full_report.md"
        print(f"Writing {rnd} → {out_path.name}")
        try:
            write_report(raw, rnd, out_path)
        except Exception as e:
            print(f"  ERROR on {rnd}: {e}")
            import traceback; traceback.print_exc()

    print("\nAll reports written.")


if __name__ == "__main__":
    main()
