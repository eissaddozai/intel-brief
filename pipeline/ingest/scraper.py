"""
Scraper using requests + BeautifulSoup4. No Playwright or headless browser required.

HONEST LIMITATIONS
  - Cannot execute JavaScript. Pages that render entirely in JS will return
    empty or minimal content. Affected sources are marked status: likely in
    sources.yaml — they work if the server sends static HTML.
  - Paywalled sources (Haaretz) are disabled in sources.yaml.
  - CSS selectors in each extractor reflect the site structure as of 2026-03.
    Site redesigns will break extraction silently — run `brief check-sources`
    to detect failures.
  - Rate limiting: 1.5s delay between requests. Some sites will 429 anyway.
"""

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 20
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def load_scrape_sources() -> list[dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [
        s for s in data.get('sources', [])
        if s.get('method') == 'scrape' and s.get('enabled', True)
    ]


def _fetch(url: str) -> BeautifulSoup | None:
    """GET a URL and return a BeautifulSoup, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as exc:
        log.error('Fetch failed for %s: %s', url, exc)
        return None


def _clean(text: str) -> str:
    """Collapse whitespace, strip leading/trailing junk."""
    return re.sub(r'\s+', ' ', text).strip()


def _make_item(source: dict, title: str, text: str, url: str,
               timestamp: str | None = None) -> dict:
    return {
        'source_id': source['id'],
        'source_name': source['name'],
        'tier': source['tier'],
        'domains': source.get('domains', []),
        'title': title[:200],
        'text': _clean(f'{title}. {text}')[:2000],
        'full_content': _clean(text)[:2000],
        'url': url,
        'timestamp': timestamp or datetime.now(timezone.utc).isoformat(),
        'verification_status': 'confirmed' if source['tier'] == 1 else 'reported',
        'method': 'scrape',
    }


# ─────────────────────────────────────────────────────────────────────────────
# Source-specific extractors
# Each returns list[dict] (RawItems). Returns [] on any failure.
# ─────────────────────────────────────────────────────────────────────────────

def _extract_ctpiw(source: dict, date: datetime) -> list[dict]:
    """
    CTP-ISW Iran War Updates category page.
    Extracts article title + excerpt from the article listing.
    Selectors target the standard Critical Threats article card layout.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    # Try article cards — each has a heading and excerpt paragraph
    for card in soup.select('article, .analysis-item, .post')[:10]:
        heading = card.find(['h1', 'h2', 'h3', 'h4'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        link_el = card.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        if not link.startswith('http'):
            link = 'https://www.criticalthreats.org' + link
        if title and len(title) > 20:
            items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        # Fallback: grab all substantial paragraphs from main content
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:15]


def _extract_centcom(source: dict, date: datetime) -> list[dict]:
    """
    CENTCOM news article listing.
    US government site — static HTML, reliable.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for article in soup.select('.article-item, .news-item, li.article, article')[:20]:
        heading = article.find(['h1', 'h2', 'h3', 'h4', 'a'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        link_el = article.find('a', href=True) or heading
        link = link_el.get('href', source['url']) if hasattr(link_el, 'get') else source['url']
        if link and not link.startswith('http'):
            link = 'https://www.centcom.mil' + link
        summary_el = article.find('p')
        summary = _clean(summary_el.get_text()) if summary_el else ''
        if title and len(title) > 15:
            items.append(_make_item(source, title, summary, link or source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:15]


def _extract_ukmto(source: dict, date: datetime) -> list[dict]:
    """
    UKMTO recent incidents page.
    Targets table rows or incident div blocks.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []

    # Try structured table first
    for row in soup.select('table tr')[1:21]:  # skip header, cap at 20
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            continue
        text = ' | '.join(_clean(c.get_text()) for c in cells)
        if len(text) > 20:
            items.append(_make_item(
                source,
                title=f'UKMTO Incident: {text[:100]}',
                text=text,
                url=source['url'],
                timestamp=date.isoformat(),
            ))

    # Fallback to div blocks if no table
    if not items:
        for block in soup.select('.incident, .alert, .warning, article, .entry')[:15]:
            text = _clean(block.get_text())
            if len(text) > 30:
                items.append(_make_item(
                    source,
                    title=text[:100],
                    text=text,
                    url=source['url'],
                    timestamp=date.isoformat(),
                ))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items


def _extract_alma(source: dict, date: datetime) -> list[dict]:
    """
    Alma Research WordPress category page.
    Extracts article title + excerpt from post cards.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for post in soup.select('.post, article, .entry, .blog-post')[:10]:
        heading = post.find(['h1', 'h2', 'h3'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        link_el = heading.find('a', href=True) or post.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        excerpt_el = post.find('p') or post.find('.excerpt')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        if title and len(title) > 15:
            items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=8)

    return items[:10]


def _extract_iran_intl(source: dict, date: datetime) -> list[dict]:
    """
    Iran International homepage.
    Extracts article headlines — note: heavily JS-rendered, so this may
    only return content from the static shell. Whatever we get is better
    than nothing.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('h1, h2, h3, h4, .headline, .article-title')[:20]:
        title = _clean(el.get_text())
        if len(title) < 20:
            continue
        link_el = el.find('a', href=True) or el.parent.find('a', href=True) if el.parent else None
        link = link_el['href'] if link_el else source['url']
        if link and not link.startswith('http'):
            link = 'https://www.iranintl.com' + link
        items.append(_make_item(source, title, '', link or source['url'], date.isoformat()))

    return items[:10]


def _extract_bbc_persian(source: dict, date: datetime) -> list[dict]:
    """BBC Persian homepage. Static HTML — headline extraction is reliable."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('h3, h2, .media__title, .gs-c-promo-heading')[:20]:
        title = _clean(el.get_text())
        if len(title) < 15:
            continue
        link_el = el.find('a', href=True) or el.parent.find('a', href=True) if el.parent else None
        link = link_el['href'] if link_el else source['url']
        if link and link.startswith('/'):
            link = 'https://www.bbc.com' + link
        items.append(_make_item(source, title, '', link or source['url'], date.isoformat()))

    return items[:10]


def _extract_netblocks(source: dict, date: datetime) -> list[dict]:
    """
    NetBlocks.org — report and alert headlines.
    Static site; reliable with plain requests.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for article in soup.select('article, .report, .post, .entry')[:10]:
        heading = article.find(['h1', 'h2', 'h3'])
        title = _clean(heading.get_text()) if heading else ''
        if len(title) < 15:
            continue
        link_el = article.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        if link and not link.startswith('http'):
            link = 'https://netblocks.org' + link
        excerpt_el = article.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=5)

    return items


def _extract_eia(source: dict, date: datetime) -> list[dict]:
    """
    EIA Weekly Petroleum Status Report page.
    Extracts the main summary table and headline figures.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    # Look for the weekly report summary section
    for section in soup.select('.report-section, .summary, table, .highlights')[:5]:
        text = _clean(section.get_text())
        if len(text) < 50:
            continue
        items.append(_make_item(
            source,
            title='EIA Weekly Petroleum Status',
            text=text[:1000],
            url=source['url'],
            timestamp=date.isoformat(),
        ))
        break

    if not items:
        items = _extract_generic(source, soup, date, max_items=5)

    return items


def _extract_opec(source: dict, date: datetime) -> list[dict]:
    """OPEC press release listing."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('li a, .press-release a, td a, h3 a')[:10]:
        title = _clean(el.get_text())
        if len(title) < 20:
            continue
        link = el.get('href', source['url'])
        if link and not link.startswith('http'):
            link = 'https://www.opec.org' + link
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:8]


