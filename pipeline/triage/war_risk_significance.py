"""
War Risk Significance Gate — Claude Agent SDK (CIP) scoring subagent.

Architecture:
  score_items_cip(items, threshold, target_date) is the async public entry point
  called by war_risk_ingest.py Phase 3.  Items arrive as plain dicts; hard-pass
  filtering (JWC keywords, Tier 1 auto-pass) is applied upstream before this
  function is called.

  Remaining items are batched into groups of BATCH_SIZE and scored concurrently
  via anyio task groups.  Each batch spawns one CIP query() call — no web tools
  are needed; the subagent reasons over the item payload and returns scored JSON.

  All scored results (pass AND fail) are written to .cache/ for analyst review
  and ongoing model calibration.

Significance scoring criteria (weights sum to 100):
  +40  JWC listed area add/remove or premium directive
  +30  Quantified war risk premium movement (≥5% change cited)
  +25  P&I club / underwriter capacity change or circular
  +20  New ship seizure/attack directly affecting insurance settlement
  +20  Reinsurance market capacity withdrawal or retro pricing change
  +15  Broker or analyst commentary with specific rate/capacity data
  +10  Voyage diversion data (AIS-confirmed vessel re-routing)
  +10  Regulatory change (IMO, flag state, USCG, MCA HRA designation)
  +5   General market commentary mentioning conflict-related pricing
  -10  Duplicate of previously scored item in this cycle
  -15  Speculation without named source or data
  -20  Item is clearly non-relevant (advertising, awards, general news)

Default threshold: 45 (configurable in pipeline-config.yaml under
  war_risk.significance_threshold).
"""

from __future__ import annotations

import anyio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage  # type: ignore[import]
except ImportError:
    query = ClaudeAgentOptions = ResultMessage = None  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)

CACHE_DIR   = Path(__file__).parent.parent / '.cache'
BATCH_SIZE  = 10   # items per CIP scoring call
MAX_CONCURRENT = 4  # concurrent scoring subagents

DEFAULT_THRESHOLD = 45


# ── Public async entry point ───────────────────────────────────────────────────

async def score_items_cip(
    items: list[dict],
    threshold: int,
    target_date: datetime,
) -> list[dict]:
    """
    CIP-based significance scoring.  Called by war_risk_ingest.py Phase 3.
    Receives items that survived the hard-pass gate — plain dicts from the
    collection subagents.  Returns only items that pass the threshold.
    """
    if not items:
        return []

    # Slice into batches
    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    log.info('Significance scoring: %d items in %d batches (threshold=%d)',
             len(items), len(batches), threshold)

    results_by_batch: list[list[dict]] = [[] for _ in batches]

    # Semaphore-limited concurrent scoring
    cycle_year = target_date.year if target_date else 0
    sem = anyio.Semaphore(MAX_CONCURRENT)

    async def score_one(idx: int, batch: list[dict]) -> None:
        async with sem:
            results_by_batch[idx] = await _score_batch_cip(
                batch, threshold, idx, _cycle_year=cycle_year
            )

    async with anyio.create_task_group() as tg:
        for idx, batch in enumerate(batches):
            tg.start_soon(score_one, idx, batch)

    # Collect passing items; annotate with scores
    passing: list[dict] = []
    for batch, scored_batch in zip(batches, results_by_batch):
        for item, scored in zip(batch, scored_batch):
            score = scored.get('score', 0)
            if scored.get('passed'):
                item['significance_score']     = score
                item['significance_rationale'] = scored.get('rationale', '')
                item['passed_gate']            = True
                passing.append(item)
                log.info('[PASS %3d] %s — %s',
                         score,
                         item.get('source_name', '?'),
                         item.get('title', '')[:80])
            else:
                log.debug('[FAIL %3d] %s — %s',
                          score,
                          item.get('source_name', '?'),
                          item.get('title', '')[:60])

    _write_significance_log(batches, results_by_batch, threshold, target_date)

    log.info('Significance gate: %d/%d passed', len(passing), len(items))
    return passing


# ── CIP batch scorer ───────────────────────────────────────────────────────────

