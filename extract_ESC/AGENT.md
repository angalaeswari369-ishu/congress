# AGENT.md - ESC scraper (extract_ESC)

Instructions for an LLM/coding agent working in this folder.

## Purpose
Run `extract_ESC_oxford.py` to collect all abstracts of the European Society of Cardiology (ESC) Congress supplement
(*European Heart Journal*, Oxford Academic) into a CSV plus an audit JSON.

## Inputs you need from the user
- The URL is NOT needed from the user: `run_congress.py` looks it up in `congress_url_report.csv` (name,year,url). If the row for that name+year is missing, ask the user for the URL and add a row to `congress_url_report.csv`.
- Whether the user wants the abstract text (`--abstract yes|no`). If unknown, ASK the user; `no` drops the `abstract` and `full_text` columns from the CSV.
- How many abstracts (`--count all` or a number, first N by DOI order). If the user does not specify, use `all`.
- The congress year (`--year`, 4 digits). If the user did not give one,
  infer it from the volume, state your assumption, and tell the user.

## Procedure
1. Do NOT edit code. Run from the `Congress` parent folder:
   `python run_congress.py esc --year <year> --abstract <yes|no> --count <all|N>`
   (output file becomes `ESC_<year>_Abstracts.csv` in this folder; `--output NAME.csv` overrides it).
   Example: `python run_congress.py esc --year 2025 --abstract yes --count all`.
   Congress names accepted by the launcher: era, esc, ecco, esmo, idweek, sno.
   The script can also be run directly with the same `--url/--year/--output` options.
2. Ensure `requests` is installed (`python -m pip install requests`).
3. The command in step 1 is the run step (timeout up to 10 minutes; pagination over Crossref can take a while).
4. Success output ends with `Saved N records (N unique DOIs) to ...` and `Audit: ...`.
5. Read `<output>_audit.json` and report to the user: matched records, unique DOIs,
   successful_with_abstract, incomplete, publication_year_used.

## How it works (do not "fix" it)
Uses the Crossref API with the journal ISSN (slug `eurheartj` is mapped in the `JOURNALS` dict),
screens all works for the year, and keeps those whose volume/issue match the URL. No browser,
no Cloudflare. If a new journal slug is needed, add it to `JOURNALS` with its ISSN.

## Failure handling
- `must contain the year` -> rename OUTPUT_FILE.
- `does not support Oxford journal slug` -> add the slug/ISSN to `JOURNALS`.
- `No Crossref records matched` -> verify volume/supplement and year with the user; the script also
  tries year-1 and year+1 automatically.
- Network errors are retried 5 times; if still failing, report the error.
