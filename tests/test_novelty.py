"""Smoke tests for novelty detection."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'pipeline'))

from triage.novelty import extract_known_facts, compute_novelty_score


SAMPLE_CYCLE = {
    'strategicHeader': {
        'headlineJudgment': 'Iran escalation risk elevated after Fordow suspension.',
        'trajectoryRationale': 'Nuclear breakout timeline compressed.',
    },
    'flashPoints': [
        {'headline': 'IRGC missile strike on Haifa port', 'detail': 'Four missiles impacted.'},
    ],
    'executive': {
        'bluf': 'Iran war risk SEVERE. Diplomatic channels stalled.',
        'keyJudgments': ['Nuclear breakout within 10 days.', 'Hezbollah probing operations.'],
    },
    'domains': [
        {
            'id': 'd1',
            'keyJudgment': {'text': 'IRGC offensive preparations visible.'},
            'bodyParagraphs': [{'text': 'Three BTGs repositioned near Metula.'}],
        }
    ],
    'warningIndicators': [
        {'indicator': 'Second ballistic missile salvo', 'assessment': 'Imminent risk.'},
    ],
}


def test_extract_known_facts_includes_all_sections():
    known = extract_known_facts(SAMPLE_CYCLE)
    assert len(known) > 0
    # Strategic header phrases
    assert any('fordow suspension' in p for p in known)
    # Flash points
    assert any('haifa port' in p for p in known)
    # Warning indicators
    assert any('ballistic missile' in p for p in known)


def test_compute_novelty_fully_novel():
    item = {'text': 'A completely different event occurred in Syria.', 'title': ''}
    score = compute_novelty_score(item, {'iran fires missiles at'})
    assert score >= 0.8


def test_compute_novelty_repeated():
    known = extract_known_facts(SAMPLE_CYCLE)
    # Use verbatim text from cycle
    item = {'text': 'Iran war risk SEVERE. Diplomatic channels stalled.', 'title': ''}
    score = compute_novelty_score(item, known)
    assert score < 0.6  # Most trigrams should be in known


def test_compute_novelty_short_text():
    score = compute_novelty_score({'text': 'hi', 'title': ''}, set())
    assert score == 1.0
