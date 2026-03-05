"""
pipeline/agent_brief.py

Agentic brief runner — parallel fetch + 17 CLI subagents across 4 phases.

All Claude interaction is done via the `claude` CLI (Claude Code),
NOT via the Anthropic Python SDK. No API calls in this module.

Architecture:

  PHASE 1 — PARALLEL FETCH  (Python only, no Claude)
    ThreadPoolExecutor fetches every enabled source in sources.yaml
    simultaneously. All sources attempted in ~15–20 seconds.
    Results: {source_id: content_text}

  PHASE 2 — 6 DOMAIN SUBAGENTS  (all concurrent)
    Six `claude -p` subprocesses run simultaneously, each drafting
    one domain section from its pre-fetched source material.
    All six get full d1–d6 source data so there are no sequential
    dependencies — true parallel execution.

  PHASE 2.5 — 6 VOICE REVIEW SUBAGENTS  (all concurrent)
    Six `claude -p` subprocesses each review one domain section for
    compliance with intelligence writing standards (sentence length,
    assessment-led leads, confidence ladder, forbidden phrases).

  PHASE 2.7 — 1 CROSS-DOMAIN EDITORIAL SUBAGENT  (single pass)
    One `claude -p` subprocess reviews all 6 sections simultaneously
    for deduplication, contradiction resolution, and cross-domain
    coherence. Returns corrected sections list.

  PHASE 3 — 4 SYNTHESIS SUBAGENTS  (all concurrent, after Phase 2.7)
    Four `claude -p` subprocesses run simultaneously:
      - Executive BLUF + key judgments + KPIs
      - Strategic header + threat level/trajectory
      - Warning indicators
      - Collection gaps

  Total: 17 Claude CLI subagents across 4 rounds.

Usage (via main.py):
  python pipeline/main.py agent
  python pipeline/main.py agent --date 2026-03-05
  python pipeline/main.py agent --model claude-opus-4-6
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# requests is only used for HTTP fetch — no Anthropic SDK imported
import requests as _requests

log = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).parent
SOURCES_FILE = PIPELINE_DIR / 'ingest' / 'sources.yaml'

# ── Fetch config ───────────────────────────────────────────────────────────────
FETCH_TIMEOUT    = 15       # seconds per HTTP request
FETCH_CHAR_LIMIT = 6000     # chars returned per source
FETCH_WORKERS    = 12       # concurrent HTTP workers

# ── Subagent config ────────────────────────────────────────────────────────────
SUBAGENT_WORKERS = 10       # max concurrent claude CLI processes
CLI_TIMEOUT      = 300      # seconds per claude CLI call

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; CSE-Intel-Brief/2.0; research pipeline)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

_VOICE_REVIEW_RULES = """\
INTELLIGENCE WRITING QUALITY CONTROL — MANDATORY STANDARDS

1. MINIMUM SENTENCE LENGTH: Every sentence must be at least 8 words.
   Merge fragments into complete analytical sentences. Never write:
   BAD: "Hostilities continue."
   GOOD: "Hostilities across all five active theatres continued through the reporting period."

2. ASSESSMENT-LED PARAGRAPHS: Every paragraph's first sentence must be a judgment or assessment.
   Never open a paragraph with a bare factual description.
   BAD: "Three Houthi missiles were launched toward Israeli territory."
   GOOD: "We assess Houthi long-range targeting remains operationally viable; three ballistic missiles
          were launched toward Israeli territory during the reporting period (AP, 05 Mar 0430 UTC)."

3. CONFIDENCE LANGUAGE — use ONLY these exact phrases from the approved ladder:
   "We assess with high confidence..."        (95-99%)
   "We judge it highly likely..."             (75-95%)
   "Available evidence suggests..."           (55-75%)
   "Reporting indicates, though corroboration is limited..."  (45-55%)
   "We judge it unlikely, though we cannot exclude..."  (20-45%)
   "We assess with high confidence this will not..."   (1-5%)
   Never paraphrase. Never use phrases like "it appears", "it seems", "likely indicates".

4. SOURCE ATTRIBUTION: Every factual sentence must close with
   (Source Name, DD Mon HHMM UTC) — e.g., (AP, 05 Mar 0620 UTC).
   If timestamp is unavailable: (AP, 05 Mar).

5. TEMPORAL PRECISION: Every kinetic claim, nuclear development, or market-moving event
   must specify the UTC time and date: "As of 0600 UTC 05 Mar" or "at 1430 UTC 04 Mar".

6. FORBIDDEN PHRASES — rewrite any sentence containing:
   "kinetic activity"   → describe the specific military action
   "threat actors"      → name the specific group or use "adversary forces"
   "threat landscape"   → describe the specific threat environment
   "robust"             → use "substantial", "significant", or "extensive" with qualification
   "leverage" (verb)    → use "exploit", "employ", "use", or "apply"
   "ongoing situation"  → describe the specific developing event
   "fluid situation"    → describe what is changing and how rapidly

