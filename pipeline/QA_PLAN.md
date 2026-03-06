# CSE Intel Brief — Pipeline QA Master Plan
# 100-Step Source Health & Code Quality Programme

Generated: 2026-03-06
Branch: claude/automate-research-reports-ZmU4R
Scope: All pipeline code + sources.yaml + front-end schema alignment

---

## PART A — BUG AUDIT (Steps 1–28)

### A1 — Schema & Validation Bugs

**ISSUE 1 — CRITICAL: `serializer.py` VALID_DOMAIN_IDS missing d6**
- File: `pipeline/output/serializer.py:31`
- Bug: `VALID_DOMAIN_IDS = {'d1','d2','d3','d4','d5'}` — d6 absent
- Effect: Every cycle containing a d6 domain section fails `validate()` and
  raises ValueError, aborting the output stage. D6 domain is completely
  unwriteable to disk regardless of content quality.
- [ ] Step 1: Add `'d6'` to VALID_DOMAIN_IDS in serializer.py
- [ ] Step 2: Run serializer unit test with d6 section — expect no validation errors
- [ ] Step 3: Run demo pipeline end-to-end; confirm cycle writes to disk

**ISSUE 2 — CRITICAL: `novelty.py` glob pattern never matches cycle files**
- File: `pipeline/triage/novelty.py:75`
- Bug: `cycles_dir.glob('cycle_*.json')` — underscore after "cycle"
  but serializer writes `cycle001_20260305.json` (no underscore)
- Effect: Novelty filter always finds zero previous cycles, treating every
  item as novel. No deduplication occurs between cycles.
- [ ] Step 4: Fix glob to `cycle*.json` (no underscore) in novelty.py
- [ ] Step 5: Create two dummy cycle files and verify novelty detection fires
- [ ] Step 6: Confirm Tier 1 items always pass, Tier 2 repeats are filtered

**ISSUE 3 — HIGH: `rss_ingest.py` ignores `enabled: false` sources**
- File: `pipeline/ingest/rss_ingest.py:35`
- Bug: `load_rss_sources()` filters only by `method == 'rss'`; no `enabled` check
- Effect: CNN (`enabled: false`), and any future disabled RSS sources, are
  fetched on every cycle. CNN RSS is dead (503), producing error log noise
  and wasting request budget.
- [ ] Step 7: Add `and s.get('enabled', True)` to `load_rss_sources()`
- [ ] Step 8: Verify CNN does not appear in RSS fetch log on demo run

**ISSUE 4 — HIGH: `scraper.py` EXTRACTORS missing all 15 new Reuters IDs**
- File: `pipeline/ingest/scraper.py:438-451`
- Bug: EXTRACTORS dict only registers `reuters_mideast`. All 15 new source
  IDs (reuters_iran, reuters_israel, reuters_yemen, reuters_iraq,
  reuters_lebanon, reuters_saudi, reuters_energy, reuters_commodities,
  reuters_aerospace_defense, reuters_cybersecurity, reuters_us,
  reuters_europe, reuters_china, reuters_russia, reuters_markets,
  reuters_legal) fall through to `_extract_generic`.
- Effect: Generic extractor collects paragraph soup from Reuters topic pages
  rather than structured article cards with titles and links.
- [ ] Step 9: Register all reuters_* IDs → _extract_reuters in EXTRACTORS
- [ ] Step 10: Verify reuters_iran uses URL https://www.reuters.com/world/middle-east/iran/
- [ ] Step 11: Test _extract_reuters with mock HTML fixture

**ISSUE 5 — HIGH: `demo_seed.py` has zero D6 domain items**
- File: `pipeline/ingest/demo_seed.py`
- Bug: `get_seed_items()` returns 15 items covering d1–d5 only. D6 missing.
- Effect: Demo pipeline produces warning "Domain d6: only 0 items" and the
  d6 brief section is empty/placeholder. D6 code paths cannot be tested
  without live internet or API key.
- [ ] Step 12: Add ≥3 D6 seed items (Tier 1: JWC/Lloyd's bulletin;
               Tier 2: reinsurance market commentary; Tier 3: vessel diversion)
- [ ] Step 13: Run demo pipeline; confirm d6 section appears in output

