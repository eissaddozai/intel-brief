#!/usr/bin/env python3
"""
CSE Intel Brief Pipeline — Orchestrator
Usage:
    python pipeline/main.py                    # Full cycle
    python pipeline/main.py --stage ingest
    python pipeline/main.py --stage triage
    python pipeline/main.py --stage draft
    python pipeline/main.py --stage review
    python pipeline/main.py --stage output
    python pipeline/main.py --date 2024-03-15  # Backfill specific date
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure pipeline/ sub-packages are importable when run as `python pipeline/main.py`
PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

CACHE_DIR = PIPELINE_DIR / '.cache'
CYCLES_DIR = REPO_ROOT / 'cycles'
CONFIG_PATH = REPO_ROOT / 'pipeline-config.yaml'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('pipeline')


def load_config() -> dict:
    """Load pipeline-config.yaml, substituting ${ENV_VAR} references."""
    import os
    import re

    if not CONFIG_PATH.exists():
        log.warning('pipeline-config.yaml not found — using defaults')
        return {}

    try:
        import yaml
        text = CONFIG_PATH.read_text(encoding='utf-8')

        def _sub(m: re.Match) -> str:
            val = os.environ.get(m.group(1), '')
            if not val:
                log.warning('Environment variable %s not set', m.group(1))
            return val

        text = re.sub(r'\$\{([^}]+)\}', _sub, text)
        return yaml.safe_load(text) or {}
    except ImportError:
        log.warning('PyYAML not installed — config not loaded. Run: pip install pyyaml')
        return {}
    except Exception as exc:
        log.error('Failed to load config: %s', exc)
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='CSE Intel Brief Pipeline')
    parser.add_argument(
        '--stage',
        choices=['ingest', 'triage', 'draft', 'review', 'output'],
        default=None,
        help='Run a single stage only (default: all stages)',
    )
    parser.add_argument(
        '--date',
        default=None,
        help='Target date for backfill (YYYY-MM-DD). Default: today UTC.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-run even if cache exists for this date.',
    )
    return parser.parse_args()


def get_target_date(date_str: str | None) -> datetime:
    if date_str:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def stage_ingest(target_date: datetime, force: bool, config: dict) -> Path:
    """Run ingestion stage. Returns path to raw items cache file."""
    from ingest.rss_ingest import ingest_rss
    from ingest.scraper import ingest_scrape
    from ingest.email_ingest import ingest_email

    cache_file = CACHE_DIR / f'raw_{target_date.strftime("%Y%m%d")}.json'

    if cache_file.exists() and not force:
        log.info('Raw cache exists for %s — skipping ingestion (use --force to override)',
                 target_date.date())
        return cache_file

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    log.info('Starting ingestion for %s', target_date.date())

    raw_items: list[dict] = []

    log.info('Ingesting RSS feeds...')
    try:
        rss_items = ingest_rss(target_date, config=config)
        raw_items.extend(rss_items)
        log.info('RSS: collected %d items', len(rss_items))
    except Exception as exc:
        log.error('RSS ingestion failed: %s', exc)

    log.info('Ingesting scraped sources...')
    try:
        scraped_items = ingest_scrape(target_date, config=config)
        raw_items.extend(scraped_items)
        log.info('Scrape: collected %d items', len(scraped_items))
    except Exception as exc:
        log.error('Scrape ingestion failed: %s', exc)

    log.info('Parsing email inbox...')
    try:
        email_items = ingest_email(target_date, config=config)
        raw_items.extend(email_items)
        log.info('Email: collected %d items', len(email_items))
    except Exception as exc:
        log.warning('Email ingestion failed (non-fatal): %s', exc)

    if not raw_items:
        log.critical('No items collected from any source. Aborting.')
        sys.exit(1)

    tier1 = [item for item in raw_items if item.get('tier') == 1]
    if not tier1 and config.get('triage', {}).get('halt_if_zero_tier1', True):
        log.critical('ZERO Tier 1 items collected. Brief integrity cannot be guaranteed. Aborting.')
        sys.exit(1)

    log.info('Total items collected: %d (%d Tier 1)', len(raw_items), len(tier1))
    cache_file.write_text(json.dumps(raw_items, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Raw cache written: %s', cache_file)
    return cache_file


def stage_triage(raw_cache: Path, config: dict) -> Path:
    """Run triage stage. Returns path to tagged items cache file."""
    from triage.classifier import classify_items
    from triage.novelty import filter_novel
    from triage.confidence import assign_confidence

    tagged_file = raw_cache.parent / raw_cache.name.replace('raw_', 'tagged_')

    log.info('Loading raw cache: %s', raw_cache)
    raw_items = json.loads(raw_cache.read_text(encoding='utf-8'))

    log.info('Classifying %d items by domain...', len(raw_items))
    classified = classify_items(raw_items)

    log.info('Running novelty detection...')
    novel = filter_novel(classified, cycles_dir=CYCLES_DIR, config=config)
    log.info('%d novel items (removed %d repeated)', len(novel), len(classified) - len(novel))

    log.info('Assigning confidence tiers...')
    tagged = assign_confidence(novel)

    min_items = config.get('triage', {}).get('min_items_per_domain', 2)
    domain_counts: dict[str, int] = {}
    for item in tagged:
        for d in item.get('tagged_domains', []):
            domain_counts[d] = domain_counts.get(d, 0) + 1
    for domain_id in ['d1', 'd2', 'd3', 'd4', 'd5']:
        count = domain_counts.get(domain_id, 0)
        if count < min_items:
            log.warning('Domain %s has only %d tagged items (min: %d)', domain_id, count, min_items)

    tagged_file.write_text(json.dumps(tagged, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Tagged cache written: %s', tagged_file)
    return tagged_file


def stage_draft(tagged_cache: Path, target_date: datetime, config: dict) -> Path:
    """Run drafting stage via Claude API. Returns path to draft cache."""
    from draft.drafter import draft_cycle

    draft_file = tagged_cache.parent / tagged_cache.name.replace('tagged_', 'draft_')

    log.info('Loading tagged cache: %s', tagged_cache)
    tagged_items = json.loads(tagged_cache.read_text(encoding='utf-8'))

    prev_cycle = _find_previous_cycle()
    if prev_cycle:
        log.info('Using previous cycle for delta context')
    else:
        log.warning('No previous cycle found — drafting without prior context')

    log.info('Drafting with Claude API...')
    draft = draft_cycle(
        tagged_items=tagged_items,
        target_date=target_date,
        prev_cycle=prev_cycle,
        config=config,
    )

    draft_file.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Draft written: %s', draft_file)
    return draft_file


def stage_review(draft_file: Path) -> Path:
    """Interactive human review. Returns path to approved draft."""
    from review.review_cli import run_review

    approved_file = draft_file.parent / draft_file.name.replace('draft_', 'approved_')

    log.info('Opening review CLI for: %s', draft_file)
    draft = json.loads(draft_file.read_text(encoding='utf-8'))
    approved = run_review(draft)

    if approved is None:
        log.critical('Review aborted — no output written.')
        sys.exit(1)

    approved_file.write_text(json.dumps(approved, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Approved draft written: %s', approved_file)
    return approved_file


def stage_output(approved_file: Path, config: dict) -> Path:
    """Validate and write final cycle JSON. Delegates entirely to serializer."""
    from output.serializer import write_cycle

    approved = json.loads(approved_file.read_text(encoding='utf-8'))
    out_path = write_cycle(approved, config)
    log.info('Pipeline output complete: %s', out_path)
    return out_path


def _find_previous_cycle() -> dict | None:
    """Return the most recent non-symlink cycle JSON, or None."""
    if not CYCLES_DIR.exists():
        return None
    cycles = [p for p in CYCLES_DIR.glob('cycle*.json') if not p.is_symlink()]
    if not cycles:
        return None
    latest = max(cycles, key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(latest.read_text(encoding='utf-8'))
    except Exception:
        return None


def _resolve_cache(stage_prefix: str, target_date: datetime) -> Path:
    """Resolve cache file for a given stage prefix, or exit if missing."""
    cache_file = CACHE_DIR / f'{stage_prefix}_{target_date.strftime("%Y%m%d")}.json'
    if not cache_file.exists():
        log.error('No %s cache found for %s. Run prior stage first.', stage_prefix, target_date.date())
        sys.exit(1)
    return cache_file


def main() -> None:
    args = parse_args()
    config = load_config()
    target_date = get_target_date(args.date)
    log.info('Pipeline target date: %s', target_date.strftime('%Y-%m-%d'))

    log_level = config.get('logging', {}).get('level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    single_stage = args.stage

    raw_cache: Path
    tagged_cache: Path
    draft_file: Path
    approved_file: Path

    if single_stage == 'ingest' or single_stage is None:
        raw_cache = stage_ingest(target_date, args.force, config)
        if single_stage:
            return

    if single_stage in ('triage', None):
        if single_stage == 'triage':
            raw_cache = _resolve_cache('raw', target_date)
        tagged_cache = stage_triage(raw_cache, config)
        if single_stage:
            return

    if single_stage in ('draft', None):
        if single_stage == 'draft':
            tagged_cache = _resolve_cache('tagged', target_date)
        draft_file = stage_draft(tagged_cache, target_date, config)
        if single_stage:
            return

    if single_stage in ('review', None):
        if single_stage == 'review':
            draft_file = _resolve_cache('draft', target_date)
        approved_file = stage_review(draft_file)
        if single_stage:
            return

    if single_stage in ('output', None):
        if single_stage == 'output':
            approved_file = _resolve_cache('approved', target_date)
        output_path = stage_output(approved_file, config)
        log.info('Pipeline complete. Output: %s', output_path)


if __name__ == '__main__':
    main()