7. PARAGRAPH COMPLETENESS: Every paragraph must contain at least two complete sentences.
   A second sentence must either provide evidence, elaborate the assessment, or identify uncertainty.
"""

DOMAINS = [
    ('d1', '01', 'BATTLESPACE · KINETIC',
     'What is the current disposition of forces, and what activity occurred across all theatres in the last 24 hours?'),
    ('d2', '02', 'ESCALATION · TRAJECTORY',
     "What is Iran's nuclear trajectory and overall escalation risk horizon?"),
    ('d3', '03', 'ENERGY · ECONOMIC',
     'How has the conflict affected energy supply, pricing, and regional economic stability?'),
    ('d4', '04', 'DIPLOMATIC · POLITICAL',
     'What is the diplomatic posture of key actors?'),
    ('d5', '05', 'CYBER · INFORMATION OPS',
     'What cyber and information operations are assessed as underway?'),
    ('d6', '06', 'WAR RISK INSURANCE · MARITIME FINANCE',
     'How has the security environment affected war risk insurance pricing and vessel routing?'),
]

# ── Shared voice rules injected into every subagent prompt ────────────────────
_VOICE_RULES = """\
VOICE RULES (MANDATORY — violations invalidate the brief):
- Every lead sentence is an assessment, not a factual description.
- Confidence language — use ONLY these exact phrases:
    "We assess with high confidence…"                  95–99%  almost-certainly
    "We judge it highly likely…"                       75–95%  highly-likely
    "Available evidence suggests…"                     55–75%  likely
    "Reporting indicates, though corroboration is limited…"  45–55%  possibly
    "We judge it unlikely, though we cannot exclude…"  20–45%  unlikely
    "We assess with high confidence this will not…"    1–5%    almost-certainly-not
- Source attribution in every factual sentence: (AP, 05 Mar 0620 UTC)
- Temporal precision on every kinetic claim: "As of 0600 UTC 05 Mar"
- Tier 1 sources → verificationStatus: "confirmed"
- Tier 2 sources → verificationStatus: "reported"
- Iranian state media (PressTV, IRNA, Fars, Mehr, Tasnim) → NEVER factual.
  Label as "Iranian government asserts…" | verificationStatus: "claimed"
- Every paragraph ≥ 2 sentences. No fragment leads.
- Sub-labels: "OBSERVED ACTIVITY" (Tier 1 facts) / "OPERATIONAL ASSESSMENT" (analysis)
- FORBIDDEN: "kinetic activity", "threat actors", "threat landscape", "robust",
  "leverage" (verb), "ongoing situation", "fluid situation"