**ISSUE 6 — HIGH: `relevance.py` filters D6 Tier 2/3 RSS content**
- File: `pipeline/ingest/relevance.py` + `rss_ingest.py:146`
- Bug: D6 Tier 2 RSS sources (reinsurance_news, insurance_journal,
  marine_link, splash247, hellenicshipping, safety4sea, maritime_executive,
  bunkerspot) are ingested by `ingest_rss()`, which calls `filter_relevant()`.
  Marine insurance content about JWC listed areas / P&I circulars that
  doesn't mention "Iran" or "Hormuz" is silently dropped.
- Effect: Only D6 items that happen to mention Iran/Gulf keywords survive;
  purely insurance-market items (e.g. "Lloyd's syndicates raise marine war
  risk capacity") are discarded.
- [ ] Step 14: Add D6 insurance keywords to RELEVANCE_KEYWORDS in relevance.py
- [ ] Step 15: Test that "Lloyd's war risk capacity" item passes filter
- [ ] Step 16: Test that "FTSE 100 quarterly earnings" item still fails filter

**ISSUE 7 — MEDIUM: `cmd_check_sources()` uses HEAD; many servers return 405**
- File: `pipeline/main.py:523`
- Bug: `requests.head()` — RSS servers, especially feedparser-served ones,
  return 405 Method Not Allowed or redirect 3xx chains that distort results.
- Effect: Live RSS feeds like CNBC, France24 may show as WARN/FAIL when GET
  would succeed. Creates false alarms in source health monitoring.
- [ ] Step 17: Change to GET with `stream=True` and read 512 bytes only
- [ ] Step 18: Add 405→retry-with-GET fallback
- [ ] Step 19: Re-run check-sources; confirm CNBC shows OK

**ISSUE 8 — MEDIUM: `serializer.py` validation rejects d6 domain keyJudgment**
- File: `pipeline/output/serializer.py:79-84`
- Bug: `VALID_DOMAIN_IDS` missing d6 (same root as Issue 1) also causes
  the keyJudgment/bodyParagraphs checks on line 81-84 to never run for d6,
  so a structurally incomplete d6 domain would silently pass.
  Fixed by Step 1 — documented here for completeness.
- [ ] Step 20: After Step 1 fix, verify d6 without keyJudgment fails validation

**ISSUE 9 — MEDIUM: `bbc_persian` dead scrape extractor**
- File: `pipeline/ingest/scraper.py`
- Bug: EXTRACTORS has `bbc_persian` → `_extract_bbc_persian` but
  sources.yaml now has bbc_persian as `method: rss`. The extractor is
  dead code and will never be called (load_scrape_sources filters by method).
- Effect: Harmless but misleading. Remove from EXTRACTORS or add comment.
- [ ] Step 21: Remove or annotate dead `bbc_persian` EXTRACTORS entry

**ISSUE 10 — LOW: `war_risk_ingest.py` `reinsurance_finance` category
             includes `iras_war_risk` (Cloudflare 403)**
- File: `pipeline/ingest/war_risk_ingest.py:80`
- Bug: IRAS returns 403 in all automated contexts. CIP subagent wastes
  max_turns budget attempting a blocked URL.
- Effect: Minor token waste; subagent falls back to WebSearch which is fine.
- [ ] Step 22: Add inline note in war_risk_ingest.py noting IRAS requires
              Playwright; subagent uses WebSearch fallback

**ISSUE 11 — LOW: `_extract_opec()` in scraper.py references opec.org
             but source points to EIA**
- File: `pipeline/ingest/scraper.py:393`
- Bug: `_extract_opec()` hardcodes `'https://www.opec.org'` for link
  resolution, but `opec_statements` source points to eia.gov. Any relative
  links from EIA would get prefixed with the wrong domain.
- [ ] Step 23: Update `_extract_opec()` to use `source['url']` base domain
              for link resolution

**ISSUE 12 — LOW: `serializer.py:96` checks `'status'` but warningIndicator
             schema uses `'level'`**
- File: `pipeline/output/serializer.py:96`
- Bug: `if 'indicator' not in wi or 'status' not in wi` — but the cycle JSON
  schema uses `level` (e.g. "RED"/"AMBER"/"GREEN"), not `status`. The
  field name is mismatched.
- [ ] Step 24: Fix validation to check for `level` not `status`

---

## PART B — SOURCES.YAML HEALTH CHECKS (Steps 25–60)

### B1 — Status classification audit

- [ ] Step 25: List all sources with status: `likely` and method: `rss` —
              verify each URL is real and known to serve RSS
- [ ] Step 26: List all sources with status: `likely` and method: `scrape` —
              verify each URL exists and serves HTML
- [ ] Step 27: Confirm all `enabled: false` sources have documented reason
              in notes field
- [ ] Step 28: Confirm all `removed` sources are in the REMOVED block

### B2 — Reuters multi-source coverage

- [ ] Step 29: Verify all 16 Reuters source entries have correct tier: 1
- [ ] Step 30: Verify all 16 Reuters source entries have method: scrape
- [ ] Step 31: Confirm reuters_russia URL is /world/europe/russia/ not
              /world/russia/ (Reuters hierarchy)
- [ ] Step 32: Add missing Reuters regional entry: reuters_gulf_states
              covering /world/middle-east/ (UAE, Kuwait, Bahrain — not
              covered by existing country pages)
- [ ] Step 33: Confirm domains tags correctly reflect each Reuters section

### B3 — D6 Tier 1 source coverage

- [ ] Step 34: Verify lloyds_mkt_bulletins URL resolves
- [ ] Step 35: Verify jwc_listed_areas URL resolves (LMA/Lloyds)
- [ ] Step 36: Verify imo_circular URL resolves
- [ ] Step 37: Verify ig_pic_circulars URL resolves
- [ ] Step 38: Verify bimco_news RSS URL resolves
- [ ] Step 39: Verify nato_shipping_centre URL resolves
- [ ] Step 40: Verify usmto URL resolves

### B4 — D6 Tier 2 source audit

- [ ] Step 41: Confirm lloyds_list and tradewinds_insurance disabled, notes say paywall
- [ ] Step 42: Confirm insurance_insider disabled, notes say paywall
- [ ] Step 43: Verify reinsurance_news RSS feed returns valid XML
- [ ] Step 44: Verify insurance_journal RSS feed returns valid XML
- [ ] Step 45: Verify marine_link RSS feed returns valid XML
- [ ] Step 46: Verify splash247 RSS feed returns valid XML
- [ ] Step 47: Verify hellenicshipping RSS feed returns valid XML
- [ ] Step 48: Confirm bunkerspot URL forwards to ship.energy correctly
- [ ] Step 49: Confirm dnv_maritime URL is HTML listing, not RSS
- [ ] Step 50: Confirm safety4sea RSS feeds valid XML

### B5 — D6 Tier 3 source audit

- [ ] Step 51: Verify signal_ocean URL (thesignalgroup.com/newsroom) loads
- [ ] Step 52: Verify munichre_marine new URL loads (confirmed working)
- [ ] Step 53: Verify credit_agricole_shipping new URL loads (confirmed working)
- [ ] Step 54: Verify unctad_maritime new URL loads (confirmed working)
- [ ] Step 55: Note swissre_sigma status (403 on research subtree; /institute/ loads)
- [ ] Step 56: Note moodys_shipping status (JS-rendered; requires Playwright)
- [ ] Step 57: Note iras_war_risk status (403; requires Playwright/cookie)

### B6 — Non-D6 Tier 3 source audit

- [ ] Step 58: Verify recorded_future RSS (therecord.media/feed/) working
- [ ] Step 59: Verify cisa_advisories RSS working
- [ ] Step 60: Verify mandiant_blog RSS working

---

## PART C — SCRAPER EXTRACTOR COMPLETENESS (Steps 61–72)

- [ ] Step 61: Register all reuters_* source IDs in EXTRACTORS → _extract_reuters
              (reuters_iran, reuters_israel, reuters_yemen, reuters_iraq,
               reuters_lebanon, reuters_saudi, reuters_energy, reuters_commodities,
               reuters_aerospace_defense, reuters_cybersecurity, reuters_us,
               reuters_europe, reuters_china, reuters_russia, reuters_markets,
               reuters_legal)
- [ ] Step 62: Write _extract_d6_marine() generic extractor for D6 scrape sources
              that prioritises headline + lede extraction from industry trade press
- [ ] Step 63: Register D6 scrape sources in EXTRACTORS using _extract_d6_marine:
              lloyds_mkt_bulletins, jwc_listed_areas, imo_circular,
              ig_pic_circulars, nato_shipping_centre, usmto, dryad_global,
              ambrey_analytics, eos_risk, icc_imb, iumi_news,
              marsh_marine, willis_marine, aon_marine, gallagher_marine,
              dnv_maritime, clarksons_research, intercargo_news, intertanko_news,
              netblocks, eia_weekly, swissre_sigma, munichre_marine,
              credit_agricole_shipping, unctad_maritime, iras_war_risk,
              moodys_shipping, signal_ocean
- [ ] Step 64: Remove dead bbc_persian entry from EXTRACTORS
- [ ] Step 65: Fix _extract_opec() to resolve relative links against eia.gov base
- [ ] Step 66: Test _extract_ctpiw() against known criticalthreats.org HTML
- [ ] Step 67: Test _extract_ukmto() against known ukmto.org HTML structure
- [ ] Step 68: Test _extract_reuters() against a Reuters topic page HTML sample
- [ ] Step 69: Test _extract_d6_marine() against a Lloyd's Market Bulletins page
- [ ] Step 70: Verify _extract_generic() is never the primary for any Tier 1 source
- [ ] Step 71: Add extractor coverage report to check-sources output
- [ ] Step 72: Run ingest_scrape() with demo=False; log per-source item counts

---

## PART D — TEST RUNS (Steps 73–100)

### D1 — Test Run 1: Demo pipeline (no internet/API)

- [ ] Step 73: Run `python pipeline/main.py run --demo --auto-approve`
- [ ] Step 74: Confirm ingest stage produces ≥18 items (15 existing + 3 D6)
- [ ] Step 75: Confirm triage stage classifies all 6 domains with ≥2 items each
- [ ] Step 76: Confirm d6 domain count ≥ 3 in triage log
- [ ] Step 77: Confirm novelty filter runs in "no prior cycles" mode on first run
- [ ] Step 78: Draft stage: confirm placeholder draft builds without API key
- [ ] Step 79: Output stage: confirm cycle writes to disk (no validation errors)
- [ ] Step 80: Confirm d6 domain in written cycle JSON (fixed by Step 1)
- [ ] Step 81: Run `python pipeline/main.py show` and verify d6 section displayed
- [ ] Step 82: Run `python pipeline/main.py list` and confirm cycle appears

### D2 — Test Run 2: Novelty detection round-trip

- [ ] Step 83: Run demo pipeline a second time on same date (--force)
- [ ] Step 84: Confirm novelty filter now finds previous cycle (fixed glob pattern)
- [ ] Step 85: Confirm Tier 2 repeated items are filtered; Tier 1 items pass
- [ ] Step 86: Confirm novel_count in log is < total item count

### D3 — Test Run 3: Source health check

- [ ] Step 87: Run `python pipeline/main.py check-sources` (GET-based)
- [ ] Step 88: Verify CNN does not appear in results (disabled, skipped)
- [ ] Step 89: Verify email sources show "configure IMAP" message
- [ ] Step 90: Verify disabled paywall sources (lloyds_list, haaretz, etc.) skipped
- [ ] Step 91: Note HTTP status codes for all enabled RSS sources
- [ ] Step 92: Note HTTP status codes for all enabled scrape sources
- [ ] Step 93: Document any new 404s for further investigation

### D4 — Test Run 4: From-file ingest

- [ ] Step 94: Create minimal test research JSON with 1 d6 item, 1 d1 item, 1 d2 item
- [ ] Step 95: Run `python pipeline/main.py run --from-file test_research.json --auto-approve`
- [ ] Step 96: Confirm all 3 items appear in tagged cache
- [ ] Step 97: Confirm d6 item gets tagged_domains including d6
- [ ] Step 98: Confirm draft placeholder builds from from-file items

### D5 — Regression sweep

- [ ] Step 99: Run `python pipeline/main.py run --demo --auto-approve --date 2026-03-04`
              (backfill date) — confirm no crashes
- [ ] Step 100: Confirm `python pipeline/main.py list` shows both cycles,
               newest last

### D6 — Schema alignment

- [ ] Step 101: Confirm src/types/brief.ts includes 'd6' in DomainId type
- [ ] Step 102: Confirm front-end can render a cycle with d6 domain
- [ ] Step 103: Run `npm run build` — confirm no TypeScript errors

---

## PART E — COMMIT CHECKPOINTS

After each group of fixes, commit with descriptive message:
- After Steps 1–6 (schema/novelty/rss fixes): "fix: critical bugs — d6 validation, novelty glob, RSS enabled filter"
- After Steps 7–11 (check-sources, opec, serializer): "fix: check-sources GET method, opec link prefix, warningIndicator status→level"
- After Steps 12–16 (demo D6, relevance keywords): "feat: add D6 demo seed items + D6 relevance keywords"
- After Steps 61–72 (extractor completeness): "feat: register all Reuters+D6 extractors, _extract_d6_marine()"
- After all test runs pass: "test: all 103 QA steps green — pipeline verified"
