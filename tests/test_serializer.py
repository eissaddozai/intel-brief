"""Smoke tests for cycle serializer validation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'pipeline'))

from output.serializer import validate


VALID_CYCLE = {
    'meta': {
        'cycleId': 'cycle001_20260306',
        'cycleNum': '001',
        'classification': 'PROTECTED B',
        'tlp': 'AMBER',
        'timestamp': '2026-03-06T06:00:00+00:00',
        'region': 'Iran · Gulf',
        'analystUnit': 'CSE',
        'threatLevel': 'SEVERE',
        'threatTrajectory': 'escalating',
    },
    'strategicHeader': {'headlineJudgment': 'Test'},
    'flashPoints': [],
    'executive': {
        'bluf': 'Test BLUF.',
        'keyJudgments': ['KJ1'],
    },
    'domains': [
        {
            'id': 'd1',
            'keyJudgment': {'text': 'Test KJ.'},
            'bodyParagraphs': [{'subLabel': 'OBSERVED', 'text': 'Test para.'}],
        }
    ],
    'warningIndicators': [{'indicator': 'Test', 'level': 'AMBER'}],
    'collectionGaps': [],
    'caveats': {},
    'footer': {},
}


def test_valid_cycle_passes():
    errors = validate(VALID_CYCLE)
    assert errors == []


def test_missing_meta_field():
    cycle = dict(VALID_CYCLE)
    meta = dict(cycle['meta'])
    del meta['threatLevel']
    cycle['meta'] = meta
    errors = validate(cycle)
    assert any('threatLevel' in e for e in errors)


def test_invalid_tlp():
    cycle = dict(VALID_CYCLE)
    meta = dict(cycle['meta'])
    meta['tlp'] = 'BLACK'
    cycle['meta'] = meta
    errors = validate(cycle)
    assert any('TLP' in e for e in errors)


def test_missing_top_level_key():
    cycle = {k: v for k, v in VALID_CYCLE.items() if k != 'executive'}
    errors = validate(cycle)
    assert any('executive' in e for e in errors)


def test_domain_missing_key_judgment():
    cycle = dict(VALID_CYCLE)
    cycle['domains'] = [{'id': 'd1', 'bodyParagraphs': [{'text': 'x'}]}]
    errors = validate(cycle)
    assert any('keyJudgment' in e for e in errors)


def test_invalid_domain_id():
    cycle = dict(VALID_CYCLE)
    cycle['domains'] = [{'id': 'dx', 'keyJudgment': {'text': 'x'}, 'bodyParagraphs': [{'text': 'x'}]}]
    errors = validate(cycle)
    assert any('dx' in e for e in errors)
