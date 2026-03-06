"""
Web scraper using requests + BeautifulSoup4.

No Playwright or headless browser required. Works with pip install only.

HONEST LIMITATIONS
  - Cannot execute JavaScript. Pages that render entirely client-side will
    return empty or minimal content. Each source's extractor documents
    what it actually gets vs. what it tries to get.
  - Paywalled sources (Haaretz) are disabled in sources.yaml.
  - CSS selectors reflect site structure as of 2026-03. Site redesigns will
    break extraction silently. Run `python pipeline/main.py check-sources`
    to detect failures early.
  - Delay: 1.5s between requests to avoid rate limiting.
"""

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from ingest.http_util import build_session, fetch_with_backoff, HEADERS_BROWSER

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
REQUEST_DELAY = 1.5

# Module-level session — reused across all scrape calls in a single pipeline run
_session = build_session(headers=HEADERS_BROWSER)


def load_scrape_sources() -> list[dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [
        s for s in data.get('sources', [])
        if s.get('method') == 'scrape' and s.get('enabled', True)
    ]


def _fetch(url: str) -> BeautifulSoup | None:
    resp = fetch_with_backoff(url, _session)
    if resp is None:
        return None
    return BeautifulSoup(resp.text, 'html.parser')


def _clean(text: str) -> str:
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
# Extractors
# ─────────────────────────────────────────────────────────────────────────────

def _extract_reuters(source: dict, date: datetime) -> list[dict]:
    """
    Reuters Middle East topic page (reuters.com/world/middle-east/).
    Reuters serves static HTML for topic listing pages — no JS needed.
    Extracts article headline + dateline from the article list.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    # Reuters article cards have a few selector patterns across redesigns
    selectors = [
        'article[data-testid="MediaStoryCard"]',
        'li[data-testid="story-item"]',
        'div[data-testid="media-story-card"]',
        'a.story-card',
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    if not cards:
        # Fallback: all article-level headings with links
        cards = soup.select('article') or soup.select('li')

    for card in cards[:25]:
        heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = card.find('a', href=True)
        link = link_el['href'] if link_el else ''
        if link and link.startswith('/'):
            link = 'https://www.reuters.com' + link
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:20]


def _extract_ctpiw(source: dict, date: datetime) -> list[dict]:
    """
    CTP-ISW Iran War Updates category page (criticalthreats.org).
    Extracts article cards — title + excerpt + link.
    Individual articles may be JS-rendered; we get the index page summaries.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for card in soup.select('article, .analysis-item, .post, .entry')[:15]:
        heading = card.find(['h1', 'h2', 'h3', 'h4'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = card.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        if link and not link.startswith('http'):
            link = 'https://www.criticalthreats.org' + link
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:15]


def _extract_centcom(source: dict, date: datetime) -> list[dict]:
    """
    CENTCOM news listing (centcom.mil/MEDIA/NEWS-ARTICLES/).
    US government site — reliable static HTML.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for card in soup.select('.article-item, .news-item, article, li.media')[:20]:
        heading = card.find(['h1', 'h2', 'h3', 'h4'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < 15:
            continue
        link_el = card.find('a', href=True) or heading.find('a', href=True)
        link = ''
        if link_el and hasattr(link_el, 'get'):
            link = link_el.get('href', '')
        if link and not link.startswith('http'):
            link = 'https://www.centcom.mil' + link
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:15]


def _extract_ukmto(source: dict, date: datetime) -> list[dict]:
    """
    UKMTO recent incidents page (ukmto.org).
    Targets table rows then div blocks.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for row in soup.select('table tr')[1:21]:
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

    if not items:
        for block in soup.select('.incident, .alert, article, .entry')[:15]:
            text = _clean(block.get_text())
            if len(text) > 30:
                items.append(_make_item(source, text[:100], text, source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items


def _extract_idf(source: dict, date: datetime) -> list[dict]:
    """
    IDF Spokesperson press releases (idf.il/en/mini-sites/idf-website/press-releases/).
    Government site with static HTML listing.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for card in soup.select('.press-release, article, .item, li.release')[:20]:
        heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < 15:
            continue
        link_el = card.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        if link and link.startswith('/'):
            link = 'https://www.idf.il' + link
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:15]


def _extract_alma(source: dict, date: datetime) -> list[dict]:
    """
    Alma Research WordPress category page (israel-alma.org).
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
        if len(title) < 15:
            continue
        link_el = heading.find('a', href=True) or post.find('a', href=True)
        link = link_el['href'] if link_el else source['url']
        excerpt_el = post.find('p') or post.find('.excerpt')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link, date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=8)

    return items[:10]


def _extract_iran_intl(source: dict, date: datetime) -> list[dict]:
    """
    Iran International homepage (iranintl.com/en).
    Heavily JS-rendered — may return only static shell content.
    We extract whatever headlines are in the initial HTML payload.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('h1, h2, h3, h4, .headline, .article-title, [class*="title"]')[:25]:
        title = _clean(el.get_text())
        if len(title) < 20:
            continue
        link_el = el.find('a', href=True) or (el.parent.find('a', href=True) if el.parent else None)
        link = link_el['href'] if link_el else source['url']
        if link and not link.startswith('http'):
            link = 'https://www.iranintl.com' + link
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:10]


def _extract_bbc_persian(source: dict, date: datetime) -> list[dict]:
    """BBC Persian homepage. Static HTML — reliable headline extraction."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('h3, h2, .media__title, .gs-c-promo-heading')[:20]:
        title = _clean(el.get_text())
        if len(title) < 15:
            continue
        link_el = el.find('a', href=True) or (el.parent.find('a', href=True) if el.parent else None)
        link = link_el['href'] if link_el else source['url']
        if link and link.startswith('/'):
            link = 'https://www.bbc.com' + link
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:10]


def _extract_netblocks(source: dict, date: datetime) -> list[dict]:
    """NetBlocks.org — report headlines. Static site."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for article in soup.select('article, .report, .post, .entry')[:10]:
        heading = article.find(['h1', 'h2', 'h3'])
        if not heading:
            continue
        title = _clean(heading.get_text())
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
    """EIA Weekly Petroleum Status page. US government — reliable."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for section in soup.select('.report-section, .summary, .highlights, table')[:3]:
        text = _clean(section.get_text())
        if len(text) < 50:
            continue
        items.append(_make_item(
            source,
            title='EIA Weekly Petroleum Status Report',
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
    Last-resort: collect substantial <p> tags.
    This is a dumb fallback — it takes whatever text the server returns.
    """
    items = []
    paras = [_clean(p.get_text()) for p in soup.find_all('p')
             if len(p.get_text(strip=True)) > 80]
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


# ─── Dispatch table ───────────────────────────────────────────────────────────

EXTRACTORS: dict[str, Callable] = {
    'reuters_mideast': _extract_reuters,
    'ctpiw_evening':   _extract_ctpiw,
    'ctpiw_morning':   _extract_ctpiw,
    'centcom':         _extract_centcom,
    'ukmto':           _extract_ukmto,
    'idf_spokesperson': _extract_idf,
    'alma_research':   _extract_alma,
    'iran_intl':       _extract_iran_intl,
    'bbc_persian':     _extract_bbc_persian,
    'netblocks':       _extract_netblocks,
    'eia_weekly':      _extract_eia,
    'opec_statements': _extract_opec,
}


def ingest_scrape(target_date: datetime, config: dict | None = None) -> list[dict]:
    """
    Scrape all enabled scrape-method sources.
    Returns list of RawItem dicts (unfiltered — relevance filter runs upstream).
    """
    sources = load_scrape_sources()
    all_items: list[dict] = []

    for source in sources:
        url = source.get('url')
        if not url:
            log.warning('%s: no URL — skipping', source['id'])
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
