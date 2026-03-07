#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# CSE INTEL BRIEF — PARALLEL SOURCE FETCHER
# Fetches ALL enabled sources from sources.yaml in parallel using curl.
# Output: one file per source in $OUTPUT_DIR (default: scratch/raw/)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
OUTPUT_DIR="${1:-$REPO_ROOT/scratch/raw}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
OUTPUT_DIR="$OUTPUT_DIR/$TIMESTAMP"

mkdir -p "$OUTPUT_DIR"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT=25
MAX_PARALLEL=12

echo "═══ CSE Source Fetcher ═══"
echo "Output: $OUTPUT_DIR"
echo "Parallel: $MAX_PARALLEL"
echo ""

# ─── Source list: id|tier|method|url ──────────────────────────────────────────
# All URLs verified by curl testing 07 Mar 2026.
# Legend: [V]=verified working  [F]=fixed URL  [B]=blocked (included anyway)
# ═══════════════════════════════════════════════════════════════════════════════

SOURCES=(
  # ── TIER 1 — FACTUAL BACKBONE ──────────────────────────────────────────────
  "al_jazeera_en|1|rss|https://www.aljazeera.com/xml/rss/all.xml"                                                  # [V] 25 items
  "ap_wire|1|scrape|https://apnews.com/hub/middle-east"                                                             # [F] RSS dead; scrape hub (1.9M)
  "reuters_mideast|1|scrape|https://www.reuters.com/world/middle-east/"                                             # [V] JS-heavy HTML (498K)
  "ctpiw_evening|1|scrape|https://www.criticalthreats.org/analysis/"                                                # [F] /iran-war-updates 404; /analysis/ works (103K)
  "iaea|1|scrape|https://www.iaea.org/newscenter/pressreleases"                                                     # [F] RSS removed; scrape press page (94K)
  "ukmto|1|scrape|https://www.ukmto.org/indian-ocean/recent-incidents"                                             # [V] maritime incidents (11K)
  "ig_pic_circulars|1|scrape|https://www.igpandi.org/news/"                                                         # [V] P&I club news (54K)
  "imo_circular|1|scrape|https://www.imo.org/en/MediaCentre/IMONewsletterAndUpdates/Pages/default.aspx"             # [V] IMO circulars (44K)
  "lloyds_mkt_bulletins|1|scrape|https://www.lloyds.com/news-and-insights/market-communications/market-bulletins"   # [F] old path 404; new path works (99K)
  "bimco_news|1|scrape|https://www.bimco.org/news-and-trends"                                                       # [F] RSS gone; /news 404; /news-and-trends works (69K)
  "usmto|1|scrape|https://www.maritimesecurity.org/"                                                                 # [F] /news/ 404; root works (15K)
  "centcom|1|scrape|https://www.centcom.mil/MEDIA/NEWS-ARTICLES/"                                                   # [B] 403 WAF all methods
  "idf_spokesperson|1|scrape|https://www.idf.il/en/mini-sites/idf-website/press-releases/"                         # [B] Incapsula bot block (846B)
  "nato_shipping_centre|1|scrape|https://shipping.nato.int/nsc/operations/news"                                     # [B] 403 all methods

  # ── TIER 2 — RSS FEEDS (verified working) ─────────────────────────────────
  "bbc_mideast|2|rss|https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"                                       # [V] 36 items
  "nyt_world|2|rss|https://rss.nytimes.com/services/xml/rss/nyt/World.xml"                                          # [V] 60 items
  "times_of_israel|2|rss|https://www.timesofisrael.com/feed/"                                                        # [V] 15 items
  "guardian_mideast|2|rss|https://www.theguardian.com/world/middleeast/rss"                                          # [V] 20 items
  "cnbc_world|2|rss|https://www.cnbc.com/id/100727362/device/rss/rss.html"                                           # [V] 30 items
  "cnbc_energy|2|rss|https://www.cnbc.com/id/19832390/device/rss/rss.html"                                           # [V] 30 items
  "jerusalem_post|2|rss|https://www.jpost.com/rss/rssfeedsfrontpage.aspx"                                            # [V] 26 items
  "middle_east_eye|2|rss|https://www.middleeasteye.net/rss"                                                          # [V] 20 items
  "dw_en|2|rss|https://rss.dw.com/rdf/rss-en-all"                                                                   # [V] RSS OK (125K)
  "rfi_en|2|rss|https://www.rfi.fr/en/rss"                                                                          # [V] 22 items
  "rfi_persian|2|rss|https://www.rfi.fr/fa/rss"                                                                      # [V] 17 items
  "anadolu|2|rss|https://www.aa.com.tr/en/rss/default?cat=world"                                                    # [V] 30 items
  "france24_observers|2|rss|https://observers.france24.com/en/rss"                                                   # [V] 21 items
  "france24_mideast|2|rss|https://www.france24.com/en/middle-east/rss"                                               # [F] /en/rss blocked; topic RSS works (35K, 30 items)
  "icg|2|rss|https://www.crisisgroup.org/rss.xml"                                                                   # [V] 10 items
  "quincy_inst|2|rss|https://responsiblestatecraft.org/feed/"                                                        # [V] 30 items
  "hellenicshipping|2|rss|https://www.hellenicshippingnews.com/feed/"                                                # [V] 20 items
  "reinsurance_news|2|rss|https://www.reinsurancene.ws/feed/"                                                        # [V] 10 items
  "splash247|2|rss|https://splash247.com/feed/"                                                                      # [V] 10 items
  "offshore_energy|2|rss|https://www.offshore-energy.biz/feed/"                                                      # [V] 10 items
  "insurance_journal|2|rss|https://www.insurancejournal.com/rss/topics/marine/"                                      # [V] 1 item
  "bunkerspot|2|rss|https://www.bunkerspot.com/rss"                                                                  # [V] 10 items
  "safety4sea|2|rss|https://safety4sea.com/feed/"                                                                    # [V] RSS (485K)
  "alma_research|2|rss|https://israel-alma.org/feed/"                                                                # [F] /category/reports/ 404; WP feed works (46K)
  "dnv_maritime|2|rss|https://www.dnv.com/news/rss"                                                                  # [F] old URL 404; /news/rss works (17K)
  "recorded_future|3|rss|https://www.recordedfuture.com/feed"                                                        # [F] /research/feed 404; /feed works (923K)

  # ── TIER 2 — SCRAPE (verified working) ────────────────────────────────────
  "iran_intl|2|scrape|https://www.iranintl.com/en"                                                                   # [V] 429K
  "bbc_persian|2|scrape|https://www.bbc.com/persian"                                                                 # [V] 471K
  "rudaw|2|rss|https://www.rudaw.net/english/rss.xml"                                                                # [V] 3K
  "tradewinds_insurance|2|scrape|https://www.tradewindsnews.com/insurance"                                           # [V] 563K
  "marsh_marine|2|scrape|https://www.marsh.com/us/industries/marine/insights.html"                                   # [V] 248K
  "iumi_news|2|scrape|https://iumi.com/news"                                                                        # [V] 281K
  "intercargo_news|2|scrape|https://www.intercargo.org/news/"                                                        # [V] 119K
  "icc_imb|2|scrape|https://www.icc-ccs.org/icc/imb"                                                                # [V] 141K

  # ── TIER 2 — SCRAPE (fixed URLs) ──────────────────────────────────────────
  "ambrey_analytics|2|scrape|https://www.ambrey.com/"                                                                # [F] /intelligence/ 404; root works (171K)
  "dryad_global|2|scrape|https://www.dryadglobal.com/"                                                               # [F] /news 404; root works (335K)
  "eos_risk|2|scrape|https://www.eosrisk.com/"                                                                       # [F] /news/ 404; root works (200K)
  "intertanko_news|2|scrape|https://www.intertanko.com/"                                                             # [F] /news/ 404; root works (71K)
  "maritime_executive|2|scrape|https://www.maritime-executive.com/"                                                  # [F] RSS/feed all 404; root works (183K)
  "marine_link|2|scrape|https://www.marinelink.com/"                                                                 # [F] RSS 404; root works (83K)
  "willis_marine|2|scrape|https://www.wtwco.com/en-us/insights"                                                     # [F] old URL 404; /en-us/insights works (296K)
  "aon_marine|2|scrape|https://www.aon.com/en/"                                                                      # [F] old URL 404; root works (446K)
  "cnn_mideast|2|scrape|https://edition.cnn.com/middle-east"                                                         # [F] RSS dead; scrape page (3.5M — large)
  "lloyds_list|2|scrape|https://www.lloydslist.com/"                                                                 # [F] paywall; root partial (201K)
  "insurance_insider|2|scrape|https://www.insuranceinsider.com/"                                                     # [F] paywall; root partial (136K)
  "clarksons_research|2|scrape|https://sin.clarksons.net/"                                                           # [F] /News 500; root works (430K)

  # ── TIER 3 — DOMAIN TRIGGERS ──────────────────────────────────────────────
  "cisa_advisories|3|rss|https://www.cisa.gov/cybersecurity-advisories/all.xml"                                      # [V] 30 advisories (450K)
  "mandiant_blog|3|rss|https://www.mandiant.com/resources/blog/rss.xml"                                              # [V] 20 posts (2M)
  "netblocks|3|scrape|https://netblocks.org"                                                                         # [V] 57K
  "eia_weekly|3|scrape|https://www.eia.gov/petroleum/supply/weekly/"                                                 # [V] 85K
  "opec_statements|3|scrape|https://www.opec.org/opec_web/en/press_room/4567.htm"                                   # [V] 221K
  "iras_war_risk|3|scrape|https://www.iras.co.uk/news/"                                                              # [V] 12K
  "moodys_shipping|3|scrape|https://www.moodys.com/researchandratings/market-segment/transportation/shipping/-/0015" # [V] 3K
  "signal_ocean|3|scrape|https://www.signalocean.com/"                                                               # [F] /blog 404; root works (164K)
  "swissre_sigma|3|scrape|https://www.swissre.com/institute/research/sigma-research.html"                            # [F] RSS 404; scrape page (189K)
  "munichre_marine|3|scrape|https://www.munichre.com/"                                                               # [F] /marine 404; root partial (67K)
  "credit_agricole_shipping|3|scrape|https://www.ca-cib.com/"                                                        # [F] old URL 404; root works (877K)
  "unctad_maritime|3|scrape|https://unctad.org/"                                                                     # [F] maritime URL 404; root works (145K)

  # ── BLOCKED — no workaround (included for logging) ────────────────────────
  "gallagher_marine|2|scrape|https://www.ajg.com/us/industries/marine/"                                              # [B] Incapsula (1K)
)

