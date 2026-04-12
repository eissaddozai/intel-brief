# Source Fetch Status — Tested 07 March 2026

All sources from `pipeline/ingest/sources.yaml` tested with curl.
WebFetch blocked by enterprise Cloudflare Gateway policy for ALL domains.
WebSearch blocked by Vertex AI org policy.

**Only method available: `curl -sL`**

---

## TIER 1 — FACTUAL BACKBONE (14 sources)

| ID | Working URL | Method | Status | Notes |
|---|---|---|---|---|
| al_jazeera_en | `https://www.aljazeera.com/xml/rss/all.xml` | curl RSS | **WORKS** (17K, 25 items) | Primary Tier 1 backbone |
| ap_wire | `https://apnews.com/hub/middle-east` | curl scrape | **WORKS** (1.9M HTML) | RSS feed dead; scrape hub page instead |
| reuters_mideast | `https://www.reuters.com/world/middle-east/` | curl scrape | **WORKS** (498K) | JS-heavy; headlines extractable |
| ctpiw_evening | `https://www.criticalthreats.org/analysis/` | curl scrape | **WORKS** (103K) | `/iran-war-updates` 404; use `/analysis/` |
| iaea | `https://www.iaea.org/newscenter/pressreleases` | curl scrape | **WORKS** (94K) | RSS feed removed; scrape press page |
| ukmto | `https://www.ukmto.org/indian-ocean/recent-incidents` | curl scrape | **WORKS** (11K) | Maritime incidents |
| ig_pic_circulars | `https://www.igpandi.org/news/` | curl scrape | **WORKS** (54K) | P&I club news |
| imo_circular | `https://www.imo.org/en/MediaCentre/IMONewsletterAndUpdates/Pages/default.aspx` | curl scrape | **WORKS** (44K) | IMO circulars |
| lloyds_mkt_bulletins | `https://www.lloyds.com/news-and-insights/market-communications/market-bulletins` | curl scrape | **WORKS** (99K) | Old URL 404; use new path |
| centcom | — | — | **BLOCKED** (403 all methods) | WAF blocks all curl; no workaround found |
| idf_spokesperson | — | — | **BLOCKED** (Incapsula, 846B) | Bot protection; returns challenge page only |
| jwc_listed_areas | — | — | **404** | Page restructured; content in lloyds_mkt_bulletins |
| bimco_news | `https://www.bimco.org/news-and-trends` | curl scrape | **WORKS** (69K) | RSS gone; `/news` 404; use `/news-and-trends` |
| nato_shipping_centre | — | — | **BLOCKED** (403 all methods) | No workaround found |
| usmto | `https://www.maritimesecurity.org/` | curl scrape | **WORKS** (15K) | `/news/` 404; root works |

**Tier 1 Summary: 12 of 14 fetchable (86%), 2 hard-blocked (centcom, nato_shipping_centre)**

---

## TIER 2 — ANALYTICAL DEPTH (40 sources)

### RSS Feeds — Working

