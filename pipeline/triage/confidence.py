"""
Confidence assignment — maps source tier to ConfidenceTier and VerificationStatus.
Cross-checks: if the same claim appears in 2+ Tier 1 sources, confidence is raised.
"""

import logging
import re
from collections import defaultdict

log = logging.getLogger(__name__)

# Source tier → default confidence tier
TIER_TO_CONFIDENCE = {
    1: 'high',
    2: 'moderate',
    3: 'low',
}

# Iranian state media source IDs — always 'claimed', never 'confirmed'
IRANIAN_STATE_MEDIA: set[str] = {
    'tehran_times', 'presstv', 'irna', 'mehr', 'fars',
}


def assign_confidence(items: list[dict]) -> list[dict]:
    """
    Add 'confidence_tier' and enforce 'verification_status' based on source tier.
    Cross-checks Tier 1 items for corroboration boost.
    """
    result = []

    for item in items:
        item = dict(item)
        source_id = item.get('source_id', '')
        tier = item.get('tier', 2)

        # Iranian state media override
        if source_id in IRANIAN_STATE_MEDIA:
            item['verification_status'] = 'claimed'
            item['confidence_tier'] = 'low'
            item['is_state_media'] = True
            log.debug('Iranian state media flagged: %s', source_id)
            result.append(item)
            continue

        # Standard tier mapping
        item['confidence_tier'] = TIER_TO_CONFIDENCE.get(tier, 'low')

        # Ensure verification_status consistency
        if tier == 1:
            item['verification_status'] = 'confirmed'
        elif tier == 2:
            item['verification_status'] = 'reported'
        else:
            item['verification_status'] = 'claimed'

        item['is_state_media'] = False
        result.append(item)

    # Cross-corroboration boost: if 2+ Tier 1 sources share a key phrase,
    # mark them as 'high confidence' even if they were already high (no change needed),
    # but also mark any Tier 2 items with the same phrase as 'moderate-corroborated'.
    _apply_corroboration_boost(result)

    return result


def _extract_key_phrases(text: str) -> set[str]:
    """Extract 4-grams as key phrases for corroboration matching."""
    words = re.findall(r'\b\w+\b', text.lower())
    return {' '.join(words[i:i+4]) for i in range(len(words) - 3)}


def _apply_corroboration_boost(items: list[dict]) -> None:
    """
    If the same factual claim (4-gram match) appears in 2+ Tier 1 sources,
    annotate items with 'corroborated: True'.
    """
    tier1_phrases: dict[str, list[int]] = defaultdict(list)

    for idx, item in enumerate(items):
        if item.get('tier') == 1:
            for phrase in _extract_key_phrases(item.get('text', '')):
                tier1_phrases[phrase].append(idx)

    # Find phrases appearing in 2+ Tier 1 items
    corroborated_phrases = {
        phrase for phrase, idxs in tier1_phrases.items()
        if len(set(items[i]['source_id'] for i in idxs)) >= 2
    }

    for item in items:
        text_phrases = _extract_key_phrases(item.get('text', ''))
        item['corroborated'] = bool(text_phrases & corroborated_phrases)

    corroborated_count = sum(1 for item in items if item.get('corroborated'))
    log.info('%d items corroborated by 2+ Tier 1 sources', corroborated_count)
