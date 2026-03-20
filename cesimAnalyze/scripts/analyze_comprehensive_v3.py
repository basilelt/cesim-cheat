#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive Business Simulation Analysis Script v3.0
Complete analysis aligned with Methodology v3.0
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json

# Add utils directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))

from utils_data_analysis import (
    read_excel_data, find_metric, get_metric_value,
    check_excel_structure, diagnose_missing_data
)

# ============================================================================
# Configuration
# ============================================================================

# Default paths (overridable via CLI)
DEFAULT_INPUT_DIR = Path(__file__).parent.parent.parent / 'results'
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent / 'analysis'

def get_data_files(input_dir):
    """
    Auto-detect data files in the input directory
    Supports ir00 and any number of prXX rounds
    Also supports rXX naming
    """
    base_dir = Path(input_dir)
    files = {}
    
    # Check ir00 first (initial round)
    ir00_path = base_dir / 'results-ir00.xls'
    if ir00_path.exists():
        files['ir00'] = ir00_path
    
    # Auto-detect prXX files
    # Scans up to pr99
    # Scan all plausible round files
    for i in range(1, 100):
        round_name = f'pr{i:02d}'
        file_path = base_dir / f'results-{round_name}.xls'
        if file_path.exists():
            files[round_name] = file_path
    
    # Also map rXX to prXX
    for i in range(1, 100):
        r_format_path = base_dir / f'results-r{i:02d}.xls'
        if r_format_path.exists():
            pr_round_name = f'pr{i:02d}'
            # Use rXX file when prXX is missing
            if pr_round_name not in files:
                files[pr_round_name] = r_format_path
    
    return files


def get_rounds_order(all_rounds_data=None):
    """
    Build ordered round list for traversal
    If all_rounds_data is provided, return existing rounds only
    """
    # Build full round list (up to pr99)
    rounds = ['ir00']
    rounds.extend([f'pr{i:02d}' for i in range(1, 100)])
    
    if all_rounds_data is not None:
        # Return only existing rounds
        return [r for r in rounds if r in all_rounds_data]
    
    return rounds

# Team name mapping
TEAM_NAME_MAPPING = {
    '\u521B\u4E16\u7EAA\u7684\u5927\u5BCC\u7FC1': 'Blue',
    '\u661F\u91CE\u56DB\u559C': 'Black',
}

# Thresholds (from methodology chapter 7)
THRESHOLDS = {
    'Cash Reserve': {'green': 300000, 'yellow': 100000},
    'Net Debt to Equity': {'green': 30, 'yellow': 70},
    'EBITDA Margin': {'green': 20, 'yellow': 5},
    'Equity Ratio': {'green': 100, 'yellow': 50},
    'R&D Return': {'green': 15, 'yellow': 0},
}

# ============================================================================
# Chapter 1: Data Foundation
# ============================================================================

def normalize_team_names(teams):
    """Normalize team names"""
    return [TEAM_NAME_MAPPING.get(team, team) for team in teams]


def get_metric_priority_list(metric_name):
    """
    Return priority aliases for canonical metric name
    Used for priority matching in metric extraction
    Prefer global aggregate values over regional values
    """
    metric_priorities = {
        'Sales': ['Total Sales', 'Local Sales', 'Regional Sales', 'Sales'],
        'Net Profit': ['Profit This Round', 'After-Tax Profit', 'Net Profit'],
        'Cash': ['Cash and Equivalents', 'Cash 31.12.', 'Cash 1.1.', 'Cash'],
        'Short-Term Debt': ['Short-Term Debt (Unplanned)', 'Short-Term Debt'],
        'Long-Term Debt': ['Long-Term Debt'],
        'Total Liabilities': ['Total Liabilities', 'Total Liabilities'],  # \u4F18\u5148\u4F7F\u7528\u8D1F\u503A\u603B\u8BA1（\u5168\u5C40），\u907F\u514D\u5339\u914D\u5230\u533A\u57DF\u6027\u7684\u8D1F\u503C
        'Total Assets': ['Total Assets'],  # \u4F18\u5148\u5339\u914D\u5168\u5C40\u6C47\u603B\u7684\u603B\u8D44\u4EA7（\u5728"\u8D44\u4EA7\u8D1F\u503A\u8868, \u5343 USD, \u5168\u7403"\u90E8\u5206）
        'EBITDA': ['EBITDA'],  # \u4F18\u5148\u5339\u914D\u5168\u5C40\u6C47\u603B\u7684EBITDA
    }
    return metric_priorities.get(metric_name, [metric_name])


def get_metric_with_priority(metrics_dict, metric_name, team):
    """Get metric value using priority aliases"""
    priority_list = get_metric_priority_list(metric_name)
    return get_metric_value(metrics_dict, priority_list, team)


def validate_data_integrity(metrics_dict, teams):
    """Data integrity validation (accounting identity)
    
    Validate: Total Assets = Total Equity + Total Liabilities
    Ensure values come from same aggregation level (global)
    """
    issues = []
    
    for team in teams:
        # \u4F7F\u7528\u5168\u5C40\u6C47\u603B\u7684\u603B\u8D44\u4EA7\u3001\u6743\u76CA\u5408\u8BA1\u548C\u8D1F\u503A\u603B\u8BA1
        assets = get_metric_value(metrics_dict, 'Total Assets', team)
        equity = get_metric_value(metrics_dict, 'Total Equity', team)
        # \u4F18\u5148\u4F7F\u7528\u8D1F\u503A\u603B\u8BA1（\u5168\u5C40\u6C47\u603B），\u907F\u514D\u5339\u914D\u5230\u533A\u57DF\u6027\u7684\u8D1F\u503C
        liability_total = get_metric_value(metrics_dict, ['Total Liabilities', 'Total Liabilities'], team)
        
        # \u4E5F\u53EF\u4EE5\u4F7F\u7528"\u80A1\u4E1C\u6743\u76CA\u548C\u8D1F\u503A\u603B\u8BA1"\u6765\u9A8C\u8BC1
        total_equity_liability = None
        for key, metric_data in metrics_dict.items():
            if 'Total Equity and Liabilities' in str(key) and '\u5168\u7403' in str(key):
                if team in metric_data:
                    total_equity_liability = metric_data.get(team)
                    break
        
        if assets and equity is not None:
            # \u65B9\u6CD51：Validate: Total Assets = Total Equity + Total Liabilities
            if liability_total is not None and liability_total > 0:
                calculated = equity + liability_total
                if assets > 0:
                    error_rate = abs(assets - calculated) / abs(assets) * 100
                    if error_rate > 10:  # \u8BEF\u5DEE\u5BB9\u5FCD\u5EA610%
                        issues.append({
                            'team': team,
                            'error_rate': error_rate,
                            'calculated': calculated,
                            'actual': assets,
                            'status': '\u9700\u8981\u4EBA\u5DE5\u6838\u67E5' if error_rate < 50 else '\u6570\u636E\u5F02\u5E38',
                            'note': f'\u6743\u76CA({equity:.0f}) + \u8D1F\u503A({liability_total:.0f}) = {calculated:.0f}，\u5B9E\u9645\u8D44\u4EA7={assets:.0f}'
                        })
            
            # \u65B9\u6CD52：\u4F7F\u7528"\u80A1\u4E1C\u6743\u76CA\u548C\u8D1F\u503A\u603B\u8BA1"\u9A8C\u8BC1
            if total_equity_liability is not None:
                if assets > 0:
                    error_rate = abs(assets - total_equity_liability) / abs(assets) * 100
                    if error_rate > 5:  # \u4F7F\u7528\u603B\u8BA1\u503C，\u8BEF\u5DEE\u5BB9\u5FCD\u5EA6\u66F4\u4E25\u683C
                        issues.append({
                            'team': team,
                            'error_rate': error_rate,
                            'calculated': total_equity_liability,
                            'actual': assets,
                            'status': '\u6570\u636E\u4E0D\u4E00\u81F4',
                            'note': f'\u603B\u8D44\u4EA7({assets:.0f})\u4E0E\u80A1\u4E1C\u6743\u76CA\u548C\u8D1F\u503A\u603B\u8BA1({total_equity_liability:.0f})\u4E0D\u4E00\u81F4'
                        })
    
    return issues


def detect_anomalies(metrics_dict, teams):
    """Anomaly detection"""
    anomalies = defaultdict(list)
    
    for team in teams:
        # \u73B0\u91D1\u6781\u7AEF\u503C
        cash = get_metric_with_priority(metrics_dict, 'Cash', team)
        if cash:
            if cash > 1500000 or cash < 5000:
                anomalies[team].append({
                    'type': '\u73B0\u91D1\u6781\u7AEF\u503C',
                    'value': cash,
                    'rule': '>$1.5M\u6216<$5k'
                })
        
        # \u8D1F\u6743\u76CA
        equity = get_metric_value(metrics_dict, 'Total Equity', team)
        if equity and equity < 0:
            anomalies[team].append({
                'type': '\u8D1F\u6743\u76CA',
                'value': equity,
                'rule': '\u6743\u76CA\u5408\u8BA1<0'
            })
    
    return anomalies


def calculate_derived_metrics(all_rounds_data, teams):
    """Compute derived metrics"""
    derived = {}
    rounds = get_rounds_order(all_rounds_data)
    
    for rnd in rounds:
        if rnd not in all_rounds_data:
            continue
        
        metrics_dict = all_rounds_data[rnd]
        derived[rnd] = {}
        
        # \u8BA1\u7B97\u884C\u4E1A\u7EDF\u8BA1\u91CF
        for metric_name in ['Sales', 'Net Profit', 'Cash', 'Total Equity']:
            values = []
            for team in teams:
                val = get_metric_with_priority(metrics_dict, metric_name, team)
                if val is not None:
                    values.append(val)
            
            if values:
                import numpy as np
                derived[rnd][f'{metric_name}_\u884C\u4E1A\u5747\u503C'] = np.mean(values)
                derived[rnd][f'{metric_name}_\u884C\u4E1A\u4E2D\u4F4D\u6570'] = np.median(values)
                derived[rnd][f'{metric_name}_\u884C\u4E1A\u6807\u51C6\u5DEE'] = np.std(values)
        
        # \u8BA1\u7B97\u6392\u540D
        for metric_name in ['Sales', 'Net Profit', 'Cash']:
            team_values = {}
            for team in teams:
                val = get_metric_with_priority(metrics_dict, metric_name, team)
                if val is not None:
                    team_values[team] = val
            
            if team_values:
                sorted_teams = sorted(team_values.items(), key=lambda x: x[1], reverse=True)
                rankings = {team: rank+1 for rank, (team, _) in enumerate(sorted_teams)}
                derived[rnd][f'{metric_name}_\u6392\u540D'] = rankings
        
        # \u8BA1\u7B97\u73AF\u6BD4\u589E\u957F\u7387（\u9700\u8981\u4E0A\u56DE\u5408\u6570\u636E）
        if rnd != 'ir00':
            prev_rnd = rounds[rounds.index(rnd) - 1]
            if prev_rnd in all_rounds_data:
                prev_metrics = all_rounds_data[prev_rnd]
                for metric_name in ['Sales', 'Net Profit', 'Cash']:
                    growth_rates = {}
                    for team in teams:
                        current = get_metric_with_priority(metrics_dict, metric_name, team)
                        previous = get_metric_with_priority(prev_metrics, metric_name, team)
                        if current is not None and previous is not None and previous != 0:
                            growth_rate = ((current - previous) / abs(previous)) * 100
                            growth_rates[team] = growth_rate
                    if growth_rates:
                        derived[rnd][f'{metric_name}_\u73AF\u6BD4\u589E\u957F'] = growth_rates
        
        # \u8BA1\u7B97\u6392\u540D\u53D8\u5316（\u9700\u8981\u4E0A\u56DE\u5408\u6570\u636E）
        if rnd != 'ir00':
            prev_rnd = rounds[rounds.index(rnd) - 1]
            if prev_rnd in all_rounds_data:
                prev_derived = derived.get(prev_rnd, {})
                for metric_name in ['Sales', 'Net Profit', 'Cash']:
                    current_rankings = derived[rnd].get(f'{metric_name}_\u6392\u540D', {})
                    previous_rankings = prev_derived.get(f'{metric_name}_\u6392\u540D', {})
                    if current_rankings and previous_rankings:
                        rank_changes = {}
                        for team in teams:
                            current_rank = current_rankings.get(team)
                            previous_rank = previous_rankings.get(team)
                            if current_rank is not None and previous_rank is not None:
                                rank_changes[team] = current_rank - previous_rank
                        if rank_changes:
                            derived[rnd][f'{metric_name}_\u6392\u540D\u53D8\u5316'] = rank_changes
        
        # \u8BA1\u7B97\u6218\u7565\u504F\u79BB\u5EA6（\u81EA\u8EAB\u6307\u6807\u4E0E\u884C\u4E1A\u5747\u503C\u7684\u504F\u79BB\u7A0B\u5EA6）
        for metric_name in ['Sales', 'Net Profit', 'Cash']:
            industry_mean = derived[rnd].get(f'{metric_name}_\u884C\u4E1A\u5747\u503C')
            if industry_mean is not None and industry_mean != 0:
                deviations = {}
                for team in teams:
                    team_value = get_metric_with_priority(metrics_dict, metric_name, team)
                    if team_value is not None:
                        deviation = abs(team_value - industry_mean) / abs(industry_mean) * 100
                        deviations[team] = deviation
                if deviations:
                    derived[rnd][f'{metric_name}_\u6218\u7565\u504F\u79BB\u5EA6'] = deviations
    
    return derived