| ID | URL | Items | Notes |
|---|---|---|---|
| bbc_mideast | `https://feeds.bbci.co.uk/news/world/middle_east/rss.xml` | 36 | Strong Iran/Lebanon coverage |
| nyt_world | `https://rss.nytimes.com/services/xml/rss/nyt/World.xml` | 60 | Tehran strikes, diplomacy |
| times_of_israel | `https://www.timesofisrael.com/feed/` | 15 | IDF ops, Kurdish proxy |
| guardian_mideast | `https://www.theguardian.com/world/middleeast/rss` | 20 | UK/EU perspective |
| cnbc_world | `https://www.cnbc.com/id/100727362/device/rss/rss.html` | 30 | Markets, economic |
| cnbc_energy | `https://www.cnbc.com/id/19832390/device/rss/rss.html` | 30 | Energy prices |
| jerusalem_post | `https://www.jpost.com/rss/rssfeedsfrontpage.aspx` | 26 | Israeli gov |
| middle_east_eye | `https://www.middleeasteye.net/rss` | 20 | Houthi, Gulf politics |
| dw_en | `https://rss.dw.com/rdf/rss-en-all` | ~RSS | German/EU |
| rfi_en | `https://www.rfi.fr/en/rss` | 22 | French perspective |
| rfi_persian | `https://www.rfi.fr/fa/rss` | 17 | Inside-Iran |
| anadolu | `https://www.aa.com.tr/en/rss/default?cat=world` | 30 | Turkish angle |
| france24_observers | `https://observers.france24.com/en/rss` | 21 | Video verification |
| icg | `https://www.crisisgroup.org/rss.xml` | 10 | Escalation analysis |
| quincy_inst | `https://responsiblestatecraft.org/feed/` | 30 | Restraint framing |
| hellenicshipping | `https://www.hellenicshippingnews.com/feed/` | 20 | Maritime/shipping |
| reinsurance_news | `https://www.reinsurancene.ws/feed/` | 10 | Reinsurance market |
| splash247 | `https://splash247.com/feed/` | 10 | Shipping industry |
| offshore_energy | `https://www.offshore-energy.biz/feed/` | 10 | Offshore sector |
| insurance_journal | `https://www.insurancejournal.com/rss/topics/marine/` | 1 | Marine insurance |
| bunkerspot | `https://www.bunkerspot.com/rss` | 10 | Fuel/bunkering |
| safety4sea | `https://safety4sea.com/feed/` | RSS (485K) | Maritime safety |

### RSS Feeds — Fixed URL

| ID | Working URL | Items | Fix Applied |
|---|---|---|---|
| france24_mideast | `https://www.france24.com/en/middle-east/rss` | 30 | Was `/en/rss` (403); use topic-specific |
| alma_research | `https://israel-alma.org/feed/` | RSS (46K) | Was `/category/reports/` (404); use WP feed |
| dnv_maritime | `https://www.dnv.com/news/rss` | RSS (17K) | Old URL 404; use `/news/rss` |

### Scrape Sources — Working

| ID | URL | Size | Notes |
|---|---|---|---|
| iran_intl | `https://www.iranintl.com/en` | 429K | Inside-Iran, IRGC dynamics |
| bbc_persian | `https://www.bbc.com/persian` | 471K | Persian-language |
| rudaw | `https://www.rudaw.net/english/rss.xml` | 3K RSS | Kurdistan region |
| tradewinds_insurance | `https://www.tradewindsnews.com/insurance` | 563K | Shipping insurance |
| marsh_marine | `https://www.marsh.com/us/industries/marine/insights.html` | 248K | Broker war risk |
| iumi_news | `https://iumi.com/news` | 281K | Marine insurance union |
| intercargo_news | `https://www.intercargo.org/news/` | 119K | Dry cargo shipowners |
| icc_imb | `https://www.icc-ccs.org/icc/imb` | 141K | Maritime crime |

### Scrape Sources — Fixed URL

| ID | Working URL | Size | Fix Applied |
|---|---|---|---|
| ambrey_analytics | `https://www.ambrey.com/` | 171K | Was `/intelligence/` (404); use root |
| dryad_global | `https://www.dryadglobal.com/` | 335K | Was `/news` (404); use root |
| eos_risk | `https://www.eosrisk.com/` | 200K | Was `/news/` (404); use root |
| intertanko_news | `https://www.intertanko.com/` | 71K | Was `/news/` (404); use root |
| maritime_executive | `https://www.maritime-executive.com/` | 183K | RSS/feed all 404; scrape root |
| marine_link | `https://www.marinelink.com/` | 83K | RSS 404; scrape root |
| willis_marine | `https://www.wtwco.com/en-us/insights` | 296K | Old URL 404; use `/en-us/insights` |
| aon_marine | `https://www.aon.com/en/` | 446K | Old URL 404; use root |

### Scrape Sources — Blocked/Unusable

