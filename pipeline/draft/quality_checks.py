"""
Post-draft content quality validator.

Catches writing-clarity violations that the schema validator cannot:
forbidden jargon, paragraph minimums, word-limit breaches, ad-hoc hedging,
description-first leads, invalid confidence values, passive voice excess,
nominalizations, weasel words, redundant modifiers, source-tier mismatches,
quantification gaps, structural count violations, Iranian state media misuse,
repetition between KJ and body, and vague geographic references.

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


# ═══════════════════════════════════════════════════════════════════════════
#  REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════════

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
    'broader region',
    'wider region',
    'broader conflict',
    'heightened tensions',
    'amid tensions',
    'amid escalating',
    'significant development',
    'notable development',
    'key development',
    'rapidly evolving',
    'fast-moving',
    'fast moving',
    'dynamic situation',
    'complex situation',
    'multi-faceted',
    'nuanced situation',
    'holistic approach',
    'paradigm shift',
    'game changer',
    'game-changer',
    'at this juncture',
    'at this time',
    'at the present time',
    'in the current climate',
    'in this context',
    'it should be noted',
    'it is worth noting',
    'it bears noting',
    'needless to say',
    'as previously mentioned',
    'interestingly',
    'importantly',
    'significantly',
    'notably',
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
    r'\bperhaps\b',
    r'\bseemingly\b',
    r'\bseems to\b',
    r'\bappears that\b',
    r'\bapparently\b',
    r'\bostensibly\b',
    r'\bpurportedly\b',
    r'\bsupposedly\b',
    r'\ballegedly\b(?!.*\bclaim)',   # "allegedly" without attribution context
    r'\bcould conceivably\b',
    r'\bmay or may not\b',
    r'\bto some extent\b',
    r'\bto a certain degree\b',
    r'\bin all likelihood\b',
    r'\bfor all intents and purposes\b',
    r'\bone could argue\b',
    r'\bit could be argued\b',
    r'\bit stands to reason\b',
]

# Description-first lead patterns (BAD leads that describe rather than assess)
DESCRIPTION_LEAD_PATTERNS: list[re.Pattern] = [
    re.compile(r'^(Israeli|Iranian|US|American|Russian|Houthi|Hezbollah|Saudi|Turkish|Egyptian|Qatari|Chinese|British|French)\s+(forces?|aircraft|military|troops|navy|officials?|government|authorities|missiles?)\s+(struck|attacked|launched|fired|conducted|carried out|deployed|announced|stated|said|declared)', re.IGNORECASE),
    re.compile(r'^The conflict (entered|continued|reached|saw|has entered|has continued)', re.IGNORECASE),
    re.compile(r'^(On|During|In|Over|Throughout)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d)', re.IGNORECASE),
    re.compile(r'^(Three|Four|Five|Six|Seven|Eight|Nine|Ten|\d+)\s+(BTGs?|brigades?|battalions?|strikes?|missiles?|rockets?|drones?|sorties?|incidents?|ships?|vessels?|tankers?)\s+(were|have been|are)\s+(observed|reported|spotted|noted|recorded|detected|tracked)', re.IGNORECASE),
    re.compile(r'^(A|An|The)\s+(series|wave|barrage|number|spate|flurry|string)\s+of\s+(strikes?|attacks?|incidents?|launches?|operations?)', re.IGNORECASE),
    re.compile(r'^(There were|There have been|There are)\s+', re.IGNORECASE),
    re.compile(r'^(Yesterday|Today|This morning|Last night|Overnight),?\s+', re.IGNORECASE),
    re.compile(r'^Reports (indicate|suggest|emerge|surfaced)\s+', re.IGNORECASE),
    re.compile(r'^(Sources|Officials|Analysts)\s+(say|report|indicate|suggest|confirm|state)\s+', re.IGNORECASE),
    re.compile(r'^(Tensions|Violence|Fighting|Hostilities|Clashes)\s+(rose|increased|intensified|continued|erupted|escalated|flared|spread)', re.IGNORECASE),
    re.compile(r'^(Brent|WTI|Oil|Crude|Gas|Gold|Markets?)\s+(rose|fell|dropped|surged|plunged|traded|closed|opened)', re.IGNORECASE),
    re.compile(r'^(The|A)\s+(United Nations|UN|Security Council|IAEA|NATO)\s+(met|convened|held|issued|released|called)', re.IGNORECASE),
    re.compile(r'^(War risk|Insurance|Premium|Shipping)\s+(rates?|costs?|prices?|premiums?)\s+(rose|fell|increased|decreased|surged)', re.IGNORECASE),
]

# Passive voice indicators (assessment paragraphs should minimize these)
PASSIVE_VOICE_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b(is|are|was|were|been|being)\s+(being\s+)?(observed|assessed|believed|considered|deemed|determined|estimated|expected|found|indicated|judged|known|noted|perceived|regarded|reported|seen|shown|thought|understood|viewed)\b', re.IGNORECASE),
    re.compile(r'\b(is|are|was|were|been|being)\s+(being\s+)?(carried out|conducted|executed|launched|initiated|undertaken|implemented|deployed|performed|accomplished)\b', re.IGNORECASE),
    re.compile(r'\b(is|are|was|were|been|being)\s+(being\s+)?(struck|hit|targeted|destroyed|damaged|impacted|affected|disrupted|intercepted)\b', re.IGNORECASE),
    re.compile(r'\b(can|could|may|might|should|would|will)\s+be\s+(observed|assessed|seen|noted|expected|considered|determined|regarded|viewed)\b', re.IGNORECASE),
]

# Nominalizations — noun forms that should be verbs for clarity
NOMINALIZATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bthe (conduct|execution|implementation|utilization|deployment|initiation) of\b', re.IGNORECASE), 'Use verb form instead: "conducted", "executed", "deployed", etc.'),
    (re.compile(r'\b(escalation|de-escalation|stabilization|normalization|deterioration) (of|in) the situation\b', re.IGNORECASE), 'Rewrite with active verb: "the situation escalated" / "conditions deteriorated"'),
    (re.compile(r'\bmade (a|an|the) (decision|assessment|determination|evaluation|judgment)\b', re.IGNORECASE), 'Use direct verb: "decided", "assessed", "determined", "evaluated", "judged"'),
    (re.compile(r'\bprovided (assistance|support|guidance|authorization)\b', re.IGNORECASE), 'Use direct verb: "assisted", "supported", "guided", "authorized"'),
    (re.compile(r'\btook (action|steps|measures)\b', re.IGNORECASE), 'Use direct verb: "acted", "moved to", "imposed"'),
    (re.compile(r'\bgave (approval|authorization|permission|indication)\b', re.IGNORECASE), 'Use direct verb: "approved", "authorized", "permitted", "indicated"'),
    (re.compile(r'\bhad (an|a) (impact|effect|influence) on\b', re.IGNORECASE), 'Use direct verb: "affected", "influenced", "shaped"'),
    (re.compile(r'\bthe (issuance|promulgation|dissemination|publication) of\b', re.IGNORECASE), 'Use verb form: "issued", "published", "disseminated"'),
]

# Weasel words — vague quantifiers that hide precision
WEASEL_WORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(some|several|many|numerous|various|multiple|a number of)\s+(analysts?|sources?|officials?|reports?|countries|states|actors?)\b', re.IGNORECASE), 'Quantify or name: how many? which ones?'),
    (re.compile(r'\b(some|several|certain|various)\s+(areas?|regions?|sectors?|zones?)\b', re.IGNORECASE), 'Name the specific areas or regions'),
    (re.compile(r'\b(significant|substantial|considerable|major|minor|modest)\s+(number|amount|quantity|portion|percentage)\b', re.IGNORECASE), 'Quantify: provide the number, percentage, or range'),
    (re.compile(r'\bin recent (days|weeks|months|times)\b', re.IGNORECASE), 'Specify the time period: "since DD MMM" or "over the past N days"'),
    (re.compile(r'\bwidely (reported|believed|expected|known|regarded)\b', re.IGNORECASE), 'Cite specific sources instead of claiming wide agreement'),
    (re.compile(r'\b(growing|increasing|rising|mounting)\s+(concern|pressure|tensions?|risk|threat|evidence|consensus)\b', re.IGNORECASE), 'Quantify the change: from what level to what level? Over what period?'),
    (re.compile(r'\b(large|small|high|low)\s+number\b', re.IGNORECASE), 'Provide the actual number or a calibrated range'),
]

# Redundant modifiers — tautological or empty intensifiers
REDUNDANT_MODIFIER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bcompletely (destroyed|eliminated|annihilated)\b', re.IGNORECASE), '"destroyed" already means completely — remove "completely"'),
    (re.compile(r'\btotally (destroyed|eliminated|unprecedented)\b', re.IGNORECASE), 'Redundant intensifier — remove "totally"'),
    (re.compile(r'\bvery (unique|unprecedented|critical|essential|crucial)\b', re.IGNORECASE), 'These adjectives are absolute — cannot be modified by "very"'),
    (re.compile(r'\babsolutely (essential|critical|crucial|necessary|certain)\b', re.IGNORECASE), 'Redundant intensifier — the adjective is already absolute'),
    (re.compile(r'\bextremely (important|significant|critical|dangerous|serious)\b', re.IGNORECASE), 'Empty intensifier — be specific about magnitude instead'),
    (re.compile(r'\bhighly (significant|important|likely|probable)\b(?!.*confidence)', re.IGNORECASE), 'Use the confidence ladder for likelihood; otherwise specify what makes it significant'),
    (re.compile(r'\bcurrently (ongoing|underway|active)\b', re.IGNORECASE), '"currently" is redundant with present-tense verbs — remove it'),
    (re.compile(r'\bnew (innovation|development|breakthrough)\b', re.IGNORECASE), '"innovation" already implies new — remove "new"'),
    (re.compile(r'\bpast (history|experience|precedent)\b', re.IGNORECASE), '"history" already refers to the past — remove "past"'),
    (re.compile(r'\bfuture (plans?|prospects?|outlook|forecast)\b', re.IGNORECASE), '"plans" and "outlook" inherently refer to the future — remove "future"'),
    (re.compile(r'\bclose proximity\b', re.IGNORECASE), '"proximity" already means close — use "near" or "adjacent to"'),
    (re.compile(r'\bstill (remains?|continues?)\b', re.IGNORECASE), '"still" is redundant with "remains" or "continues" — remove one'),
]

# Iranian state media source identifiers
IRANIAN_STATE_MEDIA_SOURCES: set[str] = {
    'tehran times', 'press tv', 'presstv', 'irna', 'mehr', 'fars',
    'mehr news', 'fars news', 'tasnim', 'isna', 'iranian state media',
    'irib', 'iran daily', 'kayhan', 'iran front page',
}

# Vague geographic references
VAGUE_GEO_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bin the (area|region|zone|vicinity)\b(?!\s+of\s+\w)', re.IGNORECASE), 'Specify which area/region: "in the Strait of Hormuz", "in northern Gaza"'),
    (re.compile(r'\bnear(by)? (the )?border\b(?!\s+(with|between|crossing))', re.IGNORECASE), 'Specify which border: "near the Lebanon-Israel border"'),
    (re.compile(r'\bin the (Middle East|Gulf|Mediterranean)\b(?!\s+(Sea|of|coast|littoral|basin|rim))', re.IGNORECASE), 'Too broad — narrow to specific country, strait, or maritime zone'),
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


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _word_count(text: str) -> int:
    return len(text.split())


def _sentence_count(text: str) -> int:
    """Count sentences using period/question/exclamation boundaries.
    Avoids false positives on abbreviations like 'U.S.' and decimal numbers."""
    # Collapse known abbreviations
    normalized = text.strip()
    for abbr in ('U.S.', 'U.K.', 'U.N.', 'E.U.', 'i.e.', 'e.g.', 'vs.', 'Dr.', 'Mr.', 'Mrs.', 'Gen.', 'Adm.', 'Col.', 'Lt.', 'Sgt.'):
        normalized = normalized.replace(abbr, abbr.replace('.', '·'))
    sentences = re.split(r'(?<=[.!?])\s+', normalized)
    return len([s for s in sentences if s.strip()])


# ═══════════════════════════════════════════════════════════════════════════
#  INDIVIDUAL CHECK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

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
        match = re.search(pattern, text_lower)
        if match:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='ADHOC_HEDGING',
                message=f'Ad-hoc hedging detected: "{match.group()}". Use confidence language ladder instead.',
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
    """Validate citation fields: verification status, tier values, and tier-status consistency."""
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

            # Tier-status consistency check
            if tier == 1 and vs == 'claimed':
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'{field_prefix}.citations[{cidx}]',
                    rule='TIER_STATUS_MISMATCH',
                    message=f'Tier 1 source "{cit.get("source", "?")}" marked as "claimed". Tier 1 sources should be "confirmed" or "reported".',
                ))
            if tier == 3 and vs == 'confirmed':
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'{field_prefix}.citations[{cidx}]',
                    rule='TIER_STATUS_MISMATCH',
                    message=f'Tier 3 source "{cit.get("source", "?")}" marked as "confirmed". Tier 3 can only be "claimed" or "disputed".',
                ))

            # Iranian state media check
            source_lower = (cit.get('source') or '').lower()
            if source_lower in IRANIAN_STATE_MEDIA_SOURCES and vs != 'claimed':
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'{field_prefix}.citations[{cidx}]',
                    rule='IRANIAN_STATE_MEDIA',
                    message=f'Iranian state media source "{cit.get("source")}" must be verificationStatus "claimed", not "{vs}".',
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
    """Flag kinetic/factual claims in OBSERVED paragraphs missing timestamps."""
    warnings = []
    # Check d1, d3, d6 — all domains with factual/market claims needing timestamps
    if domain not in ('d1', 'd3', 'd6'):
        return warnings

    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        variant = para.get('subLabelVariant', '')
        if variant != 'observed':
            continue
        text = para.get('text', '')
        # Check for UTC timestamp pattern or date pattern
        has_timestamp = bool(re.search(r'\d{4}\s*UTC', text))
        has_date = bool(re.search(r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', text))
        if not has_timestamp and not has_date and _word_count(text) > 10:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}].text',
                rule='MISSING_TEMPORAL_PRECISION',
                message='OBSERVED paragraph lacks timestamp. Factual claims require: "As of HHMM UTC DD Mon" or at minimum a date reference.',
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


def check_passive_voice(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag excessive passive voice in assessment paragraphs."""
    warnings = []
    matches = []
    for pattern in PASSIVE_VOICE_PATTERNS:
        matches.extend(pattern.findall(text))

    word_count = _word_count(text)
    # Allow some passive in observed paragraphs; flag if >2 instances in short text
    # or >3 in longer text
    threshold = 2 if word_count < 60 else 3
    if len(matches) > threshold:
        warnings.append(QualityWarning(
            domain=domain,
            field=field,
            rule='EXCESSIVE_PASSIVE',
            message=f'Found {len(matches)} passive-voice constructions in {word_count} words. Rewrite in active voice: "We assess X" not "X is assessed."',
        ))
    return warnings