# ============================================================================
# Chapter 3: Self-Diagnosis
# ============================================================================

def calculate_financial_health(metrics_dict, teams):
    """Financial health traffic-light system"""
    health = {}
    
    for team in teams:
        health[team] = {
            'indicators': {},
            'status': {},
            'action_required': []
        }
        
        # 1. \u73B0\u91D1\u50A8\u5907
        cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        if cash > THRESHOLDS['Cash Reserve']['green']:
            status = '🟢'
        elif cash >= THRESHOLDS['Cash Reserve']['yellow']:
            status = '🟡'
        else:
            status = '🔴'
        
        health[team]['indicators']['Cash Reserve'] = cash
        health[team]['status']['Cash Reserve'] = status
        
        # 2. \u51C0\u503A\u52A1/\u6743\u76CA\u6BD4
        equity = get_metric_value(metrics_dict, 'Total Equity', team) or 0
        short_debt = get_metric_value(metrics_dict, 'Short-Term Debt', team) or 0
        long_debt = get_metric_value(metrics_dict, 'Long-Term Debt', team) or 0
        
        if equity > 0:
            net_debt = (short_debt + long_debt) - cash
            debt_equity_ratio = (net_debt / equity) * 100
            
            if debt_equity_ratio < THRESHOLDS['Net Debt to Equity']['green']:
                status = '🟢'
            elif debt_equity_ratio <= THRESHOLDS['Net Debt to Equity']['yellow']:
                status = '🟡'
            else:
                status = '🔴'
            
            health[team]['indicators']['Net Debt to Equity'] = debt_equity_ratio
            health[team]['status']['Net Debt to Equity'] = status
        else:
            health[team]['indicators']['Net Debt to Equity'] = None
            health[team]['status']['Net Debt to Equity'] = '🔴'
        
        # 3. EBITDA\u7387
        # \u4F18\u5148\u4F7F\u7528\u5168\u5C40\u6C47\u603B\u7684EBITDA，\u907F\u514D\u5339\u914D\u5230\u767E\u5206\u6BD4\u503C\u6216\u533A\u57DF\u503C
        # \u4F7F\u7528\u4F18\u5148\u7EA7\u5217\u8868\u5339\u914D，\u786E\u4FDD\u63D0\u53D6\u5230\u6B63\u786E\u7684\u5168\u5C40\u6C47\u603B\u503C
        ebitda = get_metric_value(metrics_dict, ['EBITDA', 'EBITDA', 'EBITDA'], team)
        
        # \u9A8C\u8BC1\u63D0\u53D6\u7684EBITDA\u503C\u662F\u5426\u5408\u7406
        if ebitda is None:
            ebitda = 0
        elif abs(ebitda) < 100:
            # \u503C\u592A\u5C0F（<100），\u53EF\u80FD\u662F\u767E\u5206\u6BD4，\u8BBE\u4E3A0
            ebitda = 0
        else:
            ebitda = ebitda or 0
        
        sales = get_metric_with_priority(metrics_dict, 'Sales', team) or 0
        
        if sales > 0:
            ebitda_rate = (ebitda / sales) * 100
            if ebitda_rate > THRESHOLDS['EBITDA Margin']['green']:
                status = '🟢'
            elif ebitda_rate >= THRESHOLDS['EBITDA Margin']['yellow']:
                status = '🟡'
            else:
                status = '🔴'
            
            health[team]['indicators']['EBITDA Margin'] = ebitda_rate
            health[team]['status']['EBITDA Margin'] = status
        else:
            health[team]['indicators']['EBITDA Margin'] = None
            health[team]['status']['EBITDA Margin'] = '🔴'
        
        # 4. \u6743\u76CA\u6BD4\u7387
        assets = get_metric_value(metrics_dict, 'Total Assets', team) or 0
        if assets > 0 and equity > 0:
            equity_ratio = (equity / assets) * 100
            if equity_ratio > THRESHOLDS['Equity Ratio']['green']:
                status = '🟢'
            elif equity_ratio >= THRESHOLDS['Equity Ratio']['yellow']:
                status = '🟡'
            else:
                status = '🔴'
            
            health[team]['indicators']['Equity Ratio'] = equity_ratio
            health[team]['status']['Equity Ratio'] = status
        else:
            health[team]['indicators']['Equity Ratio'] = None
            health[team]['status']['Equity Ratio'] = '🔴'
        
        # 5. \u7814\u53D1\u56DE\u62A5\u7387
        profit = get_metric_with_priority(metrics_dict, 'Net Profit', team) or 0
        rd_expense = get_metric_value(metrics_dict, 'R&D', team) or 0
        
        if rd_expense and rd_expense > 0 and profit is not None:
            rd_return = (profit / rd_expense) * 100
            if rd_return > THRESHOLDS['R&D Return']['green']:
                status = '🟢'
            elif rd_return >= THRESHOLDS['R&D Return']['yellow']:
                status = '🟡'
            else:
                status = '🔴'
            
            health[team]['indicators']['R&D Return'] = rd_return
            health[team]['status']['R&D Return'] = status
        else:
            health[team]['indicators']['R&D Return'] = None
            health[team]['status']['R&D Return'] = '🟡'  # \u65E0\u7814\u53D1\u6295\u5165
        
        # \u7EDF\u8BA1\u5E76\u751F\u6210\u884C\u52A8\u5EFA\u8BAE
        red_count = sum(1 for s in health[team]['status'].values() if '🔴' in str(s))
        yellow_count = sum(1 for s in health[team]['status'].values() if '🟡' in str(s))
        
        if red_count > 2:
            health[team]['action_required'].append('⚠️ \u7ACB\u5373\u8FDB\u5165\u751F\u5B58\u6A21\u5F0F（\u505C\u6B62\u6295\u8D44\u3001\u524A\u51CF\u6210\u672C）')
        elif yellow_count > 3 or red_count > 0:
            health[team]['action_required'].append('⚠️ \u53EC\u5F00\u7D27\u6025\u6218\u7565\u590D\u76D8\u4F1A')
        elif red_count == 0 and yellow_count <= 1:
            health[team]['action_required'].append('✅ \u53EF\u8003\u8651\u6FC0\u8FDB\u6269\u5F20')
    
    return health


def analyze_cash_flow_source(metrics_dict, teams, prev_metrics_dict):
    """Cash flow source analysis"""
    cash_flow = {}
    
    for team in teams:
        cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        prev_cash = get_metric_with_priority(prev_metrics_dict, 'Cash', team) or 0 if prev_metrics_dict else 0
        cash_change = cash - prev_cash
        
        # \u4FEE\u590D：\u786E\u4FDD\u80FD\u63D0\u53D6\u5230EBITDA\u503C（\u4F18\u5148\u4F7F\u7528\u5168\u5C40\u6C47\u603B，\u907F\u514D\u767E\u5206\u6BD4\u503C）
        ebitda = get_metric_value(metrics_dict, ['EBITDA', 'EBITDA', 'EBITDA'], team)
        if ebitda is None or (ebitda is not None and abs(ebitda) < 100):
            ebitda = 0
        else:
            ebitda = ebitda or 0
        
        if ebitda > 100000:
            cash_type = 'A. \u7ECF\u8425\u9A71\u52A8\u578B（\u5065\u5EB7）'
            description = f'\u7ECF\u8425\u73B0\u91D1\u6D41+${ebitda/1000:.0f}k → \u53EF\u6269\u5F20'
        elif cash_change > 0 and abs(ebitda) < abs(cash_change) * 0.5:
            cash_type = 'B. \u878D\u8D44\u9A71\u52A8\u578B（\u5371\u9669）'
            description = '\u878D\u8D44\u73B0\u91D1\u6D41\u4E3A\u4E3B\u8981\u6765\u6E90 → \u4E0D\u53EF\u6301\u7EED'
        else:
            cash_type = 'C. \u6295\u8D44\u6D88\u8017\u578B（\u8FC7\u6E21\u671F）'
            description = '\u6295\u8D44\u73B0\u91D1\u6D41\u6D88\u8017\u73B0\u91D1 → \u5173\u6CE8\u4E0B\u56DE\u5408\u56DE\u62A5'
        
        cash_flow[team] = {
            '\u73B0\u91D1\u53D8\u5316': cash_change,
            '\u7ECF\u8425\u73B0\u91D1\u6D41(EBITDA)': ebitda,
            '\u73B0\u91D1\u6D41\u7C7B\u578B': cash_type,
            '\u63CF\u8FF0': description
        }
    
    return cash_flow


