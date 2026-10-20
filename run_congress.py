"""Run the abstract scraper for one congress by name and year.

The supplement URL is looked up in congress_url_report.csv (columns: name,year,url).

Examples:
    python run_congress.py esc --year 2025 --abstract yes --count all
    python run_congress.py sno --year 2025
    python run_congress.py --list

Names: era, esc, ecco, esmo, idweek, sno. Output goes into that congress's folder.
Optional: --url to override the URL from congress_url_report.csv.
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL_FILE = HERE / "congress_url_report.csv"
CONGRESSES = {
    "era": "extract_ERA/extract_ERA_oxford.py",
    "esc": "extract_ESC/extract_ESC_oxford.py",
    "ecco": "extract_ECCO/extract_ECCO_oxford.py",
    "esmo": "extract_ESMO/extract_ESMO_oxford.py",
    "idweek": "extract_IDWEEK/extract_IDWEEK_oxford.py",
    "sno": "extract_SNO/extract_SNO_oxford.py",
}


def lookup_url(name: str, year: int) -> str | None:
    if not URL_FILE.exists():
        return None
    with URL_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("name") or "").strip().lower() == name and (row.get("year") or "").strip() == str(year):
                return (row.get("url") or "").strip() or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", help="congress name: " + ", ".join(CONGRESSES))
    parser.add_argument("--year", type=int, help="congress year, e.g. 2025")
    parser.add_argument("--url", help="optional: override the URL from congress_url_report.csv")
    parser.add_argument("--output", help="optional output CSV name (must contain the year)")
    parser.add_argument("--abstract", choices=["yes", "no"], help="include abstract text? (asked if omitted)")
    parser.add_argument("--count", help='how many abstracts: "all" or a number (asked if omitted)')
    parser.add_argument("--list", action="store_true", help="list supported congresses")
    args = parser.parse_args()

    if args.list:
        print("Supported congresses:", ", ".join(CONGRESSES))
        return 0

    name = args.name or input(f"Congress name ({', '.join(CONGRESSES)}): ")
    key = name.strip().lower()
    if key not in CONGRESSES:
        print(f"Unknown congress '{name}'. Choose from: {', '.join(CONGRESSES)}", file=sys.stderr)
        return 2

    year = args.year
    while year is None:
        answer = input("Year (e.g. 2025): ").strip()
        year = int(answer) if answer.isdigit() and len(answer) == 4 else None

    url = args.url or lookup_url(key, year)
    if not url:
        print(f"No URL found for {key} {year} in {URL_FILE.name}. "
              f"Add a row 'name,year,url' to that file (or pass --url).", file=sys.stderr)
        return 2
    print(f"Using URL: {url}")

    abstract = args.abstract
    while abstract is None:
        answer = input("Do you need the abstract text in the CSV? (y/n): ").strip().lower()
        abstract = {"y": "yes", "yes": "yes", "n": "no", "no": "no"}.get(answer)

    count = args.count
    while count is None or not (count.strip().lower() == "all" or count.strip().isdigit()):
        count = input("How many abstracts do you need? (all or a number) [all]: ").strip() or "all"

    script = HERE / CONGRESSES[key]
    cmd = [sys.executable, str(script), "--url", url]
    cmd += ["--output", args.output] if args.output else ["--year", str(year)]
    cmd += ["--abstract", abstract, "--count", count.strip().lower()]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