echo "Total sources: ${#SOURCES[@]}"
echo ""

# ─── Fetch function ──────────────────────────────────────────────────────────

fetch_source() {
  local entry="$1"
  IFS='|' read -r id tier method url <<< "$entry"
  local outfile="$OUTPUT_DIR/${id}.raw"
  local metafile="$OUTPUT_DIR/${id}.meta"
  local start_time=$(date +%s)

  # Fetch with curl
  local http_code
  http_code=$(curl -sL -o "$outfile" -w "%{http_code}" \
    -H "User-Agent: $UA" \
    --connect-timeout 10 \
    --max-time "$TIMEOUT" \
    "$url" 2>/dev/null || echo "000")

  local end_time=$(date +%s)
  local duration=$((end_time - start_time))
  local size=$(wc -c < "$outfile" 2>/dev/null | tr -d ' ' || echo "0")

  # Write metadata
  cat > "$metafile" << METAEOF
{
  "id": "$id",
  "tier": $tier,
  "method": "$method",
  "url": "$url",
  "http_code": $http_code,
  "size_bytes": $size,
  "fetch_duration_s": $duration,
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
METAEOF

  # Status indicator
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 400 ] && [ "$size" -gt 500 ]; then
    printf "  %-35s [%s] tier=%s %6s bytes  %ss\n" "$id" "$http_code" "$tier" "$size" "$duration"
  else
    printf "  %-35s [%s] tier=%s FAILED (%s bytes) %ss\n" "$id" "$http_code" "$tier" "$size" "$duration" >&2
  fi
}

