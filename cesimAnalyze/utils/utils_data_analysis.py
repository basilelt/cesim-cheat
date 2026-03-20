#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data analysis and Excel processing utility module.
Includes data reading, structure checks, and diagnostics.
"""

import pandas as pd


def read_excel_data(file_path, team_row_idx=4, data_start_row=5):
    """
    Read an Excel file and parse the data structure.

    Args:
        file_path: Path to Excel file.
        team_row_idx: Row index where team names are stored (default 4, row 5).
        data_start_row: Start row index for metric data (default 5, row 6).

    Returns:
        metrics_dict: Dict in the form {metric_name: {team_name: value}}
        teams: Team name list
    """
    df = pd.read_excel(file_path, sheet_name='Results', header=None)

    # Read team names.
    team_row = df.iloc[team_row_idx]
    teams = [str(t).strip() for t in team_row[1:] if pd.notna(t) and str(t).strip() != '']

    # Read data rows.
    data_df = df.iloc[data_start_row:].copy()
    data_df.columns = ['指标'] + teams + ['Unnamed'] * (len(data_df.columns) - len(teams) - 1)

    # Build metric dictionary.
    metrics_dict = {}
    # Track section context (for example: "损益表, 千 USD, 全球").
    current_section = None

    for _, row in data_df.iterrows():
        indicator = str(row['指标']).strip() if pd.notna(row['指标']) else ''

        if indicator == '' or indicator == 'nan':
            continue

        # Detect section header rows.
        if '损益表' in indicator or '资产负债表' in indicator:
            current_section = indicator
            continue

        # Parse each team's value.
        team_data = {}
        for team in teams:
            val = row[team]
            if pd.notna(val):
                try:
                    if isinstance(val, (int, float)):
                        team_data[team] = float(val)
                    elif isinstance(val, str):
                        cleaned = val.replace(',', '').replace('$', '').replace('%', '').replace(' ', '').strip()
                        if cleaned:
                            team_data[team] = float(cleaned)
                        else:
                            team_data[team] = None
                    else:
                        team_data[team] = None
                except Exception:
                    team_data[team] = None
            else:
                team_data[team] = None

        if any(v is not None for v in team_data.values()):
            # Handle duplicate metric names.
            if indicator in metrics_dict:
                existing_data = metrics_dict[indicator]
                for team in teams:
                    existing_val = existing_data.get(team)
                    new_val = team_data.get(team)
                    if existing_val is not None and new_val is not None:
                        # For EBITDA-like metrics, prefer larger absolute values (global totals).
                        if 'EBITDA' in indicator or '息税折旧' in indicator:
                            if (abs(new_val) > 100 and abs(existing_val) < 100) or abs(new_val) > abs(existing_val) * 2:
                                existing_data[team] = new_val
                        else:
                            # For other metrics, prefer values in a global section.
                            if current_section and '全球' in current_section:
                                existing_data[team] = new_val
                    elif new_val is not None:
                        existing_data[team] = new_val
            else:
                metrics_dict[indicator] = team_data

    return metrics_dict, teams


def find_metric(metrics_dict, keywords, exact_match=False):
    """
    Find a metric by keyword(s).

    Args:
        metrics_dict: Metrics dictionary.
        keywords: Keyword list or one keyword string.
        exact_match: Whether to require exact match.

    Returns:
        Matched metric dict, or empty dict if not found.
    """
    if isinstance(keywords, str):
        keywords = [keywords]

    for key in metrics_dict.keys():
        for keyword in keywords:
            if exact_match:
                if keyword == str(key).strip():
                    return metrics_dict[key]
            else:
                if keyword in str(key):
                    return metrics_dict[key]
    return {}


def list_all_metrics(file_path, max_count=200):
    """
    List all metric names in an Excel file.

    Args:
        file_path: Path to Excel file.
        max_count: Maximum number of metrics returned.

    Returns:
        Metric name list.
    """
    metrics_dict, _ = read_excel_data(file_path)
    return list(metrics_dict.keys())[:max_count]


def check_excel_structure(file_path):
    """
    Inspect Excel file structure.

    Args:
        file_path: Path to Excel file.

    Returns:
        Structure summary dictionary.
    """
    excel_file = pd.ExcelFile(file_path)
    df = pd.read_excel(file_path, sheet_name='Results', header=None)

    team_row = df.iloc[4]
    teams = [str(t).strip() for t in team_row[1:] if pd.notna(t) and str(t).strip() != '']

    metrics_dict, _ = read_excel_data(file_path)

    regions = ['美国', '亚洲', '欧洲', 'America', 'Asia', 'Europe']
    region_metrics = {}
    for region in regions:
        region_metrics[region] = [k for k in metrics_dict.keys() if region in str(k)]

    market_keywords = ['市场', '份额', '占有率']
    market_metrics = [k for k in metrics_dict.keys() if any(kw in str(k) for kw in market_keywords)]

    demand_keywords = ['需求', '未满足']
    demand_metrics = [k for k in metrics_dict.keys() if any(kw in str(k) for kw in demand_keywords)]

    capacity_keywords = ['产能', '利用率', '产量']
    capacity_metrics = [k for k in metrics_dict.keys() if any(kw in str(k) for kw in capacity_keywords)]

    return {
        'sheet_names': excel_file.sheet_names,
        'shape': df.shape,
        'teams': teams,
        'total_metrics': len(metrics_dict),
        'region_metrics': region_metrics,
        'market_metrics': market_metrics,
        'demand_metrics': demand_metrics,
        'capacity_metrics': capacity_metrics,
    }


def diagnose_missing_data(file_path, target_metrics=None, target_team=None):
    """
    Diagnose missing metrics for a given team.

    Args:
        file_path: Path to Excel file.
        target_metrics: Target metric list; defaults to a built-in list.
        target_team: Target team name.

    Returns:
        Diagnosis dictionary.
    """
    metrics_dict, teams = read_excel_data(file_path)

    if target_metrics is None:
        target_metrics = [
            '销售额', '净利润', '现金', '权益', 'EBITDA',
            '美国市场份额', '亚洲市场份额', '欧洲市场份额',
            '美国未满足需求', '亚洲未满足需求', '欧洲未满足需求',
            '美国产能利用率', '亚洲产能利用率', '欧洲产能利用率',
        ]

    if target_team is None:
        target_team = teams[0] if teams else None

    diagnosis = {
        'found_metrics': {},
        'missing_metrics': [],
        'similar_metrics': {},
    }

    for metric in target_metrics:
        exact_match = find_metric(metrics_dict, [metric], exact_match=True)
        if exact_match:
            diagnosis['found_metrics'][metric] = exact_match.get(target_team)
            continue

        partial_match = find_metric(metrics_dict, [metric], exact_match=False)
        if partial_match:
            similar_keys = [k for k in metrics_dict.keys() if metric in str(k)]
            if similar_keys:
                diagnosis['similar_metrics'][metric] = similar_keys
                diagnosis['found_metrics'][metric] = partial_match.get(target_team)
                continue

        diagnosis['missing_metrics'].append(metric)

    return diagnosis


def get_metric_value(metrics_dict, metric_name, team_name):
    """
    Get a metric value for a team (supports priority list matching).
    Prefers global aggregate values over regional values.

    Args:
        metrics_dict: Metrics dictionary.
        metric_name: Metric name (string) or priority list.
        team_name: Team name.

    Returns:
        Metric value, or None if not found.
    """
    if isinstance(metric_name, list):
        all_matches = []
        for name in metric_name:
            for key, metric_data in metrics_dict.items():
                if name in str(key) and team_name in metric_data:
                    val = metric_data.get(team_name)
                    if val is not None:
                        # For liability metrics, skip suspicious negative regional values.
                        if '负债' in str(key) and val < 0 and '总计' not in str(key):
                            continue

                        # For EBITDA, skip likely percentage values.
                        if 'EBITDA' in str(key) or '息税折旧' in str(key):
                            if abs(val) < 100:
                                continue

                        priority = 0
                        if '全球' in str(key) or '总计' in str(key):
                            priority = 3
                        elif any(region in str(key) for region in ['美国', '亚洲', '欧洲', 'America', 'Asia', 'Europe']):
                            priority = 1

                        if ('EBITDA' in str(key) or '息税折旧' in str(key)) and abs(val) > 1000:
                            priority += 2

                        all_matches.append((priority, abs(val), val, str(key)))

        if all_matches:
            all_matches.sort(key=lambda x: (-x[0], -x[1]))
            return all_matches[0][2]
        return None

    all_matches = []
    for key, metric_data in metrics_dict.items():
        if metric_name in str(key) and team_name in metric_data:
            val = metric_data.get(team_name)
            if val is not None:
                if '负债' in str(key) and val < 0 and '总计' not in str(key):
                    continue
                if ('EBITDA' in str(key) or '息税折旧' in str(key)) and abs(val) < 100:
                    continue

                priority = 0
                if '全球' in str(key) or '总计' in str(key):
                    priority = 2
                elif any(region in str(key) for region in ['美国', '亚洲', '欧洲', 'America', 'Asia', 'Europe']):
                    priority = 1
                all_matches.append((priority, val, str(key)))

    if all_matches:
        all_matches.sort(key=lambda x: (-x[0], abs(x[1])), reverse=True)
        return all_matches[0][1]
    return None


def print_structure_info(structure_info):
    """Print Excel structure analysis info."""
    print("=" * 80)
    print("Excel Structure Analysis")
    print("=" * 80)
    print(f"\nSheets: {structure_info['sheet_names']}")
    print(f"Data shape: {structure_info['shape']}")
    print(f"Number of teams: {len(structure_info['teams'])}")
    print(f"Teams: {', '.join(structure_info['teams'])}")
    print(f"Total metrics: {structure_info['total_metrics']}")

    print("\nRegion-related metrics:")
    for region, metrics in structure_info['region_metrics'].items():
        if metrics:
            print(f"  {region}: {len(metrics)}")
            for m in metrics[:5]:
                print(f"    - {m}")

    print(f"\nMarket-related metrics: {len(structure_info['market_metrics'])}")
    for m in structure_info['market_metrics'][:10]:
        print(f"  - {m}")

    print(f"\nDemand-related metrics: {len(structure_info['demand_metrics'])}")
    for m in structure_info['demand_metrics'][:10]:
        print(f"  - {m}")

    print(f"\nCapacity-related metrics: {len(structure_info['capacity_metrics'])}")
    for m in structure_info['capacity_metrics'][:10]:
        print(f"  - {m}")


def print_diagnosis(diagnosis):
    """Print diagnosis results."""
    print("=" * 80)
    print("Data Diagnosis")
    print("=" * 80)

    if diagnosis['found_metrics']:
        print(f"\nFound metrics ({len(diagnosis['found_metrics'])}):")
        for metric, value in diagnosis['found_metrics'].items():
            print(f"  {metric}: {value}")

    if diagnosis['similar_metrics']:
        print(f"\nSimilar metrics found ({len(diagnosis['similar_metrics'])}):")
        for metric, similar in diagnosis['similar_metrics'].items():
            print(f"  {metric}:")
            for sim in similar[:3]:
                print(f"    - {sim}")

    if diagnosis['missing_metrics']:
        print(f"\nMissing metrics ({len(diagnosis['missing_metrics'])}):")
        for metric in diagnosis['missing_metrics']:
            print(f"  - {metric}")