"""


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — PARALLEL SOURCE FETCH (Python, no Claude)
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_html(text: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>',  ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                          ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        text = text.replace(entity, char)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_rss(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _strip_html(xml_text)[:FETCH_CHAR_LIMIT]

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    is_atom = 'atom' in root.tag or root.tag == 'feed'
    items: list[str] = []

    if is_atom:
        for e in root.findall('atom:entry', ns)[:15]:
            title   = (e.findtext('atom:title', '', ns) or '').strip()
            summary = _strip_html(e.findtext('atom:summary', '', ns) or
                                  e.findtext('atom:content', '', ns) or '')
            pub     = (e.findtext('atom:published', '', ns) or
                       e.findtext('atom:updated', '', ns) or '')[:16]
            if title:
                items.append(f'[{pub}] {title}. {summary[:350]}')
    else:
        for e in root.findall('.//item')[:15]:
            title   = (e.findtext('title') or '').strip()
            summary = _strip_html(e.findtext('description') or '')
            pub     = (e.findtext('pubDate') or '')[:25]
            if title:
                items.append(f'[{pub}] {title}. {summary[:350]}')

    return ('\n\n'.join(items) or _strip_html(xml_text))[:FETCH_CHAR_LIMIT]


def _fetch_one(source: dict) -> tuple[str, str]:
    """Fetch one source URL. Returns (source_id, content_text)."""
    sid  = source['id']
    url  = source.get('url', '')
    name = source.get('name', sid)
    if not url:
        return sid, '[NO URL]'
    try:
        resp = _requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT,
                             allow_redirects=True)
        resp.raise_for_status()
        ct   = resp.headers.get('Content-Type', '')
        text = resp.text.lstrip()
        if ('xml' in ct or 'rss' in ct
                or text.startswith('<rss') or text.startswith('<feed')):
            content = _parse_rss(resp.text)
        else:
            content = _strip_html(resp.text)[:FETCH_CHAR_LIMIT]
        log.info('OK       %-35s  %d chars', name, len(content))
        return sid, content
    except _requests.exceptions.Timeout:
        log.warning('TIMEOUT  %-35s', name)
        return sid, f'[TIMEOUT — {url}]'
    except _requests.exceptions.HTTPError as exc:
        log.warning('HTTP %-3s  %-35s', exc.response.status_code, name)
        return sid, f'[HTTP {exc.response.status_code} — {url}]'
    except Exception as exc:
        log.warning('ERROR    %-35s  %s', name, str(exc)[:80])
        return sid, f'[ERROR — {exc}]'


def fetch_all_sources(sources: list[dict]) -> dict[str, str]:
    """
    Fetch all enabled, non-email sources in parallel.
    Returns {source_id: content_text}.
    """
    fetchable = [s for s in sources
                 if s.get('enabled', True)
                 and s.get('url')
                 and s.get('method') != 'email']
    log.info('Fetching %d sources (workers=%d)...', len(fetchable), FETCH_WORKERS)
    t0      = time.time()
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for sid, content in pool.map(_fetch_one, fetchable):
            results[sid] = content
    ok = sum(1 for v in results.values() if not v.startswith('['))
    log.info('Fetch done: %d/%d OK — %.1fs', ok, len(fetchable), time.time() - t0)
    return results


def _load_sources() -> list[dict]:
    data    = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    sources = [s for s in data.get('sources', []) if s.get('enabled', True)]
    sources.sort(key=lambda s: (s.get('tier', 3), s.get('id', '')))
    return sources


def _domain_content_block(domain_id: str, sources: list[dict],
                           fetched: dict[str, str]) -> str:
    """Format fetched content for all sources tagged to this domain."""
    relevant = [s for s in sources if domain_id in s.get('domains', [])]
    if not relevant:
        return '(no sources tagged for this domain)'
    parts = []
    for s in relevant:
        tier_label = {1: 'TIER 1 — CONFIRMED', 2: 'TIER 2 — REPORTED',
                      3: 'TIER 3 — CLAIMED'}.get(s.get('tier', 3), 'TIER ?')
        content = fetched.get(s['id'], '[NOT FETCHED]')
        parts.append(f'### [{tier_label}] {s["name"]}\n{content}')
    return '\n\n---\n\n'.join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE CLI INVOCATION
# ═══════════════════════════════════════════════════════════════════════════════

_RETRYABLE_PATTERNS = ('rate limit', 'overloaded', 'too many requests', 'temporarily')
_RETRY_DELAYS       = (8, 20)   # seconds between attempts 1→2 and 2→3


def _call_claude(prompt: str, model: str, label: str = '') -> str:
    """
    Invoke the claude CLI with the given prompt.
    Returns the stdout response text.

    Retries up to 2 times with backoff on transient errors (rate limits,
    server overload, subprocess timeout).  Permanent errors (bad model,
    invalid flags) raise immediately after the first attempt.
    """
    cmd = ['claude', '-p', prompt]
    if model:
        cmd += ['--model', model]
    cmd += ['--dangerously-skip-permissions']

    max_attempts = len(_RETRY_DELAYS) + 1
    log.info('CLI subagent %-20s starting...', label or '?')
    t0 = time.time()

    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CLI_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            if attempt < max_attempts - 1:
                delay = _RETRY_DELAYS[attempt]
                log.warning('CLI subagent %s timed out (attempt %d/%d) — retrying in %ds',
                            label, attempt + 1, max_attempts, delay)
                time.sleep(delay)
                continue
            raise RuntimeError(f'claude CLI timed out after {CLI_TIMEOUT}s [{label}]')
        except FileNotFoundError:
            raise RuntimeError(
                'claude CLI not found. Ensure Claude Code CLI is installed and on PATH.'
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            is_transient = any(p in stderr.lower() for p in _RETRYABLE_PATTERNS)
            if is_transient and attempt < max_attempts - 1:
                delay = _RETRY_DELAYS[attempt]
                log.warning('CLI subagent %s transient error (attempt %d/%d) — retrying in %ds: %s',
                            label, attempt + 1, max_attempts, delay, stderr[:200])
                time.sleep(delay)
                continue
            raise RuntimeError(
                f'claude CLI exited {result.returncode} [{label}]: {stderr[:400]}'
            )

        elapsed = time.time() - t0
        log.info('CLI subagent %-20s done — %.1fs', label or '?', elapsed)
        return result.stdout.strip()

    raise RuntimeError(f'CLI subagent [{label}] failed after {max_attempts} attempts')


def _extract_json(text: str) -> dict | list:
    """
    Extract a JSON object or array from CLI response text.

    Tries code fences first, then bare JSON, then searches for the outermost
    bracket that appears FIRST in the text — so an array response like
    `[{...}, {...}]` isn't mistakenly parsed as the first inner dict.
    """
    text = text.strip()
    if '```json' in text:
        text = text.split('```json', 1)[1].split('```', 1)[0].strip()
    elif '```' in text:
        text = text.split('```', 1)[1].split('```', 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find whichever outermost bracket appears first in the text.
    # This is critical: if the response is a JSON array, trying '{' first
    # would extract the first inner dict instead of the full array.
    brace_pos   = text.find('{')
    bracket_pos = text.find('[')

    candidates: list[tuple[int, str, str]] = []
    if brace_pos   != -1: candidates.append((brace_pos,   '{', '}'))
    if bracket_pos != -1: candidates.append((bracket_pos, '[', ']'))
    candidates.sort(key=lambda t: t[0])  # try whichever comes first

    for start, open_ch, close_ch in candidates:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f'No valid JSON found in response (first 300 chars): {text[:300]}')


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — 6 DOMAIN SUBAGENTS (all concurrent)
# ═══════════════════════════════════════════════════════════════════════════════

_DOMAIN_SCHEMA = """\
Return a single JSON object with this exact structure (raw JSON, no fences):
{
  "id": "<domain_id>",
  "num": "<domain_num>",
  "title": "<DOMAIN TITLE>",
  "assessmentQuestion": "<assessment question>",
  "confidence": "high|moderate|low",
  "keyJudgment": {
    "id": "kj-<domain_id>",
    "domain": "<domain_id>",
    "confidence": "high|moderate|low",
    "probabilityRange": "e.g. 75-95%",
    "language": "almost-certainly|highly-likely|likely|possibly|unlikely|almost-certainly-not",
    "text": "Single assessment sentence beginning with the confidence phrase.",
    "basis": "Evidence basis in one sentence.",
    "citations": [{"source": "AP", "tier": 1, "verificationStatus": "confirmed"}]
  },
  "bodyParagraphs": [
    {
      "subLabel": "OBSERVED ACTIVITY",
      "subLabelVariant": "observed",
      "text": "Tier 1 factual paragraph (>=2 sentences). Time-stamped and attributed.",
      "timestamp": "2026-03-05T06:00:00Z",
      "citations": [{"source": "AP", "tier": 1, "verificationStatus": "confirmed"}],
      "confidenceLanguage": "highly-likely"
    },
    {
      "subLabel": "OPERATIONAL ASSESSMENT",
      "subLabelVariant": "assessment",
      "text": "Analytical paragraph (>=2 sentences). What does the evidence mean?",
      "citations": []
    }
  ]
}"""


def _domain_prompt(domain_id: str, domain_num: str, domain_title: str,
                   aq: str, content: str, date_str: str, date_iso: str) -> str:
    return f"""You are a senior conflict intelligence analyst drafting the {domain_id.upper()} section of the CSE Daily Intelligence Brief.

