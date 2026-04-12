---
name: intel-triage
description: "Phase 2 of the intelligence brief pipeline. Parses raw fetched sources into structured items, then runs domain classification, novelty detection, and confidence assignment. Triggered by /intel-triage or as step 2 of /workflow."
---

# Intel Triage — Parse + Classify + Filter

**Invocation:** `/intel-triage`

Converts raw source content from `/intel-ingest` into triaged, domain-tagged items ready for drafting.

## Steps

### 1. Parse raw sources into items

```bash
python scripts/parse_raw_sources.py
```

This reads the latest `scratch/raw/<timestamp>/` directory and writes `pipeline/.cache/raw_YYYYMMDD.json`.

If a specific date is needed: `python scripts/parse_raw_sources.py --date YYYY-MM-DD`

### 2. Run triage (classify + novelty + confidence)

```bash
cd /Users/tomrooney/src/intel-brief && python -c "
import json, sys, logging
from pathlib import Path
sys.path.insert(0, 'pipeline')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
from pipeline.main import stage_triage, CACHE_DIR, load_config
from datetime import datetime, timezone

target = datetime.now(timezone.utc)
date_str = target.strftime('%Y%m%d')
raw_cache = CACHE_DIR / f'raw_{date_str}.json'
if not raw_cache.exists():
    print(f'ERROR: No raw cache at {raw_cache}. Run parse_raw_sources.py first.')
    sys.exit(1)

config = load_config()
tagged = stage_triage(raw_cache, config)
print(f'Triage complete: {tagged}')
"
```

### 3. Review output

After triage completes, check `pipeline/.cache/tagged_YYYYMMDD.json`:

- **Domain distribution**: every domain (d1-d6) should have 3+ items. Warn if any domain is thin.
- **Tier 1 coverage**: at least 5 Tier 1 items should survive filtering.
- **Novelty**: report how many items were filtered as repetitions of the previous cycle.

Report these counts to the user before proceeding to `/intel-draft`.

## Output Contract

- **Input:** `scratch/raw/<timestamp>/` (from `/intel-ingest`)
- **Intermediate:** `pipeline/.cache/raw_YYYYMMDD.json` (parsed items)
- **Output:** `pipeline/.cache/tagged_YYYYMMDD.json` (triaged items with `tagged_domains`, `novelty_score`, `confidence_tier`, `verification_status`)

## Error Handling

- If parse produces < 10 items: warn that source coverage is thin, but proceed.
- If any domain has 0 items after triage: flag as a **Collection Gap** for `/intel-draft`.
- If all Tier 1 items are filtered: halt and alert — the brief has no factual backbone.