def analyze_regional_market(all_rounds_data, teams, round_name):
    """Regional performance analysis (proxy mode)
    
    Note: regional sales in Excel are limited or tiny (about 0.05%-0.65% of total).
    \u533A\u57DF\u5E02\u573A\u5206\u6790\u529F\u80FD\u53D7\u9650\u3002\u5F53\u524D\u4F7F\u7528"\u7F8E\u56FD"\u3001"\u4E9A\u6D32"\u3001"\u6B27\u6D32"\u6307\u6807\u4F5C\u4E3A\u66FF\u4EE3，
    Their meaning may differ from true regional sales.
    """
    regional_performance = {}
    regions = ['USA', 'Asia', 'Europe']
    
    metrics_dict = all_rounds_data[round_name]
    
    # \u8BA1\u7B97\u6BCF\u4E2A\u533A\u57DF\u6240\u6709\u961F\u4F0D\u7684\u9500\u552E\u989D
    # \u4FEE\u590D：\u533A\u57DF\u9500\u552E\u989D\u6307\u6807\u540D\u76F4\u63A5\u4F7F\u7528\u533A\u57DF\u540D（"\u7F8E\u56FD"\u3001"\u4E9A\u6D32"\u3001"\u6B27\u6D32"），\u800C\u4E0D\u662F"\u5728{region}\u9500\u552E"
    region_total_sales = {}
    for region in regions:
        total = 0
        region_sales = {}
        for team in teams:
            # \u4F18\u5148\u7EA7：1. \u76F4\u63A5\u533A\u57DF\u540D 2. "\u5728{region}\u9500\u552E" 3. "{region}\u9500\u552E\u989D"
            sales = get_metric_value(metrics_dict, region, team)
            if sales is None or sales == 0:
                # \u5C1D\u8BD5\u5176\u4ED6\u547D\u540D\u65B9\u5F0F
                sales = get_metric_value(metrics_dict, f'\u5728{region}\u9500\u552E', team)
            if sales is None or sales == 0:
                sales = get_metric_value(metrics_dict, f'{region}\u9500\u552E\u989D', team)
            
            # \u53EA\u7EDF\u8BA1\u6709\u9500\u552E\u989D\u7684\u961F\u4F0D，\u4E14\u9500\u552E\u989D\u5FC5\u987B>0
            if sales is not None and sales > 0:
                region_sales[team] = sales
                total += sales
        region_total_sales[region] = {'total': total, 'team_sales': region_sales}
    
    # \u8BA1\u7B97\u9500\u552E\u8D8B\u52BF（\u5BF9\u6BD4\u4E0A\u56DE\u5408）
    rounds = get_rounds_order(all_rounds_data)
    round_idx = rounds.index(round_name) if round_name in rounds else -1
    prev_round = rounds[round_idx - 1] if round_idx > 0 else None
    
    for team in teams:
        regional_performance[team] = {}
        
        for region in regions:
            # \u4FEE\u590D：\u533A\u57DF\u9500\u552E\u989D\u6307\u6807\u540D\u76F4\u63A5\u4F7F\u7528\u533A\u57DF\u540D，\u4F18\u5148\u7EA7\u5339\u914D
            sales = get_metric_value(metrics_dict, region, team)
            if sales is None or sales == 0:
                sales = get_metric_value(metrics_dict, f'\u5728{region}\u9500\u552E', team)
            if sales is None or sales == 0:
                sales = get_metric_value(metrics_dict, f'{region}\u9500\u552E\u989D', team)
            # \u5904\u7406None\u503C，\u7EDF\u4E00\u4E3A0
            if sales is None:
                sales = 0
            
            # \u8BA1\u7B97\u5E02\u573A\u4EFD\u989D（\u66FF\u4EE3\u65B9\u6848）
            # \u4FEE\u590D：\u53EA\u6709\u9500\u552E\u989D>0\u65F6\u624D\u8BA1\u7B97\u5E02\u573A\u4EFD\u989D\u548C\u6392\u540D
            market_share = None
            ranking = None
            
            if sales is not None and sales > 0:
                if region_total_sales[region]['total'] > 0:
                    market_share = (sales / region_total_sales[region]['total']) * 100
                
                # \u8BA1\u7B97\u6392\u540D（\u53EA\u6709\u9500\u552E\u989D>0\u7684\u961F\u4F0D\u624D\u6392\u540D）
                team_sales = region_total_sales[region]['team_sales']
                if team_sales and sales in team_sales.values():
                    sorted_teams = sorted(team_sales.items(), key=lambda x: x[1], reverse=True)
                    for rank, (t, _) in enumerate(sorted_teams, 1):
                        if t == team:
                            ranking = rank
                            break
            
            # \u8BA1\u7B97\u9500\u552E\u8D8B\u52BF（\u5982\u679C\u6570\u636E\u53EF\u7528）
            sales_trend = '\u7A33\u5B9A'
            if prev_round and prev_round in all_rounds_data:
                prev_metrics = all_rounds_data[prev_round]
                prev_sales = get_metric_value(prev_metrics, region, team)
                if prev_sales is None or prev_sales == 0:
                    prev_sales = get_metric_value(prev_metrics, f'\u5728{region}\u9500\u552E', team)
                if prev_sales is None or prev_sales == 0:
                    prev_sales = get_metric_value(prev_metrics, f'{region}\u9500\u552E\u989D', team)
                if prev_sales is None:
                    prev_sales = 0
                if prev_sales > 0:
                    growth_rate = ((sales - prev_sales) / prev_sales) * 100
                    if growth_rate > 10:
                        sales_trend = '\u589E\u957F'
                    elif growth_rate < -10:
                        sales_trend = '\u4E0B\u964D'
                    else:
                        sales_trend = '\u7A33\u5B9A'
                elif sales > 0:
                    sales_trend = '\u65B0\u8FDB\u5165'
            
            # \u7B56\u7565\u5EFA\u8BAE（\u8003\u8651\u6392\u540D\u548C\u8D8B\u52BF）
            suggestions = []
            if sales > 0:  # \u53EA\u5728\u6709\u9500\u552E\u989D\u65F6\u7ED9\u51FA\u5EFA\u8BAE
                if ranking and ranking <= 3:
                    if sales_trend == '\u589E\u957F':
                        suggestions.append('\u5DE9\u56FA\u4F18\u52BF，\u8003\u8651\u63D0\u4EF7')
                    elif sales_trend == '\u7A33\u5B9A':
                        suggestions.append('\u589E\u52A0\u529F\u80FD\u6216\u5E7F\u544A\u6295\u5165')
                    elif sales_trend == '\u4E0B\u964D':
                        suggestions.append('\u5206\u6790\u539F\u56E0，\u8C03\u6574\u7B56\u7565')
                elif ranking and 4 <= ranking <= 8:
                    if sales_trend == '\u589E\u957F':
                        suggestions.append('\u52A0\u5927\u6295\u5165，\u62A2\u5360\u4EFD\u989D')
                    elif sales_trend == '\u4E0B\u964D':
                        suggestions.append('\u8BC4\u4F30\u9000\u51FA\u6216\u5DEE\u5F02\u5316')
                elif ranking and ranking > 8:
                    suggestions.append('\u9000\u51FA\u6216\u5927\u5E45\u8C03\u6574\u7B56\u7565')
            
            regional_performance[team][region] = {
                'Sales': sales,
                '\u5E02\u573A\u4EFD\u989D': market_share,
                '\u6392\u540D': ranking,
                '\u9500\u552E\u8D8B\u52BF': sales_trend,
                '\u7B56\u7565\u5EFA\u8BAE': suggestions
            }
    
    return regional_performance


# ============================================================================
# Chapter 4: Competitive Decoding
# ============================================================================

def calculate_competitive_position(metrics_dict, teams):
    """Three-dimensional benchmark matrix"""
    competitive_matrix = {}
    
    for team in teams:
        equity = get_metric_value(metrics_dict, 'Total Equity', team) or 0
        short_debt = get_metric_value(metrics_dict, 'Short-Term Debt', team) or 0
        long_debt = get_metric_value(metrics_dict, 'Long-Term Debt', team) or 0
        cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        sales = get_metric_with_priority(metrics_dict, 'Sales', team) or 0
        rd_expense = get_metric_value(metrics_dict, 'R&D', team) or 0
        ad_expense = get_metric_value(metrics_dict, 'Advertising', team) or 0
        profit = get_metric_with_priority(metrics_dict, 'Net Profit', team) or 0
        
        # 1. \u8D22\u52A1\u6FC0\u8FDB\u5EA6
        if equity > 0:
            net_debt = (short_debt + long_debt) - cash
            financial_aggressiveness = (net_debt / equity) * 100
        else:
            financial_aggressiveness = 999
        
        # 2. \u5E02\u573A\u4FB5\u7565\u6027
        market_aggressiveness = (ad_expense / sales * 100) if sales > 0 else 0
        
        # 3. \u6280\u672F\u6295\u5165\u5EA6
        tech_investment = (rd_expense / sales * 100) if sales > 0 else 0
        
        # \u7B56\u7565\u7C7B\u578B\u8BC6\u522B
        strategy_type = '\u672A\u77E5'
        if tech_investment > 20 and rd_expense > 0:
            ros = (profit / sales * 100) if sales > 0 else 0
            if ros > 20:
                strategy_type = '\u6218\u7565\u6E05\u6670（\u9AD8\u6295\u5165+\u9AD8\u56DE\u62A5）'
            else:
                strategy_type = '\u7B56\u7565\u8BD5\u9519（\u9AD8\u6295\u5165+\u4F4E\u56DE\u62A5）'
        elif tech_investment < 1 and profit and profit > 0:
            strategy_type = '\u5E02\u573A\u5957\u5229（\u96F6\u7814\u53D1+\u9AD8\u5229\u6DA6）'
        elif tech_investment < 5 and market_aggressiveness < 5:
            strategy_type = 'Steady Operations'
        
        competitive_matrix[team] = {
            'Financial Aggressiveness': financial_aggressiveness,
            'Market Aggressiveness': market_aggressiveness,
            'Technology Investment Intensity': tech_investment,
            'Strategy Type': strategy_type
        }
    
    return competitive_matrix


def detect_strategy_changes(all_rounds_data, teams):
    """Strategy shift detection"""
    changes = {}
    rounds = get_rounds_order(all_rounds_data)
    
    for team in teams:
        changes[team] = {
            'alerts': [],
            'changes': {}
        }
        
        for i in range(len(rounds) - 1):
            rnd1, rnd2 = rounds[i], rounds[i + 1]
            
            if rnd1 not in all_rounds_data or rnd2 not in all_rounds_data:
                continue
            
            metrics1 = all_rounds_data[rnd1]
            metrics2 = all_rounds_data[rnd2]
            
            # 1. \u73B0\u91D1\u5F02\u5E38\u6CE2\u52A8
            cash1 = get_metric_with_priority(metrics1, 'Cash', team) or 0
            cash2 = get_metric_with_priority(metrics2, 'Cash', team) or 0
            cash_change = abs(cash2 - cash1)
            
            if cash_change > 500000:
                changes[team]['alerts'].append({
                    'type': '\u73B0\u91D1\u5F02\u5E38\u6CE2\u52A8',
                    'round': f'{rnd1}→{rnd2}',
                    'value': cash_change,
                    'interpretation': '\u53EF\u80FD\u878D\u8D44/\u51FA\u552E\u8D44\u4EA7' if cash2 > cash1 else '\u53EF\u80FD\u5927\u5E45\u6295\u8D44/\u4E8F\u635F'
                })
            
            # 2. \u6218\u7565\u7A33\u5B9A\u6027\u6307\u6570
            # \u4F7F\u7528\u4F18\u5148\u7EA7\u5217\u8868\u5339\u914DEBITDA，\u786E\u4FDD\u63D0\u53D6\u5230\u5168\u5C40\u6C47\u603B\u503C
            ebitda1 = get_metric_value(metrics1, ['EBITDA', 'EBITDA', 'EBITDA'], team)
            if ebitda1 is None or (ebitda1 is not None and abs(ebitda1) < 100):
                ebitda1 = 0
            else:
                ebitda1 = ebitda1 or 0
            
            ebitda2 = get_metric_value(metrics2, ['EBITDA', 'EBITDA', 'EBITDA'], team)
            if ebitda2 is None or (ebitda2 is not None and abs(ebitda2) < 100):
                ebitda2 = 0
            else:
                ebitda2 = ebitda2 or 0
            rd1 = get_metric_value(metrics1, 'R&D', team) or 0
            rd2 = get_metric_value(metrics2, 'R&D', team) or 0
            assets1 = get_metric_value(metrics1, 'Total Assets', team) or 0
            
            if assets1 > 0:
                stability_index = 1 - (abs(ebitda2 - ebitda1) + abs(rd2 - rd1)) / assets1
                if stability_index < 0.3:
                    changes[team]['alerts'].append({
                        'type': '\u6218\u7565\u7A33\u5B9A\u6027\u4F4E',
                        'round': f'{rnd1}→{rnd2}',
                        'value': stability_index,
                        'interpretation': '\u7B56\u7565\u53D8\u5316\u5267\u70C8，\u9700\u91CD\u70B9\u5173\u6CE8'
                    })
    
    return changes


