"""
Post-draft content quality validator.

Catches writing-clarity violations that the schema validator cannot:
forbidden jargon, paragraph minimums, word-limit breaches,
ad-hoc hedging, description-first leads, and invalid confidence values.

Each check returns a list of Warning namedtuples so the review CLI
(and logs) can surface them to the analyst before approval.
"""

import logging
import re
from typing import NamedTuple

log = logging.getLogger(__name__)

# ── Violation record ────────────────────────────────────────────────────────

class QualityWarning(NamedTuple):
    domain: str        # e.g. "d1", "executive", "strategicHeader"
    field: str         # e.g. "bodyParagraphs[0].text", "keyJudgment.text"
    rule: str          # short rule ID
    message: str       # human-readable description


# ── Global forbidden phrases (from CLAUDE.md + domain prompts) ──────────────

FORBIDDEN_PHRASES: list[str] = [
    'kinetic activity',
    'threat actors',
    'threat landscape',
    'robust',
    'leverage',              # verb usage
    'diplomatic efforts',
    'international community',
    'stakeholders',
    'going forward',
    'ongoing situation',
    'fluid situation',
    'escalatory dynamics',
    'economic headwinds',
    'market volatility',
    'risk environment',
    'uncertain times',
    'volatile market',
    'market participants',
    'cyber domain',
    'advanced persistent threat',
    'remains to be seen',
    'ongoing conflict',
]

# Ad-hoc hedging patterns that bypass the confidence language ladder
ADHOC_HEDGE_PATTERNS: list[str] = [
    r'\bit is possible that it might\b',
    r'\bpossibly triggered\b',
    r'\bappears to be\b',
    r'\bmay have\b',
    r'\bimpossible to determine\b',
    r'\bwe cannot know\b',
    r'\bit remains unclear\b',
    r'\btime will tell\b',
    r'\bonly time\b',
    r'\bcould potentially\b',
    r'\bmight potentially\b',
    r'\bsomewhat likely\b',
    r'\bfairly likely\b',
    r'\bquite possible\b',
    r'\bmore or less\b',
    r'\breasonably certain\b',
    r'\brelatively confident\b',
]

# Description-first lead patterns (BAD leads that describe rather than assess)
DESCRIPTION_LEAD_PATTERNS: list[re.Pattern] = [
    re.compile(r'^(Israeli|Iranian|US|American|Russian|Houthi|Hezbollah)\s+(forces?|aircraft|military|troops|navy)\s+(struck|attacked|launched|fired|conducted|carried out)', re.IGNORECASE),
    re.compile(r'^The conflict (entered|continued|reached|saw)', re.IGNORECASE),
    re.compile(r'^(On|During|In|Over)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d)', re.IGNORECASE),
    re.compile(r'^(Three|Four|Five|Six|Seven|Eight|Nine|Ten|\d+)\s+(BTGs?|brigades?|battalions?|strikes?|missiles?|rockets?|drones?)\s+(were|have been)\s+(observed|reported|spotted|noted)', re.IGNORECASE),
    re.compile(r'^(A|An)\s+(series|wave|barrage|number)\s+of\s+(strikes?|attacks?|incidents?)', re.IGNORECASE),
]

# Valid confidence language enum values
VALID_CONFIDENCE_LANGUAGE: set[str] = {
    'almost-certainly',
    'highly-likely',
    'likely',
    'possibly',
    'unlikely',
    'almost-certainly-not',
}

VALID_CONFIDENCE_TIERS: set[str] = {'high', 'moderate', 'low'}

VALID_VERIFICATION_STATUS: set[str] = {'confirmed', 'reported', 'claimed', 'disputed'}

# Word limits per domain (bodyParagraphs combined)
DOMAIN_WORD_LIMITS: dict[str, int] = {
    'd1': 200,
    'd2': 200,
    'd3': 180,
    'd4': 180,
    'd5': 120,
    'd6': 220,
}

KJ_WORD_LIMITS: dict[str, int] = {
    'd1': 30,
    'd2': 35,
    'd3': 30,
    'd4': 35,
    'd5': 25,
    'd6': 35,
}


