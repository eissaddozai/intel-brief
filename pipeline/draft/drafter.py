"""
Claude API drafting module.
Drafts each domain section, then the executive summary, using structured JSON output.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / 'prompts'

DOMAIN_CONFIG = [
    ('d1', '01', 'BATTLESPACE · KINETIC'),
    ('d2', '02', 'ESCALATION · TRAJECTORY'),
    ('d3', '03', 'ENERGY · ECONOMIC'),
    ('d4', '04', 'DIPLOMATIC · POLITICAL'),
    ('d5', '05', 'CYBER · INFORMATION OPS'),
    ('d6', '06', 'WAR RISK INSURANCE · MARITIME FINANCE'),
]

DOMAIN_PROMPTS = {
    'd1': 'battlespace.md',
    'd2': 'escalation.md',
    'd3': 'energy.md',
    'd4': 'diplomatic.md',
    'd5': 'cyber.md',
    'd6': 'war_risk.md',
}


def _fill_template(template: str, **kwargs: str) -> str:
    """
    Replace {variable} placeholders in a template string.

    Uses manual replacement instead of str.format() to avoid clashing with
    literal curly braces in JSON examples inside the prompt files.
    Logs a warning for any placeholder that was not replaced (typo guard).
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace('{' + key + '}', str(value))

    # Detect unreplaced placeholders — only flag simple snake_case identifiers
    # (not short domain IDs like d1/d2 which appear in JSON schema examples)
    unfilled = re.findall(r'\{([a-z][a-z0-9_]{2,})\}', result)
    if unfilled:
        log.warning(
            '_fill_template: unreplaced placeholder(s) in prompt: %s — check kwargs',
            unfilled,
        )
    return result


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Prompt file not found: {path}')
    return path.read_text(encoding='utf-8')


def filter_by_domain(items: list[dict], domain: str) -> tuple[list[dict], list[dict]]:
    """Split items into (tier1, tier2_plus) for a given domain.

    tier2_plus includes Tier 2 and Tier 3 items — Tier 3 (PKK-affiliated,
    Iranian state media) are included so prompts can cite them as claimed
    sources; their verification_status distinguishes them from Tier 2.
    """
    domain_items = [i for i in items if domain in i.get('tagged_domains', [])]
    tier1 = [i for i in domain_items if i.get('tier') == 1]
    tier2_plus = [i for i in domain_items if i.get('tier') != 1]
    return tier1, tier2_plus


def _domain_kj_text(domain_sections: list[dict], domain_id: str) -> str:
    """Extract the key judgment text for a given domain from drafted sections."""
    section = next((d for d in domain_sections if d.get('id') == domain_id), None)
    if not section:
        return '(not yet drafted)'
    return section.get('keyJudgment', {}).get('text', '(no key judgment)')


def _domain_summary(section: dict) -> str:
    """Produce a compact text summary of a domain section for use as context."""
    kj = section.get('keyJudgment', {})
    paras = section.get('bodyParagraphs', [])
    summary_parts = [
        f"Domain: {section.get('title', '')}",
        f"Key Judgment: {kj.get('text', '')} "
        f"[confidence: {kj.get('confidence', '?')}, {kj.get('probabilityRange', '')}, "
        f"language: {kj.get('language', '?')}]",
    ]
    # Include up to 4 paragraphs with up to 500 chars each for richer cross-domain context
    for p in paras[:4]:
        text = p.get('text', '')
        if len(text) > 500:
            text = text[:500] + '…'
        summary_parts.append(f"  [{p.get('subLabel', 'PARA')}]: {text}")
    return '\n'.join(summary_parts)


_CALL_RETRY_DELAYS = (5, 15, 30)  # seconds between retries for transient API errors


