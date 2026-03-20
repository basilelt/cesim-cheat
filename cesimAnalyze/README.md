# Cesim Analysis Toolkit

This project provides scripts and prompts to analyze Cesim simulation results and prepare next-round decisions.

## Main Workflow

1. Run comprehensive analysis with `scripts/analyze_comprehensive_v3.py`.
2. Parse Cesim MHTML decision pages with `docs/prompts/mhtml_page_parsing_prompt.md`.
3. Build a full decision plan with `docs/prompts/decision_making_prompt.md`.

## Additional Scripts

- `scripts/analyze_team_detail.py`: deep report for one team
- `scripts/generate_all_team_reports.py`: generate reports for all teams
- `scripts/generate_gap_analysis.py`: compare one team against peers

## Data Files

Supported files include:
- `results-ir00.xls`
- `results-pr01.xls`, `results-pr02.xls`, ...
- `results-r01.xls`, `results-r02.xls`, ...

## Notes

Some scripts keep original Chinese metric aliases for compatibility with Cesim Excel exports.