Date: {date_str} | Period: 24h ending 0600 UTC {date_iso}
Domain: {domain_num} — {domain_title}
Assessment Question: {aq}

{_VOICE_RULES}

SOURCE MATERIAL (fetched live — Tier 1 sources are the factual floor):

{content}

TASK: Draft the complete {domain_id.upper()} domain section.
- Answer the assessment question above with evidence from the source material
- Write ≥3 body paragraphs (at least 1 OBSERVED ACTIVITY, at least 1 OPERATIONAL ASSESSMENT)
- If source material is thin, note that explicitly in a collection gap paragraph

{_DOMAIN_SCHEMA}"""


def run_domain_subagent(domain_id: str, domain_num: str, domain_title: str,
                        aq: str, content: str, target_date: datetime,
                        model: str) -> dict:
    """Run one domain subagent via claude CLI. Returns the domain section dict."""
    date_str = target_date.strftime('%d %B %Y')
    date_iso = target_date.strftime('%Y-%m-%d')
    prompt   = _domain_prompt(domain_id, domain_num, domain_title,
                               aq, content, date_str, date_iso)
    try:
        text    = _call_claude(prompt, model, label=domain_id.upper())
        section = _extract_json(text)
        if not isinstance(section, dict):
            section = {}
    except Exception as exc:
        log.error('Domain %s subagent failed: %s', domain_id.upper(), exc)
        section = {}

    # Guarantee required keys
    section.setdefault('id',    domain_id)
    section.setdefault('num',   domain_num)
    section.setdefault('title', domain_title)
    section.setdefault('assessmentQuestion', aq)
    section.setdefault('confidence', 'moderate')
    section.setdefault('keyJudgment', {
        'id': f'kj-{domain_id}', 'domain': domain_id,
        'confidence': 'moderate', 'probabilityRange': '55-75%',
        'language': 'likely',
        'text': f'[{domain_id.upper()} draft unavailable — subagent failed]',
        'basis': '', 'citations': [],
    })
    section.setdefault('bodyParagraphs', [])
    return section


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2.5 — VOICE REVIEW SUBAGENTS (6 concurrent, after domain drafts)
# ═══════════════════════════════════════════════════════════════════════════════

_VOICE_REVIEW_SCHEMA = """\
Return the corrected domain section as a single JSON object (raw JSON, no fences).
Keep all fields identical to the input — only rewrite the TEXT CONTENT of:
  - keyJudgment.text
  - keyJudgment.basis
  - bodyParagraphs[].text