def call_claude(
    client: anthropic.Anthropic,
    prompt: str,
    max_tokens: int = 2000,
    model: str = 'claude-opus-4-6',
) -> dict | list:
    """Call Claude API and parse the JSON response. Retries on transient errors."""
    system = (
        'You are a senior conflict intelligence analyst. '
        'Write in the dispassionate, precise voice of serious foreign affairs journalism. '
        'Always produce structured JSON output exactly as specified. '
        'Never fabricate citations. Never use forbidden jargon. '
        'Distinguish Tier 1 confirmed facts from Tier 2 analytical interpretation.'
    )
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + list(_CALL_RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.3,
                system=system,
                messages=[{'role': 'user', 'content': prompt}],
            )
        except Exception as exc:
            err_str = str(exc).lower()
            _transient = any(kw in err_str for kw in ('rate limit', 'overloaded', '529', '529'))
            if _transient and attempt < len(_CALL_RETRY_DELAYS):
                log.warning('Claude API transient error (attempt %d/%d): %s — retrying in %ds',
                            attempt + 1, len(_CALL_RETRY_DELAYS) + 1, exc, _CALL_RETRY_DELAYS[attempt])
                last_exc = exc
                continue
            raise
        else:
            text = response.content[0].text
            # Strip markdown code fences if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                log.error('JSON parse failed: %s\nRaw response (first 600 chars): %s',
                          exc, text[:600])
                raise
    raise RuntimeError(f'Claude API failed after {len(_CALL_RETRY_DELAYS) + 1} attempts') from last_exc


def draft_domain(
    client: anthropic.Anthropic,
    domain: str,
    items: list[dict],
    target_date: datetime,
    prev_cycle: dict | None = None,
    context_sections: dict | None = None,  # {domain_id: drafted_section_dict}
    model: str = 'claude-opus-4-6',
) -> dict:
    """Draft a single domain section."""
    tier1, tier2 = filter_by_domain(items, domain)

    if not tier1 and not tier2:
        log.warning('Domain %s: zero items — drafting with empty source material', domain)

    template = load_prompt(DOMAIN_PROMPTS[domain])

    # Previous cycle key judgment for delta context
    prev_kj = ''
    if prev_cycle:
        prev_domains = prev_cycle.get('domains', [])
        prev_d = next((d for d in prev_domains if d.get('id') == domain), None)
        if prev_d:
            prev_kj = prev_d.get('keyJudgment', {}).get('text', '')

    # Cross-domain context (d2/d3 get d1; d4 gets d2)
    context_sections = context_sections or {}
    d1_context = _domain_summary(context_sections['d1']) if 'd1' in context_sections else '(not yet available)'
    d2_context = _domain_summary(context_sections['d2']) if 'd2' in context_sections else '(not yet available)'

    # d3 (energy) context — needed by the d6 war_risk template as {d3_context}
    d3_context = _domain_summary(context_sections['d3']) if 'd3' in context_sections else '(not yet available)'

    prompt = _fill_template(
        template,
        tier1_items=json.dumps(tier1[:15], indent=2, ensure_ascii=False),
        tier2_items=json.dumps(tier2[:15], indent=2, ensure_ascii=False),
        prev_cycle_kj=prev_kj or '(no previous cycle)',
        d1_context=d1_context,
        d2_context=d2_context,
        d3_context=d3_context,  # war_risk.md uses {d3_context}; others ignore it harmlessly
    )

    log.info('Drafting domain %s (%d T1, %d T2 items)...', domain, len(tier1), len(tier2))
    result = call_claude(client, prompt, max_tokens=3000, model=model)
    return result if isinstance(result, dict) else {}


