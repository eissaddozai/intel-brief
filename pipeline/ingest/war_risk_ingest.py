"""
War Risk Insurance & Maritime Finance — Collection Engine (Domain D6)
Uses the Claude Agent SDK (CIP) for all intelligence gathering.

Architecture:
  Phase 1 — Concurrent collection subagents (one per source category).
             Each subagent has WebFetch + WebSearch access and collects
             everything it can find, regardless of significance.

  Phase 2 — Hard-pass gate: JWC/listed-area items and all Tier 1 sources
             bypass significance scoring and go straight to the brief.

  Phase 3 — Significance subagent (war_risk_significance.py) scores
             remaining items via claude_agent_sdk query() and filters
             to threshold.

  Audit  —  The raw dump (all collected items, pre-significance) is
             written to .cache/ every cycle for analyst review.

Source categories map to CATEGORIES dict; add/remove entries there to
adjust which sources each subagent is responsible for.
"""

from __future__ import annotations

import anyio
import hashlib
import json
import logging
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
CACHE_DIR    = Path(__file__).parent.parent / '.cache'
MAX_ITEM_AGE_HOURS = 30

# JWC keyword patterns — items matching these bypass significance scoring
JWC_HARD_PASS: list[str] = [
    'joint war committee', 'jwc listed', 'jwc area', 'listed area change',
    'breach area', 'jwc adds', 'jwc removes', 'war risk area update',
    'conwartime clause', 'voywar clause',
]

# Tier 1 source IDs from sources.yaml that get automatic 70+ score
TIER1_AUTO_PASS: set[str] = {
    'lloyds_mkt_bulletins', 'jwc_listed_areas', 'imo_circular',
    'ig_pic_circulars', 'bimco_news', 'nato_shipping_centre', 'usmto',
}

# Source category groupings — each spawns one concurrent collection subagent.
# Keep groups ≤8 sources so each agent can complete within reasonable turns.
CATEGORIES: dict[str, list[str]] = {
    'regulatory': [
        'lloyds_mkt_bulletins', 'jwc_listed_areas', 'imo_circular',
        'ig_pic_circulars', 'bimco_news', 'nato_shipping_centre', 'usmto',
    ],
    'market_intelligence': [
        'lloyds_list', 'tradewinds_insurance', 'reinsurance_news',
        'insurance_journal', 'insurance_insider', 'iumi_news',
    ],
    'maritime_security': [
        'dryad_global', 'ambrey_analytics', 'eos_risk', 'icc_imb',
    ],
    'shipping_trade': [
        'marine_link', 'splash247', 'hellenicshipping', 'maritime_executive',
        'bunkerspot', 'dnv_maritime', 'clarksons_research', 'safety4sea',
    ],
    'brokers_associations': [
        'marsh_marine', 'willis_marine', 'aon_marine', 'gallagher_marine',
        'intertanko_news', 'intercargo_news', 'offshore_energy',
    ],
    'reinsurance_finance': [
        'swissre_sigma', 'munichre_marine', 'moodys_shipping',
        'signal_ocean', 'credit_agricole_shipping', 'unctad_maritime',
        'iras_war_risk',
    ],
}


# ── JSON extraction helpers ───────────────────────────────────────────────────

