---
name: intel-ingest
description: "Phase 1 of the intelligence brief pipeline. This skill fetches ALL 90+ sources from sources.yaml in parallel using curl. It should be triggered by /intel-ingest or as the first step of /workflow. Output is raw source content saved to scratch/raw/<timestamp>/."
---

# Intel Ingest — Source Collection

**Invocation:** `/intel-ingest`

Fetch all 90+ sources defined in `pipeline/ingest/sources.yaml` in parallel. This is Phase 1 of the multi-skill intelligence brief pipeline.

## How It Works

1. Run the parallel fetch script: `bash .claude/skills/intel-ingest/scripts/fetch_all_sources.sh`
2. The script uses `xargs -P 12` to fetch up to 12 sources simultaneously
3. Each source produces two files in `scratch/raw/<timestamp>/`:
   - `<source_id>.raw` — the raw HTML/XML/RSS content
   - `<source_id>.meta` — JSON metadata (HTTP code, size, tier, duration)
4. A `_manifest.json` summarizes the fetch run

## After Fetching

After the script completes, review the manifest for:
- **Tier 1 failures** (critical — these are the factual backbone)
- **Sources returning < 500 bytes** (likely blocked or empty)
- **Sources returning captcha/403** (need fallback approach)

For failed Tier 1 sources, attempt manual fetches with alternate User-Agent strings or alternate URLs before proceeding to triage.

## Output Contract

The output directory (`scratch/raw/<timestamp>/`) is the input for `/intel-triage`.

Each `.meta` file contains:
```json
{
  "id": "source_id",
  "tier": 1,
  "method": "rss",
  "url": "https://...",
  "http_code": 200,
  "size_bytes": 45230,
  "fetch_duration_s": 3,
  "timestamp": "2026-03-07T06:00:00Z"
}
```

## Source Count Target

The fetch script contains 75+ source URLs. Combined with any manual fallback fetches, the goal is to attempt ALL sources in `pipeline/ingest/sources.yaml` every cycle.

## Important Rules

- **Never truncate** source content — save the full response
- **Never skip Tier 1 sources** — if they fail, retry with alternate methods
- **Log every failure** — failed sources become Collection Gaps in the brief
- If WebFetch or WebSearch are available and working, use them as supplements for article-level deep reads after the bulk fetch

## Next Step

After ingestion completes, proceed to `/intel-triage` which will:
1. Run `python scripts/parse_raw_sources.py` to convert raw files into structured items
2. Run the Python triage pipeline (classify, novelty, confidence)

The raw output in `scratch/raw/<timestamp>/` is not directly usable by the drafter — it must be parsed and triaged first.
