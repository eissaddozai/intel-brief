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
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 20

# Rotate User-Agent to reduce bot-detection blocks
_USER_AGENTS = [
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
]


def _browser_headers(url: str) -> dict:
    """
    Generate realistic browser headers for a given URL.
    Bot-blocking sites (Reuters, AP, CENTCOM, IDF, NATO Shipping Centre)
    check User-Agent, Sec-Fetch-*, Referer, and Accept headers.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'

    ua = random.choice(_USER_AGENTS)
    is_chrome = 'Chrome' in ua
    is_firefox = 'Firefox' in ua

    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # Chrome-style Sec-Fetch headers (bot detectors check these)
    # Sec-Fetch-Site: none = typed URL / bookmark (first navigation)
    if is_chrome:
        headers.update({
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Linux"',
        })
    elif is_firefox:
        headers.update({
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })

    return headers


def _build_session() -> requests.Session:
    """Build a requests session with retry logic and connection pooling."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET', 'HEAD'],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


# Module-level session — created once, reused across all fetches in a cycle
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = _build_session()
    return _session


def load_scrape_sources() -> list[dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [
        s for s in data.get('sources', [])
        if s.get('method') == 'scrape' and s.get('enabled', True)
    ]


def _fetch(url: str) -> BeautifulSoup | None:
    """
    Fetch a URL with anti-bot-detection headers. On 401/403, retries
    once with a different User-Agent (many bot-blockers are UA-sensitive).
    """
    session = _get_session()

    for attempt in range(2):
        headers = _browser_headers(url)
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code in (401, 403) and attempt == 0:
                log.warning('Fetch %d on %s — retrying with different UA', resp.status_code, url)
                time.sleep(1.0 + random.random())
                continue
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else '?'
            log.error('Fetch HTTP %s on %s (attempt %d)', status, url, attempt + 1)
            if attempt == 0 and status in (401, 403):
                time.sleep(1.0 + random.random())
                continue
            return None
        except requests.exceptions.ConnectionError as exc:
            log.error('Fetch connection error %s: %s', url, exc)
            return None
        except requests.exceptions.Timeout:
            log.error('Fetch timeout %s (>%ds)', url, REQUEST_TIMEOUT)
            return None
        except Exception as exc:
            log.error('Fetch failed %s: %s', url, exc)
            return None
    return None


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _make_item(source: dict, title: str, text: str, url: str,
               timestamp: str | None = None) -> dict:
    tier = source['tier']
    if tier == 1:
        vstatus = 'confirmed'
    elif tier == 2:
        vstatus = 'reported'
    else:
        vstatus = 'claimed'
    return {
        'source_id': source['id'],
        'source_name': source['name'],
        'tier': tier,
        'domains': source.get('domains', []),
        'title': title[:200],
        'text': _clean(f'{title}. {text}')[:2000],
        'full_content': _clean(text)[:2000],
        'url': url,
        'timestamp': timestamp or datetime.now(timezone.utc).isoformat(),
        'verification_status': vstatus,
        'method': 'scrape',
    }


def _resolve_link(link: str, base_domain: str) -> str:
    """Resolve relative links to absolute URLs."""
    if not link:
        return ''
    if link.startswith('http'):
        return link
    if link.startswith('//'):
        return 'https:' + link
    if link.startswith('/'):
        return base_domain.rstrip('/') + link
    return base_domain.rstrip('/') + '/' + link


# ─────────────────────────────────────────────────────────────────────────────
# Generic article-list extractor (used as base pattern for many sources)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_article_list(
    source: dict,
    date: datetime,
    base_domain: str,
    selectors: list[str] | None = None,
    max_items: int = 15,
    min_title_len: int = 20,
) -> list[dict]:
    """
    Generic article-list scraper. Tries CSS selectors in order to find article
    cards, extracts heading + excerpt + link from each.
    """
    soup = _fetch(source['url'])
    if not soup:
        return []

    default_selectors = [
        'article', '.post', '.entry', '.news-item', '.item',
        '.article-item', '.card', 'li.media', '.blog-post',
    ]
    selectors = selectors or default_selectors

    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    items = []
    for card in cards[:max_items + 5]:
        heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'])
        if not heading:
            continue
        title = _clean(heading.get_text())
        if len(title) < min_title_len:
            continue
        link_el = card.find('a', href=True) or heading.find_parent('a', href=True)
        link = link_el['href'] if link_el else ''
        link = _resolve_link(link, base_domain)
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))
        if len(items) >= max_items:
            break

    if not items:
        items = _extract_generic(source, soup, date, max_items=8)

    return items


