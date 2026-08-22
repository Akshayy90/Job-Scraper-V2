# Job Scraper — Streamlit + CLI + Google Sheets

A Python job-scraping pipeline using Playwright, site-specific adapters, Streamlit, CLI, and Google Sheets.

## What changed

The Naukri target is now scraped directly from the rendered search-result cards instead of opening every candidate link and feeding it to a generic heuristic parser.

For the current Naukri page, the adapter reads:

- `div.srp-jobtuple-wrapper` — job card
- `h2 a.title` — role + job URL
- `a.comp-name` — company
- `.loc-wrap .locWdth` — location
- `.exp-wrap .expwdth` — experience (logged for diagnostics)
- `.job-post-day` — posted age (logged for diagnostics)
- `link[rel="next"]` — next page

The requested Google Sheet schema remains:

| Company Name | Role | Link | Location | Date Added | Deadline | Status | Last Checked |
|---|---|---|---|---|---|---|---|

## Project structure

```text
job_scraper/
├── app.py
├── cli.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── credentials/
│   └── service-account.json       # local only; never commit
├── scraper/
│   ├── __init__.py
│   ├── browser.py
│   ├── config.py
│   ├── models.py
│   ├── parser.py                  # generic fallback
│   ├── pipeline.py
│   ├── sheets.py
│   └── adapters/
│       ├── __init__.py
│       └── naukri.py
└── output/
    └── debug/
```

## Install on Windows

```powershell
py -m venv .ak
.ak\Scripts\activate.bat
pip install -r requirements.txt
python -m playwright install chromium
```

If PowerShell execution policy blocks activation, using Command Prompt is fine:

```cmd
.ak\Scripts\activate.bat
```

You can also skip activation and run `.ak\Scripts\python.exe` directly.

## `.env`

```env
TARGET_URLS=https://www.naukri.com/front-office-executive-jobs-in-hyderabad-secunderabad?expJD=true
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service-account.json
HEADLESS=true
REQUEST_TIMEOUT_MS=30000
MAX_PAGES_PER_TARGET=3
MAX_JOBS_PER_TARGET=100
DEBUG=false
SAVE_HTML=false
SCREENSHOTS=false
OUTPUT_DIR=output
```

Multiple URLs can be comma-separated or placed one per line.

## CLI

Scrape only:

```powershell
.ak\Scripts\python.exe cli.py scrape
```

Scrape and save CSV:

```powershell
.ak\Scripts\python.exe cli.py scrape --csv output/jobs.csv
```

Scrape and sync Google Sheets:

```powershell
.ak\Scripts\python.exe cli.py run --sync
```

Sync an existing CSV:

```powershell
.ak\Scripts\python.exe cli.py sync --csv output/jobs.csv
```

## Streamlit

```powershell
.ak\Scripts\python.exe -m streamlit run app.py
```

The UI previews the actual scraped records and optionally synchronizes them to Google Sheets.

## Naukri scraping behavior

The Naukri adapter does not invent job data. It reads the rendered job cards from the Playwright page.

For each card it extracts:

```text
Company Name  ← a.comp-name
Role          ← h2 a.title
Link          ← h2 a.title[href]
Location      ← .loc-wrap .locWdth
```

`Deadline` is left blank when it is not available in the listing card. We do not fabricate a deadline.

The adapter follows Naukri's `rel="next"` URL up to `MAX_PAGES_PER_TARGET`.

## Date Added vs Last Checked

`Date Added` means the first time the job was inserted into the Sheet.

`Last Checked` is updated on every successful sync.

The Google Sheets layer preserves the existing `Date Added` when the same job URL is seen again.

## Debug mode

Use:

```env
DEBUG=true
SAVE_HTML=true
SCREENSHOTS=true
```

Then run:

```powershell
.ak\Scripts\python.exe cli.py scrape
```

Debug files are written under:

```text
output/debug/
```

This is useful when a site changes its DOM.

## Adding another site

Create an adapter under:

```text
scraper/adapters/<site>.py
```

Implement:

```python
can_handle(url)
extract_jobs(page, source_url)
next_page_url(page)
```

Then register the adapter in `scraper/pipeline.py`.

The Google Sheets and Streamlit layers do not need to change.

## Google Sheets

The service account must have Editor access to the target Google Sheet. Do not commit the JSON credential.
