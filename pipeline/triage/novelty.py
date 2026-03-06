"""
Novelty detection — filters out items that repeat information
already present in the previous cycle's brief.
"""

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)


_HTML_TAG_RE = re.compile(r'<[^>]+>')


def _clean(text: str) -> str:
    """Strip HTML and normalise whitespace before phrase extraction."""
    return re.sub(r'\s+', ' ', _HTML_TAG_RE.sub(' ', text)).strip()


def extract_known_facts(prev_cycle: dict) -> set[str]:
    """
    Extract a set of key phrases from the previous cycle JSON
    that represent 'known' information already reported.
    Covers: flashPoints, strategicHeader, executive, domains, warningIndicators.
    """
    known: set[str] = set()

    def add_text(text: str) -> None:
        if not text:
            return
        clean = _clean(text)
        words = re.findall(r'\b\w+\b', clean.lower())
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            if len(phrase) > 10:
                known.add(phrase)

    # Flash points
    for fp in prev_cycle.get('flashPoints', []):
        add_text(fp.get('headline', ''))
        add_text(fp.get('detail', ''))

    # Strategic header
    sh = prev_cycle.get('strategicHeader', {})
    add_text(sh.get('headlineJudgment', ''))
    add_text(sh.get('trajectoryRationale', ''))

    # Executive assessment
    exec_data = prev_cycle.get('executive', {})
    add_text(exec_data.get('bluf', ''))
    for kj in exec_data.get('keyJudgments', []):
        if isinstance(kj, str):
            add_text(kj)
        elif isinstance(kj, dict):
            add_text(kj.get('text', ''))

    # Domain body paragraphs and key judgments
    for domain in prev_cycle.get('domains', []):
        kj = domain.get('keyJudgment', {})
        if isinstance(kj, dict):
            add_text(kj.get('text', ''))
        for para in domain.get('bodyParagraphs', []):
            add_text(para.get('text', ''))

    # Warning indicators
    for wi in prev_cycle.get('warningIndicators', []):
        add_text(wi.get('indicator', ''))
        add_text(wi.get('assessment', ''))
        add_text(wi.get('detail', ''))

    return known


def compute_novelty_score(item: dict, known_phrases: set[str]) -> float:
    """
    Returns a score from 0.0 (fully repeated) to 1.0 (completely novel).
    Score is the fraction of the item's 3-grams NOT in known_phrases.
    """
    text = (item.get('text', '') + ' ' + item.get('title', '')).lower()
    words = re.findall(r'\b\w+\b', text)
    if len(words) < 3:
        return 1.0

    trigrams = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
    if not trigrams:
        return 1.0

    novel_count = sum(1 for tg in trigrams if tg not in known_phrases)
    return novel_count / len(trigrams)


DEFAULT_NOVELTY_THRESHOLD = 0.35  # Items below this are considered repeats

# Regex to extract cycle number from filenames like cycle001_20260305.json
_CYCLE_NUM_RE = re.compile(r'cycle_?(\d+)')


def filter_novel(items: list[dict], cycles_dir: Path, config: dict | None = None) -> list[dict]:
    """
    Filter out items that are largely repetitions of the previous cycle.
    Items from Tier 1 sources are never filtered (factual updates always included).
    Config key: triage.novelty_threshold (float, default 0.35).
    """
    threshold = DEFAULT_NOVELTY_THRESHOLD
    if config:
        threshold = float(
            config.get('triage', {}).get('novelty_threshold', DEFAULT_NOVELTY_THRESHOLD)
        )

    # Find most recent cycle by cycle number embedded in filename (not mtime)
    def _cycle_num(p: Path) -> int:
        m = _CYCLE_NUM_RE.search(p.name)
        return int(m.group(1)) if m else 0

    cycle_files = sorted(
        (p for p in cycles_dir.glob('cycle*.json') if not p.is_symlink()),
        key=_cycle_num,
    )
    if not cycle_files:
        log.info('No previous cycles found — treating all items as novel')
        return items

    prev_file = cycle_files[-1]
    log.info('Comparing against previous cycle: %s', prev_file.name)

    try:
        prev_cycle = json.loads(prev_file.read_text(encoding='utf-8'))
    except Exception as exc:
        log.warning('Could not load previous cycle: %s — skipping novelty filter', exc)
        return items

    known_phrases = extract_known_facts(prev_cycle)
    log.info('Previous cycle yielded %d known phrases', len(known_phrases))

    novel_items: list[dict] = []
    filtered_count = 0

    for item in items:
        # Always keep Tier 1 items
        if item.get('tier') == 1:
            item['novelty_score'] = 1.0
            item['is_novel'] = True
            novel_items.append(item)
            continue

        score = compute_novelty_score(item, known_phrases)
        item['novelty_score'] = round(score, 3)
        item['is_novel'] = score >= NOVELTY_THRESHOLD

        if item['is_novel']:
            novel_items.append(item)
        else:
            filtered_count += 1

    log.info(
        'Novelty filter: kept %d / %d items (%d filtered as repetitions)',
        len(novel_items), len(items), filtered_count
    )
    return novel_items
