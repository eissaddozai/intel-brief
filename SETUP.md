# Setup Guide

## Run locally

```bash
# 1. Frontend
npm install
npm run dev           # http://localhost:5173

# 2. Pipeline (Python 3.11+)
pip install -r requirements.txt
playwright install chromium

export ANTHROPIC_API_KEY=sk-ant-...
python pipeline/main.py --auto-approve
```

## GitHub Actions (automated daily brief)

### 1. Add secrets
Go to your repo → **Settings → Secrets and variables → Actions → New secret**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `CSE_EMAIL_USER` | Gmail address (optional, for CFR newsletter) |
| `CSE_EMAIL_PASS` | Gmail App Password (optional) |

### 2. Enable GitHub Pages
Go to **Settings → Pages → Source → GitHub Actions** → Save.

### 3. Trigger the first run
Go to **Actions → Daily Intel Brief → Run workflow**.

The workflow will:
1. Pull RSS feeds from 20+ sources
2. Triage and classify items by domain
3. Draft each section with Claude API
4. Write the cycle JSON to `cycles/` and `src/data/`
5. Commit and push the new cycle
6. Deploy the updated frontend to GitHub Pages

Your brief will be live at: `https://eissaddozai.github.io/intel-brief`

---

## Pipeline stages (run individually)

```bash
python pipeline/main.py --stage ingest    # Collect from RSS + scrape + email
python pipeline/main.py --stage triage    # Classify + novelty filter + confidence
python pipeline/main.py --stage draft     # Claude API drafting
python pipeline/main.py --stage review    # Interactive human review CLI
python pipeline/main.py --stage output    # Write final cycle JSON

# Backfill a specific date
python pipeline/main.py --date 2026-03-01 --auto-approve
```
