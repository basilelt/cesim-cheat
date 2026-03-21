#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed analysis script for a single team.
Generates an in-depth report from simulation round result files.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add utils directory to import path.
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))

from utils_data_analysis import (
    read_excel_data, get_metric_value
)


def get_metric_with_priority(metrics_dict, metric_name, team):
    """Get metric value using a priority list of column aliases.
    Supports both English (Cesim Excel) and Chinese legacy key names.
    """
    metric_priorities = {
        # English keys (Cesim Excel output)
        'Sales revenue': ['Sales revenue total', 'Sales revenue'],
        'Profit for the round': ['Profit for the round'],
        'Cash and cash equivalents': ['Cash and cash equivalents'],
        'Short-term debts (unplanned)': ['Short-term debts (unplanned)', 'Short-term debts'],
        'Long-term debts': ['Long-term debts'],
        # Chinese legacy keys
        '\u9500\u552E\u989D': ['\u9500\u552E\u989D\u5408\u8BA1', '\u672C\u5730\u9500\u552E\u989D', '\u5F53\u5730\u9500\u552E\u989D', '\u9500\u552E\u989D'],
        '\u51C0\u5229\u6DA6': ['\u672C\u56DE\u5408\u5229\u6DA6', '\u7A0E\u540E\u5229\u6DA6', '\u51C0\u5229\u6DA6'],
        '\u73B0\u91D1': ['\u73B0\u91D1\u53CA\u7B49\u4EF7\u7269', '\u73B0\u91D1 31.12.', '\u73B0\u91D1 1.1.', '\u73B0\u91D1'],
        '\u77ED\u671F\u8D37\u6B3E': ['\u77ED\u671F\u8D37\u6B3E\uff08\u65E0\u8BA1\u5212\uff09', '\u77ED\u671F\u8D37\u6B3E'],
        '\u957F\u671F\u8D37\u6B3E': ['\u957F\u671F\u8D37\u6B3E'],
    }
    priority_list = metric_priorities.get(metric_name, [metric_name])
    return get_metric_value(metrics_dict, priority_list, team)


def _get(metrics_dict, primary_en, fallback_cn, team):
    """Try English key first, fall back to Chinese legacy key."""
    val = get_metric_with_priority(metrics_dict, primary_en, team)
    if val is None:
        val = get_metric_with_priority(metrics_dict, fallback_cn, team)
    return val or 0


def get_all_rounds_data(input_dir):
    """Read all available rounds from input directory."""
    input_dir = Path(input_dir)
    all_rounds_data = {}
    teams = []

    # ir00
    ir00_path = input_dir / 'results-ir00.xls'
    if ir00_path.exists():
        metrics_dict, teams = read_excel_data(str(ir00_path))
        all_rounds_data['ir00'] = metrics_dict

    # r01/pr01, r02/pr02, ...
    for i in range(1, 100):
        r_path = input_dir / f'results-r{i:02d}.xls'
        if not r_path.exists():
            r_path = input_dir / f'results-pr{i:02d}.xls'
        if r_path.exists():
            metrics_dict, teams = read_excel_data(str(r_path))
            all_rounds_data[f'pr{i:02d}'] = metrics_dict

    return all_rounds_data, teams


