#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate a gap analysis report comparing a target team to peers.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
from utils_data_analysis import read_excel_data, get_metric_value


def get_metric_with_priority(metrics_dict, metric_name, team):
    """Get metric value using an ordered alias list.
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

def get_all_rounds_data(input_dir):
    """Read all available rounds from input directory."""
    input_dir = Path(input_dir)
    all_rounds_data = {}
    
    # ir00
    ir00_path = input_dir / 'results-ir00.xls'
    if ir00_path.exists():
        metrics_dict, teams = read_excel_data(str(ir00_path))
        all_rounds_data['ir00'] = {'metrics': metrics_dict, 'teams': teams}
    
    # pr01, pr02, ... (also supports r01, r02, ...)
    for i in range(1, 10):
        r_path = input_dir / f'results-r{i:02d}.xls'
        if not r_path.exists():
            r_path = input_dir / f'results-pr{i:02d}.xls'
        if r_path.exists():
            metrics_dict, teams = read_excel_data(str(r_path))
            all_rounds_data[f'pr{i:02d}'] = {'metrics': metrics_dict, 'teams': teams}
    
    return all_rounds_data

def calculate_metrics(metrics_dict, team):
    """Compute core metrics and derived health indicators."""
    # Try English keys first (Cesim Excel), fall back to Chinese legacy keys.
    def _get(primary_en, fallback_cn):
        val = get_metric_with_priority(metrics_dict, primary_en, team)
        if val is None:
            val = get_metric_with_priority(metrics_dict, fallback_cn, team)
        return val or 0

    cash   = _get('Cash and cash equivalents', '\u73B0\u91D1')
    sales  = _get('Sales revenue', '\u9500\u552E\u989D')
    profit = _get('Profit for the round', '\u51C0\u5229\u6DA6')
    equity = get_metric_value(metrics_dict, ['Total equity', '\u6743\u76CA\u5408\u8BA1'], team) or 0
    assets = get_metric_value(metrics_dict, ['Total assets', '\u603B\u8D44\u4EA7'], team) or 0
    short_debt = get_metric_value(metrics_dict, ['Short-term debts (unplanned)', 'Short-term debts', '\u77ED\u671F\u8D37\u6B3E'], team) or 0
    long_debt  = get_metric_value(metrics_dict, ['Long-term debts', '\u957F\u671F\u8D37\u6B3E'], team) or 0

    # EBITDA — English key first
    ebitda = get_metric_value(metrics_dict, [
        'Operating profit before depreciation (EBITDA)',
        '\u606F\u7A0E\u6298\u65E7\u53CA\u644A\u9500\u524D\u5229\u6DA6(EBITDA)',
        '\u606F\u7A0E\u6298\u65E7\u53CA\u644A\u9100\u524D\u5229\u6DA6',
        'EBITDA',
    ], team)
    # Very small absolute values are often percentages rather than amounts.
    if ebitda is not None and abs(ebitda) < 100:
        ebitda = None
    if ebitda is None:
        ebitda = 0
    
    # Derived indicators.
    net_debt = (short_debt + long_debt) - cash
    debt_equity_ratio = (net_debt / equity * 100) if equity > 0 else None
    ebitda_rate = (ebitda / sales * 100) if sales > 0 else None
    profit_margin = (profit / sales * 100) if sales > 0 else None
    equity_ratio = (equity / assets * 100) if assets > 0 else None
    
    return {
        'cash': cash,
        'sales': sales,
        'profit': profit,
        'equity': equity,
        'assets': assets,
        'short_debt': short_debt,
        'long_debt': long_debt,
        'ebitda': ebitda,
        'net_debt': net_debt,
        'debt_equity_ratio': debt_equity_ratio,
        'ebitda_rate': ebitda_rate,
        'profit_margin': profit_margin,
        'equity_ratio': equity_ratio,
    }

def generate_gap_analysis(target_team, input_dir, output_dir):
    """Generate a markdown report with ranking and gap analysis."""

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load all rounds.
    all_rounds_data = get_all_rounds_data(input_dir)

    if not all_rounds_data:
        print("Error: No data file found.")
        return

    # Pick latest available round.
    latest_round = None
    for rnd in ['pr09', 'pr08', 'pr07', 'pr06', 'pr05', 'pr04', 'pr03', 'pr02', 'pr01', 'ir00']:
        if rnd in all_rounds_data:
            latest_round = rnd
            break
    
    if latest_round is None:
        latest_round = list(all_rounds_data.keys())[-1]
    
    metrics_dict = all_rounds_data[latest_round]['metrics']
    teams = all_rounds_data[latest_round]['teams']
    
    if target_team not in teams:
        print(f"Error: Team '{target_team}' was not found")
        print(f"Available teams: {', '.join(teams)}")
        return

    # Compute metrics for all teams.
    all_teams_metrics = {}
    for team in teams:
        all_teams_metrics[team] = calculate_metrics(metrics_dict, team)
    
    target_metrics = all_teams_metrics[target_team]
    
    # Build report.
    report = []
    report.append(f"# Gap Analysis Report: {target_team} vs Peers\n")
    report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"Analyzed round: {latest_round.upper()}\n")
    report.append("=" * 80 + "\n")

    # Section 1: overall rankings.
    report.append("\n## 1. Overall Ranking Comparison\n")

    # Sales ranking
    sales_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['sales'], reverse=True)
    sales_rank = sales_ranking.index(target_team) + 1
    report.append("### 1.1 Sales Ranking\n")
    report.append(f"- **{target_team} rank**: {sales_rank} / {len(teams)}\n")
    report.append(f"- **Sales**: ${target_metrics['sales']/1000:.0f}k\n")

    if sales_rank > 1:
        prev_team = sales_ranking[sales_rank - 2]
        gap = all_teams_metrics[prev_team]['sales'] - target_metrics['sales']
        report.append(f"- **Gap to next higher team**: ${gap/1000:.0f}k ({prev_team})\n")

    if sales_rank < len(teams):
        next_team = sales_ranking[sales_rank]
        gap = target_metrics['sales'] - all_teams_metrics[next_team]['sales']
        report.append(f"- **Lead over next lower team**: ${gap/1000:.0f}k ({next_team})\n")

    # Net profit ranking
    profit_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['profit'], reverse=True)
    profit_rank = profit_ranking.index(target_team) + 1
    report.append("\n### 1.2 Net Profit Ranking\n")
    report.append(f"- **{target_team} rank**: {profit_rank} / {len(teams)}\n")
    report.append(f"- **Net profit**: ${target_metrics['profit']/1000:.0f}k\n")

    # Cash ranking
    cash_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['cash'], reverse=True)
    cash_rank = cash_ranking.index(target_team) + 1
    report.append("\n### 1.3 Cash Ranking\n")
    report.append(f"- **{target_team} rank**: {cash_rank} / {len(teams)}\n")
    report.append(f"- **Cash**: ${target_metrics['cash']/1000:.0f}k\n")

    # EBITDA ranking
    ebitda_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['ebitda'], reverse=True)
    ebitda_rank = ebitda_ranking.index(target_team) + 1
    report.append("\n### 1.4 EBITDA Ranking\n")
    report.append(f"- **{target_team} rank**: {ebitda_rank} / {len(teams)}\n")
    report.append(f"- **EBITDA**: ${target_metrics['ebitda']/1000:.0f}k\n")

    # Section 2: comparison with top 3.
    report.append("\n## 2. Detailed Comparison Against Top 3 Teams\n")

    top3_teams = sales_ranking[:3]
    report.append("| Metric | " + " | ".join([target_team] + top3_teams) + " |")
    report.append("|------|" + "|".join(["------" for _ in range(4)]) + "|")

    key_metrics = [
        ('Sales (k USD)',        'sales',             'k'),
        ('Net Profit (k USD)',   'profit',            'k'),
        ('Cash (k USD)',         'cash',              'k'),
        ('Total Equity (k USD)', 'equity',            'k'),
        ('EBITDA (k USD)',       'ebitda',            'k'),
        ('EBITDA Margin',        'ebitda_rate',       '%'),
        ('Net Profit Margin',    'profit_margin',     '%'),
        ('Net Debt / Equity',    'debt_equity_ratio', '%'),
        ('Equity Ratio',         'equity_ratio',      '%'),
    ]

    for metric_name, metric_key, unit in key_metrics:
        target_val = target_metrics[metric_key]
        if target_val is not None:
            values = [f"${target_val/1000:.0f}k" if unit == 'k' else f"{target_val:.1f}%"]
        else:
            values = ["N/A"]
        for team in top3_teams:
            val = all_teams_metrics[team][metric_key]
            if val is not None:
                values.append(f"${val/1000:.0f}k" if unit == 'k' else f"{val:.1f}%")
            else:
                values.append("N/A")
        report.append(f"| {metric_name} | " + " | ".join(values) + " |")

    # Section 3: gap diagnostics.
    report.append("\n## 3. Key Gap Analysis\n")

    top1_team = top3_teams[0]
    top1_metrics = all_teams_metrics[top1_team]

    report.append(f"### 3.1 Gap vs #1 Team ({top1_team})\n")

    sales_gap = top1_metrics['sales'] - target_metrics['sales']
    sales_gap_pct = (sales_gap / top1_metrics['sales'] * 100) if top1_metrics['sales'] > 0 else 0
    report.append(f"- **Sales gap**: ${sales_gap/1000:.0f}k ({sales_gap_pct:.1f}% behind)\n")

    profit_gap = top1_metrics['profit'] - target_metrics['profit']
    if top1_metrics['profit'] > 0:
        profit_gap_pct = profit_gap / top1_metrics['profit'] * 100
    elif target_metrics['profit'] > 0:
        profit_gap_pct = profit_gap / target_metrics['profit'] * 100
    else:
        profit_gap_pct = 0
    report.append(f"- **Net profit gap**: ${profit_gap/1000:.0f}k ({profit_gap_pct:.1f}% behind)\n")

    cash_gap = top1_metrics['cash'] - target_metrics['cash']
    cash_gap_pct = (cash_gap / top1_metrics['cash'] * 100) if top1_metrics['cash'] > 0 else 0
    report.append(f"- **Cash gap**: ${cash_gap/1000:.0f}k ({cash_gap_pct:.1f}% behind)\n")

    ebitda_gap = top1_metrics['ebitda'] - target_metrics['ebitda']
    ebitda_gap_pct = (ebitda_gap / top1_metrics['ebitda'] * 100) if top1_metrics['ebitda'] > 0 else 0
    report.append(f"- **EBITDA gap**: ${ebitda_gap/1000:.0f}k ({ebitda_gap_pct:.1f}% behind)\n")

    # Compare against industry average.
    report.append("\n### 3.2 Comparison vs Industry Average\n")

    import numpy as np
    avg_sales  = np.mean([all_teams_metrics[t]['sales']  for t in teams])
    avg_profit = np.mean([all_teams_metrics[t]['profit'] for t in teams])
    avg_cash   = np.mean([all_teams_metrics[t]['cash']   for t in teams])
    avg_ebitda = np.mean([all_teams_metrics[t]['ebitda'] for t in teams])

    def _vs_avg(val, avg):
        if avg != 0:
            return (val - avg) / abs(avg) * 100
        return 0

    report.append(f"- **Sales**: ${target_metrics['sales']/1000:.0f}k (industry avg: ${avg_sales/1000:.0f}k, {_vs_avg(target_metrics['sales'], avg_sales):+.1f}%)\n")
    report.append(f"- **Net profit**: ${target_metrics['profit']/1000:.0f}k (industry avg: ${avg_profit/1000:.0f}k, {_vs_avg(target_metrics['profit'], avg_profit):+.1f}%)\n")
    report.append(f"- **Cash**: ${target_metrics['cash']/1000:.0f}k (industry avg: ${avg_cash/1000:.0f}k, {_vs_avg(target_metrics['cash'], avg_cash):+.1f}%)\n")
    report.append(f"- **EBITDA**: ${target_metrics['ebitda']/1000:.0f}k (industry avg: ${avg_ebitda/1000:.0f}k, {_vs_avg(target_metrics['ebitda'], avg_ebitda):+.1f}%)\n")

    # Section 4: multi-round trend comparison.
    report.append("\n## 4. Multi-Round Trend Comparison\n")

    rounds_order = ['ir00', 'pr01', 'pr02', 'pr03', 'pr04', 'pr05', 'pr06', 'pr07', 'pr08', 'pr09']
    available_rounds = [r for r in rounds_order if r in all_rounds_data]

    if len(available_rounds) > 1:
        report.append("### 4.1 Sales Trend Comparison\n")
        report.append("| Team | " + " | ".join([r.upper() for r in available_rounds]) + " |")
        report.append("|------|" + "|".join(["------" for _ in available_rounds]) + "|")

        display_teams = [target_team] + top3_teams
        for team in display_teams:
            values = []
            for rnd in available_rounds:
                rnd_metrics = all_rounds_data[rnd]['metrics']
                s = get_metric_with_priority(rnd_metrics, 'Sales revenue', team) or 0
                values.append(f"${s/1000:.0f}k")
            report.append(f"| {team} | " + " | ".join(values) + " |")

    # Section 5: recommendations.
    report.append("\n## 5. Recommendations\n")
    report.append("### 5.1 Priority Improvement Areas\n")

    if sales_rank > 3:
        report.append(f"1. Increase sales: currently ranked #{sales_rank}; ~${sales_gap/1000:.0f}k needed to match #1\n")
    if target_metrics['ebitda_rate'] is not None and target_metrics['ebitda_rate'] < 20:
        report.append("2. Improve profitability: EBITDA margin below 20%; review cost structure and pricing\n")
    if target_metrics['cash'] < 300000:
        report.append("3. Increase cash reserve: maintain a larger liquidity buffer\n")
    if target_metrics['debt_equity_ratio'] is not None and target_metrics['debt_equity_ratio'] > 70:
        report.append("4. Rebalance debt: net debt/equity > 70%; reduce debt or strengthen equity\n")
    if target_metrics['equity_ratio'] is not None and target_metrics['equity_ratio'] < 40:
        report.append("5. Equity ratio below 40%; consider debt reduction or equity issuance\n")

    report.append("\n### 5.2 Benchmark Teams to Learn From\n")
    report.append(f"- **Sales benchmark**: {top1_team} (${top1_metrics['sales']/1000:.0f}k)\n")

    profit_leader = max(teams, key=lambda t: all_teams_metrics[t]['profit'])
    report.append(f"- **Profit benchmark**: {profit_leader} (net profit ${all_teams_metrics[profit_leader]['profit']/1000:.0f}k)\n")

    cash_leader = max(teams, key=lambda t: all_teams_metrics[t]['cash'])
    report.append(f"- **Cash management benchmark**: {cash_leader} (cash ${all_teams_metrics[cash_leader]['cash']/1000:.0f}k)\n")

    ebitda_leader = max(teams, key=lambda t: all_teams_metrics[t]['ebitda'])
    report.append(f"- **EBITDA benchmark**: {ebitda_leader} (${all_teams_metrics[ebitda_leader]['ebitda']/1000:.0f}k)\n")

    # Save report.
    report_text = "\n".join(report)
    output_file = output_dir / f'{target_team}_gap_analysis_report.md'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"Report saved to: {output_file}")
    return output_file

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate a team gap analysis report')
    parser.add_argument('--team', '-t', type=str, default='Make the Team Bigger and Stronger', help='Target team name')
    parser.add_argument('--input-dir', '-i', type=str, required=True, help='Input data directory')
    parser.add_argument('--output-dir', '-o', type=str, required=True, help='Output report directory')

    args = parser.parse_args()

    generate_gap_analysis(args.team, args.input_dir, args.output_dir)