Do NOT change: id, num, title, assessmentQuestion, confidence, language,
probabilityRange, citations, subLabel, subLabelVariant, timestamp.
If a paragraph already meets all standards, reproduce it unchanged."""


def _voice_review_prompt(section: dict, date_iso: str) -> str:
    section_json = json.dumps(section, indent=2, ensure_ascii=False)
    return f"""\
You are an intelligence product quality control reviewer.
Your task is to correct the following domain section so it fully complies with
the intelligence writing standards below. You are reviewing for publication.
Date: {date_iso}

{_VOICE_REVIEW_RULES}

DOMAIN SECTION TO REVIEW:
{section_json}

{_VOICE_REVIEW_SCHEMA}"""


def run_voice_review_subagent(section: dict, target_date: datetime, model: str) -> dict:
    """
    Run a voice compliance review on one domain section via claude CLI.
    Returns the corrected section dict (same schema, improved prose).
    """
    domain_id = section.get('id', '?')
    date_iso  = target_date.strftime('%Y-%m-%d')
    prompt    = _voice_review_prompt(section, date_iso)

    try:
        text   = _call_claude(prompt, model, label=f'voice-{domain_id.upper()}')
        result = _extract_json(text)
        if not isinstance(result, dict):
            log.warning('Voice review %s returned non-dict — keeping original', domain_id)
            return section
        # Preserve guaranteed keys in case the reviewer dropped them
        for key in ('id', 'num', 'title', 'assessmentQuestion', 'confidence',
                    'keyJudgment', 'bodyParagraphs'):
            if key not in result:
                result[key] = section.get(key)
        return result
    except Exception as exc:
        log.warning('Voice review %s failed (%s) — keeping original draft', domain_id, exc)
        return section


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2.7 — CROSS-DOMAIN EDITORIAL SUBAGENT (single pass after voice review)
# ═══════════════════════════════════════════════════════════════════════════════

_EDITORIAL_RULES = """\
CROSS-DOMAIN EDITORIAL STANDARDS — CSE INTELLIGENCE BRIEF

You are the senior editor of the CSE Intelligence Brief. Review all six domain
sections for internal consistency, cross-domain coherence, and analytical quality.

STANDARDS TO ENFORCE:
1. DEDUPLICATION: If the same event appears in two domains, keep the primary
   reference (higher-tier source) and reduce the secondary to a brief cross-ref.
2. CONTRADICTION CHECK: If two domains make contradictory claims, flag the lower-
   confidence one with a note. Do NOT silently delete either claim.
3. LEAD SENTENCE DISCIPLINE: Every body paragraph must begin with an analytical
   assessment, not a factual description. Fix any that do not.
4. MINIMUM SENTENCE LENGTH: Every sentence ≥ 8 words. Merge short sentences.
5. FORBIDDEN PHRASES: Remove any instance of "kinetic activity", "threat actors",
   "threat landscape", "robust", "leverage" (as verb), "ongoing situation".
6. BLUF ALIGNMENT: Ensure the executive BLUF (if present) is consistent with the
   domain key judgments. Do not invent new facts.
7. CLARITY: Remove jargon, academic hedging, and excessive qualification.
   Every sentence must be clear to a senior official with no domain expertise.

WHAT YOU MAY CHANGE:
  - bodyParagraphs[].text in any domain section
  - keyJudgment.text and keyJudgment.basis in any domain section
  - You may add a one-sentence cross-reference note to a paragraph's end

WHAT YOU MUST NOT CHANGE:
  - id, num, title, assessmentQuestion, confidence, language, probabilityRange
  - citations, subLabel, subLabelVariant, timestamp on any paragraph
  - Any structural fields — only free-text prose content"""


def _editorial_prompt(sections: list[dict], date_iso: str) -> str:
    sections_json = json.dumps(sections, indent=2, ensure_ascii=False)
    return f"""\
You are the senior editor of the CSE Daily Intelligence Brief.
Date: {date_iso}

{_EDITORIAL_RULES}

ALL SIX DOMAIN SECTIONS (review all simultaneously):
{sections_json}

