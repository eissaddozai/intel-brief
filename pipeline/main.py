#!/usr/bin/env python3
"""
CSE Intel Brief — Pipeline CLI

SUBCOMMANDS
  run            Run the full pipeline (ingest → triage → draft → review → output)
  check-sources  Test every source URL and report status
  show           Pretty-print a cycle to the terminal
  list           List all generated cycles

EXAMPLES
  python pipeline/main.py run --auto-approve
  python pipeline/main.py run --demo --auto-approve
  python pipeline/main.py run --stage ingest
  python pipeline/main.py run --date 2026-03-01 --auto-approve
  python pipeline/main.py run --from-file my_research.json --auto-approve
  python pipeline/main.py check-sources
  python pipeline/main.py show
  python pipeline/main.py show cycles/cycle001_20260304.json
  python pipeline/main.py list

MANUAL RESEARCH WORKFLOW
  Use --from-file to skip automated ingestion and feed your own curated research
  directly into the pipeline (triage → draft → review → output).

  Your research file must be a JSON array. Each item requires "source", "title",
  and "text". All other fields are optional:

    [
      {
        "source": "AP",
        "title": "Iran fires ballistic missiles at Israeli positions",
        "text":  "Full article text here...",
        "url":   "https://apnews.com/...",    // optional
        "tier":  1,                            // optional; inferred from source name
        "date":  "2026-03-06"                  // optional; defaults to today
      }
    ]

  Tier 1 outlets (auto-detected): AP, Reuters, AFP, CTP-ISW, IAEA, CENTCOM, UKMTO.
  All other sources default to Tier 2. Override with "tier": 1 if needed.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

CACHE_DIR = PIPELINE_DIR / '.cache'
CYCLES_DIR = REPO_ROOT / 'cycles'
CONFIG_PATH = REPO_ROOT / 'pipeline-config.yaml'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('pipeline')

# ─── ANSI colour helpers ──────────────────────────────────────────────────────
_USE_COLOUR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f'\033[{code}m{text}\033[0m' if _USE_COLOUR else text

def red(t: str) -> str:    return _c('31;1', t)
def yellow(t: str) -> str: return _c('33;1', t)
def green(t: str) -> str:  return _c('32;1', t)
def cyan(t: str) -> str:   return _c('36;1', t)
def bold(t: str) -> str:   return _c('1', t)
def dim(t: str) -> str:    return _c('2', t)


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    import os, re
    if not CONFIG_PATH.exists():
        return {}
    try:
        import yaml
        text = CONFIG_PATH.read_text(encoding='utf-8')
        def _sub(m: re.Match) -> str:
            val = os.environ.get(m.group(1), '')
            if not val:
                log.warning('Environment variable %s not set', m.group(1))
            return val
        return yaml.safe_load(re.sub(r'\$\{([^}]+)\}', _sub, text)) or {}
    except Exception as exc:
        log.error('Config load failed: %s', exc)
        return {}


def get_target_date(date_str: str | None) -> datetime:
    if date_str:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


# ─── Pipeline stages ──────────────────────────────────────────────────────────

def stage_ingest_from_file(research_file: Path, target_date: datetime, force: bool) -> Path:
    """Ingest from a user-provided research file instead of automated sources."""
    from ingest.manual_ingest import ingest_from_file
    return ingest_from_file(
        research_file=research_file,
        target_date=target_date,
        cache_dir=CACHE_DIR,
        force=force,
    )


def stage_ingest_demo(target_date: datetime) -> Path:
    """Synthetic seed data — no internet required."""
    from ingest.demo_seed import get_seed_items
    cache_file = CACHE_DIR / f'raw_{target_date.strftime("%Y%m%d")}.json'
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    items = get_seed_items(target_date)
    cache_file.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Demo mode: wrote %d seed items → %s', len(items), cache_file)
    return cache_file


def stage_ingest(target_date: datetime, force: bool, config: dict) -> Path:
    """Ingest from all sources. Returns path to raw cache."""
    from ingest.rss_ingest import ingest_rss
    from ingest.scraper import ingest_scrape
    from ingest.email_ingest import ingest_email

    cache_file = CACHE_DIR / f'raw_{target_date.strftime("%Y%m%d")}.json'

    if cache_file.exists() and not force:
        log.info('Raw cache exists for %s — skipping (use --force to override)',
                 target_date.date())
        return cache_file

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    log.info('Starting ingestion for %s', target_date.date())
    raw_items: list[dict] = []

    log.info('── RSS feeds ──')
    try:
        rss_items = ingest_rss(target_date, config=config)
        raw_items.extend(rss_items)
        log.info('RSS total: %d items', len(rss_items))
    except Exception as exc:
        log.error('RSS ingestion failed: %s', exc)

    log.info('── Web scrape ──')
    try:
        from ingest.relevance import filter_relevant
        scraped = ingest_scrape(target_date, config=config)
        scraped = filter_relevant(scraped)
        raw_items.extend(scraped)
        log.info('Scrape total: %d items (after relevance filter)', len(scraped))
    except Exception as exc:
        log.error('Scrape ingestion failed: %s', exc)

    log.info('── Email ──')
    try:
        email_items = ingest_email(target_date, config=config)
        raw_items.extend(email_items)
        log.info('Email total: %d items', len(email_items))
    except Exception as exc:
        log.warning('Email ingestion failed (non-fatal): %s', exc)

    log.info('── War Risk Insurance (D6) — parallel subagent collection ──')
    try:
        from ingest.war_risk_ingest import ingest_war_risk
        wr_items = ingest_war_risk(target_date, config=config, force=force)
        raw_items.extend(wr_items)
        wr_t1 = sum(1 for i in wr_items if i.get('tier') == 1)
        log.info(
            'War risk collection: %d items (%d Tier 1) passed significance gate',
            len(wr_items), wr_t1,
        )
    except Exception as exc:
        log.warning(
            'War risk ingestion failed (non-fatal — d6 section will be thin): %s', exc
        )

    if not raw_items:
        log.critical('No items collected from any source. Aborting.')
        sys.exit(1)

    tier1 = [i for i in raw_items if i.get('tier') == 1]
    if not tier1 and config.get('triage', {}).get('halt_if_zero_tier1', True):
        log.critical('Zero Tier 1 items. Brief integrity cannot be guaranteed. Aborting.')
        sys.exit(1)

    log.info('Total collected: %d items (%d Tier 1)', len(raw_items), len(tier1))
    cache_file.write_text(json.dumps(raw_items, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Raw cache written: %s', cache_file)
    return cache_file


def stage_triage(raw_cache: Path, config: dict) -> Path:
    from triage.classifier import classify_items
    from triage.novelty import filter_novel
    from triage.confidence import assign_confidence

    tagged_file = raw_cache.parent / raw_cache.name.replace('raw_', 'tagged_')
    raw_items = json.loads(raw_cache.read_text(encoding='utf-8'))

    log.info('Classifying %d items by domain...', len(raw_items))
    classified = classify_items(raw_items)

    log.info('Running novelty detection...')
    novel = filter_novel(classified, cycles_dir=CYCLES_DIR, config=config)
    log.info('%d novel items (%d repeated filtered)', len(novel), len(classified) - len(novel))

    log.info('Assigning confidence tiers...')
    tagged = assign_confidence(novel)

    min_items = config.get('triage', {}).get('min_items_per_domain', 2)
    domain_counts: dict[str, int] = {}
    for item in tagged:
        for d in item.get('tagged_domains', []):
            domain_counts[d] = domain_counts.get(d, 0) + 1
    for did in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
        n = domain_counts.get(did, 0)
        if n < min_items:
            log.warning('Domain %s: only %d items (min %d)', did, n, min_items)

    tagged_file.write_text(json.dumps(tagged, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Tagged cache written: %s', tagged_file)
    return tagged_file


def _build_placeholder_draft(tagged_items: list[dict], target_date: datetime) -> dict:
    """
    Structurally valid placeholder when Claude API is unavailable.
    Contains all collected items verbatim — just not AI-synthesised prose.
    """
    DOMAINS = [
        ('d1', '01', 'BATTLESPACE · KINETIC'),
        ('d2', '02', 'ESCALATION · TRAJECTORY'),
        ('d3', '03', 'ENERGY · ECONOMIC'),
        ('d4', '04', 'DIPLOMATIC · POLITICAL'),
        ('d5', '05', 'CYBER · INFORMATION OPS'),
        ('d6', '06', 'WAR RISK INSURANCE · MARITIME FINANCE'),
    ]

    def items_for(did: str) -> list[dict]:
        return [i for i in tagged_items if did in i.get('tagged_domains', [])]

    def domain_section(did: str, num: str, title: str) -> dict:
        items = items_for(did)
        tier1 = [i for i in items if i.get('tier') == 1]
        body_items = (tier1 or items)[:3]
        paras = [
            {
                'subLabel': f'ITEM {idx+1}',
                'text': item.get('text', item.get('title', ''))[:500],
                'citations': [{'ref': item.get('source_name', ''), 'tier': item.get('tier', 2)}],
            }
            for idx, item in enumerate(body_items)
        ] or [{'subLabel': 'STATUS', 'text': 'No items collected.', 'citations': []}]

        confidence = 'high' if tier1 else ('moderate' if items else 'low')
        return {
            'id': did, 'num': num, 'title': title,
            'keyJudgment': {
                'text': (
                    f'{len(items)} items collected ({len(tier1)} Tier 1). '
                    'Re-run after adding Anthropic API credits for AI synthesis.'
                ),
                'confidence': confidence,
                'probabilityRange': 'placeholder',
                'corroborated': bool(tier1),
            },
            'bodyParagraphs': paras,
            'confidence': confidence,
        }

    domains = [domain_section(d, n, t) for d, n, t in DOMAINS]
    total = len(tagged_items)
    cycle_id = f'CSE-BRIEF-PLACEHOLDER-{target_date.strftime("%Y%m%d")}'
    date_str = target_date.strftime('%d %B %Y')

    return {
        'meta': {
            'cycleId': cycle_id, 'cycleNum': '000',
            'classification': 'PROTECTED B', 'tlp': 'AMBER',
            'timestamp': target_date.strftime('%Y-%m-%dT06:00:00Z'),
            'region': 'Iran · Gulf Region · Eastern Mediterranean',
            'analystUnit': 'CSE Conflict Assessment Unit',
            'threatLevel': 'SEVERE', 'threatTrajectory': 'escalating',
            'subtitle': 'Iran War File — Daily Assessment [PLACEHOLDER — NO AI SYNTHESIS]',
            'contextNote': (
                f'Placeholder draft — {total} items collected for {date_str}. '
                'Fund Anthropic API and re-run `brief run --stage draft` to generate analysis.'
            ),
            'stripCells': [
                {'top': 'SEVERE', 'bot': 'THREAT LEVEL'},
                {'top': str(total), 'bot': 'ITEMS INGESTED'},
                {'top': '—', 'bot': 'BRENT CRUDE'},
                {'top': 'ACTIVE', 'bot': 'HORMUZ STATUS'},
                {'top': '—', 'bot': 'FLASH POINTS'},
            ],
        },
        'strategicHeader': {
            'headlineJudgment': f'PLACEHOLDER — {total} items ingested, no AI synthesis.',
            'oneLineSummary': 'Fund API credits and re-run draft stage.',
        },
        'flashPoints': [],
        'executive': {
            'bluf': f'PLACEHOLDER — {total} items across 5 domains. Re-run after funding API.',
            'keyJudgments': [d['keyJudgment']['text'] for d in domains],
            'kpis': [],
        },
        'domains': domains,
        'warningIndicators': [],
        'collectionGaps': [],
        'caveats': {
            'cycleRef': f'CSE-BRIEF-PLACEHOLDER · {date_str.upper()}',
            'items': [{'label': 'PLACEHOLDER', 'text': 'Not an intelligence product.'}],
            'confidenceAssessment': 'N/A',
            'dissenterNotes': [], 'sourceQuality': 'See domain citations.',
            'handling': 'DRAFT — NOT FOR DISTRIBUTION',
        },
        'footer': {
            'id': cycle_id, 'classification': 'PROTECTED B // TLP:AMBER',
            'sources': 'See domain citations', 'handling': 'PLACEHOLDER — NOT FOR DISTRIBUTION',
        },
    }


def stage_draft(tagged_cache: Path, target_date: datetime, config: dict) -> Path:
    from draft.drafter import draft_cycle
    draft_file = tagged_cache.parent / tagged_cache.name.replace('tagged_', 'draft_')
    tagged_items = json.loads(tagged_cache.read_text(encoding='utf-8'))
    prev_cycle = _find_previous_cycle()

    if prev_cycle:
        log.info('Previous cycle found — using for delta context')
    else:
        log.warning('No previous cycle — drafting without prior context')

    log.info('Calling Claude API...')
    try:
        draft = draft_cycle(
            tagged_items=tagged_items,
            target_date=target_date,
            prev_cycle=prev_cycle,
            config=config,
        )
    except Exception as exc:
        err = str(exc)
        _api_issue = any(kw in err.lower() for kw in [
            'credit balance', 'quota', 'rate limit', 'billing',
            'api_key not set', 'anthropic_api_key', 'not set',
        ])
        if _api_issue:
            log.warning(
                'Claude API unavailable (%s). '
                'Building placeholder draft — fund credits and re-run `--stage draft`.',
                err.split('.')[0],
            )
            draft = _build_placeholder_draft(tagged_items, target_date)
        else:
            raise

    draft_file.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Draft written: %s', draft_file)
    return draft_file


def stage_review(draft_file: Path, auto_approve: bool = False) -> Path:
    approved_file = draft_file.parent / draft_file.name.replace('draft_', 'approved_')
    draft = json.loads(draft_file.read_text(encoding='utf-8'))

    if auto_approve:
        log.info('Auto-approve — skipping interactive review')
        approved = draft
    else:
        from review.review_cli import run_review
        log.info('Opening review CLI...')
        approved = run_review(draft)
        if approved is None:
            log.critical('Review aborted.')
            sys.exit(1)

    approved_file.write_text(json.dumps(approved, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Approved draft: %s', approved_file)
    return approved_file


def stage_output(approved_file: Path, config: dict) -> Path:
    from output.serializer import write_cycle
    approved = json.loads(approved_file.read_text(encoding='utf-8'))
    out_path = write_cycle(approved, config)
    log.info('Output: %s', out_path)
    return out_path


def _find_previous_cycle() -> dict | None:
    if not CYCLES_DIR.exists():
        return None
    cycles = [p for p in CYCLES_DIR.glob('cycle*.json') if not p.is_symlink()]
    if not cycles:
        return None
    latest = max(cycles, key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(latest.read_text(encoding='utf-8'))
    except Exception:
        return None


def _resolve_cache(prefix: str, target_date: datetime) -> Path:
    f = CACHE_DIR / f'{prefix}_{target_date.strftime("%Y%m%d")}.json'
    if not f.exists():
        log.error('No %s cache for %s — run prior stage first.', prefix, target_date.date())
        sys.exit(1)
    return f


# ─── Subcommand: run ─────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace, config: dict) -> None:
    target_date = get_target_date(args.date)
    log.info('Target date: %s', target_date.strftime('%Y-%m-%d'))

    stage = args.stage
    demo = args.demo
    auto_approve = args.auto_approve
    from_file = Path(args.from_file) if getattr(args, 'from_file', None) else None

    if from_file and not from_file.exists():
        log.error('Research file not found: %s', from_file)
        sys.exit(1)

    raw_cache: Path
    tagged_cache: Path
    draft_file: Path
    approved_file: Path

    if stage in ('ingest', None):
        if from_file:
            raw_cache = stage_ingest_from_file(from_file, target_date, args.force)
        elif demo:
            raw_cache = stage_ingest_demo(target_date)
        else:
            raw_cache = stage_ingest(target_date, args.force, config)
        if stage:
            return

    if stage in ('triage', None):
        if stage == 'triage':
            raw_cache = _resolve_cache('raw', target_date)
        tagged_cache = stage_triage(raw_cache, config)
        if stage:
            return

    if stage in ('draft', None):
        if stage == 'draft':
            tagged_cache = _resolve_cache('tagged', target_date)
        draft_file = stage_draft(tagged_cache, target_date, config)
        if stage:
            return

    if stage in ('review', None):
        if stage == 'review':
            draft_file = _resolve_cache('draft', target_date)
        approved_file = stage_review(draft_file, auto_approve=auto_approve)
        if stage:
            return

    if stage in ('output', None):
        if stage == 'output':
            approved_file = _resolve_cache('approved', target_date)
        out = stage_output(approved_file, config)
        log.info('Pipeline complete → %s', out)


# ─── Subcommand: check-sources ───────────────────────────────────────────────

def cmd_check_sources(args: argparse.Namespace, config: dict) -> None:
    """Test every enabled source URL and report status."""
    import yaml
    import time

    sources_file = PIPELINE_DIR / 'ingest' / 'sources.yaml'
    data = yaml.safe_load(sources_file.read_text(encoding='utf-8'))
    sources = [s for s in data.get('sources', []) if s.get('enabled', True)]

    import requests as req
    TIMEOUT = 10
    HEADERS = {'User-Agent': 'CSE-Intel-Brief/1.0 check-sources'}

    print(bold('\nCHECKING SOURCES') + f'  ({len(sources)} enabled)\n')
    print(f'{"SOURCE":<35} {"METHOD":<7} {"STATUS":<8} {"HTTP":<6} {"NOTE"}')
    print('─' * 80)

    ok = warn = fail = 0

    for s in sources:
        url = s.get('url') or s.get('url_pattern', '')
        method = s.get('method', '?')
        name = s['name']
        declared_status = s.get('status', 'unknown')

        if method == 'email':
            print(f'{name:<35} {method:<7} {dim("email"):<8} {"—":<6} configure IMAP credentials')
            continue

        if not url:
            print(f'{name:<35} {method:<7} {yellow("no-url"):<8} {"—":<6}')
            warn += 1
            continue

        # Strip date interpolation for testing
        test_url = url.replace('{YYYY-MM-DD}', '2026-03-04').replace('{YYYY}', '2026')

        try:
            t0 = time.time()
            r = req.head(test_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            elapsed = int((time.time() - t0) * 1000)
            code = r.status_code
            if code < 400:
                status_str = green(f'{"OK":<8}')
                ok += 1
                note = f'{elapsed}ms'
            elif code == 403:
                status_str = yellow(f'{"403":<8}')
                warn += 1
                note = 'forbidden (may need auth/cookie)'
            elif code == 404:
                status_str = red(f'{"404":<8}')
                fail += 1
                note = 'not found — URL may be wrong'
            elif code == 429:
                status_str = yellow(f'{"429":<8}')
                warn += 1
                note = 'rate limited — try later'
            else:
                status_str = yellow(f'{code:<8}')
                warn += 1
                note = ''
        except req.exceptions.ConnectionError:
            status_str = red(f'{"CONN ERR":<8}')
            fail += 1
            note = 'connection refused or proxy block'
            code = '—'
        except req.exceptions.Timeout:
            status_str = yellow(f'{"TIMEOUT":<8}')
            warn += 1
            note = f'>{TIMEOUT}s'
            code = '—'
        except Exception as exc:
            status_str = red(f'{"ERROR":<8}')
            fail += 1
            note = str(exc)[:60]
            code = '—'

        print(f'{name:<35} {method:<7} {status_str} {str(code):<6} {note}')
        time.sleep(0.3)

    print('─' * 80)
    summary = f'{green(str(ok)+" OK")}  {yellow(str(warn)+" WARN")}  {red(str(fail)+" FAIL")}'
    print(f'\n{summary}\n')

    if fail > 0:
        print(yellow('TIP:') + ' CONN ERR usually means this sandbox blocks outbound HTTP.')
        print('     Run check-sources on a machine with internet access.\n')


# ─── Subcommand: show ────────────────────────────────────────────────────────

def cmd_show(args: argparse.Namespace, config: dict) -> None:
    """Pretty-print a cycle to the terminal."""
    if args.cycle:
        path = Path(args.cycle)
    else:
        latest = CYCLES_DIR / 'latest.json'
        if latest.exists():
            path = latest.resolve()
        else:
            cycles = sorted(CYCLES_DIR.glob('cycle*.json'))
            if not cycles:
                print(red('No cycles found.'))
                sys.exit(1)
            path = cycles[-1]

    try:
        cycle = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(red(f'Cannot read {path}: {exc}'))
        sys.exit(1)

    m = cycle.get('meta', {})
    sh = cycle.get('strategicHeader', {})
    ex = cycle.get('executive', {})

    # Header strip
    print()
    print(bold(cyan('═' * 72)))
    print(bold(cyan(f'  CSE INTEL BRIEF  ·  {m.get("subtitle", "")}')))
    print(bold(cyan(f'  {m.get("timestamp","")[:10]}  ·  {m.get("cycleId","")}')))
    print(bold(cyan('═' * 72)))
    print(f'  Classification: {bold(m.get("classification",""))}  ·  TLP: {bold(m.get("tlp",""))}')
    print(f'  Threat: {red(m.get("threatLevel","?"))} / {m.get("threatTrajectory","?")}')
    print()

    # Status strip
    cells = m.get('stripCells', [])
    if cells:
        strip = '  '.join(f'{bold(c["top"])} {dim(c["bot"])}' for c in cells)
        print('  ' + strip)
        print()

    # Strategic header
    if sh.get('headlineJudgment'):
        print(bold('HEADLINE JUDGMENT'))
        print(f'  {sh["headlineJudgment"]}')
        print()

    # Executive BLUF
    print(bold('EXECUTIVE BLUF'))
    print(f'  {ex.get("bluf", "")}')
    print()

    # Key judgments
    kjs = ex.get('keyJudgments', [])
    if kjs:
        print(bold('KEY JUDGMENTS'))
        for i, kj in enumerate(kjs, 1):
            print(f'  {dim(str(i)+".")} {kj}')
        print()

    # Domain sections
    for d in cycle.get('domains', []):
        kj = d.get('keyJudgment', {})
        conf = kj.get('confidence', '?')
        conf_colour = green if conf == 'high' else (yellow if conf == 'moderate' else dim)
        print(bold(f'[{d["id"].upper()}] {d["title"]}') +
              f'  {conf_colour("["+conf+"]")}')
        print(f'  KJ: {kj.get("text", "")}')
        for para in d.get('bodyParagraphs', [])[:2]:
            label = dim(f'[{para.get("subLabel","PARA")}]')
            text = para.get('text', '')[:300]
            print(f'  {label} {text}')
        print()

    # Warning indicators
    wi = cycle.get('warningIndicators', [])
    if wi:
        print(bold(yellow('WARNING INDICATORS')))
        for w in wi:
            level = w.get('level', '?')
            c = red if level == 'RED' else (yellow if level == 'AMBER' else green)
            print(f'  {c(level)} {w.get("indicator","?")} — {w.get("assessment","")}')
        print()

    # Footer
    print(dim('─' * 72))
    print(dim(f'  {cycle.get("footer",{}).get("classification","")}  ·  {path.name}'))
    print()


# ─── Subcommand: list ────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace, config: dict) -> None:
    """List all generated cycles."""
    if not CYCLES_DIR.exists():
        print('No cycles directory found.')
        return

    cycles = sorted(
        [p for p in CYCLES_DIR.glob('cycle*.json') if not p.is_symlink()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not cycles:
        print('No cycles generated yet. Run: python pipeline/main.py run --demo --auto-approve')
        return

    print()
    print(bold(f'{"CYCLE FILE":<40} {"DATE":<12} {"THREAT":<10} {"ITEMS":>6}'))
    print('─' * 72)

    latest = (CYCLES_DIR / 'latest.json').resolve() if (CYCLES_DIR / 'latest.json').exists() else None

    for p in cycles:
        try:
            c = json.loads(p.read_text(encoding='utf-8'))
            m = c.get('meta', {})
            date_str = m.get('timestamp', '')[:10]
            threat = m.get('threatLevel', '?')
            total_items = sum(len(d.get('bodyParagraphs', [])) for d in c.get('domains', []))
            threat_col = red(f'{threat:<10}') if threat in ('CRITICAL', 'SEVERE') else yellow(f'{threat:<10}')
            marker = green(' ← latest') if p == latest else ''
            print(f'{p.name:<40} {date_str:<12} {threat_col} {total_items:>6}{marker}')
        except Exception:
            print(f'{p.name:<40} {"(unreadable)":<12}')

    print()


# ─── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python pipeline/main.py',
        description='CSE Intel Brief pipeline CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command')

    # ── run ──
    run_p = sub.add_parser('run', help='Run the pipeline (default command)')
    run_p.add_argument('--stage', choices=['ingest','triage','draft','review','output'],
                       default=None, help='Run a single stage only')
    run_p.add_argument('--date', default=None, help='Target date YYYY-MM-DD (default: today)')
    run_p.add_argument('--force', action='store_true', help='Re-run even if cache exists')
    run_p.add_argument('--auto-approve', action='store_true',
                       help='Skip interactive review (for CI)')
    run_p.add_argument('--demo', action='store_true',
                       help='Use synthetic seed data — no internet or API required')
    run_p.add_argument('--from-file', metavar='PATH',
                       help=(
                           'Path to a JSON file of curated research items. '
                           'Skips automated ingestion; runs triage → draft → review → output '
                           'from your research. See MANUAL RESEARCH WORKFLOW in --help for '
                           'the expected JSON format.'
                       ))

    # ── check-sources ──
    sub.add_parser('check-sources', help='Test every source URL and report status')

    # ── show ──
    show_p = sub.add_parser('show', help='Pretty-print a cycle to the terminal')
    show_p.add_argument('cycle', nargs='?', default=None,
                        help='Path to cycle JSON (default: latest)')

    # ── list ──
    sub.add_parser('list', help='List all generated cycles')

    return parser


def main() -> None:
    parser = build_parser()

    # Backward-compat: if first arg is not a subcommand, treat as `run`
    argv = sys.argv[1:]
    known_cmds = {'run', 'check-sources', 'show', 'list'}
    if argv and argv[0] not in known_cmds and not argv[0].startswith('-'):
        # Unknown positional — fall through to argparse error
        pass
    elif not argv or argv[0].startswith('-'):
        # No subcommand given — default to 'run'
        argv = ['run'] + argv

    args = parser.parse_args(argv)

    config = load_config()
    log_level = config.get('logging', {}).get('level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    if args.command == 'run':
        cmd_run(args, config)
    elif args.command == 'check-sources':
        cmd_check_sources(args, config)
    elif args.command == 'show':
        cmd_show(args, config)
    elif args.command == 'list':
        cmd_list(args, config)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