# ─────────────────────────────────────────────────────────────────────────────
# Source-specific extractors
# ─────────────────────────────────────────────────────────────────────────────

def _extract_reuters(source: dict, date: datetime) -> list[dict]:
    """Reuters Middle East topic page. Static HTML article listing."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
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
        link = _resolve_link(link, 'https://www.reuters.com')
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=10)

    return items[:20]


def _extract_ap(source: dict, date: datetime) -> list[dict]:
    """AP News Middle East hub page. Headline + excerpt extraction."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    # AP uses various card patterns across redesigns
    selectors = [
        '[data-key="feed-card"]',
        '[class*="FeedCard"]',
        'article', '.PageList-items-item',
        'div[class*="CardHeadline"]',
        '.hub-peek-card',
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    if not cards:
        cards = soup.select('a[href*="/article/"]')

    for card in cards[:25]:
        heading = card.find(['h1', 'h2', 'h3', 'h4', 'span'])
        if not heading:
            # The card itself might be an anchor with text
            title = _clean(card.get_text()) if card.name == 'a' else ''
        else:
            title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = card.find('a', href=True) or (card if card.name == 'a' and card.get('href') else None)
        link = link_el['href'] if link_el else ''
        link = _resolve_link(link, 'https://apnews.com')
        excerpt_el = card.find('p')
        excerpt = _clean(excerpt_el.get_text()) if excerpt_el else ''
        items.append(_make_item(source, title, excerpt, link or source['url'], date.isoformat()))

    if not items:
        items = _extract_generic(source, soup, date, max_items=15)

    return items[:20]


def _extract_ctpiw(source: dict, date: datetime) -> list[dict]:
    """CTP-ISW analysis listing page (criticalthreats.org/analysis)."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.criticalthreats.org',
        selectors=['article', '.analysis-item', '.post', '.entry'],
        max_items=15,
    )


def _extract_centcom(source: dict, date: datetime) -> list[dict]:
    """CENTCOM news listing. US government static HTML."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.centcom.mil',
        selectors=['.article-item', '.news-item', 'article', 'li.media'],
        max_items=15,
        min_title_len=15,
    )


def _extract_ukmto(source: dict, date: datetime) -> list[dict]:
    """UKMTO recent incidents page. Targets table rows then div blocks."""
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
    """IDF Spokesperson press releases."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.idf.il',
        selectors=['.press-release', 'article', '.item', 'li.release'],
        max_items=15,
        min_title_len=15,
    )


def _extract_alma(source: dict, date: datetime) -> list[dict]:
    """Alma Research WordPress category page."""
    return _extract_article_list(
        source, date,
        base_domain='https://israel-alma.org',
        selectors=['.post', 'article', '.entry', '.blog-post'],
        max_items=10,
        min_title_len=15,
    )


def _extract_iran_intl(source: dict, date: datetime) -> list[dict]:
    """Iran International homepage. Heavily JS-rendered — partial content."""
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
        link = _resolve_link(link, 'https://www.iranintl.com')
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:10]


def _extract_bbc_persian(source: dict, date: datetime) -> list[dict]:
    """BBC Persian homepage. Static HTML — reliable headline extraction."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    for el in soup.select('h3, h2, .media__title, .gs-c-promo-heading, [class*="promo"]')[:20]:
        title = _clean(el.get_text())
        if len(title) < 15:
            continue
        link_el = el.find('a', href=True) or (el.parent.find('a', href=True) if el.parent else None)
        link = link_el['href'] if link_el else source['url']
        link = _resolve_link(link, 'https://www.bbc.com')
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:10]


def _extract_netblocks(source: dict, date: datetime) -> list[dict]:
    """NetBlocks.org — report headlines. Static site."""
    return _extract_article_list(
        source, date,
        base_domain='https://netblocks.org',
        selectors=['article', '.report', '.post', '.entry'],
        max_items=10,
        min_title_len=15,
    )


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
        link = _resolve_link(link, 'https://www.opec.org')
        items.append(_make_item(source, title, '', link, date.isoformat()))

    return items[:8]


