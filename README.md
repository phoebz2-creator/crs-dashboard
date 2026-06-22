# CRS Daily Reports

CRS Daily Reports is a static dashboard for public Congressional Research Service reports. The frontend reads `reports.json`; `update_reports.py` refreshes that JSON from the official Congress.gov API.

## Data Source

This project uses the official Congress.gov API CRS Reports endpoints:

```text
GET https://api.congress.gov/v3/crsreport
GET https://api.congress.gov/v3/crsreport/{reportNumber}
```

The updater requests the list endpoint, fetches detail records when report numbers are available, normalizes fields, and writes `reports.json`.

## Setup

Request a Congress.gov API key from:

```text
https://api.congress.gov/sign-up/
```

Set the key in your shell:

```bash
export CONGRESS_API_KEY="your_api_key_here"
```

## Update Reports

Run the updater from this folder:

```bash
cd /Users/phoeeebesmacbook/Desktop/Codex
python3 update_reports.py
```

Fetch a larger set:

```bash
python3 update_reports.py --limit 50
```

Change the lookback window:

```bash
python3 update_reports.py --days 30
```

You can also pass a key directly:

```bash
python3 update_reports.py --api-key "your_api_key_here"
```

The script overwrites `reports.json`. If the API request fails, the existing `reports.json` remains unchanged.

## Open Locally

Because the browser loads `reports.json` with `fetch()`, use a local server:

```bash
cd /Users/phoeeebesmacbook/Desktop/Codex
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## Daily Updates

Manual daily update:

```bash
cd /Users/phoeeebesmacbook/Desktop/Codex
export CONGRESS_API_KEY="your_api_key_here"
python3 update_reports.py
```

Example macOS cron schedule for 7:00 AM daily:

```bash
crontab -e
```

Add:

```cron
0 7 * * * cd /Users/phoeeebesmacbook/Desktop/Codex && CONGRESS_API_KEY="your_api_key_here" /usr/bin/python3 update_reports.py >> update.log 2>&1
```

## GitHub Actions Updates

This repository includes `.github/workflows/update-reports.yml`, which runs `update_reports.py` every hour and can also be started manually from the GitHub Actions tab. If `reports.json` changes, the workflow commits and pushes the updated file back to the `main` branch.

Add the API key as a GitHub repository secret:

1. Open the GitHub repository in your browser.
2. Go to `Settings`.
3. Go to `Secrets and variables`.
4. Select `Actions`.
5. Click `New repository secret`.
6. Set the secret name to:

```text
CONGRESS_API_KEY
```

7. Paste your Congress.gov API key as the secret value.
8. Click `Add secret`.

Do not commit the API key to the repository. The workflow reads it securely through `${{ secrets.CONGRESS_API_KEY }}`.

## Architecture

```text
Congress.gov API
      |
      | GET /v3/crsreport
      | GET /v3/crsreport/{reportNumber}
      v
update_reports.py
      |
      | normalize title, date, report number, topic, summary, PDF URL
      v
reports.json
      |
      | browser fetch()
      v
CRS Daily Reports static dashboard
      |
      | search and category filters
      v
Policy researchers, analysts, and think tank users
```

## Production Notes

For production, run `update_reports.py` on a scheduler such as cron, GitHub Actions, or a serverless scheduled job. Store `CONGRESS_API_KEY` as a secret, preserve the previous `reports.json` on failures, and publish the static site after each successful update.
