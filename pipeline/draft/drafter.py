"""
Claude API drafting module.
Drafts each domain section, then the executive summary, using structured JSON output.
Runs post-draft quality checks to catch forbidden jargon, ad-hoc hedging,
description-first leads, and other writing-clarity violations before review.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic

from draft.quality_checks import (
    validate_domain_section,
    validate_executive,
    validate_strategic_header,
    validate_cycle,
)

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
    """Split items into (tier1, tier2_and_tier3) for a given domain."""
    domain_items = [i for i in items if domain in i.get('tagged_domains', [])]
    tier1 = [i for i in domain_items if i.get('tier') == 1]
    tier2 = [i for i in domain_items if i.get('tier') in (2, 3)]
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


SYSTEM_PROMPT = (
    'You are a senior conflict intelligence analyst writing for the CSE daily brief. '
    'Write in the dispassionate, precise voice of the Economist\'s intelligence unit — '
    'authoritative, economical, and never theatrical. '
    'Always produce structured JSON output exactly as specified.\n\n'

    'WRITING CLARITY RULES — your output passes through an automated quality gate. '
    'Violations are flagged and the section is returned for redraft.\n\n'

    '1. ASSESSMENT-FIRST LEADS (the most important rule):\n'
    '   Every key judgment, BLUF, and lead sentence must begin with an analytical judgment, '
    'not a factual description. The analyst\'s job is to tell the reader what facts MEAN.\n'
    '   BAD: "Israeli aircraft struck targets." (description)\n'
    '   BAD: "Tensions rose after events." (cliché)\n'
    '   BAD: "There were six strikes." (existential construction)\n'
    '   BAD: "Brent crude rose to $94." (price ticker)\n'
    '   GOOD: "We assess the IDF has shifted to a sustained attrition posture."\n'
    '   GOOD: "Available evidence suggests conflict-driven supply risk is the primary driver of the $2.40/bbl Brent rise."\n\n'

    '2. CONFIDENCE LANGUAGE — use ONLY these six phrases (never ad-hoc hedging):\n'
    '   • "We assess with high confidence..." (95–99%)\n'
    '   • "We judge it highly likely..." (75–95%)\n'
    '   • "Available evidence suggests..." (55–75%)\n'
    '   • "Reporting indicates, though corroboration is limited..." (45–55%)\n'
    '   • "We judge it unlikely, though we cannot exclude..." (20–45%)\n'
    '   • "We assess with high confidence this will not..." (1–5%)\n'
    '   BANNED hedging: "appears to be", "may have", "could potentially", "remains to be seen", '
    '"perhaps", "seemingly", "ostensibly", "purportedly", "to some extent", "one could argue", '
    '"it stands to reason", "in all likelihood", "time will tell"\n\n'

    '3. SENTENCE CONSTRUCTION:\n'
    '   • Every paragraph ≥ 2 sentences. No fragment leads. No one-line paragraphs.\n'
    '   • Active voice always: "We assess", "France abstained" — never "It is assessed", "Abstention was made"\n'
    '   • Never nominalize verbs: "struck" not "the conduct of strikes"; "deployed" not "the deployment of"\n'
    '   • Be verb-precise: "struck", "repositioned", "interdicted", "sortied", "hardened" (market), '
    '"abstained" (vote), "suspended" (access) — never "conducted operations", "carried out activities", '
    '"engaged in", "undertook measures", "took action"\n'
    '   • Cut every word that adds no information. If removing a word changes nothing, remove it.\n\n'

    '4. PRECISION:\n'
    '   • Temporal: "As of 0600 UTC 15 Mar" — never "recently", "in recent days", "overnight"\n'
    '   • Geographic: "the Bekaa Valley", "Strait of Hormuz" — never "the region", "the area", "the Middle East"\n'
    '   • Quantify: "six strikes", "$94.20/bbl", "+18%" — never "several", "many", "a number of", '
    '"a significant amount"\n'
    '   • Name actors: "APT33/Elfin" not "Iranian hackers"; "Secretary Blinken" not "senior U.S. officials" '
    '(when identity is confirmed); "Hiscox" not "a major insurer"\n\n'

    '5. FORBIDDEN PHRASES (automatic rejection — quality gate blocks output):\n'
    '   "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb), '
    '"diplomatic efforts", "international community", "stakeholders", "going forward", '
    '"ongoing situation", "fluid situation", "escalatory dynamics", "economic headwinds", '
    '"market volatility", "risk environment", "uncertain times", "volatile market", '
    '"market participants", "cyber domain", "advanced persistent threat", "remains to be seen", '
    '"ongoing conflict", "significant development", "notable development", "rapidly evolving", '
    '"dynamic situation", "heightened tensions", "broader conflict", "amid tensions", '
    '"amid escalating", "it should be noted", "it is worth noting", "it bears noting", '
    '"importantly", "significantly", "notably", "interestingly", "needless to say", '
    '"at this juncture", "at this time", "in the current climate", "complex situation", '
    '"multi-faceted", "nuanced situation", "holistic approach", "paradigm shift", "game changer", '
    '"key development", "fast-moving", "a major insurer", "a leading broker", "market sources"\n\n'

    '6. SOURCE DISCIPLINE:\n'
    '   • Cite every factual claim: "(AP, 15 Mar 0620 UTC)"\n'
    '   • Tier 1 (AP/Reuters/AFP/CENTCOM/IAEA/UKMTO) = "confirmed"\n'
    '   • Tier 2 (CFR/broker/NGO) = "reported"\n'
    '   • Tier 3 (hacktivist/unverified) = "claimed"\n'
    '   • Iranian state media (PressTV/IRNA/Fars/Tasnim) = ALWAYS "claimed", '
    'ALWAYS prefix with "Iranian government asserts..."\n'
    '   • Never fabricate citations, sources, or data points.\n\n'

    '7. STRUCTURAL:\n'
    '   • Distinguish OBSERVED (Tier 1 facts) from ASSESSMENT (analytical judgment) with sub-labels\n'
    '   • Key judgment basis field must explain WHAT EVIDENCE supports the judgment\n'
    '   • Do not repeat key judgment text verbatim in body paragraphs\n'
    '   • Energy/insurance sections (D3/D6) must include numeric data in every non-Canadian paragraph'
)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from Claude response."""
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        text = text.split('```')[1].split('```')[0].strip()
    return text