def analyze_team_detailed(team_name, input_dir, output_dir):
    """Generate a detailed report for one team."""

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rounds_data, teams = get_all_rounds_data(input_dir)

    if not all_rounds_data:
        print("Error: No result files found")
        return

    if team_name not in teams:
        print(f"Error: Team '{team_name}' was not found")
        print(f"Available teams: {', '.join(teams)}")
        return

    # Determine round order dynamically.
    rounds_order = []
    if 'ir00' in all_rounds_data:
        rounds_order.append('ir00')
    for i in range(1, 100):
        key = f'pr{i:02d}'
        if key in all_rounds_data:
            rounds_order.append(key)
    available_rounds = [r for r in rounds_order if r in all_rounds_data]
    latest_round = available_rounds[-1] if available_rounds else None

    # Build report.
    report = []
    report.append(f"# {team_name} Detailed Analysis Report\n")
    report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("=" * 80 + "\n")

    # Section 1: key metric comparison across rounds.
    report.append("\n## 1. Multi-Round Key Metric Comparison\n")

    report.append("### 1.1 Core Financial Metrics\n")
    report.append("| Metric | " + " | ".join([r.upper() for r in available_rounds]) + " | Change |")
    report.append("|------|" + "|".join(["------" for _ in available_rounds]) + "|------|")

    metrics_to_analyze = [
        ('Sales', 'Sales revenue', '\u9500\u552E\u989D'),
        ('Net Profit', 'Profit for the round', '\u51C0\u5229\u6DA6'),
        ('Cash', 'Cash and cash equivalents', '\u73B0\u91D1'),
        ('Total Equity', 'Total equity', '\u6743\u76CA\u5408\u8BA1'),
        ('Total Assets', 'Total assets', '\u603B\u8D44\u4EA7'),
        ('Short-Term Debt', 'Short-term debts (unplanned)', '\u77ED\u671F\u8D37\u6B3E'),
        ('Long-Term Debt', 'Long-term debts', '\u957F\u671F\u8D37\u6B3E'),
        ('Total Liabilities', 'Total liabilities', '\u8D1F\u503A\u5408\u8BA1'),
    ]

    for item in metrics_to_analyze:
        metric_display = item[0]
        en_key = item[1]
        cn_key = item[2]

        values = []
        for rnd in available_rounds:
            metrics_dict = all_rounds_data[rnd]
            val = _get(metrics_dict, en_key, cn_key, team_name)

            if val is not None and val != 0:
                values.append(f"{val/1000:.0f}k")
            elif val == 0:
                values.append("0")
            else:
                values.append("N/A")

        # Compute change between first and last round.
        if len(available_rounds) >= 2 and values[0] != "N/A" and values[-1] != "N/A":
            try:
                val0 = float(values[0].replace('$', '').replace('k', '').replace(',', ''))
                val_last = float(values[-1].replace('$', '').replace('k', '').replace(',', ''))
                if val0 != 0:
                    change = ((val_last - val0) / abs(val0)) * 100
                    change_str = f"{change:+.1f}%"
                else:
                    change_str = "N/A"
            except Exception:
                change_str = "-"
        else:
            change_str = "-"

        report.append(f"| {metric_display} | " + " | ".join(values) + f" | {change_str} |")

    # Section 2: financial health.
    report.append("\n\n## 2. Financial Health Deep Dive\n")

    if latest_round and latest_round in all_rounds_data:
        metrics_dict = all_rounds_data[latest_round]

        # Cash reserve
        cash = _get(metrics_dict, 'Cash and cash equivalents', '\u73B0\u91D1', team_name)
        report.append("### 2.1 Cash Reserve\n")
        report.append(f"- **Current cash**: ${cash/1000:.0f}k\n")

        if cash < 100000:
            status = "High risk (< $100k)"
        elif cash < 300000:
            status = "Warning (< $300k)"
        else:
            status = "Safe (>= $300k)"
        report.append(f"- **Status**: {status}\n")

        # Net debt / equity
        equity = get_metric_value(metrics_dict, ['Total equity', '\u6743\u76CA\u5408\u8BA1'], team_name) or 0
        short_debt = get_metric_value(metrics_dict, ['Short-term debts (unplanned)', 'Short-term debts', '\u77ED\u671F\u8D37\u6B3E'], team_name) or 0
        long_debt = get_metric_value(metrics_dict, ['Long-term debts', '\u957F\u671F\u8D37\u6B3E'], team_name) or 0

        if equity > 0:
            net_debt = (short_debt + long_debt) - cash
            debt_equity_ratio = (net_debt / equity) * 100
            report.append("\n### 2.2 Debt Structure\n")
            report.append(f"- **Total equity**: ${equity/1000:.0f}k\n")
            report.append(f"- **Short-term debt**: ${short_debt/1000:.0f}k\n")
            report.append(f"- **Long-term debt**: ${long_debt/1000:.0f}k\n")
            report.append(f"- **Net debt**: ${net_debt/1000:.0f}k\n")
            report.append(f"- **Net debt / equity**: {debt_equity_ratio:.1f}%\n")

            if debt_equity_ratio < 30:
                debt_status = "Safe (< 30%)"
            elif debt_equity_ratio <= 70:
                debt_status = "Warning (30%-70%)"
            else:
                debt_status = "High risk (> 70%)"
            report.append(f"- **Status**: {debt_status}\n")

        # EBITDA margin
        ebitda = get_metric_value(metrics_dict, [
            'Operating profit before depreciation (EBITDA)',
            '\u606F\u7A0E\u6298\u65E7\u53CA\u644A\u9500\u524D\u5229\u6DA6(EBITDA)',
            'EBITDA',
        ], team_name)
        if ebitda is not None and abs(ebitda) < 100:
            ebitda = None
        if ebitda is None:
            ebitda = 0

        sales = _get(metrics_dict, 'Sales revenue', '\u9500\u552E\u989D', team_name)
        profit = _get(metrics_dict, 'Profit for the round', '\u51C0\u5229\u6DA6', team_name)

        report.append("\n### 2.3 Profitability\n")
        report.append(f"- **Sales**: ${sales/1000:.0f}k\n")
        report.append(f"- **Net profit**: ${profit/1000:.0f}k\n")

        if sales > 0:
            profit_margin = (profit / sales) * 100
            report.append(f"- **Net profit margin**: {profit_margin:.2f}%\n")

            ebitda_rate = (ebitda / sales) * 100
            report.append(f"- **EBITDA margin**: {ebitda_rate:.4f}%\n")

            if ebitda_rate > 20:
                ebitda_status = "Strong (> 20%)"
            elif ebitda_rate >= 5:
                ebitda_status = "Moderate (5%-20%)"
            else:
                ebitda_status = "Weak (< 5%)"
            report.append(f"- **EBITDA status**: {ebitda_status}\n")

        # Equity ratio
        assets = get_metric_value(metrics_dict, ['Total assets', '\u603B\u8D44\u4EA7'], team_name) or 0
        if assets > 0 and equity > 0:
            equity_ratio = (equity / assets) * 100
            report.append("\n### 2.4 Capital Structure\n")
            report.append(f"- **Total assets**: ${assets/1000:.0f}k\n")
            report.append(f"- **Equity ratio**: {equity_ratio:.1f}%\n")

            if equity_ratio > 100:
                equity_status = "Safe (> 100%)"
            elif equity_ratio >= 50:
                equity_status = "Warning (50%-100%)"
            else:
                equity_status = "High risk (< 50%)"
            report.append(f"- **Status**: {equity_status}\n")

    # Section 3: peer benchmark.
    report.append("\n\n## 3. Peer Benchmark Analysis\n")

    if latest_round and latest_round in all_rounds_data:
        metrics_dict = all_rounds_data[latest_round]

        # Collect values for all teams.
        all_teams_sales = {}
        all_teams_profit = {}
        all_teams_cash = {}

        for team in teams:
            sales_val = _get(metrics_dict, 'Sales revenue', '\u9500\u552E\u989D', team)
            profit_val = _get(metrics_dict, 'Profit for the round', '\u51C0\u5229\u6DA6', team)
            cash_val = _get(metrics_dict, 'Cash and cash equivalents', '\u73B0\u91D1', team)

            if sales_val:
                all_teams_sales[team] = sales_val
            if profit_val:
                all_teams_profit[team] = profit_val
            if cash_val:
                all_teams_cash[team] = cash_val

        # Sales ranking
        if all_teams_sales:
            sorted_sales = sorted(all_teams_sales.items(), key=lambda x: x[1], reverse=True)
            sales_rank = next((i+1 for i, (t, _) in enumerate(sorted_sales) if t == team_name), None)
            sales_rank_total = len(sorted_sales)

            report.append("### 3.1 Sales Ranking\n")
            report.append(f"- **Current rank**: {sales_rank} / {sales_rank_total}\n")
            if sales_rank:
                team_sales = all_teams_sales.get(team_name, 0)
                if sales_rank > 1:
                    prev_team, prev_sales = sorted_sales[sales_rank - 2]
                    gap = prev_sales - team_sales
                    report.append(f"- **Gap to next higher team**: ${gap/1000:.0f}k ({prev_team})\n")
                if sales_rank < sales_rank_total:
                    next_team, next_sales = sorted_sales[sales_rank]
                    gap = team_sales - next_sales
                    report.append(f"- **Lead over next lower team**: ${gap/1000:.0f}k ({next_team})\n")

        # Net profit ranking
        if all_teams_profit:
            sorted_profit = sorted(all_teams_profit.items(), key=lambda x: x[1], reverse=True)
            profit_rank = next((i+1 for i, (t, _) in enumerate(sorted_profit) if t == team_name), None)

            report.append("\n### 3.2 Net Profit Ranking\n")
            report.append(f"- **Current rank**: {profit_rank} / {len(sorted_profit)}\n")

        # Cash ranking
        if all_teams_cash:
            sorted_cash = sorted(all_teams_cash.items(), key=lambda x: x[1], reverse=True)
            cash_rank = next((i+1 for i, (t, _) in enumerate(sorted_cash) if t == team_name), None)

            report.append("\n### 3.3 Cash Ranking\n")
            report.append(f"- **Current rank**: {cash_rank} / {len(sorted_cash)}\n")

    # Section 4: strategy suggestions.
    report.append("\n\n## 4. Strategy Recommendations and Action Plan\n")

    if latest_round and latest_round in all_rounds_data:
        metrics_dict = all_rounds_data[latest_round]

        cash = _get(metrics_dict, 'Cash and cash equivalents', '\u73B0\u91D1', team_name)

        report.append("### 4.1 Current Position Assessment\n")

        if cash < 100000:
            report.append("- **High risk**: cash reserve is critically low\n")
            report.append("- Enter a survival mode focused on liquidity\n")
        elif cash < 300000:
            report.append("- **Medium risk**: cash is below the safety line\n")
            report.append("- Keep a larger safety buffer and avoid aggressive moves\n")
        else:
            report.append("- **Low risk**: cash reserve supports selective expansion\n")
            report.append("- Operate in growth mode with controlled downside\n")

        report.append("\n### 4.2 Actionable Recommendations\n")

        if cash < 100000:
            report.append("1. Stop all non-essential investments immediately\n")
            report.append("2. Monetize idle capacity or non-core assets\n")
            report.append("3. Reduce advertising and R&D spend to essential levels\n")
            report.append("4. Prioritize repayment of high-interest debt\n")
            report.append("5. Evaluate financing or strategic partnership options\n")
        elif cash < 300000:
            report.append("1. Keep at least 70% of available cash as buffer\n")
            report.append("2. Maintain only essential advertising spend\n")
            report.append("3. Hold capacity steady; avoid expansion this round\n")
            report.append("4. Monitor competitor moves and preserve flexibility\n")
            report.append("5. Wait for a clearer expansion window\n")
        else:
            report.append("1. Consider measured capacity expansion\n")
            report.append("2. Increase marketing to capture share where ROI is strongest\n")
            report.append("3. Add targeted R&D investment for differentiation\n")
            report.append("4. Keep 20%-30% of cash as a risk buffer\n")
            report.append("5. Evaluate region-specific entry opportunities\n")

    # Save report.
    report_text = "\n".join(report)
    output_file = output_dir / f'{team_name}_detailed_analysis_report.md'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"Report saved to: {output_file}")
    return output_file

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate a detailed analysis report for one team')
    parser.add_argument('--team', '-t', type=str, default='Make the Team Bigger and Stronger', help='Team name')
    parser.add_argument('--input-dir', '-i', type=str, required=True, help='Input data directory')
    parser.add_argument('--output-dir', '-o', type=str, required=True, help='Output report directory')

    args = parser.parse_args()

    analyze_team_detailed(args.team, args.input_dir, args.output_dir)
