"""
pipeline/agent_brief.py

Agentic brief runner — Claude drives the full workflow from the CLI.

Claude Sonnet 4.6 is given a `fetch_url` tool and the prioritised source list
from sources.yaml. It autonomously fetches Tier 1 sources first, then Tier 2,
builds its own corpus, and drafts the complete BriefCycle JSON — all six domain
sections, executive assessment, strategic header, warning indicators, and
collection gaps — in a single agentic loop.

The final JSON is written to cycles/ and rendered to briefs/brief_YYYYMMDD.html.

Usage (via main.py):
  python pipeline/main.py agent
  python pipeline/main.py agent --date 2026-03-05
  python pipeline/main.py agent --model claude-opus-4-6

Direct usage:
  python -m pipeline.agent_brief
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests as _requests
import yaml

log = logging.getLogger(__name__)

PIPELINE_DIR  = Path(__file__).parent
SOURCES_FILE  = PIPELINE_DIR / 'ingest' / 'sources.yaml'
PROMPTS_DIR   = PIPELINE_DIR / 'draft' / 'prompts'

# ── Fetch limits ──────────────────────────────────────────────────────────────
FETCH_TIMEOUT     = 15          # seconds per request
FETCH_CHAR_LIMIT  = 5000        # chars returned to Claude per URL
MAX_TOOL_CALLS    = 60          # hard cap on total fetch iterations
FETCH_DELAY       = 0.4         # seconds between requests (rate-limit courtesy)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; CSE-Intel-Brief/2.0; research pipeline)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# ── Tool definition ───────────────────────────────────────────────────────────

FETCH_URL_TOOL = {
    'name': 'fetch_url',
    'description': (
        'Fetch the content of a URL and return the text. '
        'Handles both HTML pages and RSS/Atom feeds. '
        'For RSS feeds, returns structured article summaries. '
        'For HTML pages, returns the main text content stripped of markup. '
        'Content is truncated to the most informative portion. '
        'Use this to retrieve news from each source in the source list.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'url': {
                'type': 'string',
                'description': 'The URL to fetch.',
            },
            'source_name': {
                'type': 'string',
                'description': 'Human-readable name of the source (for logging).',
            },
        },
        'required': ['url'],
    },
}


# ── URL fetching ──────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>',  ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;',  '&',  text)
    text = re.sub(r'&lt;',   '<',  text)
    text = re.sub(r'&gt;',   '>',  text)
    text = re.sub(r'&quot;', '"',  text)
    text = re.sub(r'&#39;',  "'",  text)
    text = re.sub(r'&nbsp;', ' ',  text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_rss(xml_text: str) -> str:
    """Parse an RSS/Atom feed and return a readable summary of recent items."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _strip_html(xml_text)[:FETCH_CHAR_LIMIT]

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    is_atom = 'atom' in root.tag or root.tag == 'feed'

    if is_atom:
        entries = root.findall('atom:entry', ns)
        items = []
        for e in entries[:12]:
            title   = (e.findtext('atom:title', '', ns) or '').strip()
            summary = (e.findtext('atom:summary', '', ns) or
                       e.findtext('atom:content', '', ns) or '').strip()
            pub     = (e.findtext('atom:published', '', ns) or
                       e.findtext('atom:updated', '', ns) or '').strip()
            if title:
                items.append(f'[{pub[:16]}] {title}. {_strip_html(summary)[:300]}')
    else:
        entries = root.findall('.//item')
        items = []
        for e in entries[:12]:
            title   = (e.findtext('title') or '').strip()
            summary = (e.findtext('description') or '').strip()
            pub     = (e.findtext('pubDate') or '').strip()
            if title:
                items.append(f'[{pub[:25]}] {title}. {_strip_html(summary)[:300]}')

    if not items:
        return _strip_html(xml_text)[:FETCH_CHAR_LIMIT]

    result = '\n\n'.join(items)
    return result[:FETCH_CHAR_LIMIT]