def _extract_generic(source: dict, soup: BeautifulSoup, date: datetime,
                     max_items: int = 10) -> list[dict]:
    """
    Last-resort extractor: collect substantial <p> tags.
    This is a dumb fallback — it will pull whatever text the server returns.
    """
    items = []
    paras = [_clean(p.get_text()) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 80]
    # Chunk into groups of 3 paragraphs
    for i in range(0, min(len(paras), max_items * 3), 3):
        chunk = ' '.join(paras[i:i+3])
        if chunk:
            items.append(_make_item(
                source,
                title=paras[i][:120] if paras[i:] else 'Extract',
                text=chunk,
                url=source['url'],
                timestamp=date.isoformat(),
            ))
        if len(items) >= max_items:
            break
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTORS = {
    'ctpiw_evening': _extract_ctpiw,
    'ctpiw_morning': _extract_ctpiw,
    'centcom': _extract_centcom,
    'ukmto': _extract_ukmto,
    'alma_research': _extract_alma,
    'iran_intl': _extract_iran_intl,
    'bbc_persian': _extract_bbc_persian,
    'netblocks': _extract_netblocks,
    'eia_weekly': _extract_eia,
    'opec_statements': _extract_opec,
}


def ingest_scrape(target_date: datetime, config: dict | None = None) -> list[dict]:
    """
    Scrape all enabled scrape-method sources.
    Returns list of RawItem dicts.
    """
    sources = load_scrape_sources()
    all_items: list[dict] = []

    for source in sources:
        url = source.get('url')
        if not url:
            log.warning('Source %s has no URL — skipping', source['id'])
            continue

        extractor = EXTRACTORS.get(source['id'])
        if extractor is None:
            log.warning('%s: no extractor defined — using generic', source['id'])
            soup = _fetch(url)
            items = _extract_generic(source, soup, target_date) if soup else []
        else:
            try:
                items = extractor(source, target_date)
            except Exception as exc:
                log.error('%s: extractor failed — %s', source['id'], exc)
                items = []

        all_items.extend(items)
        log.info('%-35s %3d items', source['name'], len(items))
        time.sleep(REQUEST_DELAY)

    return all_items