# ─────────────────────────────────────────────────────────────────────────────
# D6 War Risk Insurance extractors
# ─────────────────────────────────────────────────────────────────────────────

def _extract_lloyds_bulletins(source: dict, date: datetime) -> list[dict]:
    """Lloyd's Market Bulletins page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.lloyds.com',
        selectors=['.bulletin-item', '.news-item', 'article', '.card', '.list-item'],
        max_items=15,
    )


def _extract_jwc_listed_areas(source: dict, date: datetime) -> list[dict]:
    """JWC Listed Areas page — LMA/Lloyd's. Table or listing format."""
    soup = _fetch(source['url'])
    if not soup:
        return []

    items = []
    # Try table extraction first (listed areas are often in tabular form)
    for row in soup.select('table tr')[1:20]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            continue
        text = ' | '.join(_clean(c.get_text()) for c in cells)
        if len(text) > 20:
            items.append(_make_item(
                source,
                title=f'JWC Listed Area: {text[:100]}',
                text=text,
                url=source['url'],
                timestamp=date.isoformat(),
            ))

    if not items:
        items = _extract_article_list(
            source, date,
            base_domain='https://www.lmalloyds.com',
            max_items=10,
        )

    return items


def _extract_imo(source: dict, date: datetime) -> list[dict]:
    """IMO Circulars & Alerts page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.imo.org',
        selectors=['.news-item', '.circular-item', 'article', '.list-item', '.card'],
        max_items=15,
    )


def _extract_igpandi(source: dict, date: datetime) -> list[dict]:
    """International Group of P&I Clubs news page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.igpandi.org',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=15,
    )


def _extract_nato_shipping(source: dict, date: datetime) -> list[dict]:
    """NATO Shipping Centre advisories."""
    return _extract_article_list(
        source, date,
        base_domain='https://shipping.nato.int',
        selectors=['.news-item', 'article', '.advisory', '.card'],
        max_items=15,
    )


def _extract_usmto(source: dict, date: datetime) -> list[dict]:
    """US Maritime Transportation System ISAC news."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.maritimesecurity.org',
        selectors=['.news-item', 'article', '.post', '.alert'],
        max_items=15,
    )


def _extract_lloyds_list(source: dict, date: datetime) -> list[dict]:
    """Lloyd's List insurance/legal section."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.lloydslist.com',
        selectors=['article', '.article-item', '.story', '.card'],
        max_items=12,
    )


def _extract_tradewinds(source: dict, date: datetime) -> list[dict]:
    """TradeWinds insurance section."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.tradewindsnews.com',
        selectors=['article', '.story', '.card', '.news-item'],
        max_items=12,
    )


def _extract_insurance_insider(source: dict, date: datetime) -> list[dict]:
    """Insurance Insider marine section."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.insuranceinsider.com',
        selectors=['article', '.story', '.card', '.news-item'],
        max_items=10,
    )


def _extract_dryad(source: dict, date: datetime) -> list[dict]:
    """Dryad Global maritime security news."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.dryadglobal.com',
        selectors=['article', '.news-item', '.post', '.card', '.blog-post'],
        max_items=12,
    )


def _extract_ambrey(source: dict, date: datetime) -> list[dict]:
    """Ambrey Maritime Security intelligence page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.ambrey.com',
        selectors=['article', '.intelligence-item', '.post', '.card'],
        max_items=10,
    )


def _extract_eos_risk(source: dict, date: datetime) -> list[dict]:
    """EOS Risk Group news."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.eosrisk.com',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=10,
    )


def _extract_iumi(source: dict, date: datetime) -> list[dict]:
    """International Union of Marine Insurance news."""
    return _extract_article_list(
        source, date,
        base_domain='https://iumi.com',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=10,
    )


def _extract_marsh(source: dict, date: datetime) -> list[dict]:
    """Marsh marine risk insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.marsh.com',
        selectors=['article', '.insight-card', '.card', '.post', '.content-item'],
        max_items=10,
    )


def _extract_willis(source: dict, date: datetime) -> list[dict]:
    """WTW marine & cargo insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.wtwco.com',
        selectors=['article', '.insight-card', '.card', '.content-item'],
        max_items=10,
    )


def _extract_aon(source: dict, date: datetime) -> list[dict]:
    """Aon marine risk insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.aon.com',
        selectors=['article', '.insight-card', '.card', '.content-item'],
        max_items=10,
    )