def call_claude(
    client: anthropic.Anthropic,
    prompt: str,
    max_tokens: int = 2000,
    config: dict | None = None,
) -> dict | list:
    """Call Claude API and parse the JSON response."""
    cfg = config or {}
    model = cfg.get('claude', {}).get('model', 'claude-opus-4-6')
    temperature = cfg.get('claude', {}).get('temperature', 0.3)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = _strip_code_fences(response.content[0].text)

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
    config: dict | None = None,
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

    # d3 context for d6 (war risk prompt uses {d2_context} slot for energy context)
    d3_context = _domain_summary(context_sections['d3']) if 'd3' in context_sections else '(not yet available)'

    prompt = _fill_template(
        template,
        tier1_items=json.dumps(tier1[:15], indent=2, ensure_ascii=False),
        tier2_items=json.dumps(tier2[:15], indent=2, ensure_ascii=False),
        prev_cycle_kj=prev_kj or '(no previous cycle)',
        d1_context=d1_context,
        d2_context=d3_context if domain == 'd6' else d2_context,
    )

    max_tok = config.get('claude', {}).get('max_tokens_per_domain', 1500) if config else 1500
    log.info('Drafting domain %s (%d T1, %d T2 items)...', domain, len(tier1), len(tier2))
    result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    section = result if isinstance(result, dict) else {}

    # Post-draft quality check — log warnings for human review
    section.setdefault('id', domain)
    qw = validate_domain_section(section)
    if qw:
        log.warning('Domain %s draft has %d quality issue(s):', domain, len(qw))
        for w in qw:
            log.warning('  [%s] %s → %s', w.rule, w.field, w.message)

    return section