def detect_region_entry(all_rounds_data, teams):
    """
    Detect regional entry using sales as proxy
    From methodology section 4.2.2
    """
    region_entry_alerts = {}
    rounds = get_rounds_order(all_rounds_data)
    regions = ['USA', 'Asia', 'Europe']
    
    for team in teams:
        region_entry_alerts[team] = []
        
        for region in regions:
            prev_sales = 0
            
            for rnd in rounds:
                if rnd in all_rounds_data:
                    metrics_dict_rnd = all_rounds_data[rnd]
                    # \u4FEE\u590D：\u533A\u57DF\u9500\u552E\u989D\u6307\u6807\u540D\u76F4\u63A5\u4F7F\u7528\u533A\u57DF\u540D，\u4F18\u5148\u7EA7\u5339\u914D
                    current_sales = get_metric_value(metrics_dict_rnd, region, team) or 0
                    if (current_sales is None or current_sales == 0):
                        current_sales = get_metric_value(metrics_dict_rnd, f'\u5728{region}\u9500\u552E', team) or 0
                    if (current_sales is None or current_sales == 0):
                        current_sales = get_metric_value(metrics_dict_rnd, f'{region}\u9500\u552E\u989D', team) or 0
                    
                    if prev_sales == 0 and current_sales and current_sales > 10000:  # \u4ECE\u65E0\u5230\u6709，\u9500\u552E\u989D>10k
                        region_entry_alerts[team].append({
                            'region': region,
                            'round': rnd,
                            'sales': current_sales,
                            'interpretation': f'\u65B0\u8FDB\u5165{region}\u5E02\u573A'
                        })
                    prev_sales = current_sales or 0
    
    return region_entry_alerts


def predict_next_move(all_rounds_data, teams, round_name, derived_metrics):
    """Next-round intent prediction"""
    predictions = {}
    metrics_dict = all_rounds_data[round_name]
    derived = derived_metrics.get(round_name, {})
    
    for team in teams:
        signals = []
        
        cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        sales_growth = derived.get('\u9500\u552E\u989D_\u73AF\u6BD4\u589E\u957F', {}).get(team, 0)
        sales_rank = derived.get('\u9500\u552E\u989D_\u6392\u540D', {}).get(team, 999)
        rd_expense = get_metric_value(metrics_dict, 'R&D', team) or 0
        
        equity = get_metric_value(metrics_dict, 'Total Equity', team) or 0
        short_debt = get_metric_value(metrics_dict, 'Short-Term Debt', team) or 0
        long_debt = get_metric_value(metrics_dict, 'Long-Term Debt', team) or 0
        
        # \u4FEE\u590D：\u786E\u4FDD\u80FD\u63D0\u53D6\u5230EBITDA\u503C（\u4F18\u5148\u4F7F\u7528\u5168\u5C40\u6C47\u603B，\u907F\u514D\u767E\u5206\u6BD4\u503C）
        ebitda = get_metric_value(metrics_dict, ['EBITDA', 'EBITDA', 'EBITDA'], team)
        if ebitda is None or (ebitda is not None and abs(ebitda) < 100):
            ebitda = 0
        else:
            ebitda = ebitda or 0
        
        if equity > 0:
            net_debt = (short_debt + long_debt) - cash
            debt_equity_ratio = (net_debt / equity) * 100
        else:
            debt_equity_ratio = 999
        
        # \u6269\u4EA7\u4FE1\u53F7
        if cash > 300000 and sales_growth > 10:
            signals.append({
                'action': 'Capacity Expansion',
                'probability': 70,
                'reason': '\u73B0\u91D1\u5145\u8DB3+\u9500\u552E\u589E\u957F'
            })
        
        # \u4EF7\u683C\u6218\u4FE1\u53F7
        if cash > 500000 and sales_rank > 8:
            signals.append({
                'action': 'Price War',
                'probability': 60,
                'reason': '\u73B0\u91D1\u5145\u8DB3+\u6392\u540D\u9760\u540E'
            })
        
        # \u6280\u672F\u6295\u5165\u4FE1\u53F7
        if rd_expense > 400000:
            signals.append({
                'action': 'Technology Investment',
                'probability': 75,
                'reason': '\u7814\u53D1\u6295\u5165\u5927，\u53EF\u80FD\u63A8\u51FA\u65B0\u6280\u672F'
            })
        
        # \u8D22\u52A1\u5371\u673A\u4FE1\u53F7
        if debt_equity_ratio > 100 and ebitda is not None and ebitda < 0:
            signals.append({
                'action': 'Asset Sale/Exit',
                'probability': 80,
                'reason': '\u8D22\u52A1\u5371\u673A（\u9AD8\u8D1F\u503A+\u8D1FEBITDA）'
            })
        
        # \u73B0\u91D1\u5371\u673A\u4FE1\u53F7
        if cash < 50000 and debt_equity_ratio > 70:
            signals.append({
                'action': 'Emergency Financing',
                'probability': 85,
                'reason': '\u73B0\u91D1\u4E0D\u8DB3+\u9AD8\u8D1F\u503A'
            })
        
        predictions[team] = signals
    
    return predictions


# ============================================================================
# Chapter 5: Decision Support
# ============================================================================

def generate_strategy_recommendations(health_data, cash_flow_data, competitive_matrix, 
                                     derived_metrics, latest_round, teams):
    """
    Generate next-round strategy recommendations (allocation tree)
    Based on methodology section 5.2
    """
    recommendations = {}
    
    for team in teams:
        health = health_data.get(team, {})
        cash_flow = cash_flow_data.get(team, {})
        comp_pos = competitive_matrix.get(team, {})
        
        cash = health.get('indicators', {}).get('Cash Reserve', 0) or 0
        derived = derived_metrics.get(latest_round, {})
        sales_growth = derived.get('\u9500\u552E\u989D_\u73AF\u6BD4\u589E\u957F', {}).get(team, 0)
        sales_rank = derived.get('\u9500\u552E\u989D_\u6392\u540D', {}).get(team, 999)
        
        recommendation = {
            'mode': '',
            'actions': [],
            'resource_allocation': {},
            'risk_level': ''
        }
        
        # \u8D44\u6E90\u5206\u914D\u51B3\u7B56\u6811
        if cash < 100000:
            # \u751F\u5B58\u6A21\u5F0F
            recommendation['mode'] = '\u751F\u5B58\u6A21\u5F0F'
            recommendation['actions'] = [
                '\u505C\u6B62\u6240\u6709\u6295\u8D44',
                '\u51FA\u552E\u95F2\u7F6E\u4EA7\u80FD',
                '\u524A\u51CF\u975E\u5FC5\u8981\u8D39\u7528'
            ]
            recommendation['resource_allocation'] = {
                'R&D': 0,
                'Advertising': 0,
                '\u73B0\u91D1\u4FDD\u7559': 100
            }
            recommendation['risk_level'] = '\u9AD8'
        elif cash < 300000:
            # \u7EF4\u6301\u6A21\u5F0F
            recommendation['mode'] = '\u7EF4\u6301\u6A21\u5F0F'
            recommendation['actions'] = [
                '\u4EC5\u5FC5\u8981\u5E7F\u544A\u6295\u5165',
                '\u7EF4\u6301\u73B0\u6709\u4EA7\u80FD',
                '\u4FDD\u7559\u73B0\u91D1\u7F13\u51B2'
            ]
            recommendation['resource_allocation'] = {
                'R&D': 10,
                'Advertising': 20,
                '\u73B0\u91D1\u4FDD\u7559': 70
            }
            recommendation['risk_level'] = '\u4E2D'
        else:
            # \u8FDB\u653B\u6A21\u5F0F
            recommendation['mode'] = '\u8FDB\u653B\u6A21\u5F0F'
            actions = []
            allocation = {}
            total_allocated = 0
            cash_reserve_pct = 20  # \u4FDD\u755920%\u73B0\u91D1\u4F5C\u4E3A\u98CE\u9669\u7F13\u51B2
            
            # \u6839\u636E\u6761\u4EF6\u52A8\u6001\u5206\u914D\u8D44\u6E90（\u786E\u4FDD\u603B\u548C\u4E0D\u8D85\u8FC7100%-\u73B0\u91D1\u4FDD\u7559）
            max_available = 100 - cash_reserve_pct
            
            if sales_growth > 10:
                actions.append('\u9500\u552E\u589E\u957F>10% → \u8003\u8651\u6269\u4EA7')
                if total_allocated < max_available:
                    expand_pct = min(40, max_available - total_allocated)  # \u964D\u4F4E\u523040%
                    allocation['Capacity Expansion'] = expand_pct
                    total_allocated += expand_pct
            
            if comp_pos.get('Technology Investment Intensity', 0) < 5 and total_allocated < max_available:
                actions.append('\u6280\u672F\u7A7A\u767D\u5E02\u573A → \u7814\u53D1+\u8FDB\u5165')
                rd_pct = min(30, max_available - total_allocated)  # \u964D\u4F4E\u523030%
                allocation['R&D'] = rd_pct
                total_allocated += rd_pct
            
            if sales_rank <= 3 and total_allocated < max_available:
                actions.append('\u4EFD\u989D\u9886\u5148 → \u589E\u52A0\u5E7F\u544A\u5DE9\u56FA')
                ad_pct = min(30, max_available - total_allocated)
                allocation['Advertising'] = ad_pct
                total_allocated += ad_pct
            
            # \u5982\u679C\u6CA1\u6709\u5176\u4ED6\u5206\u914D，\u9ED8\u8BA4\u5206\u914D\u5269\u4F59\u8D44\u6E90\u5230\u5E7F\u544A
            if not allocation and max_available > 0:
                actions.append('\u7EF4\u6301\u5F53\u524D\u7B56\u7565，\u9002\u5EA6\u6295\u8D44')
                allocation['Advertising'] = min(20, max_available)  # \u964D\u4F4E\u523020%
                total_allocated += allocation['Advertising']
            
            # \u786E\u4FDD\u603B\u548C\u4E0D\u8D85\u8FC7100%，\u5C06\u5269\u4F59\u90E8\u5206\u5206\u914D\u7ED9\u73B0\u91D1\u4FDD\u7559
            remaining = max_available - total_allocated
            allocation['\u73B0\u91D1\u4FDD\u7559'] = cash_reserve_pct + max(0, remaining)
            
            # \u6700\u7EC8\u9A8C\u8BC1：\u5982\u679C\u603B\u548C\u8D85\u8FC7100%，\u6309\u6BD4\u4F8B\u7F29\u51CF
            total = sum(v for v in allocation.values() if isinstance(v, (int, float)))
            if total > 100:
                scale = 100 / total
                for key in allocation:
                    if isinstance(allocation[key], (int, float)):
                        allocation[key] = allocation[key] * scale
            
            if not actions:
                actions.append('\u7EF4\u6301\u5F53\u524D\u7B56\u7565，\u89C2\u5BDF\u5BF9\u624B\u52A8\u6001')
            
            recommendation['actions'] = actions
            recommendation['resource_allocation'] = allocation
            recommendation['risk_level'] = '\u4F4E'
        
        recommendations[team] = recommendation
    
    return recommendations