def draft_executive(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
    model: str = 'claude-opus-4-6',
) -> dict:
    """Draft executive summary (BLUF + key judgments + KPIs)."""
    template = load_prompt('executive.md')

    # Build per-domain summary strings matching {d1_summary} … {d5_summary}
    section_map = {s.get('id'): s for s in domain_sections}
    prev_bluf = prev_cycle.get('executive', {}).get('bluf', '') if prev_cycle else ''

    prompt = _fill_template(
        template,
        d1_summary=_domain_summary(section_map.get('d1', {})),
        d2_summary=_domain_summary(section_map.get('d2', {})),
        d3_summary=_domain_summary(section_map.get('d3', {})),
        d4_summary=_domain_summary(section_map.get('d4', {})),
        d5_summary=_domain_summary(section_map.get('d5', {})),
        d6_summary=_domain_summary(section_map.get('d6', {})),
        prev_cycle_bluf=prev_bluf or '(no previous cycle)',
    )

    log.info('Drafting executive summary...')
    result = call_claude(client, prompt, max_tokens=2000, model=model)
    return result if isinstance(result, dict) else {}


def draft_strategic_header(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    executive: dict,
    prev_cycle: dict | None = None,
    model: str = 'claude-opus-4-6',
) -> dict:
    """Draft the strategic header (headline judgment + trajectory)."""
    template = load_prompt('strategic_header.md')

    prev_header = prev_cycle.get('strategicHeader', {}) if prev_cycle else {}
    prev_header_text = (
        f"{prev_header.get('headlineJudgment', '')} "
        f"[{prev_header.get('threatLevel', '')} / {prev_header.get('threatTrajectory', '')}]"
        if prev_header else '(no previous cycle)'
    )

    all_kjs = '\n'.join(
        f"- [{s.get('id')}] {s.get('keyJudgment', {}).get('text', '')}"
        for s in domain_sections
    )

    prompt = _fill_template(
        template,
        executive_bluf=executive.get('bluf', ''),
        all_kjs=all_kjs,
        prev_cycle_header=prev_header_text,
    )

    log.info('Drafting strategic header...')
    result = call_claude(client, prompt, max_tokens=800, model=model)
    return result if isinstance(result, dict) else {}


def draft_warning_indicators(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
    model: str = 'claude-opus-4-6',
) -> list[dict]:
    """Draft / update warning indicators."""
    template = load_prompt('warning_indicators.md')

    all_domain_summaries = '\n\n'.join(_domain_summary(s) for s in domain_sections)
    prev_wi = json.dumps(
        prev_cycle.get('warningIndicators', []) if prev_cycle else [],
        indent=2
    )

    prompt = _fill_template(
        template,
        all_domain_summaries=all_domain_summaries,
        prev_cycle_indicators=prev_wi,
    )

    log.info('Drafting warning indicators...')
    result = call_claude(client, prompt, max_tokens=2500, model=model)
    if isinstance(result, list):
        return result
    return result.get('warningIndicators', [])


def draft_collection_gaps(
    client: anthropic.Anthropic,
    tagged_items: list[dict],
    domain_sections: list[dict],
    model: str = 'claude-opus-4-6',
) -> list[dict]:
    """Identify collection gaps from triage output and domain confidence."""
    template = load_prompt('collection_gaps.md')

    # Triage summary: item counts per domain, failed sources
    domain_counts: dict[str, int] = {}
    for item in tagged_items:
        for d in item.get('tagged_domains', []):
            domain_counts[d] = domain_counts.get(d, 0) + 1

    triage_summary = (
        'Items collected per domain: '
        + ', '.join(f'{k}={v}' for k, v in sorted(domain_counts.items()))
    )

    all_domain_summaries = '\n\n'.join(
        f"[{s.get('id')}] {s.get('title', '')} — confidence: {s.get('confidence', '?')}"
        for s in domain_sections
    )

    prompt = _fill_template(
        template,
        triage_summary=triage_summary,
        all_domain_summaries=all_domain_summaries,
    )

    log.info('Drafting collection gaps...')
    result = call_claude(client, prompt, max_tokens=1500, model=model)
    if isinstance(result, list):
        return result
    return result.get('collectionGaps', [])


_BRENT_PATTERN = re.compile(
    r'\$\s*(\d{2,3}(?:\.\d{1,2})?)\s*/?\s*(?:bbl|barrel|b)?',
    re.IGNORECASE,
)


