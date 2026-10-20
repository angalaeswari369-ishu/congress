# IDWeek abstract scraper

Collects all abstracts from the **IDWeek (Infectious Diseases Society of America)** supplement published in
*Open Forum Infectious Diseases (also supports Clinical Infectious Diseases, slug `cid`)* on Oxford Academic and saves them to a CSV.

- Script: `extract_IDWEEK_oxford.py`
- The script does **not** open Oxford's website. It reads the abstract metadata that Oxford deposited with Crossref (`api.crossref.org`), so there is no Cloudflare / verification prompt and no browser window.

## Steps

1. **Install Python 3** (once) and open a terminal in the parent `Congress` folder.
2. **Install dependencies** (once):
   ```bash
   python -m pip install requests
   ```
3. **Run it with the congress name and year** (no URL and no code editing needed):
   ```bash
   python run_congress.py idweek --year 2026 --abstract yes --count all
   ```
   - `idweek`: the congress name (`era`, `esc`, `ecco`, `esmo`, `idweek`, `sno`) - it picks the right script.
   - `--year`: the congress year. The output file is named `<NAME>_<year>_Abstracts.csv` automatically.
   - The supplement **URL is read from `congress_url_report.csv`** (columns `name,year,url`) in the Congress folder.
     For a new year, add one row there first. `--url` can override it for a one-off run.
   - `--abstract yes|no`: `yes` = full CSV with abstract text, `no` = without the `abstract` and `full_text` columns.
   - `--count all|N`: `all` for everything, or e.g. `50` for the first 50.
   - Any of `name`, `year`, `--abstract`, `--count` you leave out is asked interactively
     (count: press Enter for all).
4. Run `python run_congress.py --list` to see all supported congress names.
5. **Collect the results** in this folder:
   - `IDWeek_2026_Abstracts.csv` (the abstracts)
   - `IDWeek_2026_Abstracts_audit.json` (record counts: matched, with abstract, incomplete)

## Output columns

congress, journal, supplement_url, issue_url, article_url, doi, abstract_number, title, authors,
publication_date, volume, issue, pages, abstract, full_text, status (`OK` / `INCOMPLETE`),
scraped_utc, error.

## Checking the result

Open the `_audit.json`: `matched_supplement_records` should be close to the number of abstracts in
the supplement, and `incomplete` should be small.

## Common errors

- `OUTPUT_FILE must contain the year` - add the year to the filename.
- `Use an Oxford issue URL such as ...` - the URL format is wrong; copy it from the issue page.
- `No Crossref records matched` - wrong volume/supplement number or year in the filename.
