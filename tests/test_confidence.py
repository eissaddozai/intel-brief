"""Smoke tests for confidence assignment."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'pipeline'))

from triage.confidence import assign_confidence, _extract_key_phrases


def _item(source_id: str, tier: int, text: str = 'test text') -> dict:
    return {
        'source_id': source_id,
        'tier': tier,
        'text': text,
        'verification_status': '',
    }


def test_tier1_confirmed():
    result = assign_confidence([_item('reuters', 1)])
    assert result[0]['verification_status'] == 'confirmed'
    assert result[0]['confidence_tier'] == 'high'


def test_tier2_reported():
    result = assign_confidence([_item('icg', 2)])
    assert result[0]['verification_status'] == 'reported'
    assert result[0]['confidence_tier'] == 'moderate'


def test_tier3_claimed():
    result = assign_confidence([_item('some_blogger', 3)])
    assert result[0]['verification_status'] == 'claimed'
    assert result[0]['confidence_tier'] == 'low'


def test_iranian_state_media_always_claimed():
    result = assign_confidence([_item('presstv', 1)])  # Even if tier=1 in registry
    assert result[0]['verification_status'] == 'claimed'
    assert result[0]['confidence_tier'] == 'low'
    assert result[0]['is_state_media'] is True


def test_extract_key_phrases_short_text():
    """Texts shorter than 4 words should return empty set (not crash)."""
    assert _extract_key_phrases('hi') == set()
    assert _extract_key_phrases('one two three') == set()  # exactly 3 words


def test_extract_key_phrases_normal():
    phrases = _extract_key_phrases('Iran fires missiles at Haifa')
    assert len(phrases) > 0
    assert 'iran fires missiles at' in phrases


def test_corroboration_does_not_crash_on_empty():
    result = assign_confidence([])
    assert result == []