def check_nominalizations(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag nominalizations that should be direct verbs for clarity."""
    warnings = []
    for pattern, suggestion in NOMINALIZATION_PATTERNS:
        match = pattern.search(text)
        if match:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='NOMINALIZATION',
                message=f'Nominalization detected: "{match.group()}". {suggestion}',
            ))
    return warnings


def check_weasel_words(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag vague quantifiers that hide precision."""
    warnings = []
    for pattern, suggestion in WEASEL_WORD_PATTERNS:
        match = pattern.search(text)
        if match:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='WEASEL_WORDS',
                message=f'Vague quantifier: "{match.group()}". {suggestion}',
            ))
    return warnings


def check_redundant_modifiers(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag tautological or empty intensifiers."""
    warnings = []
    for pattern, suggestion in REDUNDANT_MODIFIER_PATTERNS:
        match = pattern.search(text)
        if match:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='REDUNDANT_MODIFIER',
                message=f'Redundant modifier: "{match.group()}". {suggestion}',
            ))
    return warnings


def check_vague_geography(text: str, domain: str, field: str) -> list[QualityWarning]:
    """Flag vague geographic references that lack specificity."""
    warnings = []
    for pattern, suggestion in VAGUE_GEO_PATTERNS:
        match = pattern.search(text)
        if match:
            warnings.append(QualityWarning(
                domain=domain,
                field=field,
                rule='VAGUE_GEOGRAPHY',
                message=f'Vague geographic reference: "{match.group()}". {suggestion}',
            ))
    return warnings


def check_kj_body_repetition(section: dict, domain: str) -> list[QualityWarning]:
    """Flag when key judgment text appears verbatim in body paragraphs."""
    warnings = []
    kj_text = section.get('keyJudgment', {}).get('text', '')
    if not kj_text or len(kj_text) < 20:
        return warnings

    # Check if KJ text or large portions appear in body paragraphs
    kj_lower = kj_text.lower()
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        para_lower = para.get('text', '').lower()
        if kj_lower in para_lower:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}].text',
                rule='KJ_BODY_REPETITION',
                message='Key judgment text repeated verbatim in body paragraph. Body should provide supporting evidence, not restate the KJ.',
            ))
            break

        # Also check for long substring overlap (>60% of KJ appears in body)
        kj_words = set(kj_lower.split())
        para_words = set(para_lower.split())
        if len(kj_words) > 5:
            overlap = len(kj_words & para_words) / len(kj_words)
            if overlap > 0.7:
                warnings.append(QualityWarning(
                    domain=domain,
                    field=f'bodyParagraphs[{idx}].text',
                    rule='KJ_BODY_OVERLAP',
                    message=f'Body paragraph shares {overlap:.0%} of key judgment vocabulary. Vary language and add evidence not in the KJ.',
                ))
                break

    return warnings


def check_quantification(section: dict, domain: str) -> list[QualityWarning]:
    """Flag d3/d6 paragraphs that lack numeric quantification."""
    if domain not in ('d3', 'd6'):
        return []

    warnings = []
    has_number = re.compile(r'(\$[\d,.]+|[\d,.]+%|↑|↓|[\d,.]+\s*(bbl|GRT|bps|tonnes?|USD|EUR|day))', re.IGNORECASE)

    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        text = para.get('text', '')
        sub_label = (para.get('subLabel') or '').upper()

        # Skip Canadian Exposure (short, may not have numbers)
        if 'CANADIAN' in sub_label:
            continue

        if _word_count(text) > 15 and not has_number.search(text):
            warnings.append(QualityWarning(
                domain=domain,
                field=f'bodyParagraphs[{idx}].text',
                rule='MISSING_QUANTIFICATION',
                message=f'{"Energy" if domain == "d3" else "War risk"} paragraph lacks numeric data. Quantify: "$X/bbl", "+X%", "$Y/GRT/day".',
            ))

    return warnings


def check_dissenter_attribution(section: dict, domain: str) -> list[QualityWarning]:
    """Validate dissenter notes have proper analyst attribution."""
    warnings = []
    dissenter = section.get('dissenterNote')
    if not dissenter:
        return warnings

    analyst_id = dissenter.get('analystId', '')
    if not re.match(r'^ANALYST [A-Z]$', analyst_id):
        warnings.append(QualityWarning(
            domain=domain,
            field='dissenterNote.analystId',
            rule='INVALID_DISSENTER_ID',
            message=f'Dissenter analystId must be "ANALYST B", "ANALYST C", etc. Got: "{analyst_id}".',
        ))

    text = dissenter.get('text', '')
    if text and _sentence_count(text) < 2:
        warnings.append(QualityWarning(
            domain=domain,
            field='dissenterNote.text',
            rule='DISSENTER_TOO_SHORT',
            message='Dissenter note must contain at least 2 sentences of explicit reasoning.',
        ))

    return warnings


def check_flashpoint_headlines(flashpoints: list[dict]) -> list[QualityWarning]:
    """Validate flash point headline length (≤12 words)."""
    warnings = []
    for fp in flashpoints:
        headline = fp.get('headline', '')
        wc = _word_count(headline)
        if wc > 12:
            warnings.append(QualityWarning(
                domain=f'fp:{fp.get("id", "?")}',
                field='headline',
                rule='FLASHPOINT_HEADLINE_LENGTH',
                message=f'Flash point headline is {wc} words; maximum is 12.',
            ))
    return warnings


# ═══════════════════════════════════════════════════════════════════════════
#  COMPOSITE VALIDATION ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════

def _check_text_quality(text: str, domain: str, field: str,
                         is_assessment: bool = False) -> list[QualityWarning]:
    """Run all text-level quality checks on a single string."""
    warnings: list[QualityWarning] = []
    warnings.extend(check_forbidden_jargon(text, domain, field))
    warnings.extend(check_adhoc_hedging(text, domain, field))
    warnings.extend(check_weasel_words(text, domain, field))
    warnings.extend(check_redundant_modifiers(text, domain, field))
    warnings.extend(check_nominalizations(text, domain, field))
    warnings.extend(check_vague_geography(text, domain, field))
    if is_assessment:
        warnings.extend(check_passive_voice(text, domain, field))
    return warnings


def validate_domain_section(section: dict) -> list[QualityWarning]:
    """Run all quality checks against a single domain section."""
    domain = section.get('id', '?')
    warnings: list[QualityWarning] = []

    # Key judgment checks
    kj = section.get('keyJudgment', {})
    kj_text = kj.get('text', '')
    if kj_text:
        warnings.extend(_check_text_quality(kj_text, domain, 'keyJudgment.text', is_assessment=True))
        warnings.extend(check_description_lead(kj_text, domain, 'keyJudgment.text'))

    # Basis check — must exist and be substantive
    kj_basis = kj.get('basis', '')
    if kj_text and not kj_basis:
        warnings.append(QualityWarning(
            domain=domain,
            field='keyJudgment.basis',
            rule='MISSING_KJ_BASIS',
            message='Key judgment has no evidentiary basis statement. Every KJ must explain what evidence supports it.',
        ))
    elif kj_basis and _word_count(kj_basis) < 5:
        warnings.append(QualityWarning(
            domain=domain,
            field='keyJudgment.basis',
            rule='THIN_KJ_BASIS',
            message=f'Key judgment basis is only {_word_count(kj_basis)} words. Provide a substantive 1-2 sentence evidence basis.',
        ))

    # Body paragraph checks
    for idx, para in enumerate(section.get('bodyParagraphs', [])):
        text = para.get('text', '')
        field = f'bodyParagraphs[{idx}].text'
        variant = para.get('subLabelVariant', '')
        is_assessment = variant == 'assessment'

        warnings.extend(_check_text_quality(text, domain, field, is_assessment=is_assessment))
        warnings.extend(check_paragraph_minimum(text, domain, field))

        # Check first body paragraph for description-lead
        if idx == 0:
            warnings.extend(check_description_lead(text, domain, field))

    # Structural / enum checks
    warnings.extend(check_confidence_values(section, domain))
    warnings.extend(check_citation_integrity(section, domain))
    warnings.extend(check_word_limits(section, domain))
    warnings.extend(check_temporal_precision(section, domain))
    warnings.extend(check_source_attribution(section, domain))
    warnings.extend(check_kj_body_repetition(section, domain))
    warnings.extend(check_quantification(section, domain))
    warnings.extend(check_dissenter_attribution(section, domain))

    # Assessment question should not contain forbidden jargon
    aq = section.get('assessmentQuestion', '')
    if aq:
        warnings.extend(check_forbidden_jargon(aq, domain, 'assessmentQuestion'))

    return warnings


def validate_executive(executive: dict) -> list[QualityWarning]:
    """Run quality checks on the executive summary."""
    domain = 'executive'
    warnings: list[QualityWarning] = []

    bluf = executive.get('bluf', '')
    if bluf:
        warnings.extend(_check_text_quality(bluf, domain, 'bluf', is_assessment=True))
        warnings.extend(check_description_lead(bluf, domain, 'bluf'))
        sc = _sentence_count(bluf)
        if sc < 2:
            warnings.append(QualityWarning(
                domain=domain,
                field='bluf',
                rule='BLUF_TOO_SHORT',
                message=f'BLUF has {sc} sentence(s); minimum is 2.',
            ))
        if sc > 4:
            warnings.append(QualityWarning(
                domain=domain,
                field='bluf',
                rule='BLUF_TOO_LONG',
                message=f'BLUF has {sc} sentences; maximum is 4.',
            ))

    kjs = executive.get('keyJudgments', [])
    for idx, kj in enumerate(kjs):
        text = kj.get('text', '')
        field = f'keyJudgments[{idx}].text'
        warnings.extend(_check_text_quality(text, domain, field, is_assessment=True))

        lang = kj.get('language')
        if lang and lang not in VALID_CONFIDENCE_LANGUAGE:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'keyJudgments[{idx}].language',
                rule='INVALID_CONFIDENCE_LANGUAGE',
                message=f'Invalid confidence language: "{lang}".',
            ))

        # Check KJ basis exists
        basis = kj.get('basis', '')
        if text and not basis:
            warnings.append(QualityWarning(
                domain=domain,
                field=f'keyJudgments[{idx}].basis',
                rule='MISSING_KJ_BASIS',
                message='Executive key judgment has no evidentiary basis statement.',
            ))

    # Key judgment count check (4-6 required)
    if kjs and (len(kjs) < 4 or len(kjs) > 6):
        warnings.append(QualityWarning(
            domain=domain,
            field='keyJudgments',
            rule='KJ_COUNT',
            message=f'Executive has {len(kjs)} key judgments; should be 4-6.',
        ))

    # KPI count check (5 required)
    kpis = executive.get('kpis', [])
    if kpis and len(kpis) != 5:
        warnings.append(QualityWarning(
            domain=domain,
            field='kpis',
            rule='KPI_COUNT',
            message=f'Executive has {len(kpis)} KPI cells; should be exactly 5.',
        ))

    return warnings


def validate_strategic_header(header: dict) -> list[QualityWarning]:
    """Run quality checks on the strategic header."""
    domain = 'strategicHeader'
    warnings: list[QualityWarning] = []

    headline = header.get('headlineJudgment', '')
    if headline:
        warnings.extend(_check_text_quality(headline, domain, 'headlineJudgment', is_assessment=True))
        warnings.extend(check_description_lead(headline, domain, 'headlineJudgment'))

        # Must be exactly one sentence
        sc = _sentence_count(headline)
        if sc != 1:
            warnings.append(QualityWarning(
                domain=domain,
                field='headlineJudgment',
                rule='HEADLINE_SENTENCE_COUNT',
                message=f'Headline judgment must be exactly 1 sentence; found {sc}.',
            ))

    rationale = header.get('trajectoryRationale', '')
    if rationale:
        warnings.extend(_check_text_quality(rationale, domain, 'trajectoryRationale', is_assessment=True))

        # Must be 2-3 sentences
        sc = _sentence_count(rationale)
        if sc < 2 or sc > 3:
            warnings.append(QualityWarning(
                domain=domain,
                field='trajectoryRationale',
                rule='RATIONALE_SENTENCE_COUNT',
                message=f'Trajectory rationale must be 2-3 sentences; found {sc}.',
            ))

    # Threat level must be valid
    threat_level = header.get('threatLevel')
    valid_threats = {'CRITICAL', 'SEVERE', 'ELEVATED', 'GUARDED', 'LOW'}
    if threat_level and threat_level not in valid_threats:
        warnings.append(QualityWarning(
            domain=domain,
            field='threatLevel',
            rule='INVALID_THREAT_LEVEL',
            message=f'Invalid threat level: "{threat_level}". Must be: {valid_threats}',
        ))

    # Trajectory must be valid
    trajectory = header.get('threatTrajectory')
    valid_trajectories = {'escalating', 'stable', 'de-escalating'}
    if trajectory and trajectory not in valid_trajectories:
        warnings.append(QualityWarning(
            domain=domain,
            field='threatTrajectory',
            rule='INVALID_TRAJECTORY',
            message=f'Invalid trajectory: "{trajectory}". Must be: {valid_trajectories}',
        ))

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

    # Flash points
    warnings.extend(check_flashpoint_headlines(cycle.get('flashPoints', [])))

    # Warning indicators — full text quality checks
    for wi in cycle.get('warningIndicators', []):
        detail = wi.get('detail', '')
        wi_id = wi.get('id', '?')
        domain_tag = f'wi:{wi_id}'
        warnings.extend(_check_text_quality(detail, domain_tag, 'detail'))
        warnings.extend(check_adhoc_hedging(detail, domain_tag, 'detail'))

        # Status validation
        status = wi.get('status')
        if status and status not in ('watching', 'triggered', 'cleared', 'elevated'):
            warnings.append(QualityWarning(
                domain=domain_tag,
                field='status',
                rule='INVALID_WI_STATUS',
                message=f'Invalid warning indicator status: "{status}". Must be: watching/triggered/cleared/elevated.',
            ))

        change = wi.get('change')
        if change and change not in ('new', 'elevated', 'unchanged', 'cleared'):
            warnings.append(QualityWarning(
                domain=domain_tag,
                field='change',
                rule='INVALID_WI_CHANGE',
                message=f'Invalid warning indicator change: "{change}". Must be: new/elevated/unchanged/cleared.',
            ))

    # Collection gaps — full text quality checks
    for gap in cycle.get('collectionGaps', []):
        gap_text = gap.get('gap', '')
        sig_text = gap.get('significance', '')
        gap_id = gap.get('id', '?')
        domain_tag = f'gap:{gap_id}'
        warnings.extend(_check_text_quality(gap_text, domain_tag, 'gap'))
        warnings.extend(_check_text_quality(sig_text, domain_tag, 'significance'))

        severity = gap.get('severity')
        if severity and severity not in ('critical', 'significant', 'minor'):
            warnings.append(QualityWarning(
                domain=domain_tag,
                field='severity',
                rule='INVALID_GAP_SEVERITY',
                message=f'Invalid gap severity: "{severity}". Must be: critical/significant/minor.',
            ))

    # Log summary
    if warnings:
        log.warning('Quality check found %d issue(s):', len(warnings))
        for w in warnings:
            log.warning('  [%s] %s → %s: %s', w.rule, w.domain, w.field, w.message)
    else:
        log.info('Quality check: all clear — no issues found')

    return warnings
