#!/usr/bin/env python3
"""
Bridge script: converts raw fetch output (scratch/raw/<timestamp>/) into
the pipeline's raw_YYYYMMDD.json format for triage consumption.

Reads .raw + .meta files from the latest fetch directory, parses RSS/XML
and HTML content, applies relevance filtering, and writes items to
pipeline/.cache/raw_YYYYMMDD.json.

Usage:
    python scripts/parse_raw_sources.py                    # latest fetch dir, today's date
    python scripts/parse_raw_sources.py --date 2026-03-07  # explicit date
    python scripts/parse_raw_sources.py --raw-dir scratch/raw/20260307_031748
"""

import argparse
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / 'pipeline'
SCRATCH_RAW = REPO_ROOT / 'scratch' / 'raw'
CACHE_DIR = PIPELINE_DIR / '.cache'

sys.path.insert(0, str(PIPELINE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('parse_raw')

# Reuse the pipeline's relevance filter
from ingest.relevance import filter_relevant, RELEVANCE_KEYWORDS

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_ITEM_AGE_HOURS = 48
_HTML_TAG_RE = re.compile(r'<[^>]+>')

# RSS / Atom namespace map (matches rss_ingest.py)
NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


# ─── Date parsing (from rss_ingest.py) ────────────────────────────────────────

def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(text[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


# ─── XML helper ───────────────────────────────────────────────────────────────

def _text(el: ET.Element | None, *tags: str) -> str:
    if el is None:
        return ''
    for tag in tags:
        child = el.find(tag)
        if child is None:
            child = el.find(f'{{http://www.w3.org/2005/Atom}}{tag}')
        if child is not None and child.text:
            return child.text.strip()
    return ''


# ─── RSS/Atom parser (adapted from rss_ingest._parse_feed) ───────────────────

def parse_rss(xml_text: str, meta: dict, cutoff: datetime) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning('%s: XML parse error: %s', meta['id'], exc)
        return items

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
            summary = _text(entry, '{http://www.w3.org/2005/Atom}summary',
                            '{http://www.w3.org/2005/Atom}content')
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

        summary_clean = _HTML_TAG_RE.sub(' ', summary or '').strip()
        # Collapse whitespace
        summary_clean = re.sub(r'\s+', ' ', summary_clean)

        items.append({
            'source_id': meta['id'],
            'source_name': _source_name(meta['id']),
            'tier': meta['tier'],
            'domains': _source_domains(meta['id']),
            'title': title,
            'text': f"{title}. {summary_clean}".strip('. '),
            'full_content': summary_clean,
            'url': link,
            'timestamp': ts.isoformat() if ts else None,
            'verification_status': 'confirmed' if meta['tier'] == 1 else 'reported',
            'method': 'rss',
        })

    return items


# ─── HTML parser for scraped pages ────────────────────────────────────────────

def parse_html(html_text: str, meta: dict, cutoff: datetime) -> list[dict]:
    """Extract headline-like chunks from scraped HTML pages."""
    items: list[dict] = []

    # Extract text from headings and links that look like headlines
    # Pattern: <h1-h3>, <a> with substantial text, <title>
    headline_patterns = [
        re.compile(r'<h[1-3][^>]*>(.*?)</h[1-3]>', re.DOTALL | re.IGNORECASE),
        re.compile(r'<a[^>]+href="([^"]*)"[^>]*>([^<]{20,})</a>', re.DOTALL | re.IGNORECASE),
        re.compile(r'<title[^>]*>(.*?)</title>', re.DOTALL | re.IGNORECASE),
    ]

    seen_titles: set[str] = set()

    # Extract from headings
    for pattern in headline_patterns:
        for match in pattern.finditer(html_text):
            if pattern.groups == 2:
                # <a> pattern — group 1 is href, group 2 is text
                link = match.group(1)
                raw_title = match.group(2)
            else:
                link = meta.get('url', '')
                raw_title = match.group(1)

            title = _HTML_TAG_RE.sub('', raw_title).strip()
            title = re.sub(r'\s+', ' ', title)

            if not title or len(title) < 15:
                continue
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            items.append({
                'source_id': meta['id'],
                'source_name': _source_name(meta['id']),
                'tier': meta['tier'],
                'domains': _source_domains(meta['id']),
                'title': title,
                'text': title,
                'full_content': '',
                'url': link if link.startswith('http') else meta.get('url', ''),
                'timestamp': meta.get('timestamp'),
                'verification_status': 'confirmed' if meta['tier'] == 1 else 'reported',
                'method': 'scrape',
            })

    # Also try to extract <p> text near headings for richer content
    paragraph_re = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL | re.IGNORECASE)
    paragraphs = []
    for m in paragraph_re.finditer(html_text):
        text = _HTML_TAG_RE.sub('', m.group(1)).strip()
        text = re.sub(r'\s+', ' ', text)
        if len(text) > 50:
            paragraphs.append(text)

    # Attach paragraph content to items as full_content enrichment
    if paragraphs and items:
        combined_text = ' '.join(paragraphs[:10])  # First 10 paragraphs
        for item in items:
            if not item['full_content']:
                item['full_content'] = combined_text[:1000]
                item['text'] = f"{item['title']}. {combined_text[:500]}".strip('. ')

    return items


# ─── Source metadata lookup ───────────────────────────────────────────────────

_SOURCES_YAML_CACHE: dict | None = None

def _load_sources_yaml() -> dict:
    global _SOURCES_YAML_CACHE
    if _SOURCES_YAML_CACHE is None:
        sources_file = PIPELINE_DIR / 'ingest' / 'sources.yaml'
        try:
            import yaml
            data = yaml.safe_load(sources_file.read_text(encoding='utf-8'))
            _SOURCES_YAML_CACHE = {
                s['id']: s for s in data.get('sources', [])
            }
        except ImportError:
            # PyYAML not installed — parse minimally with regex
            log.warning('PyYAML not available; falling back to regex source parsing')
            _SOURCES_YAML_CACHE = _parse_sources_yaml_fallback(sources_file)
    return _SOURCES_YAML_CACHE


def _parse_sources_yaml_fallback(path: Path) -> dict:
    """Minimal YAML parser for sources.yaml — extracts id, name, tier, domains."""
    result: dict = {}
    text = path.read_text(encoding='utf-8')
    # Split on source entries
    entries = re.split(r'\n  - id:\s*', text)
    for entry in entries[1:]:  # Skip header
        lines = entry.strip().split('\n')
        source_id = lines[0].strip()
        source: dict = {'id': source_id}
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('name:'):
                source['name'] = line.split(':', 1)[1].strip().strip('"\'')
            elif line.startswith('tier:'):
                try:
                    source['tier'] = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith('domains:'):
                domains_str = line.split(':', 1)[1].strip()
                source['domains'] = re.findall(r'd\d', domains_str)
        result[source_id] = source
    return result


def _source_name(source_id: str) -> str:
    sources = _load_sources_yaml()
    s = sources.get(source_id)
    if s:
        return s.get('name', source_id)
    # Fallback: prettify the ID
    return source_id.replace('_', ' ').title()


def _source_domains(source_id: str) -> list[str]:
    sources = _load_sources_yaml()
    s = sources.get(source_id)
    if s:
        return s.get('domains', [])
    return []


# ─── Main orchestrator ────────────────────────────────────────────────────────

def find_latest_raw_dir() -> Path:
    """Find the most recent scratch/raw/<timestamp>/ directory."""
    if not SCRATCH_RAW.exists():
        log.critical('No scratch/raw/ directory found. Run /intel-ingest first.')
        sys.exit(1)

    dirs = sorted(
        [d for d in SCRATCH_RAW.iterdir() if d.is_dir() and not d.name.startswith('.')],
        reverse=True,
    )
    if not dirs:
        log.critical('No fetch directories in scratch/raw/. Run /intel-ingest first.')
        sys.exit(1)

    latest = dirs[0]
    log.info('Using raw directory: %s', latest.name)
    return latest


def parse_raw_directory(raw_dir: Path, target_date: datetime) -> list[dict]:
    """Parse all .raw + .meta files in a fetch directory into items."""
    cutoff = target_date - timedelta(hours=MAX_ITEM_AGE_HOURS)
    all_items: list[dict] = []
    meta_files = sorted(raw_dir.glob('*.meta'))

    if not meta_files:
        log.critical('No .meta files found in %s', raw_dir)
        sys.exit(1)

    log.info('Found %d source files to parse', len(meta_files))

    rss_count = 0
    html_count = 0
    empty_count = 0

    for meta_path in meta_files:
        source_id = meta_path.stem
        raw_path = meta_path.with_suffix('.raw')

        # Read meta
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception as exc:
            log.warning('Cannot read meta %s: %s', meta_path.name, exc)
            continue

        # Skip failed fetches
        http_code = meta.get('http_code', 0)
        if http_code >= 400 or http_code == 0:
            log.debug('Skipping %s (HTTP %s)', source_id, http_code)
            continue

        # Read raw content
        if not raw_path.exists():
            log.debug('No .raw file for %s', source_id)
            continue

        try:
            content = raw_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            log.warning('Cannot read %s', raw_path.name)
            continue

        if len(content.strip()) < 100:
            empty_count += 1
            continue

        # Determine parse method
        method = meta.get('method', 'scrape')
        is_xml = (
            method == 'rss' or
            content.lstrip()[:100].startswith('<?xml') or
            '<rss' in content[:500] or
            '<feed' in content[:500]
        )

        if is_xml:
            items = parse_rss(content, meta, cutoff)
            rss_count += 1
        else:
            items = parse_html(content, meta, cutoff)
            html_count += 1

        if items:
            log.info('  %-30s %3d items (%s)', source_id, len(items), 'rss' if is_xml else 'html')
        all_items.extend(items)

    log.info('Parsed %d RSS feeds, %d HTML pages (%d empty/tiny skipped)',
             rss_count, html_count, empty_count)
    log.info('Total raw items before relevance filter: %d', len(all_items))

    # Apply relevance filter
    relevant = filter_relevant(all_items)
    log.info('After relevance filter: %d items', len(relevant))

    return relevant


def main():
    parser = argparse.ArgumentParser(description='Parse raw fetched sources into pipeline items')
    parser.add_argument('--date', default=None, help='Target date YYYY-MM-DD (default: today)')
    parser.add_argument('--raw-dir', default=None, help='Explicit raw directory path')
    args = parser.parse_args()

    # Determine target date
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        target_date = datetime.now(timezone.utc)

    # Find raw directory
    if args.raw_dir:
        raw_dir = Path(args.raw_dir)
        if not raw_dir.is_absolute():
            raw_dir = REPO_ROOT / raw_dir
    else:
        raw_dir = find_latest_raw_dir()

    # Parse
    items = parse_raw_directory(raw_dir, target_date)

    if not items:
        log.critical('No items extracted. Check source content and relevance keywords.')
        sys.exit(1)

    # Write output
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = CACHE_DIR / f'raw_{target_date.strftime("%Y%m%d")}.json'
    out_file.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding='utf-8')

    # Summary
    tier_counts = {}
    for item in items:
        t = item.get('tier', 0)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    log.info('Output: %s (%d items)', out_file, len(items))
    log.info('Tier distribution: %s', {f'T{k}': v for k, v in sorted(tier_counts.items())})

    # Domain preview
    domain_counts: dict[str, int] = {}
    for item in items:
        for d in item.get('domains', []):
            domain_counts[d] = domain_counts.get(d, 0) + 1
    log.info('Domain distribution (source registry): %s', domain_counts)

    print(f'\nWrote {len(items)} items to {out_file}')


if __name__ == '__main__':
    main()
