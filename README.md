# CheckMyWeb Scraper 🔍

A personal CLI tool to track your website's Google search rankings — no API key needed. Scrapes Google directly using Python.

> No dashboard. No API key. No cost. Just your terminal.

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## ⚠️ Important note on scraping

This tool scrapes Google directly. It works well for **personal, low-volume use** (a few searches at a time, a few times a day). Google may occasionally return a CAPTCHA or block the request — if that happens, just wait a few minutes and try again with a longer `--delay`.

For **reliable, production-grade** rank checking, see [checkmyweb](https://github.com/yourusername/checkmyweb) — the SerpAPI-powered version.

---

## Features

- **No API key needed** — scrapes Google directly
- **Full ranked list** — see every result for a keyword, not just your position
- **History tracking** — saves snapshots over time so you can see rank movement (▲ ▼)
- **Trend report** — classifies keywords as rising, falling, volatile, or stable
- **Competitor tracking** — highlights rival sites in results alongside you
- **Rank alerts** — warns you if your ranking drops more than N positions
- **Export to CSV** — save results and full history anytime

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/checkmyweb-scraper.git
cd checkmyweb-scraper
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run it
```bash
python scrape.py --site yoursite.com --keywords "your keyword"
```

No API key or `.env` file needed.

---

## Usage

### Basic rank check
```bash
python scrape.py --site yoursite.com --keywords "your keyword"
```

### Save a snapshot for history tracking
```bash
python scrape.py --site yoursite.com --keywords "seo tool" "best seo" --save
```

### Check from a keywords file
```bash
python scrape.py --site yoursite.com --file keywords.txt --save
```

### Track competitors
```bash
python scrape.py --site yoursite.com --keywords "seo tool" --competitors rival.com --save
```

### Alert if rank drops 5+ positions
```bash
python scrape.py --site yoursite.com --keywords "seo tool" --alert 5 --save
```

### Philippine local search
```bash
python scrape.py --site yoursite.com --keywords "transient house daet" --country ph --save
```

### View rank history
```bash
python scrape.py --site yoursite.com --history
```

### View trend report
```bash
python scrape.py --site yoursite.com --report
```

### Export to CSV
```bash
python scrape.py --site yoursite.com --history --export history.csv
```

---

## Tips

- Use `--delay 8` or higher if Google blocks you
- Use `--country ph` for Philippine Google results (default)
- Run with `--save` every time to build history
- Use `--report` after several runs to see keyword trends
- If blocked, wait 5-10 minutes before trying again

---

## All options

| Flag | Default | Description |
|------|---------|-------------|
| `--site` | required | Your domain, e.g. `yoursite.com` |
| `--keywords` | — | One or more keywords |
| `--file` | — | Text file with keywords (one per line) |
| `--competitors` | — | Competitor domains to highlight |
| `--top` | `10` | How many results to check (max 20) |
| `--country` | `ph` | Country code e.g. `ph`, `us`, `gb` |
| `--delay` | `5` | Seconds between searches (increase if blocked) |
| `--alert` | — | Alert if rank drops by N or more positions |
| `--save` | off | Save this run to history |
| `--history` | off | View rank history |
| `--report` | off | View trend report |
| `--export` | — | Export to `.csv` |
| `--no-banner` | off | Skip ASCII banner |

---

## License

MIT