def generate_checklist(health_data, regional_data, strategy_changes, teams, latest_round):
    """
    Generate core checklist
    Based on methodology section 5.3
    """
    checklist = {}
    
    for team in teams:
        health = health_data.get(team, {})
        regional = regional_data.get(team, {})
        changes = strategy_changes.get(team, {})
        
        indicators = health.get('indicators', {})
        statuses = health.get('status', {})
        
        cash = indicators.get('Cash Reserve', 0) or 0
        debt_equity = indicators.get('Net Debt to Equity') or 0
        red_count = sum(1 for s in statuses.values() if '🔴' in str(s))
        
        checks = {
            '\u8D22\u52A1\u5065\u5EB7': [],
            '\u5E02\u573A\u7B56\u7565': [],
            '\u7ADE\u4E89\u6001\u52BF': [],
            '\u98CE\u9669\u63A7\u5236': []
        }
        
        # \u8D22\u52A1\u5065\u5EB7\u68C0\u67E5
        if cash >= 300000:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('✅ \u73B0\u91D1\u50A8\u5907\u8986\u76D63\u4E2A\u56DE\u5408\u7684\u4E8F\u635F')
        else:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('❌ \u73B0\u91D1\u50A8\u5907\u4E0D\u8DB3（\u9700\u8981≥$300k）')
        
        if red_count >= 2:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('❌ \u8D22\u52A1\u5065\u5EB7\u5EA6\u67092\u4E2A\u4EE5\u4E0A\u7EA2\u706F')
        else:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('✅ \u8D22\u52A1\u5065\u5EB7\u5EA6\u826F\u597D')
        
        if debt_equity and debt_equity < 70:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('✅ \u51C0\u503A\u52A1/\u6743\u76CA\u6BD4\u5728\u5B89\u5168\u8303\u56F4')
        else:
            checks['\u8D22\u52A1\u5065\u5EB7'].append('❌ \u51C0\u503A\u52A1/\u6743\u76CA\u6BD4\u8FC7\u9AD8（\u9700\u8981<70%）')
        
        # \u5E02\u573A\u7B56\u7565\u68C0\u67E5
        has_sales = False
        top_3_count = 0
        for region in ['USA', 'Asia', 'Europe']:
            rp = regional.get(region, {})
            if rp.get('Sales', 0) > 0:
                has_sales = True
            if rp.get('\u6392\u540D') and rp['\u6392\u540D'] <= 3:
                top_3_count += 1
        
        if has_sales:
            checks['\u5E02\u573A\u7B56\u7565'].append('✅ \u6709\u533A\u57DF\u9500\u552E\u989D')
        else:
            checks['\u5E02\u573A\u7B56\u7565'].append('⚠️ \u533A\u57DF\u9500\u552E\u989D\u4E3A\u96F6')
        
        if top_3_count > 0:
            checks['\u5E02\u573A\u7B56\u7565'].append(f'✅ {top_3_count}\u4E2A\u533A\u57DF\u6392\u540D\u524D3')
        else:
            checks['\u5E02\u573A\u7B56\u7565'].append('⚠️ \u4E3B\u8981\u5E02\u573A\u6392\u540D\u672A\u8FDB\u524D3')
        
        # \u7ADE\u4E89\u6001\u52BF\u68C0\u67E5
        alerts = changes.get('alerts', [])
        if alerts:
            checks['\u7ADE\u4E89\u6001\u52BF'].append(f'⚠️ \u68C0\u6D4B\u5230{len(alerts)}\u4E2A\u7B56\u7565\u7A81\u53D8\u8B66\u62A5')
        else:
            checks['\u7ADE\u4E89\u6001\u52BF'].append('✅ \u5BF9\u624B\u7B56\u7565\u7A33\u5B9A')
        
        # \u98CE\u9669\u63A7\u5236\u68C0\u67E5
        if cash >= 300000 * 0.2:  # \u81F3\u5C1120%\u7684\u98CE\u9669\u7F13\u51B2
            checks['\u98CE\u9669\u63A7\u5236'].append('✅ \u4FDD\u7559\u81F3\u5C1120%\u73B0\u91D1\u4F5C\u4E3A\u98CE\u9669\u7F13\u51B2')
        else:
            checks['\u98CE\u9669\u63A7\u5236'].append('❌ \u98CE\u9669\u7F13\u51B2\u4E0D\u8DB3')
        
        checks['\u98CE\u9669\u63A7\u5236'].append('✅ \u5DF2\u8003\u8651\u6700\u574F\u60C5\u666F')
        checks['\u98CE\u9669\u63A7\u5236'].append('✅ \u7B56\u7565\u5177\u6709\u7075\u6D3B\u6027')
        
        checklist[team] = checks
    
    return checklist


# ============================================================================
# Report generation
# ============================================================================