def _extract_clarksons(source: dict, date: datetime) -> list[dict]:
    """Clarksons Research shipping intelligence."""
    return _extract_article_list(
        source, date,
        base_domain='https://sin.clarksons.net',
        selectors=['article', '.news-item', '.card', '.post'],
        max_items=10,
    )


def _extract_intercargo(source: dict, date: datetime) -> list[dict]:
    """INTERCARGO news page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.intercargo.org',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=10,
    )


def _extract_intertanko(source: dict, date: datetime) -> list[dict]:
    """INTERTANKO news page."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.intertanko.com',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=10,
    )


def _extract_icc_imb(source: dict, date: datetime) -> list[dict]:
    """ICC International Maritime Bureau."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.icc-ccs.org',
        selectors=['article', '.news-item', '.post', '.card', '.report'],
        max_items=10,
    )


def _extract_gallagher(source: dict, date: datetime) -> list[dict]:
    """Gallagher marine risk insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.ajg.com',
        selectors=['article', '.insight-card', '.card', '.content-item'],
        max_items=10,
    )


def _extract_signal_ocean(source: dict, date: datetime) -> list[dict]:
    """Signal Ocean blog — vessel tracking insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.signalocean.com',
        selectors=['article', '.blog-post', '.post', '.card'],
        max_items=8,
    )


def _extract_moodys(source: dict, date: datetime) -> list[dict]:
    """Moody's shipping sector research."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.moodys.com',
        selectors=['article', '.research-item', '.card', '.content-item'],
        max_items=8,
    )


def _extract_munichre(source: dict, date: datetime) -> list[dict]:
    """Munich Re marine insights."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.munichre.com',
        selectors=['article', '.content-item', '.card', '.teaser'],
        max_items=8,
    )


def _extract_credit_agricole(source: dict, date: datetime) -> list[dict]:
    """Credit Agricole CIB shipping finance."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.ca-cib.com',
        selectors=['article', '.content-item', '.card', '.insight'],
        max_items=8,
    )


def _extract_unctad(source: dict, date: datetime) -> list[dict]:
    """UNCTAD maritime transport page."""
    return _extract_article_list(
        source, date,
        base_domain='https://unctad.org',
        selectors=['article', '.content-item', '.card', '.publication-item'],
        max_items=8,
    )


def _extract_iras(source: dict, date: datetime) -> list[dict]:
    """IRAS war risk broker news."""
    return _extract_article_list(
        source, date,
        base_domain='https://www.iras.co.uk',
        selectors=['article', '.news-item', '.post', '.card'],
        max_items=8,
    )


def _extract_generic(source: dict, soup: BeautifulSoup, date: datetime,
                     max_items: int = 10) -> list[dict]:
    """
    Last-resort: collect substantial <p> tags or heading+link combos.
    """
    items = []

    # Try heading+link combos first (more structured than raw paragraphs)
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4'], limit=max_items * 2):
        title = _clean(heading.get_text())
        if len(title) < 20:
            continue
        link_el = heading.find('a', href=True) or heading.find_parent('a', href=True)
        link = link_el['href'] if link_el else ''
        if link and not link.startswith('http'):
            link = source['url'].split('/', 3)[:3]
            link = '/'.join(link) if len(link) == 3 else source['url']
        sibling_p = heading.find_next_sibling('p')
        excerpt = _clean(sibling_p.get_text()) if sibling_p else ''
        items.append(_make_item(
            source, title, excerpt, link or source['url'], date.isoformat(),
        ))
        if len(items) >= max_items:
            return items

    # Fallback: collect substantial <p> tags
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
# Every scrape-method source in sources.yaml should have an entry here.
# Sources without a specific extractor fall back to _extract_generic via
# _extract_article_list, but having an entry ensures proper base_domain
# resolution and tailored CSS selectors.

