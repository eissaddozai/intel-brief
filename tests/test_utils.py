"""Smoke tests for pipeline utilities."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'pipeline'))

from utils import strip_html, make_base_url, resolve_relative_url, truncate_words


def test_strip_html_basic():
    assert strip_html('<b>Hello</b> World') == 'Hello World'


def test_strip_html_entities():
    assert strip_html('AT&amp;T &lt;corp&gt;') == 'AT&T <corp>'


def test_strip_html_empty():
    assert strip_html('') == ''
    assert strip_html(None) == ''  # type: ignore[arg-type]


def test_make_base_url():
    assert make_base_url('https://www.reuters.com/world/middle-east/') == 'https://www.reuters.com'
    assert make_base_url('https://netblocks.org/reports/foo') == 'https://netblocks.org'
    assert make_base_url('') == ''


def test_resolve_relative_url_absolute():
    url = 'https://example.com/article'
    assert resolve_relative_url(url, 'https://base.com') == url


def test_resolve_relative_url_relative():
    result = resolve_relative_url('/article/123', 'https://www.reuters.com/world/')
    assert result == 'https://www.reuters.com/article/123'


def test_truncate_words_short():
    assert truncate_words('Hello World', 100) == 'Hello World'


def test_truncate_words_long():
    text = 'The quick brown fox jumps over the lazy dog'
    result = truncate_words(text, 20)
    assert len(result) <= 21  # 20 + ellipsis
    assert result.endswith('\u2026')
