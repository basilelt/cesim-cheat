#!/usr/bin/env python3
"""
Build a single-file dossier bundling all available inputs for a given round.
Output: analysis/round{N}_inputs.md — ready for Claude Code to consume via @-syntax.

Usage (from cesim/ root):
    uv run python cesimAnalyze/scripts/build_round_dossier.py --round 5
    uv run python cesimAnalyze/scripts/build_round_dossier.py --all
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def find_excel_for_round(results_dir: Path, n: int) -> Path | None:
    pad = str(n).zfill(2)
    candidates = [
        results_dir / f"results-pr{pad}.xls",
        results_dir / f"results-pr{pad}.xlsx",
        results_dir / f"results-r{pad}.xls",
        results_dir / f"results-r{pad}.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_json_safe(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def decisions_to_md(panels: list) -> str:
    lines = ["## Decision Pages\n"]
    for panel in panels:
        name = panel.get("panel", "unknown")
        lines.append(f"### Panel: {name}\n")
        if panel.get("error"):
            lines.append(f"_Error: {panel['error']}_\n")
            continue
        editable = [f for f in panel.get("fields", []) if not f.get("disabled")]
        readonly = [f for f in panel.get("fields", []) if f.get("disabled")]
        if editable:
            lines.append("**Editable fields:**\n")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for f in editable:
                label = f.get("label") or f.get("name") or f.get("id") or ""
                value = str(f.get("value", "")).replace("|", "\\|")
                lines.append(f"| {label} | {value} |")
            lines.append("")
        if readonly:
            lines.append("**Reference values:**\n")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for f in readonly[:20]:
                label = f.get("label") or f.get("name") or f.get("id") or ""
                value = str(f.get("value", "")).replace("|", "\\|")
                lines.append(f"| {label} | {value} |")
            lines.append("")
        for i, tbl in enumerate(panel.get("tables", [])[:5]):
            lines.append(f"**Table {i+1}:**\n")
            for row in tbl.get("rows", []):
                lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
            lines.append("")
    return "\n".join(lines)


def market_to_md(market: dict) -> str:
    lines = ["## Market Outlook\n"]
    for h in market.get("headings", []):
        lines.append(f"**{h}**")
    prose = market.get("prose", [])
    if prose:
        lines.append("\n### Narrative\n")
        for p in prose:
            lines.append(f"> {p}\n")
    for i, tbl in enumerate(market.get("tables", [])[:6]):
        lines.append(f"\n### Market Table {i+1}\n")
        for row in tbl.get("rows", []):
            lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
    return "\n".join(lines)


def results_extras_to_md(extras: list) -> str:
    lines = ["## Results Sub-Panels\n"]
    for panel in extras:
        name = panel.get("panel", "unknown")
        lines.append(f"### {name}\n")
        if panel.get("error"):
            lines.append(f"_Not available: {panel['error']}_\n")
            continue
        for i, tbl in enumerate(panel.get("tables", [])[:4]):
            lines.append(f"**Table {i+1}:**\n")
            for row in tbl.get("rows", []):
                lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
            lines.append("")
    return "\n".join(lines)


def find_analysis_md(analysis_dir: Path, pattern: str) -> list[Path]:
    return sorted(analysis_dir.glob(pattern))


def build_dossier(round_num: int, root: Path) -> str:
    results_dir = root / "results"
    decisions_dir = root / "decisions"
    analysis_dir = root / "analysis"

    sections = [f"# Round {round_num} — Input Dossier\n"]
    sections.append(f"_Generated for Claude Code consumption. Source: all available data for round {round_num}._\n")

    # Excel presence note
    excel = find_excel_for_round(results_dir, round_num)
    if excel:
        sections.append(f"**Excel results file**: `{excel.relative_to(root)}`\n")
    else:
        sections.append(f"**Excel results file**: NOT FOUND for round {round_num}\n")

    # Decisions
    decisions_path = decisions_dir / f"round{round_num}_current.json"
    decisions = load_json_safe(decisions_path)
    if isinstance(decisions, list):
        sections.append(decisions_to_md(decisions))
    else:
        sections.append("## Decision Pages\n_Not available for this round._\n")

    # Market outlook
    market_path = decisions_dir / f"round{round_num}_market.json"
    market = load_json_safe(market_path)
    if isinstance(market, dict) and "tables" in market:
        sections.append(market_to_md(market))
    else:
        sections.append("## Market Outlook\n_Not available for this round._\n")

    # Results extras
    extras_path = decisions_dir / f"round{round_num}_results_extras.json"
    extras = load_json_safe(extras_path)
    if isinstance(extras, list):
        sections.append(results_extras_to_md(extras))

    # Analysis MDs: include all available (comprehensive, team detail, gap, round-specific)
    # Exclude inputs/full_report files to avoid recursion
    included = set()
    priority_patterns = [
        "comprehensive_analysis_*.md",
        "*detailed_analysis*.md",
        "*gap_analysis*.md",
        "*team_detail*.md",
        f"*round{round_num}*.md",
        f"*r{str(round_num).zfill(2)}*.md",
        "*.md",  # catch-all (e.g. Chinese-named reports)
    ]
    for pattern in priority_patterns:
        for md_file in find_analysis_md(analysis_dir, pattern):
            if md_file in included:
                continue
            if "_inputs" in md_file.name or "_full_report" in md_file.name:
                continue
            included.add(md_file)
            sections.append(f"\n---\n\n## From: `{md_file.name}`\n")
            sections.append(md_file.read_text(encoding="utf-8"))

    return "\n\n".join(sections)


def detect_all_rounds(root: Path) -> list[int]:
    results_dir = root / "results"
    decisions_dir = root / "decisions"
    rounds = set()
    if results_dir.exists():
        for f in results_dir.iterdir():
            m = re.search(r"(\d{2,})\.", f.name)
            if m:
                rounds.add(int(m.group(1)))
    if decisions_dir.exists():
        for f in decisions_dir.iterdir():
            m = re.search(r"round(\d+)_", f.name)
            if m:
                rounds.add(int(m.group(1)))
    return sorted(rounds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-round input dossier for Claude Code")
    parser.add_argument("--round", type=int, help="Round number")
    parser.add_argument("--all", action="store_true", help="Process all detected rounds")
    parser.add_argument("--root", type=Path, default=None, help="Repo root (auto-detected)")
    args = parser.parse_args()

    # Auto-detect root: go up from this script until CLAUDE.md found
    root = args.root
    if root is None:
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            if (candidate / "CLAUDE.md").exists():
                root = candidate
                break
    if root is None:
        root = Path.cwd()

    analysis_dir = root / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    if args.all:
        rounds = detect_all_rounds(root)
        if not rounds:
            print("No rounds detected. Download Excel files first.", file=sys.stderr)
            sys.exit(1)
        print(f"Detected rounds: {rounds}")
    elif args.round:
        rounds = [args.round]
    else:
        parser.print_help()
        sys.exit(1)

    for n in rounds:
        print(f"Building dossier for round {n}...")
        content = build_dossier(n, root)
        out = analysis_dir / f"round{n}_inputs.md"
        out.write_text(content, encoding="utf-8")
        size_kb = len(content.encode()) / 1024
        print(f"  Written: {out} ({size_kb:.1f} KB)")

    print("\nDone. To generate full reports, tell Claude Code:")
    for n in rounds:
        print(f"  @analysis/round{n}_inputs.md @cesimAnalyze/docs/prompts/round_report_prompt.md write the round {n} report to analysis/round{n}_full_report.md")


if __name__ == "__main__":
    main()