def _extract_brent_price(items: list[dict]) -> str:
    """
    Attempt to extract a Brent crude price from d3 energy items.
    Returns formatted price string like '$94.20' or '—' if not found.
    """
    for item in items:
        if 'd3' not in item.get('tagged_domains', []):
            continue
        haystack = item.get('title', '') + ' ' + item.get('text', '')
        m = _BRENT_PATTERN.search(haystack)
        if m:
            return f'${m.group(1)}/bbl'
    return '—'


def _count_kinetic_incidents(items: list[dict]) -> str:
    """
    Count d1 (battlespace/kinetic) items as a proxy for 24h incident volume.
    Returns string like '14' or '—'.
    """
    count = sum(1 for i in items if 'd1' in i.get('tagged_domains', []))
    return str(count) if count > 0 else '—'


def _build_flash_points(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    executive: dict,
    model: str,
) -> list[dict]:
    """
    Draft flash-point alerts from domain key judgments and executive summary.
    Flash points are 1–3 items representing the most time-critical events.
    Returns a list of flash-point dicts: {headline, detail, domain, urgency}.
    """
    all_kjs = '\n'.join(
        f"[{s.get('id')}] {s.get('keyJudgment', {}).get('text', '')}"
        for s in domain_sections
    )
    bluf = executive.get('bluf', '')

    prompt = (
        'You are a senior conflict intelligence analyst drafting FLASH POINTS for a daily brief.\n\n'
        'FLASH POINTS are the 1–3 most time-critical developments from the current cycle that '
        'require immediate analyst attention — not a summary of the brief, but the sharpest '
        'operational tripwires.\n\n'
        f'EXECUTIVE BLUF:\n{bluf}\n\n'
        f'DOMAIN KEY JUDGMENTS:\n{all_kjs}\n\n'
        'Select up to 3 flash points. For each, return a JSON object with exactly these fields:\n'
        '  "id": "fp-1" | "fp-2" | "fp-3"\n'
        '  "timestamp": ISO 8601 UTC timestamp of the event (use cycle timestamp if unknown)\n'
        '  "headline": one sharp sentence (≤12 words) — the event itself\n'
        '  "detail": one analytical sentence (≤25 words) — why it matters now\n'
        '  "domain": the primary domain id (d1/d2/d3/d4/d5/d6)\n'
        '  "confidence": "high" | "moderate" | "low"\n'
        '  "citations": [] (empty array unless you can name a specific Tier 1 source)\n\n'
        'Return ONLY a JSON array of 1–3 objects. No markdown, no commentary.\n'
        'If no events meet flash-point threshold, return [].'
    )

    try:
        result = call_claude(client, prompt, max_tokens=700, model=model)
        if isinstance(result, list):
            return result[:3]
    except Exception as exc:
        log.warning('Flash point drafting failed: %s', exc)
    return []