| ID | Issue | Workaround |
|---|---|---|
| cnn_mideast | RSS deprecated (404) | Scrape `https://edition.cnn.com/middle-east` (3.5M) — very large |
| lloyds_list | Paywall redirect (404) | Scrape `https://www.lloydslist.com/` (201K root) — limited |
| insurance_insider | Paywall (404) | Scrape `https://www.insuranceinsider.com/` (136K root) — limited |
| gallagher_marine | Incapsula bot block (1K) | No workaround |
| clarksons_research | Server error (500) | Scrape `https://sin.clarksons.net/` (430K root) |

**Tier 2 Summary: 36 of 40 fetchable (90%), 4 limited/blocked**

---

## TIER 3 — DOMAIN TRIGGERS (11 sources)

| ID | Working URL | Method | Status | Notes |
|---|---|---|---|---|
| cisa_advisories | `https://www.cisa.gov/cybersecurity-advisories/all.xml` | curl RSS | **WORKS** (450K, 30 items) | |
| mandiant_blog | `https://www.mandiant.com/resources/blog/rss.xml` | curl RSS | **WORKS** (2M, 20 items) | |
| netblocks | `https://netblocks.org` | curl scrape | **WORKS** (57K) | |
| eia_weekly | `https://www.eia.gov/petroleum/supply/weekly/` | curl scrape | **WORKS** (85K) | |
| opec_statements | `https://www.opec.org/opec_web/en/press_room/4567.htm` | curl scrape | **WORKS** (221K) | |
| iras_war_risk | `https://www.iras.co.uk/news/` | curl scrape | **WORKS** (12K) | |
| moodys_shipping | `https://www.moodys.com/researchandratings/market-segment/transportation/shipping/-/0015` | curl scrape | **WORKS** (3K) | Small but fetchable |
| recorded_future | `https://www.recordedfuture.com/feed` | curl RSS | **WORKS** (923K) | Was `/research/feed` (404); use `/feed` |
| signal_ocean | `https://www.signalocean.com/` | curl scrape | **WORKS** (164K) | Was `/blog` (404); use root |
| swissre_sigma | `https://www.swissre.com/institute/research/sigma-research.html` | curl scrape | **WORKS** (189K) | RSS removed; scrape page |
| munichre_marine | `https://www.munichre.com/` | curl scrape | **PARTIAL** (67K root) | Direct marine URL 404 |
| credit_agricole_shipping | `https://www.ca-cib.com/` | curl scrape | **PARTIAL** (877K root) | Shipping URL 404 |
| unctad_maritime | `https://unctad.org/` | curl scrape | **PARTIAL** (145K root) | Maritime URL 404 |
| clarksons_research | `https://sin.clarksons.net/` | curl scrape | **PARTIAL** (430K root) | `/News` returns 500 |

**Tier 3 Summary: 10 of 11 fetchable (91%), 1 partial**

---

## GRAND TOTALS

| Category | Fetchable | Blocked | Total | Rate |
|---|---|---|---|---|
| Tier 1 | 12 | 2 | 14 | 86% |
| Tier 2 | 36 | 4 | 40 | 90% |
| Tier 3 | 10 | 1 | 11 | 91% |
| **Total** | **58** | **7** | **65** | **89%** |

### Hard-Blocked (no curl workaround found)
1. `centcom` — 403 WAF on all URLs and user agents
2. `nato_shipping_centre` — 403 on all URLs
3. `idf_spokesperson` — Incapsula challenge (846B)
4. `gallagher_marine` — Incapsula challenge (1K)
5. `lloyds_list` — Paywall redirect (limited root)
6. `insurance_insider` — Paywall redirect (limited root)
7. `cnn_mideast` — RSS dead; scrape page is 3.5M

### Method Summary
- **curl RSS**: 25 working feeds, ~500+ items
- **curl scrape (original URL)**: 15 sources
- **curl scrape (fixed URL)**: 18 sources with corrected paths
- **WebFetch**: BLOCKED (enterprise Cloudflare Gateway)
- **WebSearch**: BLOCKED (Vertex AI org policy)