def _extract_json_text(text: str) -> str:
    """
    Extract JSON from agent response text.

    Handles:
      - Clean JSON (no fences)
      - Balanced ```json ... ``` fences
      - Incomplete/malformed fences (missing closing ```)
      - Falls back to finding the first [ or { and parsing from there
    """
    stripped = text.strip()

    # Case 1: Properly fenced JSON — balanced opening and closing
    if '```json' in stripped:
        parts = stripped.split('```json', 1)
        tail = parts[1]
        if '```' in tail:
            return tail.split('```', 1)[0].strip()
        # Incomplete fence — closing ``` is missing; take everything after opening
        log.debug('Incomplete ```json fence detected — using tail content')
        return tail.strip()

    if '```' in stripped:
        parts = stripped.split('```', 1)
        tail = parts[1]
        if '```' in tail:
            return tail.split('```', 1)[0].strip()
        log.debug('Incomplete ``` fence detected — using tail content')
        return tail.strip()

    # Case 2: No fences — find the first JSON structure
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        idx = stripped.find(start_char)
        if idx >= 0:
            # Walk forward to find the matching closing bracket
            depth = 0
            in_string = False
            escape_next = False
            for i in range(idx, len(stripped)):
                ch = stripped[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == start_char:
                        depth += 1
                    elif ch == end_char:
                        depth -= 1
                        if depth == 0:
                            return stripped[idx:i+1]
            # Could not find balanced end — return from start_char to end
            return stripped[idx:]

    return stripped


# ── Source loading ─────────────────────────────────────────────────────────────

def load_d6_sources() -> dict[str, dict]:
    """Load all enabled d6-tagged sources from sources.yaml, keyed by source ID."""
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return {
        s['id']: s
        for s in data.get('sources', [])
        if s.get('enabled', True)
        and 'd6' in s.get('domains', [])
        and s.get('method') in ('rss', 'scrape')
    }


# ── Prompt builders ────────────────────────────────────────────────────────────

def _collection_prompt(category: str, sources: list[dict], cutoff: datetime) -> str:
    source_lines = '\n'.join(
        f"  [{s['tier']}] {s['name']}: {s.get('url', '')}"
        + (f"\n      {s['notes'].strip()}" if s.get('notes') else '')
        for s in sources
    )
    return f"""\
You are a war risk insurance intelligence collector for the '{category}' category.

Your task: fetch and extract news items from each source below published after {cutoff.strftime('%d %b %Y %H:%M UTC')}.

SOURCES:
{source_lines}

INSTRUCTIONS:
1. Use WebFetch on each source URL to retrieve the page content.
2. Extract every news item, article, bulletin, update, or market notice.
3. Relevance scope: war risk insurance, marine premiums, JWC listed areas, P&I clubs,
   vessel seizures/attacks, shipping disruptions, underwriter capacity, reinsurance,
   tanker/cargo insurance, high risk area designations, maritime security.
4. Capture items even if only marginally relevant — significance filtering happens later.
5. If a URL returns a paywall (403/login), note it briefly and continue to the next source.
6. Use WebSearch to find additional recent news for each source if the direct URL is thin.
7. For each item, extract: title, summary text (up to 400 chars), article URL, date if visible.

OUTPUT FORMAT — return a JSON array. Each element must have these exact fields:
{{
  "source_id":           "source_id_from_list",
  "source_name":         "Human-readable source name",
  "tier":                1 or 2 or 3,
  "domains":             ["d6"],
  "title":               "Headline or title",
  "text":                "Summary text up to 400 characters",
  "url":                 "Full URL of the article or bulletin",
  "timestamp":           "ISO-8601 date string, or null",
  "verification_status": "confirmed" for tier 1, "reported" for tier 2, "claimed" for tier 3
}}

Return ONLY the JSON array. No markdown fences. No explanatory text.
If no relevant items are found, return [].
"""


# ── Collection subagents ───────────────────────────────────────────────────────

async def _run_collection_subagent(
    category: str,
    sources: list[dict],
    cutoff: datetime,
) -> list[dict]:
    """
    One CIP subagent per source category.
    Uses WebFetch + WebSearch to gather raw items.
    Returns a list of raw item dicts.
    """
    if not sources:
        return []

    prompt = _collection_prompt(category, sources, cutoff)
    items: list[dict] = []

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=['WebFetch', 'WebSearch'],
                permission_mode='dontAsk',
                model='claude-opus-4-6',
                max_turns=len(sources) * 3 + 10,
            ),
        ):
            if isinstance(message, ResultMessage):
                text = (message.result or '').strip()
                text = _extract_json_text(text)
                if text.startswith('['):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            items.extend(parsed)
                    except json.JSONDecodeError as exc:
                        log.warning('[%s] JSON parse failed: %s', category, exc)

    except Exception as exc:
        log.error('[%s] Collection subagent error: %s', category, exc)

    log.info('[%s] Collected %d raw items', category, len(items))
    return items


# ── Deduplication ──────────────────────────────────────────────────────────────