# ── Individual check functions ──────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(text.split())


def _sentence_count(text: str) -> int:
    """Count sentences using period/question/exclamation boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return len([s for s in sentences if s.strip()])


def check_forbidden_jargon(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag any forbidden phrase found in text."""
    warnings = []
    text_lower = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text_lower:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='FORBIDDEN_JARGON',
                message=f'Contains forbidden phrase: "{phrase}"',
            ))
    return warnings


def check_adhoc_hedging(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag ad-hoc hedging that bypasses the confidence language ladder."""
    warnings = []
    text_lower = text.lower()
    for pattern in ADHOC_HEDGE_PATTERNS:
        if re.search(pattern, text_lower):
            match = re.search(pattern, text_lower)
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='ADHOC_HEDGING',
                message=f'Ad-hoc hedging detected: "{match.group() if match else pattern}". Use confidence language ladder instead.',
            ))
    return warnings


def check_description_lead(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag key judgments or leads that describe rather than assess."""
    warnings = []
    for pattern in DESCRIPTION_LEAD_PATTERNS:
        if pattern.search(text):
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='DESCRIPTION_LEAD',
                message='Lead sentence describes events rather than stating an assessment. Leads must begin with analytical judgment.',
            ))
            break
    return warnings


def check_paragraph_minimum(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Ensure every paragraph has at least 2 sentences."""
    warnings = []
    if _sentence_count(text) < 2:
        warnings.append(QualityWarning(
            domain=domain,
            field=field,
            rule='PARAGRAPH_MINIMUM',
            message=f'Paragraph has {_sentence_count(text)} sentence(s); minimum is 2.',
        ))
    return warnings


def check_confidence_values(section: dict, domain: str) -> list[QualityWarning]:
    """Validate confidence enum values throughout a section."""
    warnings = []

    # Section-level confidence
    conf = section.get('confidence')
    if conf and conf not in VALID_CONFIDENCE_TIERS:
        warnings.append(QualityWarning(
            domain=domain,
            field='confidence',
            rule='INVALID_CONFIDENCE_TIER',
            message=f'Invalid confidence tier: "{conf}". Must be: {VALID_CONFIDENCE_TIERS}',
        ))

    # Key judgment confidence language
    kj = section.get('keyJudgment', {})
    lang = kj.get('language')
    if lang and lang not in VALID_CONFIDENCE_LANGUAGE:
        warnings.append(QualityWarning(
            domain=domain,
            field='keyJudgment.language',
            rule='INVALID_CONFIDENCE_LANGUAGE',
            message=f'Invalid confidence language: "{lang}". Must be one of: {VALID_CONFIDENCE_LANGUAGE}',
        ))

    kj_conf = kj.get('confidence')
    if kj_conf and kj_conf not in VALID_CONFIDENCE_TIERS:
        warnings.append(QualityWarning(
            domain=domain,
            field='keyJudgment.confidence',
            rule='INVALID_CONFIDENCE_TIER',
            message=f'Invalid confidence tier in key judgment: "{kj_conf}".',
        ))

    # Body paragraph confidence language
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        cl = para.get('confidenceLanguage')
        if cl and cl not in VALID_CONFIDENCE_LANGUAGE:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}].confidenceLanguage',
                rule='INVALID_CONFIDENCE_LANGUAGE',
                message=f'Invalid confidence language: "{cl}".',
            ))

    return warnings


def check_citation_integrity(section: dict, domain: str) -> list[QualityWarning]:
    """Validate citation fields: verification status, tier values."""
    warnings = []

    def _check_citations(citations: list[dict], field_prefix: str) -> None:
        for cidx, cit in enumerate(citations):
            vs = cit.get('verificationStatus')
            if vs and vs not in VALID_VERIFICATION_STATUS:
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'{field_prefix}.citations[{cidx}].verificationStatus',
                    rule='INVALID_VERIFICATION_STATUS',
                    message=f'Invalid verification status: "{vs}". Must be: {VALID_VERIFICATION_STATUS}',
                ))
            tier = cit.get('tier')
            if tier is not None and tier not in (1, 2, 3):
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'{field_prefix}.citations[{cidx}].tier',
                    rule='INVALID_SOURCE_TIER',
                    message=f'Invalid source tier: {tier}. Must be 1, 2, or 3.',
                ))

    # Key judgment citations
    kj = section.get('keyJudgment', {})
    _check_citations(kj.get('citations', []), 'keyJudgment')

    # Body paragraph citations
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        _check_citations(para.get('citations', []), f'bodyParagraphs[{idx}]')

    return warnings


def check_word_limits(section: dict, domain: str) -> list[QualityWarning]:
    """Check word limits for body paragraphs and key judgment."""
    warnings = []

    # Body paragraphs combined word count
    body_limit = DOMAIN_WORD_LIMITS.get(domain)
    if body_limit:
        total_words = sum(
            _word_count(p.get('text', ''))
            for p in section.get('bodyParagraphs', [])
        )
        if total_words > body_limit:
            warnings.append(QualityWarning(
                domain=domain,
                field='bodyParagraphs',
                rule='WORD_LIMIT_BODY',
                message=f'Body paragraphs total {total_words} words; limit is {body_limit}.',
            ))

    # Key judgment word count
    kj_limit = KJ_WORD_LIMITS.get(domain)
    kj_text = section.get('keyJudgment', {}).get('text', '')
    if kj_limit and kj_text:
        kj_words = _word_count(kj_text)
        if kj_words > kj_limit:
            warnings.append(QualityWarning(
                domain=domain,
                field='keyJudgment.text',
                rule='WORD_LIMIT_KJ',
                message=f'Key judgment is {kj_words} words; limit is {kj_limit}.',
            ))

    return warnings


def check_temporal_precision(section: dict, domain: str) -> list[QualityWarning]:
    """Flag kinetic/factual claims in d1/d3 OBSERVED paragraphs missing timestamps."""
    warnings = []
    if domain not in ('d1', 'd3'):
        return warnings

    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        variant = para.get('subLabelVariant', '')
        if variant != 'observed':
            continue
        text = para.get('text', '')
        # Check for UTC timestamp pattern
        has_timestamp = bool(re.search(r'\d{4}\s*UTC', text))
        if not has_timestamp and _word_count(text) > 10:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}].text',
                rule='MISSING_TEMPORAL_PRECISION',
                message='OBSERVED paragraph lacks UTC timestamp. Kinetic/factual claims require: "As of HHMM UTC DD Mon".',
            ))

    return warnings


def check_source_attribution(section: dict, domain: str) -> list[QualityWarning]:
    """Flag body paragraphs with factual claims but no citations."""
    warnings = []
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        text = para.get('text', '')
        citations = para.get('citations', [])
        variant = para.get('subLabelVariant', '')

        # Observed paragraphs must have citations
        if variant == 'observed' and not citations and _word_count(text) > 10:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}]',
                rule='MISSING_CITATIONS',
                message='OBSERVED paragraph contains factual claims without source citations.',
            ))

    return warnings


# ── Main validation entry point ─────────────────────────────────────────────

def validate_domain_section(section: dict) -> list[QualityWarning]:
    """Run all quality checks against a single domain section."""
    domain = section.get('id', '?')
    warnings: list[QualityWarning] = []

    # Key judgment checks
    kj = section.get('keyJudgment', {})
    kj_text = kj.get('text', '')
    if kj_text:
        warnings.extend(check_forbidden_jargon(kj_text, domain, 'keyJudgment.text'))
        warnings.extend(check_adhoc_hedging(kj_text, domain, 'keyJudgment.text'))
        warnings.extend(check_description_lead(kj_text, domain, 'keyJudgment.text'))

    # Body paragraph checks
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        text = para.get('text', '')
        field = f'bodyParagraphs[{idx}].text'
        warnings.extend(check_forbidden_jargon(text, domain, field))
        warnings.extend(check_adhoc_hedging(text, domain, field))
        warnings.extend(check_paragraph_minimum(text, domain, field))

    # Structural / enum checks
    warnings.extend(check_confidence_values(section, domain))
    warnings.extend(check_citation_integrity(section, domain))
    warnings.extend(check_word_limits(section, domain))
    warnings.extend(check_temporal_precision(section, domain))
    warnings.extend(check_source_attribution(section, domain))

    return warnings


def validate_executive(executive: dict) -> list[QualityWarning]:
    """Run quality checks on the executive summary."""
    domain = 'executive'
    warnings: list[QualityWarning] = []

    bluf = executive.get('bluf', '')
    if bluf:
        warnings.extend(check_forbidden_jargon(bluf, domain, 'bluf'))
        warnings.extend(check_adhoc_hedging(bluf, domain, 'bluf'))
        warnings.extend(check_description_lead(bluf, domain, 'bluf'))
        if _sentence_count(bluf) < 2:
            warnings.append(QualityWarning(
                domain=domain,
                field='bluf',
                rule='BLUF_TOO_SHORT',
                message=f'BLUF has {_sentence_count(bluf)} sentence(s); minimum is 2.',
            ))
        if _sentence_count(bluf) > 4:
            warnings.append(QualityWarning(
                domain=domain,
                field='bluf',
                rule='BLUF_TOO_LONG',
                message=f'BLUF has {_sentence_count(bluf)} sentences; maximum is 4.',
            ))

    for idx, kj in enumerate(executive.get('keyJudgments', [])):
        text = kj.get('text', '')
        field = f'keyJudgments[{idx}].text'
        warnings.extend(check_forbidden_jargon(text, domain, field))
        warnings.extend(check_adhoc_hedging(text, domain, field))

        lang = kj.get('language')
        if lang and lang not in VALID_CONFIDENCE_LANGUAGE:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'keyJudgments[{idx}].language',
                rule='INVALID_CONFIDENCE_LANGUAGE',
                message=f'Invalid confidence language: "{lang}".',
            ))

    return warnings


def validate_strategic_header(header: dict) -> list[QualityWarning]:
    """Run quality checks on the strategic header."""
    domain = 'strategicHeader'
    warnings: list[QualityWarning] = []

    headline = header.get('headlineJudgment', '')
    if headline:
        warnings.extend(check_forbidden_jargon(headline, domain, 'headlineJudgment'))
        warnings.extend(check_adhoc_hedging(headline, domain, 'headlineJudgment'))
        warnings.extend(check_description_lead(headline, domain, 'headlineJudgment'))

    rationale = header.get('trajectoryRationale', '')
    if rationale:
        warnings.extend(check_forbidden_jargon(rationale, domain, 'trajectoryRationale'))
        warnings.extend(check_adhoc_hedging(rationale, domain, 'trajectoryRationale'))

    return warnings


def validate_cycle(cycle: dict) -> list[QualityWarning]:
    """
    Run full quality validation on an assembled cycle dict.
    Returns a list of QualityWarning — empty means clean.
    """
    warnings: list[QualityWarning] = []

    # Domain sections
    for section in cycle.get('domains', []):
        warnings.extend(validate_domain_section(section))

    # Executive
    warnings.extend(validate_executive(cycle.get('executive', {})))

    # Strategic header
    warnings.extend(validate_strategic_header(cycle.get('strategicHeader', {})))

    # Warning indicators — check for forbidden hedging in detail fields
    for wi in cycle.get('warningIndicators', []):
        detail = wi.get('detail', '')
        wi_id = wi.get('id', '?')
        warnings.extend(check_forbidden_jargon(detail, f'wi:{wi_id}', 'detail'))
        warnings.extend(check_adhoc_hedging(detail, f'wi:{wi_id}', 'detail'))

    # Collection gaps — check for forbidden vagueness
    for gap in cycle.get('collectionGaps', []):
        gap_text = gap.get('gap', '') + ' ' + gap.get('significance', '')
        gap_id = gap.get('id', '?')
        warnings.extend(check_forbidden_jargon(gap_text, f'gap:{gap_id}', 'gap/significance'))

    # Log summary
    if warnings:
        log.warning('Quality check found %d issue(s):', len(warnings))
        for w in warnings:
            log.warning('  [%s] %s → %s: %s', w.rule, w.domain, w.field, w.message)
    else:
        log.info('Quality check: all clear — no issues found')

    return warnings