EXTRACTORS: dict[str, Callable] = {
    # ── AP — every entry point ──
    'ap_wire':            _extract_ap,
    'ap_iran':            _extract_ap,
    'ap_iran_nuclear':    _extract_ap,
    'ap_israel_war':      _extract_ap,
    'ap_top_news':        _extract_ap,
    # ── Reuters — full network ──
    'reuters_mideast':    _extract_reuters,
    'reuters_world':      _extract_reuters,
    'reuters_energy':     _extract_reuters,
    'reuters_markets':    _extract_reuters,
    'reuters_commodities': _extract_reuters,
    'reuters_sustainability': _extract_reuters,
    # ── CTP-ISW — everything ──
    'ctpiw_evening':      _extract_ctpiw,
    'ctpiw_morning':      _extract_ctpiw,
    'ctpiw_iran_location': _extract_ctpiw,
    'ctpiw_analysis':     _extract_ctpiw,
    # ── Other Tier 1 ──
    'centcom':            _extract_centcom,
    'ukmto':              _extract_ukmto,
    'idf_spokesperson':   _extract_idf,
    # ── Tier 2 analytical ──
    'alma_research':      _extract_alma,
    'iran_intl':          _extract_iran_intl,
    'bbc_persian':        _extract_bbc_persian,
    # ── Tier 3 triggers ──
    'netblocks':          _extract_netblocks,
    'eia_weekly':         _extract_eia,
    'opec_statements':    _extract_opec,
    # ── D6 Tier 1 regulatory ──
    'lloyds_mkt_bulletins': _extract_lloyds_bulletins,
    'jwc_listed_areas':     _extract_jwc_listed_areas,
    'imo_circular':         _extract_imo,
    'ig_pic_circulars':     _extract_igpandi,
    'nato_shipping_centre': _extract_nato_shipping,
    'usmto':                _extract_usmto,
    # ── D6 Tier 2 market intelligence ──
    'lloyds_list':          _extract_lloyds_list,
    'tradewinds_insurance': _extract_tradewinds,
    'insurance_insider':    _extract_insurance_insider,
    'iumi_news':            _extract_iumi,
    # ── D6 Tier 2 maritime security ──
    'dryad_global':         _extract_dryad,
    'ambrey_analytics':     _extract_ambrey,
    'eos_risk':             _extract_eos_risk,
    'icc_imb':              _extract_icc_imb,
    # ── D6 Tier 2 brokers/associations ──
    'marsh_marine':         _extract_marsh,
    'willis_marine':        _extract_willis,
    'aon_marine':           _extract_aon,
    'gallagher_marine':     _extract_gallagher,
    'intertanko_news':      _extract_intertanko,
    'intercargo_news':      _extract_intercargo,
    # ── D6 Tier 2 shipping data ──
    'clarksons_research':   _extract_clarksons,
    # ── D6 Tier 3 specialist triggers ──
    'signal_ocean':            _extract_signal_ocean,
    'moodys_shipping':         _extract_moodys,
    'munichre_marine':         _extract_munichre,
    'credit_agricole_shipping': _extract_credit_agricole,
    'unctad_maritime':         _extract_unctad,
    'iras_war_risk':           _extract_iras,
}


def ingest_scrape(target_date: datetime, config: dict | None = None) -> list[dict]:
    """
    Scrape all enabled scrape-method sources.
    Returns list of RawItem dicts (unfiltered — relevance filter runs upstream).
    """
    global _session
    _session = _build_session()

    sources = load_scrape_sources()
    all_items: list[dict] = []
    failed_sources: list[str] = []

    for source in sources:
        url = source.get('url')
        if not url:
            log.warning('%s: no URL — skipping', source['id'])
            continue

        extractor = EXTRACTORS.get(source['id'])
        if extractor is None:
            log.info('%s: no dedicated extractor — using generic article list', source['id'])
            # Derive base domain from URL
            parts = url.split('/', 3)
            base_domain = '/'.join(parts[:3]) if len(parts) >= 3 else url
            items = _extract_article_list(source, target_date, base_domain)
        else:
            try:
                items = extractor(source, target_date)
            except Exception as exc:
                log.error('%s: extractor failed — %s', source['id'], exc)
                items = []
                failed_sources.append(source['id'])

        all_items.extend(items)
        log.info('%-35s %3d items  [%s]', source['name'], len(items),
                 'OK' if items else 'EMPTY')
        time.sleep(REQUEST_DELAY)

    _session.close()
    _session = None

    if failed_sources:
        tier1_fails = [s for s in failed_sources
                       if any(src['id'] == s and src['tier'] == 1
                              for src in sources)]
        if tier1_fails:
            log.error('TIER 1 SCRAPE FAILURES: %s', ', '.join(tier1_fails))

    return all_items