async def _score_batch_cip(
    batch: list[dict],
    threshold: int,
    batch_idx: int,
    _cycle_year: int = 0,
) -> list[dict]:
    """
    One CIP subagent call scores a batch of up to BATCH_SIZE items.
    No web tools are needed — Claude reasons over the payload.
    Returns a list of {index, score, rationale, passed} dicts matching
    the input order.
    """
    items_payload = [
        {
            'index':  idx,
            'source': item.get('source_name', item.get('source_id', '?')),
            'tier':   item.get('tier', 3),
            'title':  item.get('title', ''),
            'text':   (item.get('text', '') or '')[:600],
        }
        for idx, item in enumerate(batch)
    ]

    prompt = _build_scoring_prompt(items_payload, threshold, cycle_year=_cycle_year)
    raw_results: list[dict] = []

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],          # no web access — reasoning only
                permission_mode='dontAsk',
                model='claude-opus-4-6',
                max_turns=6,
            ),
        ):
            if isinstance(message, ResultMessage):
                text = (message.result or '').strip()
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0].strip()
                if text.startswith('['):
                    try:
                        raw_results = json.loads(text)
                    except json.JSONDecodeError as exc:
                        log.warning('[sig-batch-%d] JSON parse error: %s', batch_idx, exc)

    except Exception as exc:
        log.error('[sig-batch-%d] CIP scoring failed: %s', batch_idx, exc)

    # Map results back to input order; fall back to score=0 on missing entries
    out: list[dict] = []
    for idx, item in enumerate(batch):
        result = next((r for r in raw_results if r.get('index') == idx), None)
        if result is None:
            score     = 0
            rationale = 'No score returned by CIP scoring subagent.'
        else:
            try:
                score = int(result.get('score', 0))
            except (TypeError, ValueError):
                score = 0
            rationale = result.get('rationale', '')

        out.append({
            'index':     idx,
            'score':     score,
            'rationale': rationale,
            'passed':    score >= threshold,
        })

    return out


# ── Audit log ─────────────────────────────────────────────────────────────────

def _write_significance_log(
    batches: list[list[dict]],
    results_by_batch: list[list[dict]],
    threshold: int,
    target_date: datetime,
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    log_path = CACHE_DIR / f'war_risk_significance_{stamp}.json'

    flat: list[dict] = []
    for batch, scored_batch in zip(batches, results_by_batch):
        for item, scored in zip(batch, scored_batch):
            flat.append({
                'title':       item.get('title', ''),
                'source_name': item.get('source_name', ''),
                'source_id':   item.get('source_id', ''),
                'tier':        item.get('tier', 3),
                'score':       scored.get('score', 0),
                'rationale':   scored.get('rationale', ''),
                'passed':      scored.get('passed', False),
            })

    log_path.write_text(
        json.dumps({
            'cycle_date':   target_date.strftime('%Y-%m-%d'),
            'threshold':    threshold,
            'total_scored': len(flat),
            'passed':       sum(1 for r in flat if r['passed']),
            'results':      flat,
        }, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    log.info('Significance log → %s', log_path)


# ── Prompt templates ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior war risk insurance analyst at a leading Lloyd's market intelligence firm.
Your task: score news items for their significance to the global war risk insurance market.

WAR RISK SIGNIFICANCE CRITERIA (score 0–100):

HIGH significance (score 60–100):
  - JWC listed area changes (add/remove) — always 90+
  - Quantified war risk premium movements ≥5% with cited source — 75+
  - P&I club circular or underwriter capacity change — 70+
  - Ship seizure/attack directly causing insurance claim/CTL — 70+
  - Reinsurance capacity withdrawal or retro pricing change — 70+
  - New war risk exclusion zone designation — 70+

MEDIUM significance (score 30–59):
  - Broker market commentary with specific data (rates, capacity limits) — 45+
  - Voyage diversion data (AIS-confirmed route changes) — 40+
  - IMO or flag state advisory affecting vessel operations — 40+
  - Named insurer or broker statement on war risk appetite — 35+
  - Regulatory changes affecting war risk policy terms — 35+

LOW significance (score 0–29):
  - General shipping news mentioning insurance without specifics — 15
  - Market commentary without data points — 10
  - Non-relevant (awards, hiring, product announcements) — 0

SCORING RULES:
  - Be precise: each score must reflect actual market impact, not just topic relevance.
  - A JWC listed area change in a conflict-active zone = 95.
  - A 10% premium increase with Lloyd's syndicate as source = 80.
  - A broker saying "market is hardening" without data = 25.
  - A general news article mentioning ship insurance = 10.

Output ONLY valid JSON — no markdown, no explanation outside the JSON.\
"""


def _build_scoring_prompt(items: list[dict], threshold: int, cycle_year: int = 0) -> str:
    items_json = json.dumps(items, indent=2, ensure_ascii=False)
    year_note = f' ({cycle_year})' if cycle_year else ''
    return f"""\
{_SYSTEM_PROMPT}

Score each of the following {len(items)} war risk insurance items.

Current market context{year_note}: Active conflict in the Middle East / Gulf region.
Red Sea shipping disruption ongoing. JWC areas under review. Lloyd's war risk
market hardening with premiums elevated vs. prior-year baseline.

Significance threshold for inclusion in the daily brief: {threshold}/100.

Items to score:
{items_json}

Return a JSON array with one object per item:
[
  {{
    "index": 0,
    "score": 72,
    "rationale": "Named P&I club circular on new Hormuz transit requirements — specific operational impact on vessel insurance terms."
  }},
  ...
]

Return ONLY the JSON array. No markdown fences. No additional text."""