Return the complete corrected sections list as a raw JSON array (no fences).
Each element is a complete domain section object with all fields preserved.
Only modify prose text fields where improvements are necessary."""


def run_editorial_subagent(sections: list[dict], target_date: datetime,
                           model: str) -> list[dict]:
    """
    Single cross-domain editorial review via claude CLI.
    Reviews all 6 sections simultaneously for consistency and quality.
    Returns corrected sections list (falls back to original on error).
    """
    date_iso = target_date.strftime('%Y-%m-%d')
    prompt   = _editorial_prompt(sections, date_iso)

    try:
        text   = _call_claude(prompt, model, label='EDITORIAL')
        result = _extract_json(text)
        if isinstance(result, list) and len(result) == len(sections):
            # Preserve guaranteed structural keys in each section
            for i, (orig, rev) in enumerate(zip(sections, result)):
                for key in ('id', 'num', 'title', 'assessmentQuestion',
                            'confidence', 'keyJudgment', 'bodyParagraphs'):
                    if key not in rev:
                        rev[key] = orig.get(key)
            log.info('Editorial pass complete — %d sections reviewed', len(result))
            return result
        else:
            log.warning('Editorial subagent returned unexpected shape — keeping reviewed draft')
            return sections
    except Exception as exc:
        log.warning('Editorial subagent failed (%s) — keeping reviewed draft', exc)
        return sections


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — 4 SYNTHESIS SUBAGENTS (all concurrent)
# ═══════════════════════════════════════════════════════════════════════════════

def _sections_summary(sections: list[dict]) -> str:
    parts = []
    for s in sections:
        kj    = s.get('keyJudgment', {})
        paras = ' '.join(p.get('text', '')[:200] for p in s.get('bodyParagraphs', [])[:2])
        parts.append(
            f"[{s.get('id','?').upper()}] {s.get('title','')}\n"
            f"KJ: {kj.get('text','')} [{kj.get('confidence','?')}]\n"
            f"Summary: {paras}"
        )
    return '\n\n'.join(parts)


def _executive_prompt(sections: list[dict], date_str: str, date_iso: str) -> str:
    summary = _sections_summary(sections)
    return f"""You are synthesising the executive layer of the CSE Daily Intelligence Brief.
Date: {date_str} | Period: 24h ending 0600 UTC {date_iso}

{_VOICE_RULES}

DOMAIN SECTION SUMMARIES:
{summary}

TASK: Draft the executive assessment as a single JSON object (raw JSON, no fences):
{{
  "bluf": "2-4 sentence BLUF. First sentence must be a judgment, not a description.",
  "keyJudgments": [
    {{
      "id": "kj-exec-1",
      "domain": "d1",
      "confidence": "high|moderate|low",
      "probabilityRange": "75-95%",
      "language": "highly-likely",
      "text": "Judgment beginning with confidence phrase.",
      "basis": "Evidence basis.",
      "citations": [{{"source": "AP", "tier": 1, "verificationStatus": "confirmed"}}]
    }}
  ],
  "kpis": [
    {{"domain": "d1", "number": "14",      "label": "Strikes (24h)",       "changeDirection": "up"}},
    {{"domain": "d2", "number": "72%",     "label": "Escalation risk",     "changeDirection": "up"}},
    {{"domain": "d3", "number": "$94.20",  "label": "Brent crude",         "changeDirection": "up"}},
    {{"domain": "d4", "number": "3",       "label": "Position shifts",     "changeDirection": "neutral"}},
    {{"domain": "d6", "number": "$0.75/GRT","label": "War risk premium",   "changeDirection": "up"}}
  ]
}}
Include 4-6 key judgments covering all six domains."""


def _strategic_header_prompt(sections: list[dict], date_str: str, date_iso: str) -> str:
    kjs = '\n'.join(
        f"- [{s.get('id','?')}] {s.get('keyJudgment',{}).get('text','')}"
        for s in sections
    )
    return f"""You are drafting the strategic header of the CSE Daily Intelligence Brief.
Date: {date_str}

KEY JUDGMENTS FROM ALL DOMAINS:
{kjs}

Return a single JSON object (raw JSON, no fences):
{{
  "headlineJudgment": "The single most important analytical sentence this cycle. Must be an assessment, not a description.",
  "trajectoryRationale": "1-2 sentence explanation of threat direction.",
  "threatLevel": "CRITICAL|SEVERE|ELEVATED|GUARDED|LOW",
  "threatTrajectory": "escalating|stable|de-escalating"
}}"""


def _warning_indicators_prompt(sections: list[dict], date_str: str) -> str:
    summary = _sections_summary(sections)
    return f"""You are drafting warning indicators for the CSE Daily Intelligence Brief.
Date: {date_str}

DOMAIN SUMMARIES:
{summary}

Return a JSON array of 4-7 warning indicators (raw JSON array, no fences):
[
  {{
    "id": "wi-01",
    "indicator": "Indicator name (e.g. IRGC ballistic missile readiness)",
    "domain": "d1|d2|d3|d4|d5|d6",
    "status": "watching|triggered|elevated|cleared",
    "change": "new|elevated|unchanged|cleared",
    "detail": "Current assessment of this indicator based on the source material."
  }}
]"""


def _collection_gaps_prompt(sections: list[dict], date_str: str) -> str:
    domain_confs = '\n'.join(
        f"- {s.get('id','?')}: confidence={s.get('confidence','?')}, "
        f"paragraphs={len(s.get('bodyParagraphs',[]))}"
        for s in sections
    )
    return f"""You are identifying collection gaps for the CSE Daily Intelligence Brief.
Date: {date_str}

DOMAIN COVERAGE:
{domain_confs}

