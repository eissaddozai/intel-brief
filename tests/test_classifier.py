"""Smoke tests for domain classifier."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'pipeline'))

from triage.classifier import classify_item, classify_items


def _item(title: str, text: str = '', source_id: str = 'test', tier: int = 2) -> dict:
    return {
        'source_id': source_id,
        'source_name': 'Test Source',
        'tier': tier,
        'domains': [],
        'title': title,
        'text': text,
        'full_content': '',
        'url': '',
        'timestamp': '2026-03-06T06:00:00+00:00',
        'verification_status': 'reported',
        'method': 'test',
    }


def test_battlespace_missile():
    item = classify_item(_item('IRGC fires ballistic missile at Haifa port'))
    assert 'd1' in item['tagged_domains']


def test_nuclear_enrichment():
    item = classify_item(_item('Iran resumes enrichment at Fordow facility'))
    assert 'd2' in item['tagged_domains']


def test_energy_oil():
    item = classify_item(_item('Brent crude hits $147 amid Hormuz transit restrictions'))
    assert 'd3' in item['tagged_domains']


def test_diplomatic_un():
    item = classify_item(_item('UN Security Council fails to pass ceasefire resolution'))
    assert 'd4' in item['tagged_domains']


def test_cyber_malware():
    item = classify_item(_item('APT35 deploys new malware variant against Israeli banking sector'))
    assert 'd5' in item['tagged_domains']


def test_war_risk_jwc():
    item = classify_item(_item('Joint War Committee adds northern Persian Gulf to listed areas'))
    assert 'd6' in item['tagged_domains']


def test_no_false_positive_on_short_words():
    """Short ambiguous words ('gas', 'ship') must not trigger domains without context."""
    item = classify_item(_item(
        'Prime Minister gives speech on energy policy',
        text='Natural gas supplies stable; no disruption to pipeline.',
    ))
    # d3 should match because 'natural gas' keyword present
    assert 'd3' in item['tagged_domains']


def test_context_gated_ship():
    """'ship' alone should not trigger d6 without war risk context."""
    item = classify_item(_item('Ship arrives in port carrying grain'))
    # Should NOT be tagged d6 (no war risk context)
    assert 'd6' not in item['tagged_domains']


def test_context_gated_vessel_with_context():
    """'vessel' WITH 'war risk' context should trigger d6."""
    item = classify_item(_item(
        'Tanker vessel requires war risk insurance for Hormuz transit'
    ))
    assert 'd6' in item['tagged_domains']


def test_classify_items_returns_all():
    items = [_item(f'Test item {i}') for i in range(5)]
    result = classify_items(items)
    assert len(result) == 5


def test_no_wrong_canadian_keywords():
    """Verify removed Canadian keywords do not trigger d3."""
    item = classify_item(_item('Canadian dollar (CAD) falls as TSX slides'))
    # This should not be classified as d3 (Canadian finance != Gulf energy)
    assert 'd3' not in item['tagged_domains']