def _dedup(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = hashlib.sha256(
            (item.get('url', '') + item.get('title', '')).encode('utf-8')
        ).hexdigest()[:16]
        if key not in seen and item.get('title'):
            seen.add(key)
            item['content_hash'] = key
            item.setdefault('tagged_domains', item.get('domains', ['d6']))
            item.setdefault('method', 'cip')
            out.append(item)
    return out


# ── Concurrent collection orchestration ───────────────────────────────────────

async def _collect_all(
    target_date: datetime,
    all_sources: dict[str, dict],
) -> list[dict]:
    """
    Launch all collection subagents concurrently via anyio task group.
    Returns deduplicated list of all collected items.
    """
    cutoff = target_date - timedelta(hours=MAX_ITEM_AGE_HOURS)
    bucket: list[list[dict]] = [[] for _ in CATEGORIES]

    async def run_category(idx: int, category: str, source_ids: list[str]) -> None:
        sources = [all_sources[sid] for sid in source_ids if sid in all_sources]
        items = await _run_collection_subagent(category, sources, cutoff)
        bucket[idx] = items

    async with anyio.create_task_group() as tg:
        for idx, (category, source_ids) in enumerate(CATEGORIES.items()):
            tg.start_soon(run_category, idx, category, source_ids)

    # Audit empty buckets — a silent subagent failure leaves the bucket at []
    category_names = list(CATEGORIES.keys())
    for idx, batch in enumerate(bucket):
        if not batch:
            log.warning(
                '[%s] Category returned 0 items — collection subagent may have '
                'failed, returned unparseable JSON, or found no relevant content',
                category_names[idx],
            )

    flat = [item for batch in bucket for item in batch]
    deduped = _dedup(flat)
    log.info('Collection complete: %d unique items (from %d raw across %d categories)',
             len(deduped), len(flat), len(CATEGORIES))
    return deduped


# ── Hard-pass gate ─────────────────────────────────────────────────────────────

def _apply_hard_pass(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split items into (hard_pass, needs_scoring).
    JWC keyword matches and Tier 1 auto-pass sources bypass significance scoring.
    """
    hard_pass: list[dict] = []
    needs_scoring: list[dict] = []

    for item in items:
        text_lower = (item.get('title', '') + ' ' + item.get('text', '')).lower()
        is_jwc = any(kw in text_lower for kw in JWC_HARD_PASS)
        is_t1_auto = item.get('source_id') in TIER1_AUTO_PASS

        if is_jwc:
            item['significance_score'] = 100
            item['significance_rationale'] = 'HARD PASS: JWC/listed-area keyword.'
            item['passed_gate'] = True
            hard_pass.append(item)
        elif is_t1_auto:
            item['significance_score'] = 70
            item['significance_rationale'] = f'AUTO PASS: Tier 1 source ({item.get("source_id")}).'
            item['passed_gate'] = True
            hard_pass.append(item)
        else:
            needs_scoring.append(item)

    return hard_pass, needs_scoring


# ── Public interface ───────────────────────────────────────────────────────────

def ingest_war_risk(
    target_date: datetime,
    config: dict | None = None,
    force: bool = False,
) -> list[dict]:
    """
    Full war risk collection and significance gate via Claude Agent SDK.
    Synchronous entry point — wraps async pipeline with anyio.run().

    Returns list of significant items in pipeline RawItem dict format.
    """
    config = config or {}
    wr_cfg = config.get('war_risk', {})
    threshold: int = wr_cfg.get('significance_threshold', 45)

    all_sources = load_d6_sources()
    if not all_sources:
        log.warning('No d6 sources found — check sources.yaml')
        return []

    log.info('War risk CIP pipeline: %d sources | threshold=%d', len(all_sources), threshold)

    async def _pipeline() -> list[dict]:
        # Phase 1: Concurrent collection subagents
        raw_items = await _collect_all(target_date, all_sources)

        # Write full raw dump (audit trail — everything before filtering)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = CACHE_DIR / f'war_risk_raw_{target_date.strftime("%Y%m%d")}.json'
        raw_path.write_text(json.dumps(raw_items, indent=2, ensure_ascii=False), encoding='utf-8')
        log.info('Raw audit dump: %d items → %s', len(raw_items), raw_path)

        # Phase 2: Hard-pass gate
        hard_pass, needs_scoring = _apply_hard_pass(raw_items)
        log.info('Hard/auto pass: %d | Needs significance scoring: %d',
                 len(hard_pass), len(needs_scoring))

        # Phase 3: Significance subagent (CIP)
        try:
            from triage.war_risk_significance import score_items_cip
            scored_pass = await score_items_cip(needs_scoring, threshold, target_date)
        except Exception as exc:
            log.error('Significance subagent failed (%s) — using pre-score fallback', exc)
            # Fallback: pass items with tier ≤ 2 that mention insurance/war keywords
            insurance_kw = ['insurance', 'premium', 'war risk', 'p&i', 'lloyd', 'underwriter']
            scored_pass = [
                i for i in needs_scoring
                if i.get('tier', 3) <= 2
                and any(kw in (i.get('title', '') + i.get('text', '')).lower()
                        for kw in insurance_kw)
            ]
            log.warning('Fallback: %d items passed', len(scored_pass))

        return hard_pass + scored_pass

    return anyio.run(_pipeline)