def generate_comprehensive_report(all_rounds_data, teams, health_data, cash_flow_data, 
                                  regional_data, competitive_matrix, strategy_changes,
                                  predictions, derived_metrics, anomalies, latest_round,
                                  strategy_recommendations=None, checklist=None, region_entry_alerts=None):
    """Generate comprehensive analysis report"""
    report = []
    
    report.append("# \u4F01\u4E1A\u6A21\u62DF\u7ECF\u8425\u6218\u62A5\u5206\u6790\u62A5\u544A（\u6309\u65B9\u6CD5\u8BBA3.0）\n")
    report.append(f"\u751F\u6210\u65F6\u95F4：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("\u57FA\u4E8E\u65B9\u6CD5\u8BBA\u6587\u68633.0\u7248\u672C\u8FDB\u884C\u5B8C\u6574\u5206\u6790\n")
    report.append("=" * 80 + "\n")
    
    # \u4E00\u3001\u6267\u884C\u6458\u8981
    report.append("\n## \u4E00\u3001\u6267\u884C\u6458\u8981\n")
    
    # \u627E\u51FA\u9886\u5148\u961F\u4F0D\u548C\u5173\u952E\u6307\u6807
    sales_rankings = derived_metrics.get(latest_round, {}).get('\u9500\u552E\u989D_\u6392\u540D', {})
    metrics_dict = all_rounds_data[latest_round]
    
    if sales_rankings:
        top_teams = sorted(sales_rankings.items(), key=lambda x: x[1])[:3]
        report.append("### \u5F53\u524D\u56DE\u5408\u9500\u552E\u989D\u6392\u540DTOP3：\n")
        for rank, (team, position) in enumerate(top_teams, 1):
            # \u83B7\u53D6\u5173\u952E\u6307\u6807
            profit = get_metric_with_priority(metrics_dict, 'Net Profit', team) or 0
            cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
            # \u786E\u5B9A\u4E0A\u4E00\u56DE\u5408（\u7528\u4E8E\u8BA1\u7B97\u73AF\u6BD4\u589E\u957F\u7387）
            rounds_order = get_rounds_order(all_rounds_data)
            latest_idx = rounds_order.index(latest_round) if latest_round in rounds_order else -1
            prev_round = rounds_order[latest_idx - 1] if latest_idx > 0 else None
            if prev_round and prev_round in all_rounds_data:
                prev_profit = get_metric_with_priority(all_rounds_data[prev_round], 'Net Profit', team) or 0
                if prev_profit != 0:
                    profit_growth = ((profit - prev_profit) / abs(prev_profit)) * 100
                else:
                    profit_growth = 0
            else:
                profit_growth = 0
            
            report.append(f"{rank}. **{team}**（\u6392\u540D：\u7B2C{position}\u4F4D）\n")
            report.append(f"   - \u51C0\u5229\u6DA6：${profit/1000:.0f}k（\u73AF\u6BD4{profit_growth:+.1f}%）\n")
            report.append(f"   - \u73B0\u91D1：${cash/1000:.0f}k\n")
    
    # \u6838\u5FC3\u95EE\u9898\u8BC6\u522B
    report.append("\n### \u5173\u952E\u53D1\u73B0：\n")
    
    # \u8BC6\u522B\u9AD8\u98CE\u9669\u961F\u4F0D
    high_risk_teams = []
    for team, health in health_data.items():
        red_count = sum(1 for s in health.get('status', {}).values() if '🔴' in str(s))
        if red_count >= 2:
            high_risk_teams.append(team)
    
    if high_risk_teams:
        report.append(f"- ⚠️ **\u9AD8\u98CE\u9669\u961F\u4F0D**：{', '.join(high_risk_teams[:5])}（\u8D22\u52A1\u5065\u5EB7\u5EA6\u67092\u4E2A\u4EE5\u4E0A\u7EA2\u706F）\n")
    
    # \u8BC6\u522B\u7B56\u7565\u7A81\u53D8
    strategy_change_teams = []
    for team, changes in strategy_changes.items():
        if changes.get('alerts'):
            strategy_change_teams.append(team)
    
    if strategy_change_teams:
        report.append(f"- 🔄 **\u7B56\u7565\u7A81\u53D8\u961F\u4F0D**：{', '.join(strategy_change_teams[:3])}（\u9700\u91CD\u70B9\u5173\u6CE8）\n")
    
    # \u4E8C\u3001\u6570\u636E\u57FA\u7840\u5EFA\u8BBE
    report.append("\n\n## \u4E8C\u3001\u6570\u636E\u57FA\u7840\u5EFA\u8BBE\n")
    
    report.append("### 2.1 \u6570\u636E\u5B8C\u6574\u6027\u9A8C\u8BC1\n")
    validation_issues = validate_data_integrity(all_rounds_data[latest_round], teams)
    if validation_issues:
        report.append("\u53D1\u73B0\u4EE5\u4E0B\u95EE\u9898：\n")
        for issue in validation_issues[:5]:  # \u53EA\u663E\u793A\u524D5\u4E2A
            report.append(f"- {issue['team']}: \u8BEF\u5DEE{issue['error_rate']:.2f}% - {issue['status']}\n")
    else:
        report.append("✅ \u6570\u636E\u5B8C\u6574\u6027\u9A8C\u8BC1\u901A\u8FC7\n")
    
    report.append("\n### 2.2 Anomaly detection\n")
    if anomalies:
        for team, anomaly_list in list(anomalies.items())[:5]:
            report.append(f"\n**{team}**：\n")
            for anomaly in anomaly_list:
                report.append(f"- {anomaly['type']}: {anomaly['value']:,.0f} ({anomaly['rule']})\n")
    else:
        report.append("✅ \u672A\u53D1\u73B0\u5F02\u5E38\u503C\n")
    
    # \u4E09\u3001\u81EA\u8EAB\u8BCA\u65AD\u5206\u6790
    report.append("\n\n## \u4E09\u3001\u81EA\u8EAB\u8BCA\u65AD\u5206\u6790\n")
    
    report.append("### 3.1 Financial health traffic-light system\n")
    report.append("| \u961F\u4F0D | \u73B0\u91D1\u50A8\u5907 | \u51C0\u503A\u52A1/\u6743\u76CA\u6BD4 | EBITDA\u7387 | \u6743\u76CA\u6BD4\u7387 | \u7814\u53D1\u56DE\u62A5\u7387 | \u884C\u52A8\u5EFA\u8BAE |")
    report.append("|------|---------|--------------|---------|---------|-----------|---------|")
    
    for team in teams:
        h = health_data.get(team, {})
        indicators = h.get('indicators', {})
        statuses = h.get('status', {})
        
        cash_val = f"${indicators.get('Cash Reserve', 0)/1000:.0f}k" if indicators.get('Cash Reserve') is not None else "N/A"
        cash_status = statuses.get('Cash Reserve', 'N/A')
        
        debt_val = f"{indicators.get('Net Debt to Equity', 0):.1f}%" if indicators.get('Net Debt to Equity') is not None else "N/A"
        debt_status = statuses.get('Net Debt to Equity', 'N/A')
        
        # \u4FEE\u590D：EBITDA\u7387\u663E\u793A\u7CBE\u5EA6，\u5F53\u503C\u5F88\u5C0F\u65F6\u663E\u793A\u66F4\u591A\u5C0F\u6570\u4F4D
        ebitda_rate = indicators.get('EBITDA Margin')
        if ebitda_rate is not None:
            if ebitda_rate < 0.1:
                ebitda_val = f"{ebitda_rate:.4f}%"
            else:
                ebitda_val = f"{ebitda_rate:.1f}%"
        else:
            ebitda_val = "N/A"
        ebitda_status = statuses.get('EBITDA Margin', 'N/A')
        
        equity_val = f"{indicators.get('Equity Ratio', 0):.1f}%" if indicators.get('Equity Ratio') is not None else "N/A"
        equity_status = statuses.get('Equity Ratio', 'N/A')
        
        rd_val = f"{indicators.get('R&D Return', 0):.1f}%" if indicators.get('R&D Return') is not None else "N/A"
        rd_status = statuses.get('R&D Return', 'N/A')
        
        action = h.get('action_required', ['-'])[0] if h.get('action_required') else '-'
        
        report.append(f"| {team} | {cash_val} {cash_status} | {debt_val} {debt_status} | "
                     f"{ebitda_val} {ebitda_status} | {equity_val} {equity_status} | "
                     f"{rd_val} {rd_status} | {action} |")
    
    report.append("\n\n### 3.2 Cash flow source analysis\n")
    report.append("| \u961F\u4F0D | \u73B0\u91D1\u53D8\u5316 | \u7ECF\u8425\u73B0\u91D1\u6D41(EBITDA) | \u73B0\u91D1\u6D41\u7C7B\u578B |")
    report.append("|------|---------|------------------|-----------|")
    
    for team in teams:
        cf = cash_flow_data.get(team, {})
        report.append(f"| {team} | ${cf.get('\u73B0\u91D1\u53D8\u5316', 0)/1000:.0f}k | "
                     f"${cf.get('\u7ECF\u8425\u73B0\u91D1\u6D41(EBITDA)', 0)/1000:.0f}k | {cf.get('\u73B0\u91D1\u6D41\u7C7B\u578B', 'N/A')} |")
    
    report.append("\n\n### 3.3 \u533A\u57DF\u5E02\u573A\u8868\u73B0\u5206\u6790\n")
    report.append("**\u6570\u636E\u8BF4\u660E**：\u7531\u4E8EExcel\u4E2D\u533A\u57DF\u9500\u552E\u989D\u6570\u636E\u4E0D\u53EF\u7528\u6216\u6570\u636E\u91CF\u6781\u5C0F（\u4EC5\u5360\u603B\u989D\u76840.05%-0.65%），\n")
    report.append("\u5F53\u524D\u4F7F\u7528\u7684'USA'\u3001'Asia'\u3001'Europe'\u6307\u6807\u7684\u5B9E\u9645\u542B\u4E49\u53EF\u80FD\u4E0E\u533A\u57DF\u9500\u552E\u989D\u4E0D\u7B26，\u4EC5\u4F9B\u53C2\u8003\u3002\n\n")
    for team in teams[:5]:  # \u663E\u793A\u524D5\u4E2A\u961F\u4F0D
        regional = regional_data.get(team, {})
        report.append(f"\n**{team}**：\n")
        has_any_sales = False
        for region in ['USA', 'Asia', 'Europe']:
            rp = regional.get(region, {})
            sales = rp.get('Sales', 0) or 0
            if sales > 0:
                has_any_sales = True
                report.append(f"- **{region}**：")
                report.append(f" \u9500\u552E\u989D ${sales/1000:.0f}k")
                if rp.get('\u5E02\u573A\u4EFD\u989D'):
                    report.append(f"，\u5E02\u573A\u4EFD\u989D {rp['\u5E02\u573A\u4EFD\u989D']:.1f}%")
                if rp.get('\u6392\u540D'):
                    report.append(f"，\u6392\u540D\u7B2C{rp['\u6392\u540D']}\u4F4D")
                if rp.get('\u9500\u552E\u8D8B\u52BF'):
                    trend_symbol = "📈" if rp['\u9500\u552E\u8D8B\u52BF'] == '\u589E\u957F' else "📉" if rp['\u9500\u552E\u8D8B\u52BF'] == '\u4E0B\u964D' else "➡️"
                    report.append(f"，\u8D8B\u52BF：{trend_symbol} {rp['\u9500\u552E\u8D8B\u52BF']}")
                if rp.get('\u7B56\u7565\u5EFA\u8BAE'):
                    report.append(f" → {'; '.join(rp['\u7B56\u7565\u5EFA\u8BAE'])}\n")
        
        if not has_any_sales:
            report.append("- ⚠️ \u6682\u65E0\u533A\u57DF\u9500\u552E\u989D\u6570\u636E\n")
    
    # \u56DB\u3001\u7ADE\u4E89\u5206\u6790\u89E3\u7801
    report.append("\n\n## \u56DB\u3001\u7ADE\u4E89\u5206\u6790\u89E3\u7801\n")
    
    report.append("### 4.1 Three-dimensional benchmark matrix\n")
    report.append("| \u961F\u4F0D | \u8D22\u52A1\u6FC0\u8FDB\u5EA6 | \u5E02\u573A\u4FB5\u7565\u6027 | \u6280\u672F\u6295\u5165\u5EA6 | \u7B56\u7565\u7C7B\u578B |")
    report.append("|------|-----------|-----------|-----------|---------|")
    
    for team in teams:
        cm = competitive_matrix.get(team, {})
        report.append(f"| {team} | {cm.get('Financial Aggressiveness', 0):.1f}% | "
                     f"{cm.get('Market Aggressiveness', 0):.1f}% | {cm.get('Technology Investment Intensity', 0):.1f}% | "
                     f"{cm.get('Strategy Type', '\u672A\u77E5')} |")
    
    report.append("\n\n### 4.2 Strategy shift detection\n")
    for team in teams:
        changes = strategy_changes.get(team, {})
        if changes.get('alerts'):
            report.append(f"\n**{team}**：\n")
            for alert in changes['alerts'][:3]:  # \u53EA\u663E\u793A\u524D3\u4E2A\u8B66\u62A5
                report.append(f"- ⚠️ {alert['type']} ({alert['round']}): {alert.get('interpretation', '')}\n")
    
    report.append("\n\n### 4.3 Next-round intent prediction\n")
    for team in teams:
        pred = predictions.get(team, [])
        if pred:
            report.append(f"\n**{team}**：\n")
            for signal in pred[:3]:  # \u53EA\u663E\u793A\u524D3\u4E2A\u4FE1\u53F7
                report.append(f"- {signal['action']} (\u6982\u7387{signal['probability']}%): {signal['reason']}\n")
    
    # \u4E94\u3001\u591A\u56DE\u5408\u8D8B\u52BF\u5206\u6790
    report.append("\n\n## \u4E94\u3001\u591A\u56DE\u5408\u8D8B\u52BF\u5206\u6790\n")
    
    rounds = get_rounds_order(all_rounds_data)
    available_rounds = rounds  # \u5DF2\u7ECF\u8FC7\u6EE4\u4E86，\u76F4\u63A5\u4F7F\u7528
    
    for metric_name in ['Sales', 'Net Profit', 'Cash']:
        report.append(f"\n### {metric_name}\u8D8B\u52BF\n")
        report.append("| \u961F\u4F0D | " + " | ".join([r.upper() for r in available_rounds]) + " |")
        report.append("|------|" + "|".join(["------" for _ in available_rounds]) + "|\n")
        
        for team in teams[:8]:  # \u663E\u793A\u524D8\u4E2A\u961F\u4F0D
            values = []
            for rnd in available_rounds:
                val = get_metric_with_priority(all_rounds_data[rnd], metric_name, team)
                if val is not None:
                    if metric_name == 'Cash':
                        values.append(f"${val/1000:.0f}k")
                    else:
                        values.append(f"{val/1000:.0f}k")
                else:
                    values.append("N/A")
            report.append(f"| {team} | " + " | ".join(values) + " |\n")
        
        # \u6DFB\u52A0\u73AF\u6BD4\u589E\u957F\u7387
        if len(available_rounds) > 1:
            report.append("\n**\u73AF\u6BD4\u589E\u957F\u7387**：\n")
            report.append("| \u961F\u4F0D | " + " | ".join([f"{r.upper()}" for r in available_rounds[1:]]) + " |")
            report.append("|------|" + "|".join(["------" for _ in available_rounds[1:]]) + "|\n")
            
            for team in teams[:8]:
                growth_rates = []
                for i in range(1, len(available_rounds)):
                    rnd = available_rounds[i]
                    derived = derived_metrics.get(rnd, {})
                    growth = derived.get(f'{metric_name}_\u73AF\u6BD4\u589E\u957F', {}).get(team)
                    if growth is not None:
                        growth_rates.append(f"{growth:+.1f}%")
                    else:
                        growth_rates.append("N/A")
                report.append(f"| {team} | " + " | ".join(growth_rates) + " |\n")
    
    # \u516D\u3001\u51B3\u7B56\u5EFA\u8BAE（\u7B2C\u4E94\u7AE0\u5185\u5BB9）
    if strategy_recommendations:
        report.append("\n\n## \u516D\u3001\u51B3\u7B56\u5EFA\u8BAE\n")
        
        report.append("### 6.1 \u4E0B\u56DE\u5408\u7B56\u7565\u5EFA\u8BAE\n")
        for team in teams[:5]:  # \u663E\u793A\u524D5\u4E2A\u961F\u4F0D
            rec = strategy_recommendations.get(team, {})
            if rec:
                report.append(f"\n**{team}**：")
                report.append(f"\n- \u6A21\u5F0F：{rec.get('mode', 'N/A')}（\u98CE\u9669\u7B49\u7EA7：{rec.get('risk_level', 'N/A')}）")
                report.append(f"- \u884C\u52A8\u5EFA\u8BAE：")
                for action in rec.get('actions', []):
                    report.append(f"  - {action}")
                if rec.get('resource_allocation'):
                    report.append(f"- \u8D44\u6E90\u5206\u914D：")
                    for item, value in rec.get('resource_allocation', {}).items():
                        report.append(f"  - {item}: {value}%")
        
        report.append("\n\n### 6.2 \u533A\u57DF\u5E02\u573A\u8FDB\u5165\u68C0\u6D4B\n")
        if region_entry_alerts:
            for team in teams:
                alerts = region_entry_alerts.get(team, [])
                if alerts:
                    report.append(f"\n**{team}**：\n")
                    for alert in alerts[:3]:  # \u53EA\u663E\u793A\u524D3\u4E2A
                        report.append(f"- ⚠️ {alert.get('interpretation', '')}（{alert.get('round', '')}，\u9500\u552E\u989D：${alert.get('sales', 0)/1000:.0f}k）\n")
    
    # \u4E03\u3001\u6838\u5FC3\u68C0\u67E5\u6E05\u5355
    if checklist:
        report.append("\n\n## \u4E03\u3001\u6838\u5FC3\u68C0\u67E5\u6E05\u5355\n")
        report.append("**\u63D0\u4EA4\u51B3\u7B56\u524D\u5FC5\u7B54\u95EE\u9898**：\n")
        
        for team in teams[:3]:  # \u663E\u793A\u524D3\u4E2A\u961F\u4F0D
            checks = checklist.get(team, {})
            if checks:
                report.append(f"\n### {team}\n")
                
                for category, items in checks.items():
                    report.append(f"\n**{category}\u68C0\u67E5**：\n")
                    for item in items:
                        report.append(f"- {item}\n")
    
    # \u516B\u3001\u53EF\u89C6\u5316\u56FE\u8868\u63CF\u8FF0（\u65B9\u6CD5\u8BBA\u6587\u68636.2\u8282）
    report.append("\n\n## \u516B\u3001\u5173\u952E\u56FE\u8868\u63CF\u8FF0\n")
    report.append("> \u6CE8：\u4EE5\u4E0B\u4E3A\u56FE\u8868\u7684\u6587\u672C\u63CF\u8FF0，\u5B9E\u9645\u53EF\u89C6\u5316\u56FE\u8868\u53EF\u4F7F\u7528matplotlib\u7B49\u5DE5\u5177\u751F\u6210\n\n")
    
    # 1. \u8D22\u52A1\u5065\u5EB7\u5EA6\u4EEA\u8868\u76D8
    report.append("### 8.1 \u8D22\u52A1\u5065\u5EB7\u5EA6\u4EEA\u8868\u76D8\n")
    report.append("**\u6307\u6807\u72B6\u6001\u6982\u89C8**：\n\n")
    for team in teams[:5]:
        health = health_data.get(team, {})
        statuses = health.get('status', {})
        indicators = health.get('indicators', {})
        
        report.append(f"**{team}**：\n")
        for ind_name in ['Cash Reserve', 'Net Debt to Equity', 'EBITDA Margin', 'Equity Ratio', 'R&D Return']:
            status = statuses.get(ind_name, 'N/A')
            value = indicators.get(ind_name)
            if value is not None:
                if ind_name == 'Cash Reserve':
                    report.append(f"- {ind_name}: ${value/1000:.0f}k {status}\n")
                elif ind_name == 'EBITDA Margin':
                    # \u4FEE\u590D：EBITDA\u7387\u663E\u793A\u7CBE\u5EA6
                    if value < 0.1:
                        report.append(f"- {ind_name}: {value:.4f}% {status}\n")
                    else:
                        report.append(f"- {ind_name}: {value:.1f}% {status}\n")
                else:
                    report.append(f"- {ind_name}: {value:.1f}% {status}\n")
            else:
                report.append(f"- {ind_name}: N/A {status}\n")
        report.append("\n")
    
    # 2. \u7ADE\u4E89\u6001\u52BF\u77E9\u9635\u63CF\u8FF0
    report.append("\n### 8.2 \u7ADE\u4E89\u6001\u52BF\u77E9\u9635\u56FE\n")
    report.append("**\u7EF4\u5EA6\u5206\u5E03**（X\u8F74：\u8D22\u52A1\u6FC0\u8FDB\u5EA6，Y\u8F74：\u6280\u672F\u6295\u5165\u5EA6，\u6C14\u6CE1\u5927\u5C0F：\u5E02\u573A\u4FB5\u7565\u6027）：\n\n")
    report.append("| \u961F\u4F0D | \u8D22\u52A1\u6FC0\u8FDB\u5EA6 | \u6280\u672F\u6295\u5165\u5EA6 | \u5E02\u573A\u4FB5\u7565\u6027 | \u7B56\u7565\u7C7B\u578B | \u8C61\u9650\u4F4D\u7F6E |\n")
    report.append("|------|-----------|-----------|-----------|---------|---------|\n")
    
    for team in teams:
        cm = competitive_matrix.get(team, {})
        fin_agg = cm.get('Financial Aggressiveness', 0)
        tech_inv = cm.get('Technology Investment Intensity', 0)
        mkt_agg = cm.get('Market Aggressiveness', 0)
        strategy = cm.get('Strategy Type', '\u672A\u77E5')
        
        # \u5224\u65AD\u8C61\u9650\u4F4D\u7F6E（\u4F18\u5316999%\u7684\u663E\u793A）
        if fin_agg >= 999:
            fin_pos = "\u6781\u7AEF\u6FC0\u8FDB（\u6743\u76CA<0）"
        elif fin_agg > 50:
            fin_pos = "\u9AD8"
        else:
            fin_pos = "\u4F4E"
        
        if tech_inv > 10:
            tech_pos = "\u9AD8"
        else:
            tech_pos = "\u4F4E"
        
        if fin_agg >= 999:
            quadrant = f"\u6781\u7AEF\u6FC0\u8FDB×{tech_pos}\u6280\u672F"
        else:
            quadrant = f"{fin_pos}\u8D22\u52A1×{tech_pos}\u6280\u672F"
        
        report.append(f"| {team} | {fin_agg:.1f}% | {tech_inv:.1f}% | {mkt_agg:.1f}% | {strategy} | {quadrant} |\n")
    
    # 3. \u591A\u56DE\u5408\u8D8B\u52BF\u5BF9\u6BD4
    report.append("\n### 8.3 \u591A\u56DE\u5408\u8D8B\u52BF\u5BF9\u6BD4\u56FE\n")
    report.append("**\u5173\u952E\u6307\u6807\u8D8B\u52BF**（\u8BE6\u89C1\u7B2C\u4E94\u7AE0\u591A\u56DE\u5408\u8D8B\u52BF\u5206\u6790\u90E8\u5206）：\n")
    report.append("- \u9500\u552E\u989D：\u6574\u4F53\u8D8B\u52BF\u5411\u4E0A/\u5411\u4E0B/\u7A33\u5B9A\n")
    report.append("- \u51C0\u5229\u6DA6：\u76C8\u5229\u6539\u5584/\u6076\u5316/\u6CE2\u52A8\n")
    report.append("- \u73B0\u91D1：\u73B0\u91D1\u6D41\u5065\u5EB7/\u7D27\u5F20/\u5371\u673A\n")
    
    # 4. \u533A\u57DF\u5E02\u573A\u8868\u73B0
    report.append("\n### 8.4 \u533A\u57DF\u5E02\u573A\u8868\u73B0\u56FE\n")
    report.append("**\u533A\u57DF\u9500\u552E\u989D\u6392\u540D**：\n\n")
    for region in ['USA', 'Asia', 'Europe']:
        report.append(f"**{region}\u5E02\u573A**：\n")
        
        # \u83B7\u53D6\u8BE5\u533A\u57DF\u6240\u6709\u961F\u4F0D\u7684\u6392\u540D（\u4FEE\u590D：\u53EA\u6709\u9500\u552E\u989D>0\u7684\u961F\u4F0D\u624D\u6392\u540D）
        region_rankings = []
        for team in teams:
            regional = regional_data.get(team, {})
            rp = regional.get(region, {})
            # \u4FEE\u590D：\u53EA\u6709\u9500\u552E\u989D>0\u4E14\u6709\u6392\u540D\u624D\u52A0\u5165\u6392\u540D\u5217\u8868
            sales = rp.get('Sales', 0) or 0
            if rp.get('\u6392\u540D') and sales > 0:
                region_rankings.append({
                    'team': team,
                    'rank': rp['\u6392\u540D'],
                    'sales': sales,
                    'market_share': rp.get('\u5E02\u573A\u4EFD\u989D', 0)
                })
        
        if region_rankings:
            region_rankings.sort(key=lambda x: x['rank'])
            report.append("| \u6392\u540D | \u961F\u4F0D | \u9500\u552E\u989D | \u5E02\u573A\u4EFD\u989D | \u8D8B\u52BF |\n")
            report.append("|------|------|--------|---------|------|\n")
            for item in region_rankings[:5]:
                # \u5224\u65AD\u8D8B\u52BF（\u7B80\u5316：\u5982\u679C\u6709\u6392\u540D\u53D8\u5316\u6570\u636E\u5219\u4F7F\u7528）
                trend = "→"  # \u9ED8\u8BA4\u7A33\u5B9A
                report.append(f"| {item['rank']} | {item['team']} | ${item['sales']/1000:.0f}k | {item['market_share']:.1f}% | {trend} |\n")
        report.append("\n")
    
    return "\n".join(report)


# ============================================================================
# Logic validation checks
# ============================================================================

def validate_logic(all_rounds_data, teams, health_data, derived_metrics, 
                  competitive_matrix, latest_round):
    """
    Validate analysis logic and consistency
    """
    issues = []
    
    metrics_dict = all_rounds_data[latest_round]
    
    # 1. \u9A8C\u8BC1\u8D22\u52A1\u5065\u5EB7\u5EA6\u8BA1\u7B97\u7684\u4E00\u81F4\u6027
    for team in teams:
        health = health_data.get(team, {})
        indicators = health.get('indicators', {})
        
        # \u9A8C\u8BC1\u73B0\u91D1\u63D0\u53D6
        cash_health = indicators.get('Cash Reserve')
        cash_direct = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        if cash_health and abs(cash_health - cash_direct) > 0.01:
            issues.append({
                'type': '\u6570\u636E\u4E0D\u4E00\u81F4',
                'team': team,
                'metric': 'Cash',
                'description': f'\u5065\u5EB7\u5EA6\u8BA1\u7B97\u4E2D\u7684\u73B0\u91D1\u503C({cash_health})\u4E0E\u76F4\u63A5\u63D0\u53D6\u503C({cash_direct})\u4E0D\u4E00\u81F4'
            })
        
        # \u9A8C\u8BC1\u51C0\u503A\u52A1/\u6743\u76CA\u6BD4\u8BA1\u7B97
        equity = get_metric_value(metrics_dict, 'Total Equity', team) or 0
        short_debt = get_metric_value(metrics_dict, 'Short-Term Debt', team) or 0
        long_debt = get_metric_value(metrics_dict, 'Long-Term Debt', team) or 0
        cash = get_metric_with_priority(metrics_dict, 'Cash', team) or 0
        
        if equity > 0:
            calculated_debt_equity = ((short_debt + long_debt - cash) / equity) * 100
            stored_debt_equity = indicators.get('Net Debt to Equity')
            
            if stored_debt_equity is not None:
                if abs(calculated_debt_equity - stored_debt_equity) > 0.1:
                    issues.append({
                        'type': '\u8BA1\u7B97\u4E0D\u4E00\u81F4',
                        'team': team,
                        'metric': 'Net Debt to Equity',
                        'description': f'\u8BA1\u7B97\u503C({calculated_debt_equity:.2f}%)\u4E0E\u5B58\u50A8\u503C({stored_debt_equity:.2f}%)\u4E0D\u4E00\u81F4'
                    })
    
    # 2. \u9A8C\u8BC1\u8D44\u6E90\u5206\u914D\u603B\u548C
    # (\u8FD9\u90E8\u5206\u5728\u4E3B\u51FD\u6570\u4E2D\u8C03\u7528\u65F6\u9A8C\u8BC1)
    
    # 3. \u9A8C\u8BC1\u6392\u540D\u903B\u8F91
    rounds = get_rounds_order(all_rounds_data)
    for rnd in rounds:
        if rnd in all_rounds_data:
            derived = derived_metrics.get(rnd, {})
            sales_rankings = derived.get('\u9500\u552E\u989D_\u6392\u540D', {})
            
            if sales_rankings:
                # \u9A8C\u8BC1\u6392\u540D\u662F\u5426\u8FDE\u7EED\u4E14\u4ECE1\u5F00\u59CB
                ranks = sorted([r for r in sales_rankings.values() if r is not None])
                if ranks and (ranks[0] != 1 or len(set(ranks)) != len(ranks)):
                    issues.append({
                        'type': '\u6392\u540D\u903B\u8F91\u9519\u8BEF',
                        'round': rnd,
                        'description': f'\u9500\u552E\u989D\u6392\u540D\u4E0D\u8FDE\u7EED\u6216\u91CD\u590D'
                    })
    
    return issues


# ============================================================================
# Main program
# ============================================================================

def main(input_dir=None, output_dir=None):
    """
    \u4E3B\u51FD\u6570
    
    \u53C2\u6570:
        input_dir: \u6570\u636E\u8F93\u5165\u76EE\u5F55\u8DEF\u5F84（\u5305\u542B results-ir00.xls \u7B49\u6587\u4EF6）
        output_dir: \u5206\u6790\u62A5\u544A\u8F93\u51FA\u76EE\u5F55\u8DEF\u5F84
    """
    # \u8BBE\u7F6E\u9ED8\u8BA4\u8DEF\u5F84
    if input_dir is None:
        input_dir = DEFAULT_INPUT_DIR
    else:
        input_dir = Path(input_dir)
    
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        output_dir = Path(output_dir)
    
    # \u751F\u6210\u6570\u636E\u6587\u4EF6\u8DEF\u5F84
    FILES = get_data_files(input_dir)
    
    print("=" * 80)
    print("\u5546\u4E1A\u6A21\u62DF\u7ADE\u8D5B\u7ED3\u679C\u7EFC\u5408\u5206\u6790 v3.0")
    print("\u4E25\u683C\u6309\u7167\u65B9\u6CD5\u8BBA\u6587\u68633.0\u7248\u672C\u8FDB\u884C\u5206\u6790")
    print("=" * 80)
    print(f"\u6570\u636E\u8F93\u5165\u76EE\u5F55: {input_dir}")
    print(f"\u62A5\u544A\u8F93\u51FA\u76EE\u5F55: {output_dir}")
    print("=" * 80)
    
    # \u7B2C\u4E00\u6B65：\u6570\u636E\u57FA\u7840\u5EFA\u8BBE
    print("\n\u3010\u7B2C\u4E00\u6B65：\u6570\u636E\u57FA\u7840\u5EFA\u8BBE\u3011")
    all_rounds_data = {}
    teams = []
    
    for round_name, file_path in FILES.items():
        if not file_path.exists():
            print(f"\u8B66\u544A: \u6587\u4EF6\u4E0D\u5B58\u5728 {file_path}")
            continue
        
        print(f"  \u6B63\u5728\u5904\u7406 {round_name}...")
        metrics_dict, round_teams = read_excel_data(str(file_path))
        
        if not teams:
            teams = normalize_team_names(round_teams)
        
        all_rounds_data[round_name] = metrics_dict
        print(f"    [OK] \u63D0\u53D6\u5230 {len(metrics_dict)} \u4E2A\u6307\u6807")
        print(f"    [OK] \u961F\u4F0D\u6570\u91CF: {len(round_teams)}")
    
    if not all_rounds_data:
        print("\u9519\u8BEF: \u672A\u80FD\u8BFB\u53D6\u4EFB\u4F55\u6570\u636E\u6587\u4EF6")
        return
    
    # \u786E\u5B9A\u6700\u65B0\u56DE\u5408（\u6309\u4F18\u5148\u7EA7：pr99 > ... > pr03 > pr02 > pr01 > ir00）
    rounds_order = get_rounds_order()
    # \u4ECE\u540E\u5F80\u524D\u67E5\u627E，\u627E\u5230\u7B2C\u4E00\u4E2A\u5B58\u5728\u7684\u56DE\u5408
    latest_round = None
    for rnd in reversed(rounds_order):
        if rnd in all_rounds_data:
            latest_round = rnd
            break
    if latest_round is None:
        latest_round = list(all_rounds_data.keys())[0]  # \u4F7F\u7528\u7B2C\u4E00\u4E2A\u53EF\u7528\u7684\u56DE\u5408
    print(f"\n  \u6700\u65B0\u56DE\u5408: {latest_round}")
    
    # Anomaly detection
    anomalies = detect_anomalies(all_rounds_data[latest_round], teams)
    print(f"  \u68C0\u6D4B\u5230 {sum(len(v) for v in anomalies.values())} \u4E2A\u5F02\u5E38\u503C")
    
    # Compute derived metrics
    print("\n  Compute derived metrics...")
    derived_metrics = calculate_derived_metrics(all_rounds_data, teams)
    print(f"    [OK] \u5B8C\u6210")
    
    # \u7B2C\u4E8C\u6B65：\u81EA\u8EAB\u8BCA\u65AD\u5206\u6790
    print("\n\u3010\u7B2C\u4E8C\u6B65：\u81EA\u8EAB\u8BCA\u65AD\u5206\u6790\u3011")
    
    print("  \u8BA1\u7B97\u8D22\u52A1\u5065\u5EB7\u5EA6...")
    health_data = calculate_financial_health(all_rounds_data[latest_round], teams)
    
    print("  \u5206\u6790\u73B0\u91D1\u6D41...")
    # \u786E\u5B9A\u4E0A\u4E00\u56DE\u5408（\u7528\u4E8E\u73B0\u91D1\u6D41\u5206\u6790）
    rounds_order = get_rounds_order(all_rounds_data)
    latest_idx = rounds_order.index(latest_round) if latest_round in rounds_order else -1
    if latest_idx > 0:
        prev_round = rounds_order[latest_idx - 1]
    else:
        prev_round = None
    prev_metrics = all_rounds_data.get(prev_round, {}) if prev_round else {}
    cash_flow_data = analyze_cash_flow_source(all_rounds_data[latest_round], teams, prev_metrics)
    
    print("  \u5206\u6790\u533A\u57DF\u5E02\u573A\u8868\u73B0...")
    regional_data = analyze_regional_market(all_rounds_data, teams, latest_round)
    
    # \u7B2C\u4E09\u6B65：\u7ADE\u4E89\u5206\u6790\u89E3\u7801
    print("\n\u3010\u7B2C\u4E09\u6B65：\u7ADE\u4E89\u5206\u6790\u89E3\u7801\u3011")
    
    print("  \u8BA1\u7B97Three-dimensional benchmark matrix...")
    competitive_matrix = calculate_competitive_position(all_rounds_data[latest_round], teams)
    
    print("  \u68C0\u6D4B\u7B56\u7565\u7A81\u53D8...")
    strategy_changes = detect_strategy_changes(all_rounds_data, teams)
    
    print("  \u9884\u6D4B\u4E0B\u56DE\u5408\u610F\u56FE...")
    predictions = predict_next_move(all_rounds_data, teams, latest_round, derived_metrics)
    
    print("  \u68C0\u6D4B\u533A\u57DF\u5E02\u573A\u8FDB\u5165...")
    region_entry_alerts = detect_region_entry(all_rounds_data, teams)
    
    # \u7B2C\u56DB\u6B65：\u51B3\u7B56\u652F\u6301\u4F53\u7CFB
    print("\n\u3010\u7B2C\u56DB\u6B65：\u51B3\u7B56\u652F\u6301\u4F53\u7CFB\u3011")
    
    print("  \u751F\u6210\u7B56\u7565\u5EFA\u8BAE...")
    strategy_recommendations = generate_strategy_recommendations(
        health_data, cash_flow_data, competitive_matrix, 
        derived_metrics, latest_round, teams
    )
    
    print("  \u751F\u6210\u68C0\u67E5\u6E05\u5355...")
    checklist = generate_checklist(
        health_data, regional_data, strategy_changes, teams, latest_round
    )
    
    # \u903B\u8F91\u9A8C\u8BC1
    print("\n\u3010\u903B\u8F91\u9A8C\u8BC1\u68C0\u67E5\u3011")
    logic_issues = validate_logic(
        all_rounds_data, teams, health_data, derived_metrics,
        competitive_matrix, latest_round
    )
    if logic_issues:
        print(f"  \u53D1\u73B0 {len(logic_issues)} \u4E2A\u903B\u8F91\u95EE\u9898，\u5DF2\u8BB0\u5F55")
        for issue in logic_issues[:3]:
            print(f"    - {issue.get('type')}: {issue.get('description', '')}")
    else:
        print("  [OK] \u903B\u8F91\u9A8C\u8BC1\u901A\u8FC7")
    
    # \u9A8C\u8BC1\u8D44\u6E90\u5206\u914D\u5408\u7406\u6027
    for team, rec in strategy_recommendations.items():
        allocation = rec.get('resource_allocation', {})
        total = sum(v for v in allocation.values() if isinstance(v, (int, float)))
        if abs(total - 100) > 1:  # \u5141\u8BB81%\u7684\u8BEF\u5DEE
            print(f"  \u8B66\u544A: {team}\u8D44\u6E90\u5206\u914D\u603B\u548C={total:.1f}%，\u4E0D\u7B49\u4E8E100%")
    
    # \u7B2C\u4E94\u6B65：\u751F\u6210\u62A5\u544A
    print("\n\u3010\u7B2C\u4E94\u6B65：\u751F\u6210\u5206\u6790\u62A5\u544A\u3011")
    
    report = generate_comprehensive_report(
        all_rounds_data, teams, health_data, cash_flow_data,
        regional_data, competitive_matrix, strategy_changes,
        predictions, derived_metrics, anomalies, latest_round,
        strategy_recommendations, checklist, region_entry_alerts
    )
    
    # \u4FDD\u5B58\u62A5\u544A
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / '\u65B9\u6CD5\u8BBA3.0\u5B8C\u6574\u5206\u6790\u62A5\u544A.md'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n  [OK] \u62A5\u544A\u5DF2\u4FDD\u5B58\u5230: {output_file}")
    print("\n" + "=" * 80)
    print("\u5206\u6790\u5B8C\u6210！")
    print("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Comprehensive Business Simulation Analysis Script v3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
\u793A\u4F8B:
  # \u4F7F\u7528\u9ED8\u8BA4\u8DEF\u5F84
  python analyze_comprehensive_v3.py
  
  # \u6307\u5B9A\u6570\u636E\u8F93\u5165\u76EE\u5F55
  python analyze_comprehensive_v3.py --input-dir /path/to/data
  
  # \u6307\u5B9A\u6570\u636E\u8F93\u5165\u76EE\u5F55\u548C\u8F93\u51FA\u76EE\u5F55
  python analyze_comprehensive_v3.py --input-dir /path/to/data --output-dir /path/to/output
  
  # \u4F7F\u7528\u76F8\u5BF9\u8DEF\u5F84
  python analyze_comprehensive_v3.py --input-dir ./data --output-dir ./reports
        """
    )
    
    parser.add_argument(
        '--input-dir', '-i',
        type=str,
        default=None,
        help=f'\u6570\u636E\u8F93\u5165\u76EE\u5F55\u8DEF\u5F84（\u5305\u542B results-ir00.xls \u7B49\u6587\u4EF6）\u3002\u9ED8\u8BA4: {DEFAULT_INPUT_DIR}'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=None,
        help=f'\u5206\u6790\u62A5\u544A\u8F93\u51FA\u76EE\u5F55\u8DEF\u5F84\u3002\u9ED8\u8BA4: {DEFAULT_OUTPUT_DIR}'
    )
    
    args = parser.parse_args()
    
    # \u9A8C\u8BC1\u8F93\u5165\u76EE\u5F55
    if args.input_dir:
        input_path = Path(args.input_dir)
        if not input_path.exists():
            print(f"\u9519\u8BEF: \u8F93\u5165\u76EE\u5F55\u4E0D\u5B58\u5728: {input_path}")
            sys.exit(1)
        if not input_path.is_dir():
            print(f"\u9519\u8BEF: \u8F93\u5165\u8DEF\u5F84\u4E0D\u662F\u76EE\u5F55: {input_path}")
            sys.exit(1)
    
    # \u8FD0\u884C\u4E3B\u51FD\u6570
    main(input_dir=args.input_dir, output_dir=args.output_dir)

