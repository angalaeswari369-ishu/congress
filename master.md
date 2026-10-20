# Congress Abstract Scraper - Master Guide

One command collects the abstracts of a medical congress from an Oxford Academic journal
supplement and saves them as a CSV. Six congresses are supported.

## 1. What is in this folder

| Item | Purpose |
|---|---|
| `run_congress.py` | The launcher. This is the only file you run. It picks the right script for the congress. |
| `congress_url_report.csv` | The URL list (`name,year,url`). The launcher looks up the supplement URL here. |
| `master.md` | This guide. |
| `extract_ERA\` | ERA - `extract_ERA_oxford.py` |
| `extract_ESC\` | ESC - `extract_ESC_oxford.py` |
| `extract_ECCO\` | ECCO - `extract_ECCO_oxford.py` |
| `extract_IDWEEK\` | IDWeek - `extract_IDWEEK_oxford.py` |
| `extract_SNO\` | SNO - `extract_SNO_oxford.py` |
| `extract_ESMO\` | ESMO - `extract_ESMO_oxford.py` (works differently, see section 7) |

Every congress folder contains, in this order:
1. `README.md` - step-by-step instructions for a person.
2. `AGENT.md` - the same instructions written for an AI/LLM assistant.
3. The Python code - `extract_<NAME>_oxford.py`.
4. `output_file\` - the results of each run: `<NAME>_<year>_Abstracts.csv` and `<NAME>_<year>_Abstracts_audit.json`.

## 2. Supported congresses

| Name to type | Congress | Journal | Data source |
|---|---|---|---|
| `era` | European Renal Association | Nephrology Dialysis Transplantation | Crossref |
| `esc` | European Society of Cardiology | European Heart Journal | Crossref |
| `ecco` | European Crohn's and Colitis Organisation | Journal of Crohn's and Colitis | Crossref |
| `idweek` | IDWeek (IDSA) | Open Forum Infectious Diseases | Crossref |
| `sno` | Society for Neuro-Oncology | Neuro-Oncology | Crossref |
| `esmo` | European Society for Medical Oncology | Annals of Oncology | Oxford website via browser |

Run `python run_congress.py --list` to see the names.

## 3. One-time setup

1. Install Python 3.
2. Install the dependency:
   ```bash
   python -m pip install requests
   ```
3. ESMO only:
   ```bash
   python -m pip install playwright beautifulsoup4
   python -m playwright install chromium
   ```
   ESMO also needs Google Chrome installed.

## 4. How to run

Open a terminal in the `Congress` folder, then:

```bash
python run_congress.py <name> --year <year> --abstract <yes|no> --count <all|N>
```

Example:

```bash
python run_congress.py era --year 2025 --abstract yes --count all
```

## 5. Input parameters

| Parameter | Required | Values | Meaning | If left out |
|---|---|---|---|---|
| `name` (first word) | Yes | `era`, `esc`, `ecco`, `idweek`, `sno`, `esmo` | Which congress to run | Asked |
| `--year` | Yes | 4-digit year, e.g. `2025` | Congress year. Used to find the URL and to name the output file | Asked |
| `--abstract` | Yes | `yes` / `no` | `yes` = full CSV with abstract text. `no` = same CSV without the `abstract` and `full_text` columns | Asked (y/n) |
| `--count` | Yes | `all` or a number | `all` = every record. A number (e.g. `50`) = the first N records in DOI order | Asked (Enter = all) |
| `--url` | No | Oxford issue URL | Overrides the URL from `congress_url_report.csv` for one run | Uses `congress_url_report.csv` |
| `--output` | No | file name containing the year | Choose the output file name | `<NAME>_<year>_Abstracts.csv` |

You do **not** give the URL each time. It is read from `congress_url_report.csv`.

## 6. Order of flow (what happens when you run it)

1. You run `run_congress.py` with the congress name and year.
2. It asks for anything you did not give (name, year).
3. It looks up the URL for that name and year in `congress_url_report.csv`.
   - Not found: it stops and prints `No URL found for <name> <year> in congress_url_report.csv`. Add a row or pass `--url`.
4. It prints `Using URL: ...` so you can see which row it used.
5. It asks for anything still missing: abstract y/n, then count.
6. It starts the congress script from that congress's folder.
7. The script downloads the records.
   - **ERA, ESC, ECCO, IDWeek, SNO:** calls the Crossref API for the journal, downloads every article for that
     year, and keeps those whose volume and issue match the URL.
   - **ESMO:** opens Chrome, loads the Oxford issue pages, collects the article links, then opens each article.
8. The records are sorted and saved to `<NAME>_<year>_Abstracts.csv`.
9. If `--abstract no`, the `abstract` and `full_text` columns are removed. If `--count` is a number, the CSV is cut to that many rows.
10. An audit file `<NAME>_<year>_Abstracts_audit.json` is written next to the CSV.

## 7. Notes for ESMO

ESMO is the only congress that cannot use Crossref (Crossref does not have its abstracts), so it reads Oxford's
pages directly. Oxford protects them with a Cloudflare "Verifying you are human" check.

- A visible Chrome window opens. A person must complete the check; the script waits up to 15 minutes, then continues.
- If the check never passes, the script stops with "Oxford verification was not completed" and saves nothing.
  Try a different network (no VPN), open the URL in normal Chrome first, or get the data from Oxford/ESMO directly.
- The scripts and agents must not try to bypass the check.
- The folder `.oxford_esmo_browser_profile` is created by this script to remember the browser session. It is safe to delete.
- The ESMO 2019 congress abstracts are in volume 30 `Supplement_5`. `congress_url_report.csv` currently has `Supplement_11` for
  2019 - confirm which one is needed.

## 8. Output

`<NAME>_<year>_Abstracts.csv` columns:

congress, journal, supplement_url, issue_url, article_url, doi, abstract_number, title, authors, publication_date,
volume, issue, pages, abstract, full_text, status (`OK` or `INCOMPLETE`), scraped_utc, error.

`abstract` and `full_text` are absent when you choose `--abstract no`.

The audit file has: records matched, unique DOIs, records with an abstract, records incomplete, year and source.
Check it after every run: matched records should be close to the number of abstracts in the supplement.

## 9. Adding a new year

1. Open the supplement on Oxford Academic and copy its issue URL, for example
   `https://academic.oup.com/ndt/issue/41/Supplement_3`.
