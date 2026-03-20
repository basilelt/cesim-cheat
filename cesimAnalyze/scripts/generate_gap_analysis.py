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
    """Get metric value using an ordered alias list."""
    metric_priorities = {
        '\u9500\u552E\u989D': ['\u9500\u552E\u989D\u5408\u8BA1', '\u672C\u5730\u9500\u552E\u989D', '\u5F53\u5730\u9500\u552E\u989D', '\u9500\u552E\u989D'],
        '\u51C0\u5229\u6DA6': ['\u672C\u56DE\u5408\u5229\u6DA6', '\u7A0E\u540E\u5229\u6DA6', '\u51C0\u5229\u6DA6'],
        '\u73B0\u91D1': ['\u73B0\u91D1\u53CA\u7B49\u4EF7\u7269', '\u73B0\u91D1 31.12.', '\u73B0\u91D1 1.1.', '\u73B0\u91D1'],
        '\u77ED\u671F\u8D37\u6B3E': ['\u77ED\u671F\u8D37\u6B3E（\u65E0\u8BA1\u5212）', '\u77ED\u671F\u8D37\u6B3E'],
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
    cash = get_metric_with_priority(metrics_dict, '\u73B0\u91D1', team) or 0
    sales = get_metric_with_priority(metrics_dict, '\u9500\u552E\u989D', team) or 0
    profit = get_metric_with_priority(metrics_dict, '\u51C0\u5229\u6DA6', team) or 0
    equity = get_metric_value(metrics_dict, '\u6743\u76CA\u5408\u8BA1', team) or 0
    assets = get_metric_value(metrics_dict, '\u603B\u8D44\u4EA7', team) or 0
    short_debt = get_metric_value(metrics_dict, '\u77ED\u671F\u8D37\u6B3E', team) or 0
    long_debt = get_metric_value(metrics_dict, '\u957F\u671F\u8D37\u6B3E', team) or 0
    
    # EBITDA
    ebitda = get_metric_value(metrics_dict, ['\u606F\u7A0E\u6298\u65E7\u53CA\u644A\u9500\u524D\u5229\u6DA6(EBITDA)', '\u606F\u7A0E\u6298\u65E7\u53CA\u644A\u9500\u524D\u5229\u6DA6', 'EBITDA'], team)
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
        '\u73B0\u91D1': cash,
        '\u9500\u552E\u989D': sales,
        '\u51C0\u5229\u6DA6': profit,
        '\u6743\u76CA\u5408\u8BA1': equity,
        '\u603B\u8D44\u4EA7': assets,
        '\u77ED\u671F\u8D37\u6B3E': short_debt,
        '\u957F\u671F\u8D37\u6B3E': long_debt,
        'EBITDA': ebitda,
        '\u51C0\u503A\u52A1': net_debt,
        '\u51C0\u503A\u52A1\u6743\u76CA\u6BD4': debt_equity_ratio,
        'EBITDA\u7387': ebitda_rate,
        '\u51C0\u5229\u6DA6\u7387': profit_margin,
        '\u6743\u76CA\u6BD4\u7387': equity_ratio,
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
    sales_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['\u9500\u552E\u989D'], reverse=True)
    sales_rank = sales_ranking.index(target_team) + 1
    report.append("### 1.1 Sales Ranking\n")
    report.append(f"- **{target_team} rank**: {sales_rank} / {len(teams)}\n")
    report.append(f"- **Sales**: ${target_metrics['\u9500\u552E\u989D']/1000:.0f}k\n")
    
    if sales_rank > 1:
        prev_team = sales_ranking[sales_rank - 2]
        gap = all_teams_metrics[prev_team]['\u9500\u552E\u989D'] - target_metrics['\u9500\u552E\u989D']
        report.append(f"- **Gap to next higher team**: ${gap/1000:.0f}k ({prev_team})\n")
    
    if sales_rank < len(teams):
        next_team = sales_ranking[sales_rank]
        gap = target_metrics['\u9500\u552E\u989D'] - all_teams_metrics[next_team]['\u9500\u552E\u989D']
        report.append(f"- **Lead over next lower team**: ${gap/1000:.0f}k ({next_team})\n")

    # Net profit ranking
    profit_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['\u51C0\u5229\u6DA6'], reverse=True)
    profit_rank = profit_ranking.index(target_team) + 1
    report.append("\n### 1.2 Net Profit Ranking\n")
    report.append(f"- **{target_team} rank**: {profit_rank} / {len(teams)}\n")
    report.append(f"- **Net profit**: ${target_metrics['\u51C0\u5229\u6DA6']/1000:.0f}k\n")

    # Cash ranking
    cash_ranking = sorted(teams, key=lambda t: all_teams_metrics[t]['\u73B0\u91D1'], reverse=True)
    cash_rank = cash_ranking.index(target_team) + 1
    report.append("\n### 1.3 Cash Ranking\n")
    report.append(f"- **{target_team} rank**: {cash_rank} / {len(teams)}\n")
    report.append(f"- **Cash**: ${target_metrics['\u73B0\u91D1']/1000:.0f}k\n")

    # Section 2: comparison with top 3.
    report.append("\n## 2. Detailed Comparison Against Top 3 Teams\n")

    top3_teams = sales_ranking[:3]
    report.append("| Metric | " + " | ".join([f"{target_team}"] + top3_teams) + " |")
    report.append("|------|" + "|".join(["------" for _ in range(4)]) + "|")

    # Key metric comparison.
    key_metrics = [
        ('Sales', '\u9500\u552E\u989D', 'k'),
        ('Net Profit', '\u51C0\u5229\u6DA6', 'k'),
        ('Cash', '\u73B0\u91D1', 'k'),
        ('Total Equity', '\u6743\u76CA\u5408\u8BA1', 'k'),
        ('EBITDA', 'EBITDA', 'k'),
        ('EBITDA Margin', 'EBITDA\u7387', '%'),
        ('Net Profit Margin', '\u51C0\u5229\u6DA6\u7387', '%'),
        ('Net Debt / Equity', '\u51C0\u503A\u52A1\u6743\u76CA\u6BD4', '%'),
        ('Equity Ratio', '\u6743\u76CA\u6BD4\u7387', '%'),
    ]

    for metric_name, metric_key, unit in key_metrics:
        # Format target team value.
        target_val = target_metrics[metric_key]
        if target_val is not None:
            if unit == 'k':
                values = [f"${target_val/1000:.0f}{unit}"]
            else:
                values = [f"{target_val:.1f}{unit}"]
        else:
            values = ["N/A"]
        
        # Format peer values.
        for team in top3_teams:
            val = all_teams_metrics[team][metric_key]
            if val is not None:
                if unit == 'k':
                    values.append(f"${val/1000:.0f}{unit}")
                else:
                    values.append(f"{val:.1f}{unit}")
            else:
                values.append("N/A")
        report.append(f"| {metric_name} | " + " | ".join(values) + " |")

    # Section 3: gap diagnostics.
    report.append("\n## 3. Key Gap Analysis\n")

    # Gap against rank #1.
    top1_team = top3_teams[0]
    top1_metrics = all_teams_metrics[top1_team]

    report.append(f"### 3.1 Gap vs #1 Team ({top1_team})\n")

    sales_gap = top1_metrics['\u9500\u552E\u989D'] - target_metrics['\u9500\u552E\u989D']
    sales_gap_pct = (sales_gap / top1_metrics['\u9500\u552E\u989D'] * 100) if top1_metrics['\u9500\u552E\u989D'] > 0 else 0
    report.append(f"- **Sales gap**: ${sales_gap/1000:.0f}k ({sales_gap_pct:.1f}% behind)\n")

    profit_gap = top1_metrics['\u51C0\u5229\u6DA6'] - target_metrics['\u51C0\u5229\u6DA6']
    # If #1 profit is positive, use that as baseline; otherwise use target team.
    if top1_metrics['\u51C0\u5229\u6DA6'] > 0:
        profit_gap_pct = (profit_gap / top1_metrics['\u51C0\u5229\u6DA6'] * 100)
    elif target_metrics['\u51C0\u5229\u6DA6'] > 0:
        profit_gap_pct = (profit_gap / target_metrics['\u51C0\u5229\u6DA6'] * 100)
    else:
        profit_gap_pct = 0
    report.append(f"- **Net profit gap**: ${profit_gap/1000:.0f}k ({profit_gap_pct:.1f}% behind)\n")

    cash_gap = top1_metrics['\u73B0\u91D1'] - target_metrics['\u73B0\u91D1']
    cash_gap_pct = (cash_gap / top1_metrics['\u73B0\u91D1'] * 100) if top1_metrics['\u73B0\u91D1'] > 0 else 0
    report.append(f"- **Cash gap**: ${cash_gap/1000:.0f}k ({cash_gap_pct:.1f}% behind)\n")

    # Compare against industry average.
    report.append("\n### 3.2 Comparison vs Industry Average\n")

    import numpy as np
    avg_sales = np.mean([all_teams_metrics[t]['\u9500\u552E\u989D'] for t in teams])
    avg_profit = np.mean([all_teams_metrics[t]['\u51C0\u5229\u6DA6'] for t in teams])
    avg_cash = np.mean([all_teams_metrics[t]['\u73B0\u91D1'] for t in teams])

    sales_vs_avg = ((target_metrics['\u9500\u552E\u989D'] - avg_sales) / avg_sales * 100) if avg_sales > 0 else 0
    # If avg profit is positive, use average as baseline; otherwise use target.
    if avg_profit > 0:
        profit_vs_avg = ((target_metrics['\u51C0\u5229\u6DA6'] - avg_profit) / avg_profit * 100)
    elif target_metrics['\u51C0\u5229\u6DA6'] > 0:
        profit_vs_avg = ((target_metrics['\u51C0\u5229\u6DA6'] - avg_profit) / target_metrics['\u51C0\u5229\u6DA6'] * 100)
    else:
        profit_vs_avg = 0
    cash_vs_avg = ((target_metrics['\u73B0\u91D1'] - avg_cash) / avg_cash * 100) if avg_cash > 0 else 0

    report.append(f"- **Sales**: ${target_metrics['\u9500\u552E\u989D']/1000:.0f}k (industry avg: ${avg_sales/1000:.0f}k, {sales_vs_avg:+.1f}%)\n")
    report.append(f"- **Net profit**: ${target_metrics['\u51C0\u5229\u6DA6']/1000:.0f}k (industry avg: ${avg_profit/1000:.0f}k, {profit_vs_avg:+.1f}%)\n")
    report.append(f"- **Cash**: ${target_metrics['\u73B0\u91D1']/1000:.0f}k (industry avg: ${avg_cash/1000:.0f}k, {cash_vs_avg:+.1f}%)\n")

    # Section 4: multi-round trend comparison.
    report.append("\n## 4. Multi-Round Trend Comparison\n")

    rounds_order = ['ir00', 'pr01', 'pr02', 'pr03', 'pr04', 'pr05']
    available_rounds = [r for r in rounds_order if r in all_rounds_data]

    if len(available_rounds) > 1:
        report.append("### 4.1 Sales Trend Comparison\n")
        report.append("| Team | " + " | ".join([r.upper() for r in available_rounds]) + " |")
        report.append("|------|" + "|".join(["------" for _ in available_rounds]) + "|")

        # Show target + top 3 teams.
        display_teams = [target_team] + top3_teams
        for team in display_teams:
            values = []
            for rnd in available_rounds:
                if rnd in all_rounds_data:
                    metrics = all_rounds_data[rnd]['metrics']
                    sales = get_metric_with_priority(metrics, '\u9500\u552E\u989D', team) or 0
                    values.append(f"${sales/1000:.0f}k")
                else:
                    values.append("N/A")
            report.append(f"| {team} | " + " | ".join(values) + " |")

    # Section 5: recommendations.
    report.append("\n## 5. Recommendations\n")

    report.append("### 5.1 Priority Improvement Areas\n")

    # Suggestions based on diagnosed gaps.
    if sales_rank > 3:
        report.append(f"1. Increase sales: currently ranked #{sales_rank}; approximately ${sales_gap/1000:.0f}k is needed to match #1\n")
    
    if target_metrics['EBITDA\u7387'] and target_metrics['EBITDA\u7387'] < 20:
        report.append("2. Improve profitability: EBITDA margin is low; optimize cost structure and/or pricing\n")
    
    if target_metrics['\u73B0\u91D1'] < 300000:
        report.append("3. Increase cash reserve: maintain a larger liquidity buffer\n")
    
    if target_metrics['\u51C0\u503A\u52A1\u6743\u76CA\u6BD4'] and target_metrics['\u51C0\u503A\u52A1\u6743\u76CA\u6BD4'] > 30:
        report.append("4. Rebalance debt structure: reduce debt load or strengthen equity base\n")

    report.append("\n### 5.2 Benchmark Teams to Learn From\n")
    report.append(f"- **Sales benchmark**: {top1_team} (${top1_metrics['\u9500\u552E\u989D']/1000:.0f}k)\n")

    # Team with highest profit.
    profit_leader = max(teams, key=lambda t: all_teams_metrics[t]['\u51C0\u5229\u6DA6'])
    report.append(f"- **Profit benchmark**: {profit_leader} (net profit ${all_teams_metrics[profit_leader]['\u51C0\u5229\u6DA6']/1000:.0f}k)\n")

    # Team with strongest cash position.
    cash_leader = max(teams, key=lambda t: all_teams_metrics[t]['\u73B0\u91D1'])
    report.append(f"- **Cash management benchmark**: {cash_leader} (cash ${all_teams_metrics[cash_leader]['\u73B0\u91D1']/1000:.0f}k)\n")

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