def do_fetch_url(url: str, source_name: str = '') -> str:
    """
    Fetch a URL and return text content suitable for Claude's context.
    Detects RSS/Atom vs HTML and parses accordingly.
    """
    label = source_name or url[:60]
    try:
        resp = _requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except _requests.exceptions.Timeout:
        log.warning('TIMEOUT fetching %s', label)
        return f'[FETCH TIMEOUT — {url}]'
    except _requests.exceptions.HTTPError as exc:
        log.warning('HTTP %s fetching %s', exc.response.status_code, label)
        return f'[HTTP {exc.response.status_code} — {url}]'
    except Exception as exc:
        log.warning('FETCH ERROR %s: %s', label, exc)
        return f'[FETCH ERROR — {url}: {exc}]'

    content_type = resp.headers.get('Content-Type', '')
    text = resp.text

    if 'xml' in content_type or 'rss' in content_type or text.lstrip().startswith('<rss') or text.lstrip().startswith('<feed'):
        result = _parse_rss(text)
    else:
        result = _strip_html(text)[:FETCH_CHAR_LIMIT]

    log.info('Fetched %-40s  %d chars', label, len(result))
    return result


# ── Source loading ────────────────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    """Load enabled sources from sources.yaml, sorted by tier then domain priority."""
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding='utf-8'))
    sources = [s for s in data.get('sources', []) if s.get('enabled', True) and s.get('url')]
    # Sort: Tier 1 first, then Tier 2, then Tier 3
    sources.sort(key=lambda s: (s.get('tier', 3), s.get('id', '')))
    return sources


