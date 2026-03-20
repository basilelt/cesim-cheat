#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate detailed analysis reports for all teams.
"""

import sys
from pathlib import Path

# Add directories to import path.
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
sys.path.insert(0, str(Path(__file__).parent))

from utils_data_analysis import read_excel_data
from analyze_team_detail import analyze_team_detailed

def main(input_dir, output_dir):
    """Generate detailed reports for every team found in the input files."""
    
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read data files to identify team names.
    ir00_path = input_dir / 'results-ir00.xls'
    if not ir00_path.exists():
        # Try r01 or pr01 if ir00 is not available.
        r01_path = input_dir / 'results-r01.xls'
        if not r01_path.exists():
            r01_path = input_dir / 'results-pr01.xls'
        if r01_path.exists():
            _, teams = read_excel_data(str(r01_path))
        else:
            print("Error: No data file found.")
            return
    else:
        _, teams = read_excel_data(str(ir00_path))
    
    print(f"Found {len(teams)} teams")
    print(f"Teams: {', '.join(teams)}")
    print("\nGenerating detailed reports for each team...\n")
    
    # Generate one report per team.
    for i, team in enumerate(teams, 1):
        print(f"[{i}/{len(teams)}] Generating report for {team}...")
        try:
            analyze_team_detailed(team, str(input_dir), str(output_dir))
            print(f"  ✓ {team} report generated")
        except Exception as e:
            print(f"  ✗ {team} report failed: {e}")
    
    print(f"\nAll reports were generated in: {output_dir}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate detailed analysis reports for all teams')
    parser.add_argument('--input-dir', '-i', type=str, required=True, help='Input data directory')
    parser.add_argument('--output-dir', '-o', type=str, required=True, help='Output report directory')
    
    args = parser.parse_args()
    main(args.input_dir, args.output_dir)

