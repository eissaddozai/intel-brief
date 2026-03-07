---
name: workflow
description: "Intelligence Brief Workflow"
---

# Intelligence Brief Workflow

**Invocation:** `/workflow`

Generate a complete CSE Intelligence Brief by chaining four pipeline skills.

## Commands

| Command | Description |
|---------|-------------|
| `/workflow` | Generate a new intelligence brief for today |
| `/workflow YYYY-MM-DD` | Generate a brief for a specific date |

## Pipeline

```
/intel-ingest  -->  /intel-triage  -->  /intel-draft  -->  /intel-publish
   fetch 70+        parse + classify      draft all         sync + build
   sources          + novelty + conf      sections          npm run dev
```

Execute each phase in order. Do not skip phases. If a phase fails, stop and report the error.

---

## Phase 1: Source Collection (`/intel-ingest`)

Run the parallel fetch script:

```bash
bash .claude/skills/intel-ingest/scripts/fetch_all_sources.sh
```

**Gate check before proceeding:**
- Read `scratch/raw/<latest>/_manifest.json`
- Verify `successful >= 60` (out of ~73 sources)
- Check `tier1_fail` — if any Tier 1 sources failed, attempt manual retry with alternate User-Agent
- Report: "Fetched X/Y sources (Z Tier 1 OK, N Tier 1 failed)"

If Tier 1 failures > 3, warn the user but continue (the brief will note collection gaps).

---

## Phase 2: Triage (`/intel-triage`)

### 2a. Parse raw sources

```bash
python scripts/parse_raw_sources.py
```

**Gate check:** Verify `pipeline/.cache/raw_YYYYMMDD.json` exists and has > 10 items.

### 2b. Classify + novelty + confidence

```bash
cd /Users/tomrooney/src/intel-brief && python -c "
import json, sys, logging
from pathlib import Path
sys.path.insert(0, 'pipeline')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
from main import stage_triage, CACHE_DIR, load_config
from datetime import datetime, timezone

target = datetime.now(timezone.utc)
raw_cache = CACHE_DIR / f'raw_{target.strftime(\"%Y%m%d\")}.json'
config = load_config()
tagged = stage_triage(raw_cache, config)
print(f'Triage complete: {tagged}')
"
```

**Gate check:**
- Read `pipeline/.cache/tagged_YYYYMMDD.json`
- Count items per domain (d1-d6). Each should have >= 3 items.
- Flag any domain with 0 items as a **Collection Gap**.
- Report domain distribution to user.

---

## Phase 3: Drafting (`/intel-draft`)

Read `pipeline/.cache/tagged_YYYYMMDD.json` and draft the complete brief.

Follow all instructions in the `/intel-draft` skill. Key points:
1. Group items by `tagged_domains`
2. Read previous brief from `briefs/` for delta context only
3. Read `pipeline/draft/prompts/*.md` for voice/structure guidance
4. Draft each domain section, then executive, strategic header, warning indicators, caveats
5. Every fact must trace to a triaged item. No fabrication.
6. Save to `briefs/CSE_Intel_Brief_YYYYMMDD_HHMMSS.json`

**Gate check:** Validate the output JSON has all required top-level keys: `meta`, `strategicHeader`, `flashPoints`, `executive`, `domains` (6), `warningIndicators`, `collectionGaps`, `caveats`, `footer`.

---

## Phase 4: Publish (`/intel-publish`)

```bash
python scripts/sync_briefs.py && npm run build
```

Then start the dev server:

```bash
npm run dev
```

Report the brief filename and URL (http://localhost:5173) to the user.

---

## Output

**Always create a NEW brief file -- never overwrite an existing one.**

Briefs are saved to: `briefs/CSE_Intel_Brief_YYYYMMDD_HHMMSS.json`

The `cycleId` in the JSON meta block must match the filename stem.

---

## Error Recovery

| Error | Action |
|-------|--------|
| Tier 1 fetch failures > 3 | Warn user, continue with collection gaps noted |
| Parse produces < 10 items | Warn user, check raw content quality |
| Domain has 0 triaged items | Note as collection gap in brief, use thin-data template |
| Build fails | Check TypeScript errors, validate JSON schema |

---

## ABSOLUTE RULES (from CLAUDE.md)

- **Every fact must come from a live-fetched source.** No fabrication. No hallucination.
- **Lead sentences are assessments.** "We assess..." not "Three BTGs were observed..."
- **Confidence language from the ladder only.** No ad-hoc hedging.
- **Iranian state media** = "Iranian government asserts" — never confirmed.
- **Forbidden phrases:** "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb)
- **All colours from CSS tokens.** Never hardcode hex values.
- **All font sizes from CSS tokens.** Never hardcode px values.
