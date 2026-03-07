"""
Shared HTTP utilities for all ingest modules.

Provides:
  - Session factory with connection pooling and retry
  - Exponential backoff with jitter
  - Consistent User-Agent and timeout defaults
  - Rate-limited fetch wrapper
"""

import logging
import random
import time
from functools import lru_cache

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 20
DEFAULT_DELAY = 1.0

UA_BOT = 'CSE-Intel-Brief/1.0 (Research pipeline; contact: research@cse.ca)'
UA_BROWSER = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

HEADERS_BOT = {'User-Agent': UA_BOT}
HEADERS_BROWSER = {
    'User-Agent': UA_BROWSER,
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


# ── Session factory ──────────────────────────────────────────────────────────

def build_session(
    *,
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    headers: dict[str, str] | None = None,
    pool_connections: int = 10,
    pool_maxsize: int = 10,
) -> requests.Session:
    """
    Build a requests.Session with:
      - Connection pooling (reuses TCP sockets across requests)
      - Automatic retry on transient HTTP errors and 429 rate-limits
      - Exponential backoff between retries
    """
    session = requests.Session()
    session.headers.update(headers or HEADERS_BOT)
    session.verify = certifi.where()  # Use certifi CA bundle for SSL

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=['GET', 'HEAD'],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    return session


def fetch_with_backoff(
    url: str,
    session: requests.Session,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_attempts: int = 3,
) -> requests.Response | None:
    """
    Fetch a URL with manual exponential backoff and jitter on failure.
    Returns the Response on success, or None on complete failure.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                log.warning('Rate limited on %s — waiting %.1fs (attempt %d/%d)',
                            url, wait, attempt, max_attempts)
                time.sleep(wait)
            elif status >= 500:
                wait = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                log.warning('Server error %d on %s — retrying in %.1fs', status, url, wait)
                time.sleep(wait)
            else:
                log.error('HTTP %d on %s — not retryable', status, url)
                return None
        except requests.exceptions.ConnectionError:
            wait = (2 ** attempt) + random.uniform(0, 1)
            log.warning('Connection error on %s — retrying in %.1fs (attempt %d/%d)',
                        url, wait, attempt, max_attempts)
            time.sleep(wait)
        except requests.exceptions.Timeout:
            log.warning('Timeout on %s (attempt %d/%d)', url, attempt, max_attempts)
        except Exception as exc:
            log.error('Unexpected error fetching %s: %s', url, exc)
            return None

    log.error('All %d attempts failed for %s', max_attempts, url)
    return None
