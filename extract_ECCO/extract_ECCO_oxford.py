"""Standalone ERA abstract collector for Oxford Academic NDT supplements.

Edit only SUPPLEMENT_URL and OUTPUT_FILE at the bottom, then run this file.
Uses Oxford's DOI metadata deposited with Crossref to retrieve the complete
supplement without Cloudflare or browser-navigation failures.

Install once: python -m pip install requests
"""
from __future__ import annotations

import csv
import html
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

CONGRESS = "ECCO"
JOURNALS = {
    "ecco-jcc": {"name": "Journal of Crohn's and Colitis", "issn": "1876-4479"},
}
ROWS_PER_PAGE = 1000
TIMEOUT = 120
RETRIES = 5
FIELDS = ["congress", "journal", "supplement_url", "issue_url", "article_url",
          "doi", "abstract_number", "title", "authors", "publication_date",
          "volume", "issue", "pages", "abstract", "full_text", "status",
          "scraped_utc", "error"]


class _JATSText(HTMLParser):
    BLOCKS = {"p", "title", "sec", "br", "li"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.split(":")[-1].lower() in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.split(":")[-1].lower() in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_multiline(value: str | None) -> str:
    return "\n".join(clean(line) for line in (value or "").splitlines() if clean(line))


def strip_jats(value: str | None) -> str:
    parser = _JATSText()
    parser.feed(value or "")
    text = clean_multiline(html.unescape("".join(parser.parts)))
    return re.sub(r"(?i)^abstract\s*", "", text).strip()


def normalize_url(value: str) -> str:
    value = unquote((value or "").strip().strip("\"'"))
    return value.rstrip("/ \"'")


def parse_issue_url(url: str) -> tuple[dict[str, str], str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "academic.oup.com":
        raise ValueError("SUPPLEMENT_URL must be an HTTPS academic.oup.com URL")
    match = re.fullmatch(r"/([^/]+)/issue/([^/]+)/([^/]+)", parsed.path, re.I)
    if not match:
        raise ValueError("Use an Oxford issue URL such as https://academic.oup.com/ndt/issue/40/Supplement_3")
    slug, volume, issue = match.groups()
    journal = JOURNALS.get(slug.casefold())
    if not journal:
        raise ValueError(f"This {CONGRESS} scraper does not support Oxford journal slug '{slug}'")
    return journal, volume, issue


def publication_year(output_file: str) -> int:
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", Path(output_file).name)
    if not match:
        raise ValueError("OUTPUT_FILE must contain the year, for example ERA_2025_Abstracts.csv")
    return int(match.group(1))


def request_json(session: requests.Session, api_url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = session.get(api_url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()["message"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"Crossref request failed after {RETRIES} attempts: {last_error}")


def item_matches_issue(item: dict, volume: str, issue: str) -> bool:
    if str(item.get("volume", "")) != volume:
        return False
    target = re.sub(r"[^a-z0-9]", "", issue.casefold())
    stored = re.sub(r"[^a-z0-9]", "", str(item.get("issue", "")).casefold())
    if stored == target:
        return True
    for link in item.get("link", []) or []:
        path_parts = [re.sub(r"[^a-z0-9]", "", part.casefold())
                      for part in urlparse(str(link.get("URL", ""))).path.split("/")]
        for index, part in enumerate(path_parts[:-1]):
            if part == volume and path_parts[index + 1] == target:
                return True
    return False


def crossref_census(issn: str, year: int, volume: str, issue: str) -> tuple[list[dict], int, int]:
    session = requests.Session()
    session.headers.update({"User-Agent": f"{CONGRESS}AbstractCollector/2.0 (research metadata collection)",
                            "Accept": "application/json"})
    api_url = f"https://api.crossref.org/journals/{issn}/works"
    for publication_year in (year, year - 1, year + 1):
        cursor = "*"
        screened = 0
        selected: dict[str, dict] = {}
        target_issue = re.sub(r"[^a-z0-9]", "", issue.casefold())
        while True:
            message = request_json(session, api_url, {
                "filter": f"from-pub-date:{publication_year}-01-01,until-pub-date:{publication_year}-12-31",
                "rows": ROWS_PER_PAGE,
                "cursor": cursor,
                "select": "DOI,volume,issue,abstract,title,author,URL,link,published,published-online,published-print,article-number,page",
            })
            batch = message.get("items", [])
            if not batch:
                break
            screened += len(batch)
            for item in batch:
                if not item_matches_issue(item, volume, issue):
                    continue
                doi = clean(item.get("DOI")).lower()
                if doi:
                    selected[doi] = item
            print(f"Screened {screened} journal records for {publication_year}; matched {len(selected)}", flush=True)
            if screened >= int(message.get("total-results", screened)):
                break
            next_cursor = message.get("next-cursor")
            if not next_cursor or next_cursor == cursor:
                raise RuntimeError("Crossref pagination stopped before all records were screened")
            cursor = next_cursor
            time.sleep(0.1)
        if selected:
            return list(selected.values()), screened, publication_year
    return [], 0, year


def date_from(item: dict) -> str:
    for key in ("published", "published-online", "published-print"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            values = list(parts[0]) + [1, 1]
            return f"{values[0]:04d}-{values[1]:02d}-{values[2]:02d}"
    return ""


def authors_from(item: dict) -> str:
    authors = []
    for person in item.get("author", []):
        name = clean(" ".join(filter(None, (person.get("given"), person.get("family")))))
        if name and name not in authors:
            authors.append(name)
    return "; ".join(authors)


def row_from(item: dict, supplement_url: str, journal_name: str) -> dict[str, str]:
    title = clean((item.get("title") or [""])[0])
    abstract = strip_jats(item.get("abstract"))
    doi = clean(item.get("DOI"))
    number_match = re.match(r"^#\s*([A-Za-z0-9.-]+)", title)
    number = number_match.group(1) if number_match else ""
    article_url = clean(item.get("URL")) or (f"https://doi.org/{doi}" if doi else "")
    status = "OK" if doi and title and abstract else "INCOMPLETE"
    missing = [name for name, value in (("doi", doi), ("title", title), ("abstract", abstract)) if not value]
    return {"congress": CONGRESS, "journal": journal_name,
            "supplement_url": supplement_url, "issue_url": supplement_url,
            "article_url": article_url, "doi": doi, "abstract_number": number,
            "title": title, "authors": authors_from(item),
            "publication_date": date_from(item), "volume": clean(item.get("volume")),
            "issue": clean(item.get("issue")),
            "pages": clean(item.get("page") or item.get("article-number")),
            "abstract": abstract, "full_text": abstract, "status": status,
            "scraped_utc": datetime.now(timezone.utc).isoformat(),
            "error": "Missing " + ", ".join(missing) if missing else ""}


def sort_key(row: dict[str, str]):
    match = re.search(r"\.(\d+)$", row["doi"])
    return (int(match.group(1)) if match else 10**12, row["doi"])


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    supplement_url = normalize_url(SUPPLEMENT_URL)
    journal, volume, issue = parse_issue_url(supplement_url)
    year = publication_year(OUTPUT_FILE)
    output = Path(OUTPUT_FILE)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent / "output_file" / output
        output.parent.mkdir(exist_ok=True)

    items, screened, publication_year_used = crossref_census(journal["issn"], year, volume, issue)
    rows = sorted((row_from(item, supplement_url, journal["name"]) for item in items), key=sort_key)
    if not rows:
        raise RuntimeError(f"No Crossref records matched volume {volume}, issue {issue}, year {year}")
    write_csv(output, rows)

    unique_dois = len({row["doi"].lower() for row in rows if row["doi"]})
    audit_data = {"congress": CONGRESS, "journal": journal["name"],
                  "supplement_url": supplement_url, "year": year, "volume": volume,
                  "publication_year_used": publication_year_used,
                  "issue": issue, "screened_journal_records": screened,
                  "matched_supplement_records": len(rows), "unique_dois": unique_dois,
                  "successful_with_abstract": sum(row["status"] == "OK" for row in rows),
                  "incomplete": sum(row["status"] != "OK" for row in rows),
                  "generated_utc": datetime.now(timezone.utc).isoformat(),
                  "source": "Oxford University Press metadata deposited with Crossref"}
    audit = output.with_name(output.stem + "_audit.json")
    audit.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} records ({unique_dois} unique DOIs) to {output}")
    print(f"Audit: {audit}")


# EDIT ONLY THESE TWO LINES FOR EACH ANNUAL RUN.
SUPPLEMENT_URL = "https://academic.oup.com/ecco-jcc/issue/20/Supplement_1"
OUTPUT_FILE = "ECCO_2026_Abstracts.csv"


if __name__ == "__main__":
    import argparse

    cli = argparse.ArgumentParser(description="ECCO abstract scraper. With no options, uses the values above.")
    cli.add_argument("--url", help="Oxford supplement issue URL (overrides SUPPLEMENT_URL)")
    cli.add_argument("--year", type=int, help="Congress year; output becomes ECCO_<year>_Abstracts.csv")
    cli.add_argument("--output", help="Output CSV name (must contain the year); overrides --year")
    cli.add_argument("--abstract", choices=["yes", "no"],
                     help="yes = include abstract text in the CSV; no = metadata only (asked if omitted)")
    cli.add_argument("--count", help='how many abstracts: "all" or a number (asked if omitted)')
    args = cli.parse_args()
    want_abstract = args.abstract
    want_count = args.count
    while want_count is None or not (want_count.strip().lower() == "all" or want_count.strip().isdigit()):
        try:
            want_count = input('How many abstracts do you need? (all or a number) [all]: ').strip() or "all"
        except EOFError:
            want_count = "all"
    want_count = want_count.strip().lower()
    MAX_RECORDS = None if want_count == "all" else int(want_count)
    while want_abstract is None:
        try:
            answer = input("Do you need the abstract text in the CSV? (y/n): ").strip().lower()
        except EOFError:
            answer = "y"
        want_abstract = {"y": "yes", "yes": "yes", "n": "no", "no": "no"}.get(answer)
    if args.url:
        SUPPLEMENT_URL = args.url
    if args.output:
        OUTPUT_FILE = args.output
    elif args.year:
        OUTPUT_FILE = f"ECCO_{args.year}_Abstracts.csv"
    main()
    if want_abstract == "no" or MAX_RECORDS is not None:
        _csv = Path(OUTPUT_FILE)
        if not _csv.is_absolute():
            _csv = Path(__file__).resolve().parent / "output_file" / _csv
        with _csv.open(encoding="utf-8-sig", newline="") as _handle:
            _rows = list(csv.DictReader(_handle))
        if MAX_RECORDS is not None:
            _rows = _rows[:MAX_RECORDS]
            print(f"Kept the first {len(_rows)} records.")
        _keep = [f for f in FIELDS if want_abstract == "yes" or f not in ("abstract", "full_text")]
        with _csv.open("w", encoding="utf-8-sig", newline="") as _handle:
            _writer = csv.DictWriter(_handle, fieldnames=_keep, extrasaction="ignore")
            _writer.writeheader()
            _writer.writerows(_rows)
        if want_abstract == "no":
            print(f"Abstract text removed from {_csv} (metadata only).")