export -f fetch_source
export OUTPUT_DIR UA TIMEOUT

# ─── Parallel execution ──────────────────────────────────────────────────────
echo "Fetching ${#SOURCES[@]} sources (max $MAX_PARALLEL parallel)..."
echo ""

printf '%s\n' "${SOURCES[@]}" | xargs -P "$MAX_PARALLEL" -I {} bash -c 'fetch_source "$@"' _ {}

echo ""

# ─── Summary ─────────────────────────────────────────────────────────────────
total=$(ls "$OUTPUT_DIR"/*.meta 2>/dev/null | wc -l | tr -d ' ')
success=0
failed=0
tier1_ok=0
tier1_fail=0
tier1_names_fail=""

for f in "$OUTPUT_DIR"/*.meta; do
  [ -f "$f" ] || continue
  eval "$(python3 -c "
import json, sys
d=json.load(open('$f'))
print(f'_code={d[\"http_code\"]}')
print(f'_sz={d[\"size_bytes\"]}')
print(f'_tier={d[\"tier\"]}')
print(f'_id={d[\"id\"]}')
" 2>/dev/null)" || continue

  if [ "$_code" -ge 200 ] 2>/dev/null && [ "$_code" -lt 400 ] 2>/dev/null && [ "$_sz" -gt 500 ] 2>/dev/null; then
    success=$((success + 1))
    [ "$_tier" = "1" ] && tier1_ok=$((tier1_ok + 1))
  else
    failed=$((failed + 1))
    if [ "$_tier" = "1" ]; then
      tier1_fail=$((tier1_fail + 1))
      tier1_names_fail="$tier1_names_fail $_id"
    fi
  fi
done

echo "═══ Fetch Complete ═══"
echo "  Total:     $total sources"
echo "  Success:   $success"
echo "  Failed:    $failed"
echo "  Tier 1:    $tier1_ok OK / $tier1_fail failed"
[ -n "$tier1_names_fail" ] && echo "  T1 fails: $tier1_names_fail"
echo "  Output:    $OUTPUT_DIR"

# Write summary manifest with per-source detail
python3 -c "
import json, glob
metas = []
for f in sorted(glob.glob('$OUTPUT_DIR/*.meta')):
    try:
        with open(f) as fh:
            metas.append(json.load(fh))
    except: pass
ok = [m for m in metas if 200 <= m['http_code'] < 400 and m['size_bytes'] > 500]
fail = [m for m in metas if not (200 <= m['http_code'] < 400 and m['size_bytes'] > 500)]
manifest = {
    'timestamp': '$(date -u +\"%Y-%m-%dT%H:%M:%SZ\")',
    'total': len(metas),
    'successful': len(ok),
    'failed': len(fail),
    'tier1_ok': len([m for m in ok if m['tier']==1]),
    'tier1_fail': len([m for m in fail if m['tier']==1]),
    'failed_sources': [{'id':m['id'],'tier':m['tier'],'http_code':m['http_code'],'size':m['size_bytes']} for m in fail],
    'sources': metas
}
with open('$OUTPUT_DIR/_manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

echo ""
echo "Next step: run /intel-triage to parse and classify collected content"