def _sources_for_prompt(sources: list[dict]) -> str:
    """Format sources as a numbered list for the system prompt."""
    lines = []
    current_tier = None
    for s in sources:
        tier = s.get('tier', 3)
        if tier != current_tier:
            current_tier = tier
            tier_label = {1: 'TIER 1 — Factual Floor (fetch these first, cite as confirmed)',
                          2: 'TIER 2 — Analytical Depth (fetch for context, cite as reported)',
                          3: 'TIER 3 — Domain Triggers (fetch if relevant signal found)'}.get(tier, f'TIER {tier}')
            lines.append(f'\n### {tier_label}')
        domains = ', '.join(s.get('domains', []))
        method = s.get('method', '?')
        if method == 'email':
            continue  # skip email sources — not fetchable via tool
        lines.append(f'- [{s["id"]}] {s["name"]} — {s["url"]} — domains: {domains}')
    return '\n'.join(lines)


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(target_date: datetime, sources: list[dict]) -> str:
    date_str    = target_date.strftime('%d %B %Y')
    date_iso    = target_date.strftime('%Y-%m-%d')
    source_list = _sources_for_prompt(sources)

    # Load domain prompts to embed the analytical questions
    def _load_prompt(fname: str) -> str:
        p = PROMPTS_DIR / fname
        return p.read_text(encoding='utf-8') if p.exists() else ''

    d1_schema = _extract_output_schema(_load_prompt('battlespace.md'))
    d2_schema = _extract_output_schema(_load_prompt('escalation.md'))
    d3_schema = _extract_output_schema(_load_prompt('energy.md'))
    d4_schema = _extract_output_schema(_load_prompt('diplomatic.md'))
    d5_schema = _extract_output_schema(_load_prompt('cyber.md'))
    d6_schema = _extract_output_schema(_load_prompt('war_risk.md'))

    return f"""You are a senior conflict intelligence analyst producing the CSE Daily Intelligence Brief for the Iran War File.

Today is {date_str} (UTC). You are covering the 24-hour period ending 0600 UTC {date_iso}.

## YOUR TASK

Use the fetch_url tool to retrieve content from the sources below. Then draft the complete intelligence brief as a single BriefCycle JSON object.

**Research sequence:**
1. Fetch all TIER 1 sources first — these are your factual floor
2. Fetch priority TIER 2 sources — these add analytical depth
3. Once you have sufficient material (minimum: all Tier 1 sources attempted), draft the complete JSON

Do not ask for confirmation. Do not summarise your actions. Fetch sources, then produce the JSON.

## SOURCE LIST
{source_list}

## VOICE AND WRITING RULES (MANDATORY — violations invalidate the brief)

- **Every lead sentence is an assessment, not a factual description.**
  BAD: "Three BTGs were observed near Kherson."
  GOOD: "We assess offensive preparations are underway; three BTGs have repositioned near Kherson."

- **Confidence language ladder** — use ONLY these exact phrases, never ad-hoc hedging:
  - "We assess with high confidence…" → 95–99% | enum: almost-certainly
  - "We judge it highly likely…" → 75–95% | enum: highly-likely
  - "Available evidence suggests…" → 55–75% | enum: likely
  - "Reporting indicates, though corroboration is limited…" → 45–55% | enum: possibly
  - "We judge it unlikely, though we cannot exclude…" → 20–45% | enum: unlikely
  - "We assess with high confidence this will not…" → 1–5% | enum: almost-certainly-not

- **Source attribution** in every sentence with a factual claim: `(AP, {date_iso[:7]}-05 0620 UTC)`
- **Temporal precision** on every kinetic claim: "As of 0600 UTC {date_iso[:7]}-05"
- **Tier 1 sources** (AP, Reuters, CTP-ISW, IAEA, CENTCOM, UKMTO, IDF) → verificationStatus: "confirmed"
- **Tier 2 sources** → verificationStatus: "reported"
- **Iranian state media** (PressTV, IRNA, Fars, Mehr, Tasnim, Tehran Times) → NEVER factual floor; always: "Iranian government asserts…" | verificationStatus: "claimed"
- **Every paragraph ≥ 2 sentences.** No fragment leads.
- **Sub-labels:** "OBSERVED ACTIVITY" for Tier 1 facts; "OPERATIONAL ASSESSMENT" for analytical judgments
- **FORBIDDEN PHRASES:** "kinetic activity" · "threat actors" · "threat landscape" · "robust" · "leverage" (as verb) · "ongoing situation" · "fluid situation"

## DOMAINS TO COVER

Draft all six domains in this exact order (each section receives prior context):

**D1 — BATTLESPACE · KINETIC**
What is the current disposition of forces, and what activity occurred across all theatres in the last 24h?
Theatres: Israeli-Iranian direct exchange, Gaza, West Bank, Lebanon/Hezbollah, Yemen/Houthi Red Sea, Iraq/Syria proxy corridor, Hormuz/maritime.

**D2 — ESCALATION · TRAJECTORY**
What is Iran's nuclear trajectory and the overall escalation risk horizon?
Cover: IAEA access, enrichment levels, retaliation thresholds, deterrence posture.

**D3 — ENERGY · ECONOMIC**
How has the conflict affected energy supply, pricing, and regional economic stability?
Cover: Brent crude, Hormuz transit, pipeline disruption, OPEC response, market reaction.

**D4 — DIPLOMATIC · POLITICAL**
What is the diplomatic posture of key actors?
Cover: US/UK/EU/Russia/China positions, UN Security Council, ceasefire negotiations, sanctions.

**D5 — CYBER · INFORMATION OPS**
What cyber operations and information operations are assessed as underway?
Cover: IRGC cyber, hacktivist activity, critical infrastructure threats, CISA advisories.

**D6 — WAR RISK INSURANCE · MARITIME FINANCE**
How has the security environment affected war risk insurance pricing and vessel routing?
Cover: JWC listed area changes, Lloyd's premium moves, vessel diversions, P&I club advisories.

## OUTPUT FORMAT

After fetching sources, return a SINGLE raw JSON object — no markdown fences, no explanation text before or after it.

The JSON must match this schema exactly:

{{
  "meta": {{
    "cycleId": "CSE-BRIEF-AGENT-{date_iso.replace('-','')}",
    "cycleNum": "000",
    "classification": "PROTECTED B",
    "tlp": "AMBER",
    "timestamp": "{date_iso}T06:00:00Z",
    "region": "Iran · Gulf Region · Eastern Mediterranean",
    "analystUnit": "CSE Conflict Assessment Unit",
    "threatLevel": "CRITICAL|SEVERE|ELEVATED|GUARDED|LOW",
    "threatTrajectory": "escalating|stable|de-escalating",
    "subtitle": "Iran War File — Daily Assessment",
    "contextNote": "Cycle covers 24h ending 0600 UTC {date_str}. All times UTC unless noted.",
    "stripCells": [
      {{"top": "<threatLevel>", "bot": "THREAT LEVEL"}},
      {{"top": "<N incidents>", "bot": "INCIDENTS / 24H"}},
      {{"top": "$<price>", "bot": "BRENT CRUDE"}},
      {{"top": "ACTIVE|RESTRICTED|CLOSED", "bot": "HORMUZ STATUS"}},
      {{"top": "<N>", "bot": "FLASH POINTS"}}
    ]
  }},
  "strategicHeader": {{
    "headlineJudgment": "Single most important analytical sentence this cycle.",
    "trajectoryRationale": "1–2 sentence explanation of threat direction."
  }},
  "flashPoints": [],
  "executive": {{
    "bluf": "2–4 sentence analytical BLUF. First sentence is a judgment.",
    "keyJudgments": [
      {{
        "id": "kj-exec-1",
        "domain": "d1",
        "confidence": "high|moderate|low",
        "probabilityRange": "75–95%",
        "language": "highly-likely",
        "text": "Judgment text beginning with confidence phrase.",
        "basis": "Evidence basis.",
        "citations": [{{"source": "AP", "tier": 1, "verificationStatus": "confirmed"}}]
      }}
    ],
    "kpis": [
      {{"domain": "d1", "number": "14", "label": "Strikes (24h)", "changeDirection": "up"}},
      {{"domain": "d2", "number": "72%", "label": "Escalation probability", "changeDirection": "up"}},
      {{"domain": "d3", "number": "$94.20", "label": "Brent crude", "changeDirection": "up"}},
      {{"domain": "d4", "number": "3", "label": "Position shifts", "changeDirection": "neutral"}},
      {{"domain": "d6", "number": "$0.75/GRT", "label": "War risk premium", "changeDirection": "up"}}
    ]
  }},
  "domains": [
    {{
      "id": "d1",
      "num": "01",
      "title": "BATTLESPACE · KINETIC",
      "assessmentQuestion": "What is the current disposition of forces, and what activity occurred across all theatres in the last 24 hours?",
      "confidence": "high|moderate|low",
      "keyJudgment": {{
        "id": "kj-d1",
        "domain": "d1",
        "confidence": "high|moderate|low",
        "probabilityRange": "75–95%",
        "language": "highly-likely",
        "text": "Single sentence assessment. Must lead with judgment not description.",
        "basis": "Evidence basis.",
        "citations": [{{"source": "CTP-ISW Evening Report", "tier": 1, "verificationStatus": "confirmed"}}]
      }},
      "bodyParagraphs": [
        {{
          "subLabel": "OBSERVED ACTIVITY",
          "subLabelVariant": "observed",
          "text": "Tier 1-sourced facts, time-stamped, attributed. (AP, {date_iso} 0620 UTC)",
          "timestamp": "{date_iso}T06:00:00Z",
          "citations": [],
          "confidenceLanguage": "highly-likely"
        }},
        {{
          "subLabel": "OPERATIONAL ASSESSMENT",
          "subLabelVariant": "assessment",
          "text": "Analytical interpretation. What does the pattern mean?",
          "citations": []
        }}
      ]
    }},
    {{ "id": "d2", "num": "02", "title": "ESCALATION · TRAJECTORY", "assessmentQuestion": "What is Iran's nuclear trajectory and overall escalation risk?", "confidence": "moderate", "keyJudgment": {{}}, "bodyParagraphs": [] }},
    {{ "id": "d3", "num": "03", "title": "ENERGY · ECONOMIC", "assessmentQuestion": "How has the conflict affected energy supply and pricing?", "confidence": "high", "keyJudgment": {{}}, "bodyParagraphs": [] }},
    {{ "id": "d4", "num": "04", "title": "DIPLOMATIC · POLITICAL", "assessmentQuestion": "What is the diplomatic posture of key actors?", "confidence": "moderate", "keyJudgment": {{}}, "bodyParagraphs": [] }},
    {{ "id": "d5", "num": "05", "title": "CYBER · INFORMATION OPS", "assessmentQuestion": "What cyber and information operations are assessed as underway?", "confidence": "low", "keyJudgment": {{}}, "bodyParagraphs": [] }},
    {{ "id": "d6", "num": "06", "title": "WAR RISK INSURANCE · MARITIME FINANCE", "assessmentQuestion": "How has the security environment affected war risk pricing and vessel routing?", "confidence": "moderate", "keyJudgment": {{}}, "bodyParagraphs": [] }}
  ],
  "warningIndicators": [
    {{
      "id": "wi-01",
      "indicator": "IRGC ballistic missile readiness",
      "domain": "d1",
      "status": "watching|triggered|elevated|cleared",
      "change": "new|elevated|unchanged|cleared",
      "detail": "Assessment of current indicator status."
    }}
  ],
  "collectionGaps": [
    {{
      "id": "cg-01",
      "domain": "d1",
      "gap": "What we don't know.",
      "significance": "Why it matters for assessment quality.",
      "severity": "critical|significant|minor"
    }}
  ],
  "caveats": {{
    "cycleRef": "CSE-BRIEF-AGENT · {date_str.upper()}",
    "items": [
      {{"label": "AGENT DRAFT", "text": "Produced by Claude Sonnet 4.6 agentic run. Human review required before distribution."}}
    ],
    "confidenceAssessment": "Overall confidence assessment across all domains.",
    "dissenterNotes": [],
    "sourceQuality": "See domain citations.",
    "handling": "DRAFT — NOT FOR DISTRIBUTION"
  }},
  "footer": {{
    "id": "CSE-BRIEF-AGENT-{date_iso.replace('-','')}",
    "classification": "PROTECTED B // TLP:AMBER",
    "sources": "AP · Reuters · CTP-ISW · IAEA · CENTCOM · UKMTO · [see domain citations]",
    "handling": "DRAFT — NOT FOR DISTRIBUTION"
  }}
}}

Produce the JSON now. All six domain objects must be fully populated — not placeholders."""


