# U.S. Policy Research Dashboard

U.S. Policy Research Dashboard is a static webpage for tracking recent publications from CRS and major U.S. think tanks in one searchable interface.

The frontend reads `sources.json`. The updater script, `update_sources.py`, refreshes that file from:

- Congressional Research Service through the official Congress.gov API
- Think tank RSS/XML feeds configured in `sources_config.json`

## Included Sources

- Congressional Research Service
- Brookings Institution
- CSIS
- RAND Corporation
- Council on Foreign Relations
- Carnegie Endowment for International Peace
- American Enterprise Institute
- Heritage Foundation
- Hudson Institute
- Hoover Institution

## Data Files

```text
sources_config.json   Feed/API source configuration
sources.json          Generated dashboard data
update_sources.py     Updater for CRS API and RSS feeds
```

Some RSS feed URLs are public feed candidates and may need adjustment if a think tank changes its website structure. Update `sources_config.json` to replace or add feed URLs without changing the Python code.

## Congress.gov API Key

CRS data uses the official Congress.gov CRS Reports API:

```text
GET https://api.congress.gov/v3/crsreport
GET https://api.congress.gov/v3/crsreport/{reportNumber}
```

Request a Congress.gov API key:

```text
https://api.congress.gov/sign-up/
```

Set the key locally:

```bash
export CONGRESS_API_KEY="your_api_key_here"
```

Do not put the API key in frontend JavaScript, `sources.json`, or committed files.

## Update Sources Locally

Run:

```bash
cd /Users/phoeeebesmacbook/Desktop/Codex
export CONGRESS_API_KEY="your_api_key_here"
python3 update_sources.py
```

Options:

```bash
python3 update_sources.py --crs-limit 50
python3 update_sources.py --feed-limit 15
python3 update_sources.py --days 30
python3 update_sources.py --api-key "your_api_key_here"
```

The script overwrites `sources.json` only after it successfully fetches at least one item.

## Open Locally

Because the browser loads `sources.json` with `fetch()`, use a local server:

```bash
cd /Users/phoeeebesmacbook/Desktop/Codex
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## GitHub Actions Updates

The workflow at `.github/workflows/update-sources.yml` runs every hour and can also be started manually from the GitHub Actions tab. It runs `update_sources.py` and commits `sources.json` back to `main` if the generated data changes.

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

The workflow reads the key through `${{ secrets.CONGRESS_API_KEY }}` and does not expose it to the frontend.

## Architecture

```text
Congress.gov CRS API      Think tank RSS/XML feeds
          |                         |
          |                         |
          v                         v
              update_sources.py
                     |
                     | normalize source, title, date, topic, summary, URL
                     v
                sources.json
                     |
                     | browser fetch()
                     v
        U.S. Policy Research Dashboard
                     |
                     | keyword search and source filters
                     v
       Policy researchers, analysts, and think tank users
```

## Production Notes

For production, verify each configured feed URL in `sources_config.json`, store `CONGRESS_API_KEY` as a secret, and let GitHub Actions or another scheduler run `update_sources.py` hourly. If a source does not expose a stable RSS feed, leave its entry in `sources_config.json` and add the approved feed or API URL later.

## Source Status

Production-ready sources currently configured with working feeds:

- RAND Corporation
- Council on Foreign Relations
- Heritage Foundation
- Hudson Institute
- Hoover Institution

CRS is production-ready through the official Congress.gov API when `CONGRESS_API_KEY` is configured.

Disabled or unstable sources:

- Brookings Institution: advertised feed returns HTML in this environment instead of RSS/Atom XML.
- CSIS: disabled as unsupported/unstable. RSS discovery failed for current publications, sitemap discovery did not yield a stable publication feed, and HTML analysis page parsing did not produce a reliable extraction path.
- Carnegie Endowment for International Peace: tested feed URL returns HTML instead of RSS/Atom XML.
- American Enterprise Institute: tested feed URL returns HTTP 403.

To support CSIS in the future, use an official current-publications RSS/Atom feed, a documented public API, or a stable export endpoint from CSIS. Avoid maintaining dashboard-specific HTML selectors unless CSIS provides a stable contract for that markup.
