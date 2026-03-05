"""
Cycle JSON serializer — validates and writes approved cycle dict to disk.
Assigns cycle number, symlinks latest.json, optionally copies to src/data/.
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import jsonschema  # optional — graceful degradation if not installed
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

log = logging.getLogger(__name__)

CYCLES_DIR = Path(__file__).resolve().parents[2] / 'cycles'
FRONTEND_DATA_DIR = Path(__file__).resolve().parents[2] / 'src' / 'data'

# Minimal structural validation (full schema lives in brief.ts; this is a safety net)
REQUIRED_TOP_LEVEL = {'meta', 'strategicHeader', 'flashPoints', 'executive',
                      'domains', 'warningIndicators', 'collectionGaps', 'caveats', 'footer'}
REQUIRED_META = {'cycleId', 'cycleNum', 'classification', 'tlp', 'timestamp',
                 'region', 'analystUnit', 'threatLevel', 'threatTrajectory',
                 'subtitle', 'contextNote'}
VALID_DOMAIN_IDS = {'d1', 'd2', 'd3', 'd4', 'd5', 'd6'}
VALID_TLP = {'RED', 'AMBER', 'GREEN', 'CLEAR'}
VALID_THREAT = {'CRITICAL', 'SEVERE', 'ELEVATED', 'GUARDED', 'LOW'}


def _next_cycle_number(cycles_dir: Path) -> int:
    """Scan existing cycle files and return next sequential number."""
    existing = list(cycles_dir.glob('cycle*.json'))
    nums = []
    for f in existing:
        if f.is_symlink():
            continue
        # Match both cycle001_20240315.json and cycle_001_20240315.json
        m = re.match(r'cycle_?(\d+)', f.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def validate(cycle: dict) -> list[str]:
    """
    Run structural validation on the cycle dict.
    Returns list of error strings (empty = valid).
    """
    errors: list[str] = []

    # Top-level keys
    missing = REQUIRED_TOP_LEVEL - set(cycle.keys())
    if missing:
        errors.append(f'Missing top-level keys: {missing}')

    # Meta fields
    meta = cycle.get('meta', {})
    missing_meta = REQUIRED_META - set(meta.keys())
    if missing_meta:
        errors.append(f'Missing meta fields: {missing_meta}')

    if meta.get('tlp') not in VALID_TLP:
        errors.append(f"Invalid TLP: {meta.get('tlp')!r}")

    if meta.get('threatLevel') not in VALID_THREAT:
        errors.append(f"Invalid threatLevel: {meta.get('threatLevel')!r}")

    # Domains
    domains = cycle.get('domains', [])
    if not domains:
        errors.append('No domains in cycle')
    for d in domains:
        if d.get('id') not in VALID_DOMAIN_IDS:
            errors.append(f"Invalid domain id: {d.get('id')!r}")
        if not d.get('keyJudgment'):
            errors.append(f"Domain {d.get('id')} missing keyJudgment")
        if not d.get('bodyParagraphs'):
            errors.append(f"Domain {d.get('id')} missing bodyParagraphs")

    # Executive
    executive = cycle.get('executive', {})
    if not executive.get('bluf'):
        errors.append('Executive missing bluf')
    if not executive.get('keyJudgments'):
        errors.append('Executive missing keyJudgments')

    # Warning indicators — just structural
    for wi in cycle.get('warningIndicators', []):
        if 'indicator' not in wi or 'status' not in wi:
            errors.append(f"Malformed warningIndicator: {wi.get('id', '?')}")

    return errors


def write_cycle(approved: dict, config: dict) -> Path:
    """
    Stamp metadata, validate, write cycle JSON, symlink latest.json.

    Args:
        approved: The approved cycle dict from review_cli.run_review().
        config:   Pipeline config dict (from pipeline-config.yaml).

    Returns:
        Path to the written cycle JSON file.

    Raises:
        ValueError: If validation fails (errors logged before raise).
        IOError:    If file write fails.
    """
    cycles_dir = Path(config.get('output', {}).get('cycles_dir', str(CYCLES_DIR)))
    cycles_dir.mkdir(parents=True, exist_ok=True)

    # ── Stamp cycle number and write-timestamp ─────────────────────────────
    cycle_num = _next_cycle_number(cycles_dir)
    # Use timestamp from meta if available (allows backfill to use correct date)
    ts = approved.get('meta', {}).get('timestamp', '')
    try:
        date_str = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%Y%m%d')
    except (ValueError, AttributeError):
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    cycle_id = f'cycle{cycle_num:03d}_{date_str}'

    approved = dict(approved)
    meta = dict(approved.get('meta', {}))
    meta['cycleId'] = cycle_id
    meta['cycleNum'] = f'{cycle_num:03d}'
    # Preserve pipeline-stamped timestamp if already set, else set now
    if not meta.get('timestamp'):
        meta['timestamp'] = datetime.now(timezone.utc).isoformat()
    approved['meta'] = meta

    # ── Validation ─────────────────────────────────────────────────────────
    errors = validate(approved)
    if errors:
        for e in errors:
            log.error('Validation error: %s', e)
        raise ValueError(f'Cycle failed validation with {len(errors)} error(s). See log.')

    # ── Write cycle file ───────────────────────────────────────────────────
    out_path = cycles_dir / f'{cycle_id}.json'
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(approved, fh, indent=2, ensure_ascii=False)
    log.info('Cycle written → %s', out_path)

    # ── Symlink latest.json ────────────────────────────────────────────────
    latest = cycles_dir / 'latest.json'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out_path.name)
    log.info('Symlinked latest.json → %s', out_path.name)

    # ── Optionally copy to src/data for front-end ──────────────────────────
    frontend_dir = config.get('output', {}).get('frontend_data_dir')
    if frontend_dir:
        frontend_dir = Path(frontend_dir)
        frontend_dir.mkdir(parents=True, exist_ok=True)
        dest = frontend_dir / f'{cycle_id}.json'
        shutil.copy2(out_path, dest)
        # Also write latest.json as a real file (not symlink) so Vite dev server can serve it
        fe_latest = frontend_dir / 'latest.json'
        shutil.copy2(out_path, fe_latest)
        log.info('Copied to frontend data dir → %s', dest)

    return out_path