def _extract_output_schema(prompt_text: str) -> str:
    """Extract the JSON schema block from a domain prompt file."""
    if '```json' in prompt_text:
        return prompt_text.split('```json')[1].split('```')[0].strip()
    return ''


# ── Agentic tool loop ─────────────────────────────────────────────────────────

def _run_tool_loop(client, messages: list[dict], tools: list[dict], model: str) -> str:
    """
    Drive the agentic loop until Claude produces end_turn (the final JSON response).
    Returns the text of the final assistant message.
    """
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=messages[0]['content'] if messages[0]['role'] == 'system' else '',
            messages=messages[1:] if messages[0]['role'] == 'system' else messages,
            tools=tools,
        )

        # Collect assistant content
        assistant_content = response.content
        messages.append({'role': 'assistant', 'content': assistant_content})

        if response.stop_reason == 'end_turn':
            # Extract text from content blocks
            for block in assistant_content:
                if hasattr(block, 'text'):
                    return block.text
            return ''

        if response.stop_reason != 'tool_use':
            log.warning('Unexpected stop_reason: %s', response.stop_reason)
            break

        # Process tool calls
        tool_results = []
        for block in assistant_content:
            if block.type != 'tool_use':
                continue

            tool_call_count += 1
            tool_name  = block.name
            tool_input = block.input

            if tool_name == 'fetch_url':
                url         = tool_input.get('url', '')
                source_name = tool_input.get('source_name', '')
                time.sleep(FETCH_DELAY)
                result_text = do_fetch_url(url, source_name)
            else:
                result_text = f'[Unknown tool: {tool_name}]'

            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': block.id,
                'content':     result_text,
            })

            log.info('[%2d/%d] %s → %d chars',
                     tool_call_count, MAX_TOOL_CALLS, tool_name, len(result_text))

        messages.append({'role': 'user', 'content': tool_results})

    log.warning('Hit max tool calls (%d) — extracting best available response', MAX_TOOL_CALLS)
    # Return whatever text the last assistant message contained
    for msg in reversed(messages):
        if msg['role'] == 'assistant':
            for block in (msg['content'] if isinstance(msg['content'], list) else []):
                if hasattr(block, 'text') and block.text:
                    return block.text
    return ''


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from Claude's response text.
    Handles raw JSON, ```json fences, and JSON embedded in prose.
    """
    text = text.strip()

    # Strip markdown fences
    if '```json' in text:
        text = text.split('```json', 1)[1].split('```', 1)[0].strip()
    elif '```' in text:
        text = text.split('```', 1)[1].split('```', 1)[0].strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... } block
    start = text.find('{')
    if start == -1:
        raise ValueError('No JSON object found in response')

    # Walk to find matching closing brace
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as exc:
                    raise ValueError(f'JSON parse failed: {exc}') from exc

    raise ValueError('Unclosed JSON object in response')


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_agent_brief(
    target_date: datetime,
    config: dict,
    model: str = 'claude-sonnet-4-6',
) -> tuple[Path, Path]:
    """
    Run the full agentic brief workflow.

    Returns:
        (cycle_json_path, html_path)
    """
    import anthropic

    api_key = (
        config.get('claude', {}).get('api_key')
        or os.environ.get('ANTHROPIC_API_KEY', '')
    )
    if not api_key:
        raise ValueError(
            'ANTHROPIC_API_KEY not set. Export it or add to pipeline-config.yaml.'
        )

    client = anthropic.Anthropic(api_key=api_key)

    sources    = _load_sources()
    sys_prompt = _build_system_prompt(target_date, sources)

    log.info('Agent model: %s', model)
    log.info('Sources available: %d (email excluded)', len(sources))
    log.info('Starting agentic fetch + draft loop...')

    messages = [
        {'role': 'system', 'content': sys_prompt},
        {
            'role': 'user',
            'content': (
                f'Today is {target_date.strftime("%d %B %Y")} UTC. '
                'Begin by fetching the Tier 1 sources, then produce the complete BriefCycle JSON.'
            ),
        },
    ]

    final_text = _run_tool_loop(client, messages, [FETCH_URL_TOOL], model)

    if not final_text:
        raise RuntimeError('Agent produced no output after tool loop.')

    log.info('Agent loop complete — extracting JSON...')
    cycle = _extract_json(final_text)

    # ── Write cycle JSON ──────────────────────────────────────────────────────
    # Use the serializer for numbering + symlinking
    repo_root  = PIPELINE_DIR.parent
    cycles_dir = repo_root / 'cycles'
    cycles_dir.mkdir(exist_ok=True)

    date_str   = target_date.strftime('%Y%m%d')

    # Stamp meta fields if missing (agent may have filled cycleId already)
    meta = cycle.setdefault('meta', {})
    meta.setdefault('cycleId',     f'CSE-BRIEF-AGENT-{date_str}')
    meta.setdefault('cycleNum',    '000')
    meta.setdefault('timestamp',   target_date.strftime('%Y-%m-%dT06:00:00Z'))

    # Assign next sequential number
    existing_nums = []
    for p in cycles_dir.glob('cycle*.json'):
        if p.is_symlink():
            continue
        m = __import__('re').match(r'cycle_?(\d+)', p.name)
        if m:
            existing_nums.append(int(m.group(1)))
    cycle_num = (max(existing_nums) + 1) if existing_nums else 1
    meta['cycleNum'] = f'{cycle_num:03d}'
    meta['cycleId']  = f'cycle{cycle_num:03d}_{date_str}'

    cycle_path = cycles_dir / f'cycle{cycle_num:03d}_{date_str}.json'
    cycle_path.write_text(json.dumps(cycle, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info('Cycle JSON → %s', cycle_path)

    # Symlink latest.json
    latest = cycles_dir / 'latest.json'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(cycle_path.name)

    # ── Render HTML ───────────────────────────────────────────────────────────
    sys.path.insert(0, str(PIPELINE_DIR))
    from render.html_renderer import render_cycle

    html        = render_cycle(cycle)
    briefs_dir  = repo_root / 'briefs'
    briefs_dir.mkdir(exist_ok=True)
    html_path   = briefs_dir / f'brief_{date_str}.html'
    html_path.write_text(html, encoding='utf-8')
    log.info('HTML → %s', html_path)

    return cycle_path, html_path
