"""
RSS ingestion module.
Uses requests + stdlib xml.etree (no feedparser dependency).
"""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import yaml

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
MAX_ITEM_AGE_HOURS = 30
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 15

HEADERS = {'User-Agent': 'CSE-Intel-Brief/1.0 (Research pipeline; contact: research@cse.ca)'}

# RSS / Atom namespace map
NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def load_rss_sources(config: dict | None = None) -> list[dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [s for s in data.get('sources', []) if s.get('method') == 'rss']


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    # Try RFC 2822 (RSS pubDate)
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        pass
    # Try ISO 8601 (Atom)
    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(text[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _text(el: ET.Element | None, *tags: str) -> str:
    """Try multiple child tags and return first non-empty text."""
    if el is None:
        return ''
    for tag in tags:
        child = el.find(tag) or el.find(f'atom:{tag}', NS)
        if child is not None and child.text:
            return child.text.strip()
    return ''


def _parse_feed(xml_text: str, source: dict, cutoff: datetime) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.error('%s: XML parse error — %s', source['name'], exc)
        return items

    # Detect RSS vs Atom
    is_atom = root.tag.startswith('{http://www.w3.org/2005/Atom}') or root.tag == 'feed'
    entries = (
        root.findall('{http://www.w3.org/2005/Atom}entry')
        if is_atom
        else root.findall('.//item')
    )

    for entry in entries:
        if is_atom:
            title = _text(entry, '{http://www.w3.org/2005/Atom}title')
            link_el = entry.find('{http://www.w3.org/2005/Atom}link')
            link = link_el.get('href', '') if link_el is not None else ''
            summary = (
                _text(entry, '{http://www.w3.org/2005/Atom}summary',
                      '{http://www.w3.org/2005/Atom}content')
            )
            date_text = _text(entry, '{http://www.w3.org/2005/Atom}updated',
                              '{http://www.w3.org/2005/Atom}published')
        else:
            title = _text(entry, 'title')
            link = _text(entry, 'link')
            summary = _text(entry, 'description', 'content:encoded')
            date_text = (_text(entry, 'pubDate') or
                         _text(entry, '{http://purl.org/dc/elements/1.1/}date'))

        ts = _parse_date(date_text)
        if ts and ts < cutoff:
            continue

        # Strip HTML tags from summary
        import re
        summary_clean = re.sub(r'<[^>]+>', ' ', summary or '').strip()

        items.append({
            'source_id': source['id'],
            'source_name': source['name'],
            'tier': source['tier'],
            'domains': source.get('domains', []),
            'title': title,
            'text': f"{title}. {summary_clean}".strip('. '),
            'full_content': summary_clean,
            'url': link,
            'timestamp': ts.isoformat() if ts else None,
            'verification_status': 'confirmed' if source['tier'] == 1 else 'reported',
            'method': 'rss',
        })

    return items


def ingest_rss(target_date: datetime, config: dict | None = None) -> list[dict]:
    sources = load_rss_sources(config)
    cutoff = target_date - timedelta(hours=MAX_ITEM_AGE_HOURS)
    all_items: list[dict] = []
    failed_tier1: list[str] = []

    for source in sources:
        url = source.get('url')
        if not url:
            log.warning('Source %s has no URL — skipping', source['id'])
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            items = _parse_feed(resp.text, source, cutoff)
            # Apply relevance filter to general feeds (Tier 1 items pass unconditionally)
            from ingest.relevance import filter_relevant
            items = filter_relevant(items)
            all_items.extend(items)
            log.info('%-35s %3d items', source['name'], len(items))
        except Exception as exc:
            log.error('Failed to fetch %s: %s', source['name'], exc)
            if source['tier'] == 1:
                failed_tier1.append(source['name'])

        time.sleep(REQUEST_DELAY)

    if failed_tier1:
        log.error('TIER 1 RSS FAILURES: %s', ', '.join(failed_tier1))

    return all_items