def draft_cycle(
    tagged_items: list[dict],
    target_date: datetime,
    prev_cycle: dict | None = None,
    config: dict | None = None,
) -> dict:
    """
    Orchestrate full cycle draft.
    Domain order: d1 → d2 (gets d1 context) → d3 (gets d1 context) →
                  d4 (gets d2 context) → d5 →
                  d6 (gets d1+d3 context) → executive → strategic header →
                  warning indicators → collection gaps.
    """
    config = config or {}
    claude_cfg = config.get('claude', {})

    api_key = claude_cfg.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError(
            'ANTHROPIC_API_KEY not set. Export the variable or add it to pipeline-config.yaml.'
        )

    # Respect configured model — never silently fall back to a different tier
    model = claude_cfg.get('model', 'claude-opus-4-6')
    client = anthropic.Anthropic(api_key=api_key)

    domain_sections: list[dict] = []
    drafted: dict[str, dict] = {}  # domain_id → section dict

    for domain_id, domain_num, domain_title in DOMAIN_CONFIG:
        section = draft_domain(
            client=client,
            domain=domain_id,
            items=tagged_items,
            target_date=target_date,
            prev_cycle=prev_cycle,
            context_sections=drafted,
            model=model,
        )
        # Ensure schema fields are present
        section.setdefault('id', domain_id)
        section.setdefault('num', domain_num)
        section.setdefault('title', domain_title)
        domain_sections.append(section)
        drafted[domain_id] = section
        log.info('Domain %s drafted', domain_id)

    executive = draft_executive(client, domain_sections, prev_cycle, model=model)
    strategic_header = draft_strategic_header(client, domain_sections, executive, prev_cycle, model=model)
    warning_indicators = draft_warning_indicators(client, domain_sections, prev_cycle, model=model)
    collection_gaps = draft_collection_gaps(client, tagged_items, domain_sections, model=model)
    flash_points = _build_flash_points(client, domain_sections, executive, model=model)

    # Derive live strip cell values from collected/drafted data
    brent_price = _extract_brent_price(tagged_items)
    incident_count = _count_kinetic_incidents(tagged_items)
    flash_point_count = str(len(flash_points)) if flash_points else '0'

    # Hormuz status from warning indicators
    hormuz_wi = next(
        (wi for wi in warning_indicators if 'hormuz' in wi.get('indicator', '').lower()),
        None,
    )
    hormuz_status = (
        'DISRUPTED' if hormuz_wi and hormuz_wi.get('status') in ('triggered', 'elevated')
        else 'ACTIVE'
    )

    # Merge strategicHeader fields into meta for convenience
    threat_level = strategic_header.pop('threatLevel', 'SEVERE')
    threat_trajectory = strategic_header.pop('threatTrajectory', 'escalating')

    cycle_id = f'CSE-BRIEF-DRAFT-{target_date.strftime("%Y%m%d")}'

    return {
        'meta': {
            'cycleId': cycle_id,
            'cycleNum': '000',  # Overwritten by serializer
            'classification': 'PROTECTED B',
            'tlp': 'AMBER',
            'timestamp': target_date.strftime('%Y-%m-%dT06:00:00Z'),
            'region': 'Iran · Gulf Region · Eastern Mediterranean',
            'analystUnit': 'CSE Conflict Assessment Unit',
            'threatLevel': threat_level,
            'threatTrajectory': threat_trajectory,
            'subtitle': 'Iran War File — Daily Assessment',
            'contextNote': (
                f'Cycle covers the 24-hour period ending 0600 UTC '
                f'{target_date.strftime("%d %B %Y")}. All times UTC unless noted.'
            ),
            'stripCells': [
                {'top': threat_level,      'bot': 'THREAT LEVEL'},
                {'top': incident_count,    'bot': 'INCIDENTS / 24H'},
                {'top': brent_price,       'bot': 'BRENT CRUDE'},
                {'top': hormuz_status,     'bot': 'HORMUZ STATUS'},
                {'top': flash_point_count, 'bot': 'FLASH POINTS'},
            ],
        },
        'strategicHeader': strategic_header,
        'flashPoints': flash_points,
        'executive': executive,
        'domains': domain_sections,
        'warningIndicators': warning_indicators,
        'collectionGaps': collection_gaps,
        'caveats': {
            'cycleRef': f'CSE-BRIEF-DRAFT · {target_date.strftime("%d %B %Y").upper()}',
            'items': [
                {
                    'label': 'DRAFT STATUS',
                    'text': 'Pipeline draft — human review required before distribution.'
                }
            ],
            'confidenceAssessment': 'See individual domain sections for confidence ratings.',
            'dissenterNotes': [],
            'sourceQuality': 'See domain citations.',
            'handling': 'DRAFT — NOT FOR DISTRIBUTION',
        },
        'footer': {
            'id': cycle_id,
            'classification': 'PROTECTED B // TLP:AMBER',
            'sources': 'AP · Reuters · CTP-ISW · IAEA · CENTCOM · UKMTO · ICG · CFR · [see domain citations]',
            'handling': 'DRAFT — NOT FOR DISTRIBUTION',
        },
    }
