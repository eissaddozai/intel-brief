"""
RSS ingestion module.
Reads sources.yaml, pulls all RSS-method sources, returns List[RawItem].
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import feedparser
import yaml

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
MAX_ITEM_AGE_HOURS = 30  # Items older than this are skipped
REQUEST_DELAY = 0.5       # Seconds between RSS requests (be polite)


def load_rss_sources() -> list[dict]:
    """Return all RSS-method sources from sources.yaml."""
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [s for s in data.get('sources', []) if s.get('method') == 'rss']


def parse_entry_timestamp(entry: Any) -> datetime | None:
    """Extract datetime from a feedparser entry."""
    for attr in ('published_parsed', 'updated_parsed', 'created_parsed'):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def entry_to_raw_item(entry: Any, source: dict) -> dict:
    """Convert a feedparser entry to a RawItem dict."""
    ts = parse_entry_timestamp(entry)
    summary = getattr(entry, 'summary', '') or ''
    content_parts = getattr(entry, 'content', [])
    content = content_parts[0].get('value', '') if content_parts else summary

    return {
        'source_id': source['id'],
        'source_name': source['name'],
        'tier': source['tier'],
        'domains': source.get('domains', []),
        'title': getattr(entry, 'title', ''),
        'text': f"{getattr(entry, 'title', '')}. {summary}".strip(),
        'full_content': content,
        'url': getattr(entry, 'link', ''),
        'timestamp': ts.isoformat() if ts else None,
        'verification_status': 'confirmed' if source['tier'] == 1 else 'reported',
        'method': 'rss',
    }


def ingest_rss(target_date: datetime) -> list[dict]:
    """
    Ingest all RSS sources.

    Returns a list of RawItem dicts covering the 30-hour window ending at target_date.
    """
    sources = load_rss_sources()
    cutoff = target_date - timedelta(hours=MAX_ITEM_AGE_HOURS)
    all_items: list[dict] = []
    failed_tier1: list[str] = []

    for source in sources:
        url = source.get('url')
        if not url:
            log.warning('Source %s has no URL — skipping', source['id'])
            continue

        log.debug('Fetching %s (%s)', source['name'], url)
        try:
            feed = feedparser.parse(url, request_headers={
                'User-Agent': 'CSE-Intel-Brief/1.0 (Research; contact your-email@cse.ca)',
            })

            if feed.bozo and not feed.entries:
                raise ValueError(f'Feed parse error: {feed.bozo_exception}')

            items_from_source = 0
            for entry in feed.entries:
                ts = parse_entry_timestamp(entry)

                # If no timestamp, include it (better safe than missing)
                if ts and ts < cutoff:
                    continue

                item = entry_to_raw_item(entry, source)
                all_items.append(item)
                items_from_source += 1

            log.info('%-30s %3d items', source['name'], items_from_source)

        except Exception as exc:
            log.error('Failed to fetch %s: %s', source['name'], exc)
            if source['tier'] == 1:
                failed_tier1.append(source['name'])

        time.sleep(REQUEST_DELAY)

    # Hard stop if any Tier 1 RSS source fails
    if failed_tier1:
        log.error(
            'TIER 1 RSS SOURCES FAILED: %s. '
            'Brief integrity cannot be guaranteed without Tier 1 factual backbone.',
            ', '.join(failed_tier1)
        )
        # Caller (main.py) decides whether to abort or continue

    return all_items
