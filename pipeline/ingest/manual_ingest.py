"""
Manual ingest — converts user-curated research notes to the raw cache format.

INPUT FORMAT  (JSON array, saved as any .json file):

[
  {
    "source": "AP",                  // outlet name; tier inferred from known Tier 1 outlets
    "tier": 1,                       // optional — overrides inferred tier
    "title": "Headline here",        // required
    "text": "Full article text ...", // required
    "url": "https://example.com/",   // optional
    "date": "2026-03-06"             // optional; defaults to target_date
  },
  ...
]

Tier inference rules (matches CLAUDE.md source hierarchy):
  Tier 1 — AP, Reuters, AFP, CTP-ISW, IAEA, CENTCOM, UKMTO
  Everything else → Tier 2

`domains` is intentionally omitted from the input format; the triage classifier's
keyword matching assigns domains automatically in the next stage.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Tier 1 outlets as listed in CLAUDE.md source hierarchy.
# Matching is case-insensitive and allows partial matches (e.g. "CTP-ISW" matches
# "CTP-ISW Evening Report").
_TIER1_PATTERNS: list[str] = [
    'ap', 'associated press',
    'reuters',
    'afp', 'agence france-presse',
    'ctp-isw', 'isw',
    'iaea',
    'centcom',
    'ukmto',
]


def _infer_tier(source_name: str) -> int:
    """Return 1 for recognised Tier 1 outlets, 2 otherwise."""
    lower = source_name.lower()
    for pattern in _TIER1_PATTERNS:
        if pattern in lower:
            return 1
    return 2


def _make_source_id(source_name: str) -> str:
    """Slug-ify a source name for use as source_id."""
    slug = re.sub(r'[^a-z0-9]+', '_', source_name.lower()).strip('_')
    return slug or 'manual'


def _parse_date(date_str: str | None, fallback: datetime) -> str:
    """Return an ISO-8601 timestamp string from a YYYY-MM-DD date string or fallback."""
    if not date_str:
        return fallback.strftime('%Y-%m-%dT06:00:00+00:00')
    try:
        dt = datetime.strptime(date_str.strip(), '%Y-%m-%d').replace(tzinfo=timezone.utc)
        return dt.strftime('%Y-%m-%dT06:00:00+00:00')
    except ValueError:
        log.warning('Could not parse date %r — using target date', date_str)
        return fallback.strftime('%Y-%m-%dT06:00:00+00:00')


def load_research_file(path: Path) -> list[dict]:
    """Load and validate a user-provided research file. Returns raw list."""
    if not path.exists():
        raise FileNotFoundError(f'Research file not found: {path}')

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Research file is not valid JSON: {exc}') from exc

    if not isinstance(data, list):
        raise ValueError(
            f'Research file must be a JSON array of articles, got {type(data).__name__}'
        )

    return data


def convert_to_raw_items(
    research_items: list[dict],
    target_date: datetime,
) -> list[dict]:
    """
    Convert user-provided research dicts to the internal RawItem format
    expected by the triage stage.

    Validates required fields and fills in defaults for optional ones.
    """
    raw_items: list[dict] = []
    errors: list[str] = []

    for idx, item in enumerate(research_items):
        label = f'Item {idx + 1}'

        # --- Required fields ---
        title = item.get('title', '').strip()
        text = item.get('text', '').strip()

        if not title:
            errors.append(f'{label}: missing required field "title"')
            continue
        if not text:
            errors.append(f'{label}: missing required field "text"')
            continue

        source_name = str(item.get('source', 'Manual Research')).strip()
        if not source_name:
            source_name = 'Manual Research'

        # --- Tier ---
        if 'tier' in item:
            try:
                tier = int(item['tier'])
                if tier not in (1, 2, 3):
                    raise ValueError
            except (ValueError, TypeError):
                log.warning('%s: invalid tier %r — falling back to inference', label, item['tier'])
                tier = _infer_tier(source_name)
        else:
            tier = _infer_tier(source_name)

        # --- Verification status (derived from tier, consistent with CLAUDE.md) ---
        verification_status = {1: 'confirmed', 2: 'reported', 3: 'claimed'}.get(tier, 'reported')

        # --- Optional fields ---
        url = str(item.get('url', '')).strip()
        timestamp = _parse_date(item.get('date'), target_date)
        source_id = _make_source_id(source_name)

        raw_items.append({
            'source_id': source_id,
            'source_name': source_name,
            'tier': tier,
            'domains': [],       # Left empty; triage keyword matching populates this
            'title': title,
            'text': text,
            'full_content': '',
            'url': url,
            'timestamp': timestamp,
            'verification_status': verification_status,
            'method': 'manual',
        })

    if errors:
        for err in errors:
            log.error('Manual ingest validation: %s', err)
        raise ValueError(
            f'{len(errors)} item(s) failed validation — see log for details.'
        )

    return raw_items


def ingest_from_file(
    research_file: Path,
    target_date: datetime,
    cache_dir: Path,
    force: bool = False,
) -> Path:
    """
    Main entry point. Loads a user research file, converts it to the raw
    cache format, and writes it to pipeline/.cache/raw_YYYYMMDD.json.

    Returns the path to the written cache file.
    """
    cache_file = cache_dir / f'raw_{target_date.strftime("%Y%m%d")}.json'

    if cache_file.exists() and not force:
        log.warning(
            'Raw cache already exists for %s (%s). '
            'Use --force to overwrite with your research file.',
            target_date.date(), cache_file,
        )
        return cache_file

    log.info('Loading research file: %s', research_file)
    research_items = load_research_file(research_file)
    log.info('Loaded %d item(s) from research file', len(research_items))

    raw_items = convert_to_raw_items(research_items, target_date)

    tier1_count = sum(1 for i in raw_items if i['tier'] == 1)
    tier2_count = sum(1 for i in raw_items if i['tier'] == 2)
    log.info(
        'Converted %d item(s): %d Tier 1, %d Tier 2',
        len(raw_items), tier1_count, tier2_count,
    )

    if tier1_count == 0:
        log.warning(
            'No Tier 1 items found. If any items are from AP / Reuters / AFP / '
            'CTP-ISW / IAEA / CENTCOM / UKMTO, set "tier": 1 explicitly or '
            'spell the source name to match one of the recognised outlets.'
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(raw_items, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Raw cache written: %s', cache_file)

    return cache_file
