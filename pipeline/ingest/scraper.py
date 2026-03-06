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
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as exc:
        log.error('Fetch failed %s: %s', url, exc)
        return None


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


def _extract_d6_marine(source: dict, date: datetime) -> list[dict]:
    """
    Generic extractor for D6 war risk / maritime finance sources.
    Targets industry trade press, regulatory bodies, and broker sites.

    Strategy:
      1. Try structured article/press-release card selectors first.
      2. Fall back to heading + lede extraction.
      3. Final fallback: generic paragraph extraction.

    Used by: lloyds_mkt_bulletins, jwc_listed_areas, imo_circular,
    ig_pic_circulars, nato_shipping_centre, usmto, dryad_global,
    ambrey_analytics, eos_risk, icc_imb, iumi_news, marsh_marine,
    willis_marine, aon_marine, gallagher_marine, clarksons_research,
    intercargo_news, intertanko_news, swissre_sigma, munichre_marine,
    credit_agricole_shipping, unctad_maritime, iras_war_risk,
    moodys_shipping, signal_ocean.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []

    # ── Strategy 1: structured card selectors common in trade press ──
    card_selectors = [
        'article',
        '.news-item', '.press-release', '.bulletin-item', '.update-item',
        '.card', '.entry', '.post', '.alert-item', '.advisory',
        'li.media', 'li.news', '.media-object',
        '[class*="bulletin"]', '[class*="advisory"]', '[class*="article"]',
    ]
    cards = []
    for sel in card_selectors:
        candidates = soup.select(sel)
        if candidates:
            cards = candidates
            break

    for card in cards[:20]:
        heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = (
            heading.find('a', href=True)
            or card.find('a', href=True)
        )
        link = ''
        if link_el and isinstance(link_el, dict):
            link = link_el.get('href', '')
        elif link_el:
            link = link_el.get('href', '')
        if link and not link.startswith('http'):
            from urllib.parse import urlparse
            base = urlparse(source['url'])
            link = f'{base.scheme}://{base.netloc}{link}'
        excerpt_el = card.find('p') or card.find('[class*="summary"]')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if items:
        return items[:15]

    # ── Strategy 2: heading + following lede paragraph ──
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4'])[:20]:
        title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = heading.find('a', href=True)
        link = ''
        if link_el:
            link = link_el.get('href', '')
            if link and not link.startswith('http'):
                from urllib.parse import urlparse
                base = urlparse(source['url'])
                link = f'{base.scheme}://{base.netloc}{link}'
        # Lede: next sibling <p>
        sibling = heading.find_next_sibling('p')
        excerpt = _clean(sibling.get_text()) if sibling else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if items:
        return items[:10]

    # ── Strategy 3: paragraph fallback ──
    return _extract_generic(source, soup, date, max_items=8)


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
            from urllib.parse import urlparse
            base = urlparse(source['url'])
            link = f'{base.scheme}://{base.netloc}{link}'
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
# All reuters_* sources use _extract_reuters — the extractor reads source['url']
# dynamically, so the same function handles every Reuters topic page correctly.

EXTRACTORS: dict[str, callable] = {
    # ── Reuters topic pages (all 16 sources → same URL-driven extractor) ──
    'reuters_mideast':           _extract_reuters,
    'reuters_iran':              _extract_reuters,
    'reuters_israel':            _extract_reuters,
    'reuters_yemen':             _extract_reuters,
    'reuters_iraq':              _extract_reuters,
    'reuters_lebanon':           _extract_reuters,
    'reuters_saudi':             _extract_reuters,
    'reuters_energy':            _extract_reuters,
    'reuters_commodities':       _extract_reuters,
    'reuters_aerospace_defense': _extract_reuters,
    'reuters_cybersecurity':     _extract_reuters,
    'reuters_us':                _extract_reuters,
    'reuters_europe':            _extract_reuters,
    'reuters_china':             _extract_reuters,
    'reuters_russia':            _extract_reuters,
    'reuters_markets':           _extract_reuters,
    'reuters_legal':             _extract_reuters,
    # ── Other Tier 1 scrape sources ──
    'ctpiw_evening':             _extract_ctpiw,
    'ctpiw_morning':             _extract_ctpiw,
    'centcom':                   _extract_centcom,
    'ukmto':                     _extract_ukmto,
    'idf_spokesperson':          _extract_idf,
    # ── Tier 2 scrape sources ──
    'alma_research':             _extract_alma,
    'iran_intl':                 _extract_iran_intl,
    'rudaw':                     _extract_generic,
    'netblocks':                 _extract_netblocks,
    # bbc_persian primary method is rss but extractor is kept live for
    # manual/fallback scrape calls (e.g. when RSS is rate-limited)
    'bbc_persian':               _extract_bbc_persian,
    # ── Energy / economic ──
    'eia_weekly':                _extract_eia,
    'opec_statements':           _extract_opec,
    # ── D6 — Tier 1 authoritative bodies ──
    'lloyds_mkt_bulletins':      _extract_d6_marine,
    'jwc_listed_areas':          _extract_d6_marine,
    'imo_circular':              _extract_d6_marine,
    'ig_pic_circulars':          _extract_d6_marine,
    'nato_shipping_centre':      _extract_d6_marine,
    'usmto':                     _extract_d6_marine,
    # ── D6 — Tier 2 maritime intelligence firms ──
    'dryad_global':              _extract_d6_marine,
    'ambrey_analytics':          _extract_d6_marine,
    'eos_risk':                  _extract_d6_marine,
    'icc_imb':                   _extract_d6_marine,
    'iumi_news':                 _extract_d6_marine,
    # ── D6 — Tier 2 brokers / associations ──
    'marsh_marine':              _extract_d6_marine,
    'willis_marine':             _extract_d6_marine,
    'aon_marine':                _extract_d6_marine,
    'gallagher_marine':          _extract_d6_marine,
    'intercargo_news':           _extract_d6_marine,
    'intertanko_news':           _extract_d6_marine,
    'clarksons_research':        _extract_d6_marine,
    # ── D6 — Tier 3 specialist triggers ──
    'swissre_sigma':             _extract_d6_marine,
    'munichre_marine':           _extract_d6_marine,
    'credit_agricole_shipping':  _extract_d6_marine,
    'unctad_maritime':           _extract_d6_marine,
    'iras_war_risk':             _extract_d6_marine,
    'moodys_shipping':           _extract_d6_marine,
    'signal_ocean':              _extract_d6_marine,
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
