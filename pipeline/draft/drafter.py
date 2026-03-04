"""
Claude API drafting module.
Drafts each domain section, then the executive summary, using structured JSON output.
"""

import json
import logging
import os
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
]

DOMAIN_PROMPTS = {
    'd1': 'battlespace.md',
    'd2': 'escalation.md',
    'd3': 'energy.md',
    'd4': 'diplomatic.md',
    'd5': 'cyber.md',
}


def _fill_template(template: str, **kwargs: str) -> str:
    """
    Replace {variable} placeholders in a template string.

    Uses manual replacement instead of str.format() to avoid clashing with
    literal curly braces in JSON examples inside the prompt files.
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace('{' + key + '}', value)
    return result


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Prompt file not found: {path}')
    return path.read_text(encoding='utf-8')


def filter_by_domain(items: list[dict], domain: str) -> tuple[list[dict], list[dict]]:
    """Split items into (tier1, tier2) for a given domain."""
    domain_items = [i for i in items if domain in i.get('tagged_domains', [])]
    tier1 = [i for i in domain_items if i.get('tier') == 1]
    tier2 = [i for i in domain_items if i.get('tier') == 2]
    return tier1, tier2


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
        f"Key Judgment: {kj.get('text', '')} [confidence: {kj.get('confidence', '?')}, {kj.get('probabilityRange', '')}]",
    ]
    for p in paras[:2]:
        text = p.get('text', '')
        summary_parts.append(f"  [{p.get('subLabel', 'PARA')}]: {text[:300]}")
    return '\n'.join(summary_parts)


def call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int = 2000) -> dict | list:
    """Call Claude API and parse the JSON response."""
    response = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            'You are a senior conflict intelligence analyst. '
            'Write in the dispassionate, precise voice of serious foreign affairs journalism. '
            'Always produce structured JSON output exactly as specified. '
            'Never fabricate citations. Never use forbidden jargon. '
            'Distinguish Tier 1 confirmed facts from Tier 2 analytical interpretation.'
        ),
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = response.content[0].text

    # Strip markdown code fences if present
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        text = text.split('```')[1].split('```')[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.error('JSON parse failed: %s\nRaw response (first 600 chars): %s', exc, text[:600])
        raise


def draft_domain(
    client: anthropic.Anthropic,
    domain: str,
    items: list[dict],
    target_date: datetime,
    prev_cycle: dict | None = None,
    context_sections: dict | None = None,  # {domain_id: drafted_section_dict}
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

    prompt = _fill_template(
        template,
        tier1_items=json.dumps(tier1[:15], indent=2, ensure_ascii=False),
        tier2_items=json.dumps(tier2[:15], indent=2, ensure_ascii=False),
        prev_cycle_kj=prev_kj or '(no previous cycle)',
        d1_context=d1_context,
        d2_context=d2_context,
    )

    log.info('Drafting domain %s (%d T1, %d T2 items)...', domain, len(tier1), len(tier2))
    result = call_claude(client, prompt, max_tokens=3000)
    return result if isinstance(result, dict) else {}


def draft_executive(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
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
        prev_cycle_bluf=prev_bluf or '(no previous cycle)',
    )

    log.info('Drafting executive summary...')
    result = call_claude(client, prompt, max_tokens=2000)
    return result if isinstance(result, dict) else {}


def draft_strategic_header(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    executive: dict,
    prev_cycle: dict | None = None,
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
    result = call_claude(client, prompt, max_tokens=500)
    return result if isinstance(result, dict) else {}


def draft_warning_indicators(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
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
    result = call_claude(client, prompt, max_tokens=1200)
    if isinstance(result, list):
        return result
    return result.get('warningIndicators', [])


def draft_collection_gaps(
    client: anthropic.Anthropic,
    tagged_items: list[dict],
    domain_sections: list[dict],
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
    result = call_claude(client, prompt, max_tokens=900)
    if isinstance(result, list):
        return result
    return result.get('collectionGaps', [])


def draft_cycle(
    tagged_items: list[dict],
    target_date: datetime,
    prev_cycle: dict | None = None,
    config: dict | None = None,
) -> dict:
    """
    Orchestrate full cycle draft.
    Domain order: d1 → d2 (gets d1 context) → d3 (gets d1 context) →
                  d4 (gets d2 context) → d5 → executive → strategic header →
                  warning indicators → collection gaps.
    """
    config = config or {}
    claude_cfg = config.get('claude', {})

    api_key = claude_cfg.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError(
            'ANTHROPIC_API_KEY not set. Export the variable or add it to pipeline-config.yaml.'
        )

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
        )
        # Ensure schema fields are present
        section.setdefault('id', domain_id)
        section.setdefault('num', domain_num)
        section.setdefault('title', domain_title)
        domain_sections.append(section)
        drafted[domain_id] = section
        log.info('Domain %s drafted', domain_id)

    executive = draft_executive(client, domain_sections, prev_cycle)
    strategic_header = draft_strategic_header(client, domain_sections, executive, prev_cycle)
    warning_indicators = draft_warning_indicators(client, domain_sections, prev_cycle)
    collection_gaps = draft_collection_gaps(client, tagged_items, domain_sections)

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
                {'top': threat_level, 'bot': 'THREAT LEVEL'},
                {'top': '—', 'bot': 'INCIDENTS / 24H'},
                {'top': '—', 'bot': 'BRENT CRUDE'},
                {'top': 'ACTIVE', 'bot': 'HORMUZ STATUS'},
                {'top': '—', 'bot': 'FLASH POINTS'},
            ],
        },
        'strategicHeader': strategic_header,
        'flashPoints': [],
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