2. Add a row to `congress_url_report.csv`:
   ```
   era,2026,https://academic.oup.com/ndt/issue/41/Supplement_3
   ```
3. Run `python run_congress.py era --year 2026 ...`.

## 10. Adding a new congress

1. Copy an existing Crossref script folder and rename it.
2. In the script, set `CONGRESS` and add the journal slug and its ISSN to the `JOURNALS` dictionary.
3. Add the congress to the `CONGRESSES` list in `run_congress.py`.
4. Add rows for it in `congress_url_report.csv`.
5. Add a `README.md` and `AGENT.md` in the new folder.

## 11. Common errors

| Message | Cause | Fix |
|---|---|---|
| `Unknown congress` | Name not in the list | Use `--list` to see the valid names |
| `No URL found for <name> <year>` | No row in `congress_url_report.csv` | Add the row, or pass `--url` |
| `PermissionError: ... .csv` | The CSV is open in Excel or being synced by OneDrive | Close the file and run again |
| `OUTPUT_FILE must contain the year` | The `--output` name has no 4-digit year | Add the year to the file name |
| `No Crossref records matched` | Wrong volume, supplement or year | Check the URL and year |
| `Oxford verification was not completed` | ESMO only: Cloudflare check not passed | See section 7 |

## 12. Known limits

- The five Crossref congresses download the whole issue and then trim it, so `--count` does not make them faster.
  For ESMO, `--count` limits how many articles are opened, so it does save time.
- Records come from what Oxford deposited with Crossref. Check the record count against the issue page if you need certainty.
- There is no option to run all congresses in one command yet; run them one at a time.
