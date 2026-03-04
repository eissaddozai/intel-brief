"""
Playwright-based scraper for JS-rendered live blogs and static pages.
Handles date-interpolated URLs (CNN, CNBC, NBC, CBS) and direct scrapes
(CTP-ISW, UKMTO, Alma Research, Iran International, Al Jazeera tracker).
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).parent / 'sources.yaml'


def load_scrape_sources() -> list[dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    return [s for s in data.get('sources', []) if s.get('method') == 'scrape']


def interpolate_url(pattern: str, date: datetime) -> str:
    """Replace {YYYY-MM-DD} and component tokens in URL patterns."""
    return (
        pattern
        .replace('{YYYY-MM-DD}', date.strftime('%Y-%m-%d'))
        .replace('{YYYY}', date.strftime('%Y'))
        .replace('{MM}', date.strftime('%m'))
        .replace('{DD}', date.strftime('%d'))
    )


def scrape_page(url: str, source: dict, date: datetime) -> list[dict]:
    """
    Scrape a single URL with Playwright.
    Returns a list of RawItem dicts extracted from the page.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error('playwright not installed. Run: pip install playwright && playwright install chromium')
        return []

    items: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (compatible; CSE-Intel-Brief/1.0; Research)',
            java_script_enabled=True,
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=30_000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)  # Allow JS to render

            # Handle cookie/GDPR banners
            for selector in ['button[id*="accept"]', 'button[class*="accept"]',
                             '[data-testid*="accept"]', '#onetrust-accept-btn-handler']:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            # Extract content based on source type
            source_id = source['id']

            if source_id in ('cnn_live', 'nbc_live', 'cbs_live'):
                items = _extract_live_blog_items(page, source, date)
            elif source_id == 'cnbc_live':
                items = _extract_cnbc_items(page, source, date)
            elif source_id in ('ctpiw_evening', 'ctpiw_morning'):
                items = _extract_ctpiw_items(page, source, date)
            elif source_id == 'ukmto':
                items = _extract_ukmto_items(page, source, date)
            elif source_id == 'alma_research':
                items = _extract_alma_items(page, source, date)
            elif source_id == 'al_jazeera_tracker':
                items = _extract_aj_tracker_items(page, source, date)
            else:
                # Generic text extraction
                items = _extract_generic(page, source, date)

        except Exception as exc:
            log.error('Scrape failed for %s (%s): %s', source['name'], url, exc)
        finally:
            context.close()
            browser.close()

    return items


def _make_item(source: dict, title: str, text: str, url: str,
               timestamp: str | None = None) -> dict:
    return {
        'source_id': source['id'],
        'source_name': source['name'],
        'tier': source['tier'],
        'domains': source.get('domains', []),
        'title': title,
        'text': f'{title}. {text}'.strip(),
        'full_content': text,
        'url': url,
        'timestamp': timestamp,
        'verification_status': 'confirmed' if source['tier'] == 1 else 'reported',
        'method': 'scrape',
    }


def _extract_live_blog_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """Extract timestamped update blocks from a generic live blog page."""
    items = []
    # Try common live blog selectors
    selectors = [
        '[data-component="live-blog-post"]',
        '.live-blog-post',
        '.update-block',
        'article[data-id]',
        '.live-update',
    ]
    for sel in selectors:
        blocks = page.locator(sel).all()
        if blocks:
            for block in blocks[:40]:  # Cap at 40 items per source
                try:
                    text = block.inner_text()
                    if len(text) > 50:
                        items.append(_make_item(
                            source,
                            title=text[:120].split('\n')[0],
                            text=text[:2000],
                            url=page.url,
                            timestamp=date.isoformat(),
                        ))
                except Exception:
                    continue
            break

    if not items:
        # Fallback: extract all paragraphs
        items = _extract_generic(page, source, date)

    return items


def _extract_cnbc_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """CNBC live blog — prioritise energy/market update blocks."""
    items = _extract_live_blog_items(page, source, date)
    # Filter: keep items containing energy/market keywords
    keywords = ['brent', 'wti', 'oil', 'crude', 'gas', 'lng', 'goldman', 'market',
                'barrel', 'energy', 'price', 'hormuz', 'tanker', 'supply']
    filtered = [
        item for item in items
        if any(kw in item['text'].lower() for kw in keywords)
    ]
    return filtered if filtered else items[:10]


def _extract_ctpiw_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """CTP-ISW — look for the evening/morning report article."""
    items = []
    # Find the main report article
    article_selectors = ['article.report', '.analysis-content', 'main article', 'article']
    for sel in article_selectors:
        block = page.locator(sel).first
        try:
            text = block.inner_text()
            if len(text) > 500:
                # Split into paragraphs for granularity
                paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 100]
                for para in paragraphs[:20]:
                    items.append(_make_item(
                        source,
                        title=para[:100],
                        text=para,
                        url=page.url,
                        timestamp=date.isoformat(),
                    ))
                break
        except Exception:
            continue
    return items


def _extract_ukmto_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """UKMTO — extract incident table rows."""
    items = []
    rows = page.locator('table tr').all()
    for row in rows[1:]:  # Skip header
        try:
            text = row.inner_text()
            if len(text) > 30:
                items.append(_make_item(
                    source,
                    title=f'UKMTO Incident: {text[:80]}',
                    text=text,
                    url=page.url,
                    timestamp=date.isoformat(),
                ))
        except Exception:
            continue
    return items


def _extract_alma_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """Alma Research — extract latest daily report."""
    return _extract_ctpiw_items(page, source, date)  # Same pattern


def _extract_aj_tracker_items(page: Any, source: dict, date: datetime) -> list[dict]:
    """Al Jazeera Casualty Tracker — structured HTML table."""
    return _extract_ukmto_items(page, source, date)


def _extract_generic(page: Any, source: dict, date: datetime) -> list[dict]:
    """Fallback: extract all visible paragraph text from the page."""
    items = []
    try:
        paragraphs = page.locator('p').all()
        batch_text = ' '.join(
            p.inner_text() for p in paragraphs[:100]
            if len(p.inner_text()) > 60
        )
        if batch_text:
            # Break into ~500-char chunks
            chunks = [batch_text[i:i+500] for i in range(0, len(batch_text), 500)]
            for chunk in chunks[:15]:
                items.append(_make_item(
                    source,
                    title=chunk[:100],
                    text=chunk,
                    url=page.url,
                    timestamp=date.isoformat(),
                ))
    except Exception as exc:
        log.debug('Generic extraction failed for %s: %s', source['name'], exc)
    return items


def ingest_scrape(target_date: datetime) -> list[dict]:
    """Ingest all scrape-method sources. Returns list of RawItem dicts."""
    sources = load_scrape_sources()
    all_items: list[dict] = []

    for source in sources:
        url_pattern = source.get('url_pattern') or source.get('url')
        if not url_pattern:
            log.warning('Source %s has no URL — skipping', source['id'])
            continue

        url = interpolate_url(url_pattern, target_date)
        log.info('Scraping %s → %s', source['name'], url)

        try:
            items = scrape_page(url, source, target_date)
            all_items.extend(items)
            log.info('%-30s %3d items', source['name'], len(items))
        except Exception as exc:
            log.error('Scrape error for %s: %s', source['name'], exc)
            if source['tier'] == 1:
                log.error('TIER 1 SOURCE FAILED: %s', source['name'])

    return all_items