Return a JSON array of 3-6 collection gaps (raw JSON array, no fences):
[
  {{
    "id": "cg-01",
    "domain": "d1|d2|d3|d4|d5|d6",
    "gap": "What specific information we lack.",
    "significance": "Why this gap matters for assessment quality.",
    "severity": "critical|significant|minor"
  }}
]"""


def run_synthesis_subagent(task: str, sections: list[dict],
                           target_date: datetime, model: str) -> dict | list:
    """
    Run one synthesis subagent (executive, strategic_header, warning_indicators,
    collection_gaps). Returns parsed JSON.
    """
    date_str = target_date.strftime('%d %B %Y')
    date_iso = target_date.strftime('%Y-%m-%d')

    if task == 'executive':
        prompt = _executive_prompt(sections, date_str, date_iso)
    elif task == 'strategic_header':
        prompt = _strategic_header_prompt(sections, date_str, date_iso)
    elif task == 'warning_indicators':
        prompt = _warning_indicators_prompt(sections, date_str)
    elif task == 'collection_gaps':
        prompt = _collection_gaps_prompt(sections, date_str)
    else:
        raise ValueError(f'Unknown synthesis task: {task}')

    try:
        text   = _call_claude(prompt, model, label=task)
        result = _extract_json(text)
    except Exception as exc:
        log.error('Synthesis subagent [%s] failed: %s', task, exc)
        result = {} if task in ('executive', 'strategic_header') else []

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent_brief(
    target_date: datetime,
    config: dict,
    model: str = 'claude-sonnet-4-6',
) -> tuple[Path, Path]:
    """
    Run the full parallel agentic brief workflow.

    Phase 1   — Parallel HTTP fetch of all sources (Python, no Claude)
    Phase 2   — 6 concurrent domain subagents (claude CLI)
    Phase 2.5 — 6 concurrent voice review subagents (claude CLI)
    Phase 2.7 — 1 cross-domain editorial subagent (claude CLI)
    Phase 3   — 4 concurrent synthesis subagents (claude CLI)

    Returns (cycle_json_path, html_path).
    """
    # ── Load sources ──────────────────────────────────────────────────────────
    sources = _load_sources()

    # ── Phase 1: Parallel fetch ───────────────────────────────────────────────
    log.info('═══ PHASE 1 — PARALLEL FETCH ══════════════════════')
    fetched = fetch_all_sources(sources)

    # ── Phase 2: 6 domain subagents in parallel ────────────────────────────────
    log.info('═══ PHASE 2 — 6 DOMAIN SUBAGENTS ══════════════════')
    domain_sections: dict[str, dict] = {}

    def _run_domain(args: tuple) -> tuple[str, dict]:
        did, num, title, aq = args
        content = _domain_content_block(did, sources, fetched)
        section = run_domain_subagent(did, num, title, aq, content, target_date, model)
        return did, section

    with ThreadPoolExecutor(max_workers=6) as pool:
        for did, section in pool.map(_run_domain, DOMAINS):
            domain_sections[did] = section
            log.info('Domain %s section received', did.upper())

    # Preserve ordered list for JSON output
    sections_list = [domain_sections[d[0]] for d in DOMAINS if d[0] in domain_sections]
    log.info('Phase 2 complete — %d/6 domain sections drafted', len(sections_list))

    # ── Phase 2.5: Voice review — 6 concurrent CLI subagents ─────────────────
    log.info('═══ PHASE 2.5 — VOICE REVIEW (6 concurrent) ════════')

    def _review_section(section: dict) -> dict:
        return run_voice_review_subagent(section, target_date, model)

    with ThreadPoolExecutor(max_workers=6) as pool:
        reviewed_list = list(pool.map(_review_section, sections_list))
    sections_list = reviewed_list
    log.info('Voice review complete')

    # ── Phase 2.7: Cross-domain editorial pass — single subagent ──────────────
    log.info('═══ PHASE 2.7 — CROSS-DOMAIN EDITORIAL ════════════')
    sections_list = run_editorial_subagent(sections_list, target_date, model)

    # ── Phase 3: 4 synthesis subagents in parallel ─────────────────────────────
    log.info('═══ PHASE 3 — 4 SYNTHESIS SUBAGENTS ═══════════════')
    synthesis_results: dict[str, dict | list] = {}

    def _run_synthesis(task: str) -> tuple[str, dict | list]:
        result = run_synthesis_subagent(task, sections_list, target_date, model)
        return task, result

    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = ['executive', 'strategic_header', 'warning_indicators', 'collection_gaps']
        for task, result in pool.map(_run_synthesis, tasks):
            synthesis_results[task] = result
            log.info('Synthesis [%s] received', task)

    log.info('Phase 3 complete')

    # ── Assemble BriefCycle JSON ──────────────────────────────────────────────
    date_str   = target_date.strftime('%Y%m%d')
    date_human = target_date.strftime('%d %B %Y').upper()

    sh          = synthesis_results.get('strategic_header', {})
    if not isinstance(sh, dict):
        sh = {}
    threat_lvl  = sh.get('threatLevel', 'SEVERE')
    threat_traj = sh.get('threatTrajectory', 'escalating')

    executive = synthesis_results.get('executive', {})
    if not isinstance(executive, dict):
        executive = {}

    warning_indicators = synthesis_results.get('warning_indicators', [])
    if not isinstance(warning_indicators, list):
        warning_indicators = []

    collection_gaps = synthesis_results.get('collection_gaps', [])
    if not isinstance(collection_gaps, list):
        collection_gaps = []

    cycle: dict = {
        'meta': {
            'cycleId':          f'cycle000_{date_str}',  # overwritten after cycle numbering below
            'cycleNum':         '000',
            'classification':   'PROTECTED B',
            'tlp':              'AMBER',
            'timestamp':        target_date.strftime('%Y-%m-%dT06:00:00Z'),
            'region':           'Iran · Gulf Region · Eastern Mediterranean',
            'analystUnit':      'CSE Conflict Assessment Unit',
            'threatLevel':      threat_lvl,
            'threatTrajectory': threat_traj,
            'subtitle':         'Iran War File — Daily Assessment',
            'contextNote': (
                f'Cycle covers the 24-hour period ending 0600 UTC '
                f'{target_date.strftime("%d %B %Y")}. All times UTC unless noted.'
            ),
            'stripCells': [
                {'top': threat_lvl, 'bot': 'THREAT LEVEL'},
                {'top': '—',        'bot': 'INCIDENTS / 24H'},
                {'top': '—',        'bot': 'BRENT CRUDE'},
                {'top': 'ACTIVE',   'bot': 'HORMUZ STATUS'},
                {'top': '—',        'bot': 'FLASH POINTS'},
            ],
        },
        'strategicHeader': {
            'headlineJudgment':    sh.get('headlineJudgment', ''),
            'trajectoryRationale': sh.get('trajectoryRationale', ''),
        },
        'flashPoints':       [],
        'executive':         executive,
        'domains':           sections_list,
        'warningIndicators': warning_indicators,
        'collectionGaps':    collection_gaps,
        'caveats': {
            'cycleRef': f'CSE-BRIEF-AGENT · {date_human}',
            'items': [{
                'label': 'AGENT DRAFT',
                'text': (
                    f'Produced by 17 {model} CLI subagents across 4 phases. '
                    'Human review required before distribution.'
                ),
            }],
            'confidenceAssessment': 'See individual domain sections.',
            'dissenterNotes':       [],
            'sourceQuality':        'See domain citations.',
            'handling':             'DRAFT — NOT FOR DISTRIBUTION',
        },
        'footer': {
            'id':             f'CSE-BRIEF-AGENT-{date_str}',
            'classification': 'PROTECTED B // TLP:AMBER',
            'sources': (
                'AP · Reuters · CTP-ISW · IAEA · CENTCOM · UKMTO · '
                "Lloyd's · JWC · BIMCO · [see domain citations]"
            ),
            'handling': 'DRAFT — NOT FOR DISTRIBUTION',
        },
    }

    # Assign sequential cycle number
    repo_root  = PIPELINE_DIR.parent
    cycles_dir = repo_root / 'cycles'
    cycles_dir.mkdir(exist_ok=True)

    existing_nums = [
        int(m.group(1))
        for p in cycles_dir.glob('cycle*.json')
        if not p.is_symlink()
        for m in [re.match(r'cycle_?(\d+)', p.name)]
        if m
    ]
    cycle_num = (max(existing_nums) + 1) if existing_nums else 1
    cycle['meta']['cycleNum'] = f'{cycle_num:03d}'
    cycle['meta']['cycleId']  = f'cycle{cycle_num:03d}_{date_str}'

    # Validate before writing — catches schema regressions before they land on disk
    from output.serializer import validate
    errors = validate(cycle)
    if errors:
        for e in errors:
            log.error('Validation error: %s', e)
        raise ValueError(
            f'Agent cycle failed validation with {len(errors)} error(s). '
            'Check subagent output and re-run.'
        )

    cycle_path = cycles_dir / f'cycle{cycle_num:03d}_{date_str}.json'
    cycle_path.write_text(json.dumps(cycle, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Cycle JSON → %s', cycle_path)

    # Update latest.json symlink
    latest = cycles_dir / 'latest.json'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(cycle_path.name)

    # Render HTML
    from render.html_renderer import render_cycle
    html       = render_cycle(cycle)
    briefs_dir = repo_root / 'briefs'
    briefs_dir.mkdir(exist_ok=True)
    html_path  = briefs_dir / f'brief_{date_str}.html'
    html_path.write_text(html, encoding='utf-8')
    log.info('HTML → %s', html_path)

    return cycle_path, html_path
