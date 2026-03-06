"""
Shared pipeline utilities.

Centralises helpers used across multiple modules:
  - strip_html()           : remove HTML tags and decode common entities
  - make_base_url()        : extract scheme+host from a URL
  - resolve_relative_url() : make relative hrefs absolute
  - utc_now_iso()          : current UTC timestamp in ISO-8601 with +00:00 suffix
  - truncate_words()       : truncate text at a word boundary
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')

_HTML_ENTITIES: dict[str, str] = {
    '&amp;':  '&',
    '&lt;':   '<',
    '&gt;':   '>',
    '&quot;': '"',
    '&apos;': "'",
    '&nbsp;': ' ',
    '&#39;':  "'",
    '&#34;':  '"',
}


def strip_html(text: str) -> str:
    """Strip HTML tags and decode common entities, then collapse whitespace."""
    if not text:
        return ''
    result = _HTML_TAG_RE.sub(' ', text)
    for entity, char in _HTML_ENTITIES.items():
        result = result.replace(entity, char)
    return _WHITESPACE_RE.sub(' ', result).strip()


def make_base_url(url: str) -> str:
    """Return scheme+host (e.g. 'https://www.reuters.com') from a full URL."""
    if not url:
        return ''
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f'{parsed.scheme}://{parsed.netloc}'
    return ''


def resolve_relative_url(href: str, base_url: str) -> str:
    """
    Resolve a potentially relative href to an absolute URL.
    Returns href unchanged if already absolute; prepends base_url if relative.
    """
    if not href:
        return ''
    if href.startswith('http'):
        return href
    base = make_base_url(base_url)
    if not base:
        return href
    if not href.startswith('/'):
        href = '/' + href
    return base + href


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string with +00:00 suffix."""
    return datetime.now(timezone.utc).isoformat()


def truncate_words(text: str, max_chars: int) -> str:
    """
    Truncate text to at most max_chars, breaking at a word boundary.
    Appends a horizontal ellipsis if truncated.
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    return truncated.rstrip(' .,;:') + '\u2026'