def draft_executive(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
    config: dict | None = None,
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

    max_tok = config.get('claude', {}).get('max_tokens_executive', 1200) if config else 1200
    log.info('Drafting executive summary...')
    result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    executive = result if isinstance(result, dict) else {}

    qw = validate_executive(executive)
    if qw:
        log.warning('Executive draft has %d quality issue(s):', len(qw))
        for w in qw:
            log.warning('  [%s] %s → %s', w.rule, w.field, w.message)

    return executive


def draft_strategic_header(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    executive: dict,
    prev_cycle: dict | None = None,
    config: dict | None = None,
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

    max_tok = config.get('claude', {}).get('max_tokens_strategic', 400) if config else 400
    log.info('Drafting strategic header...')
    result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    header = result if isinstance(result, dict) else {}

    qw = validate_strategic_header(header)
    if qw:
        log.warning('Strategic header draft has %d quality issue(s):', len(qw))
        for w in qw:
            log.warning('  [%s] %s → %s', w.rule, w.field, w.message)

    return header


def draft_warning_indicators(
    client: anthropic.Anthropic,
    domain_sections: list[dict],
    prev_cycle: dict | None = None,
    config: dict | None = None,
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

    max_tok = config.get('claude', {}).get('max_tokens_indicators', 800) if config else 800
    log.info('Drafting warning indicators...')
    result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    if isinstance(result, list):
        return result
    return result.get('warningIndicators', [])


def draft_collection_gaps(
    client: anthropic.Anthropic,
    tagged_items: list[dict],
    domain_sections: list[dict],
    config: dict | None = None,
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

    max_tok = config.get('claude', {}).get('max_tokens_gaps', 600) if config else 600
    log.info('Drafting collection gaps...')
    result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    if isinstance(result, list):
        return result
    return result.get('collectionGaps', [])


def draft_flash_points(
    client: anthropic.Anthropic,
    tagged_items: list[dict],
    domain_sections: list[dict],
    target_date: datetime,
    config: dict | None = None,
) -> list[dict]:
    """
    Draft flash points by selecting the 1–3 most operationally significant
    breaking developments from the current cycle's items.

    Candidates are pre-filtered: Tier 1 confirmed items or high-significance
    items across all domains. If no items meet the threshold, returns [].
    """
    # Build candidates: Tier 1 confirmed items + items with high significance scores
    candidates = []
    for item in tagged_items:
        is_tier1 = item.get('tier') == 1
        is_confirmed = item.get('verification_status') == 'confirmed'
        has_high_sig = item.get('significance_score', 0) >= 70
        if (is_tier1 and is_confirmed) or has_high_sig:
            candidates.append({
                'source_name': item.get('source_name', ''),
                'tier':        item.get('tier', 2),
                'domain':      (item.get('tagged_domains') or item.get('domains', ['d1']))[0],
                'title':       item.get('title', ''),
                'text':        (item.get('text', '') or '')[:400],
                'timestamp':   item.get('timestamp', ''),
                'verification_status': item.get('verification_status', 'reported'),
            })

    if not candidates:
        log.info('FlashPoints: no candidates met the threshold — returning empty')
        return []

    # Build domain context summary for the prompt
    section_map = {s.get('id'): s for s in domain_sections}
    domain_context = '\n\n'.join(
        f"[{did}] {_domain_summary(section_map[did])}"
        for did in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']
        if did in section_map
    )

    template = load_prompt('flash_points.md')
    prompt = _fill_template(
        template,
        candidate_items=json.dumps(candidates[:20], indent=2, ensure_ascii=False),
        domain_context=domain_context,
    )

    max_tok = config.get('claude', {}).get('max_tokens_flash_points', 800) if config else 800
    log.info('Drafting flash points from %d candidates...', len(candidates))

    try:
        result = call_claude(client, prompt, max_tokens=max_tok, config=config)
    except Exception as exc:
        log.warning('FlashPoints drafting failed (%s) — returning empty', exc)
        return []

    if isinstance(result, list):
        log.info('FlashPoints: %d flash points drafted', len(result))
        return result
    # If Claude returned an object with a flashPoints key, extract it
    if isinstance(result, dict) and 'flashPoints' in result:
        return result['flashPoints']
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
            config=config,
        )
        # Ensure schema fields are present
        section.setdefault('id', domain_id)
        section.setdefault('num', domain_num)
        section.setdefault('title', domain_title)
        domain_sections.append(section)
        drafted[domain_id] = section
        log.info('Domain %s drafted', domain_id)

    # Draft flash points between domains and executive so the executive
    # summary can reference any urgent breaking developments.
    flash_points = draft_flash_points(
        client, tagged_items, domain_sections, target_date, config=config,
    )

    executive = draft_executive(client, domain_sections, prev_cycle, config=config)
    strategic_header = draft_strategic_header(client, domain_sections, executive, prev_cycle, config=config)
    warning_indicators = draft_warning_indicators(client, domain_sections, prev_cycle, config=config)
    collection_gaps = draft_collection_gaps(client, tagged_items, domain_sections, config=config)

    # Merge strategicHeader fields into meta for convenience
    threat_level = strategic_header.pop('threatLevel', 'SEVERE')
    threat_trajectory = strategic_header.pop('threatTrajectory', 'escalating')

    cycle_id = f'CSE-BRIEF-DRAFT-{target_date.strftime("%Y%m%d")}'

    cycle = {
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
                {'top': str(len(flash_points)) if flash_points else '—', 'bot': 'FLASH POINTS'},
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

    # ── Full-cycle quality gate ─────────────────────────────────────────────
    all_warnings = validate_cycle(cycle)
    if all_warnings:
        log.warning(
            '╔══ QUALITY GATE: %d issue(s) found across cycle draft ══╗',
            len(all_warnings),
        )
        for w in all_warnings:
            log.warning('  [%s] %s.%s → %s', w.rule, w.domain, w.field, w.message)
        log.warning(
            '╚══ Issues will be surfaced in review CLI for analyst decision ══╝'
        )
        cycle['_qualityWarnings'] = [
            {'domain': w.domain, 'field': w.field, 'rule': w.rule, 'message': w.message}
            for w in all_warnings
        ]
    else:
        log.info('Quality gate: all clear — cycle draft passed all checks')

    return cycle
