"""
Human review CLI — mandatory step before cycle JSON is written.
Presents each domain section with source citations and allows approval, editing, or regeneration.
Target: ~10 minutes per cycle.
"""

import json
import logging
import os
import subprocess
import sys
import textwrap
import time
from typing import Any

log = logging.getLogger(__name__)

# Terminal colour codes (ANSI) — suppressed when stdout is not a TTY
_IS_TTY = sys.stdout.isatty()

def _ansi(code: str) -> str:
    return f'\033[{code}m' if _IS_TTY else ''

RED     = _ansi('91')
AMBER   = _ansi('93')
GREEN   = _ansi('92')
BLUE    = _ansi('94')
CYAN    = _ansi('96')
DIM     = _ansi('2')
BOLD    = _ansi('1')
RESET   = _ansi('0')


def print_header(text: str, colour: str = CYAN) -> None:
    width = 80
    print(f'\n{colour}{"═" * width}{RESET}')
    print(f'{colour}{BOLD} {text.upper()}{RESET}')
    print(f'{colour}{"═" * width}{RESET}\n')


def print_section(label: str, content: str, colour: str = DIM) -> None:
    print(f'{colour}{BOLD}{label}:{RESET}')
    for line in textwrap.wrap(content, width=76):
        print(f'  {line}')
    print()


def format_citations(citations: list[dict]) -> str:
    if not citations:
        return '(no citations)'
    return '; '.join(
        f"{c.get('source')} [{c.get('verificationStatus', '?').upper()}]"
        for c in citations
    )


_REGEN_RETRY_DELAYS = (8, 20)  # seconds between attempts
_REGEN_CLI_TIMEOUT  = 300       # seconds per claude CLI call


def _regenerate_domain(domain: dict) -> dict | None:
    """
    Re-draft a single domain section via the Claude CLI subprocess.
    Uses the same `claude -p` invocation pattern as agent_brief.py — no Anthropic SDK.
    Returns the new section dict, or None on failure.
    """
    domain_id = domain.get('id', '')
    if not domain_id:
        log.warning('Cannot regenerate: domain has no id field')
        return None

    # Build the regeneration prompt from the existing section's structure
    citations_json = json.dumps(
        [c for p in domain.get('bodyParagraphs', []) for c in p.get('citations', [])],
        indent=2,
    )
    body_summary = '\n'.join(
        f"  [{p.get('subLabel', '?')}]: {p.get('text', '')[:300]}"
        for p in domain.get('bodyParagraphs', [])
    )
    regen_prompt = (
        f"You are a senior conflict intelligence analyst.\n\n"
        f"The analyst has requested a full redraft of the "
        f"{domain.get('title', domain_id)} domain section.\n\n"
        f"Previous key judgment: {domain.get('keyJudgment', {}).get('text', '(none)')}\n\n"
        f"Previous body paragraphs (for context — do NOT repeat verbatim):\n{body_summary}\n\n"
        f"Source citations available from the previous draft:\n{citations_json}\n\n"
        f"TASK: Re-draft this domain section from scratch. Use the same sources but produce "
        f"a substantively different analytical framing. The lead sentence of every paragraph "
        f"must be an assessment, not a factual description. Apply the full confidence ladder. "
        f"Preserve the original schema exactly.\n\n"
        f"Return ONLY a valid JSON object matching this exact structure (raw JSON, no fences):\n"
        f'{{\n'
        f'  "id": "{domain_id}",\n'
        f'  "num": "{domain.get("num", "")}",\n'
        f'  "title": "{domain.get("title", domain_id)}",\n'
        f'  "assessmentQuestion": "{domain.get("assessmentQuestion", "")}",\n'
        f'  "confidence": "high|moderate|low",\n'
        f'  "keyJudgment": {{\n'
        f'    "id": "kj-{domain_id}",\n'
        f'    "domain": "{domain_id}",\n'
        f'    "confidence": "high|moderate|low",\n'
        f'    "probabilityRange": "55-75%",\n'
        f'    "language": "almost-certainly|highly-likely|likely|possibly|unlikely|almost-certainly-not",\n'
        f'    "text": "Assessment sentence beginning with confidence phrase.",\n'
        f'    "basis": "Evidence basis.",\n'
        f'    "citations": []\n'
        f'  }},\n'
        f'  "bodyParagraphs": [\n'
        f'    {{\n'
        f'      "subLabel": "OBSERVED ACTIVITY",\n'
        f'      "subLabelVariant": "observed",\n'
        f'      "text": "Assessment-led paragraph with source attributions. Minimum 2 sentences.",\n'
        f'      "citations": []\n'
        f'    }},\n'
        f'    {{\n'
        f'      "subLabel": "OPERATIONAL ASSESSMENT",\n'
        f'      "subLabelVariant": "assessment",\n'
        f'      "text": "Analytical judgment paragraph. Minimum 2 sentences.",\n'
        f'      "citations": []\n'
        f'    }}\n'
        f'  ]\n'
        f'}}'
    )

    # Strip CLAUDECODE from child environment so the CLI runs inside a Claude Code session
    child_env = {k: v for k, v in os.environ.items() if k != 'CLAUDECODE'}
    cmd = ['claude', '-p', regen_prompt, '--dangerously-skip-permissions']
    max_attempts = len(_REGEN_RETRY_DELAYS) + 1

    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_REGEN_CLI_TIMEOUT,
                env=child_env,
            )
        except subprocess.TimeoutExpired:
            if attempt < max_attempts - 1:
                wait = _REGEN_RETRY_DELAYS[attempt]
                log.warning('Regeneration CLI timed out (attempt %d/%d) — retrying in %ds',
                            attempt + 1, max_attempts, wait)
                time.sleep(wait)
                continue
            log.error('Regeneration CLI timed out after %ds', _REGEN_CLI_TIMEOUT)
            return None
        except FileNotFoundError:
            log.error('claude CLI not found — cannot regenerate. '
                      'Ensure Claude Code CLI is installed and on PATH.')
            return None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            _transient = any(p in stderr.lower()
                             for p in ('rate limit', 'overloaded', 'too many requests'))
            if _transient and attempt < max_attempts - 1:
                wait = _REGEN_RETRY_DELAYS[attempt]
                log.warning('Regeneration transient error (attempt %d/%d) — retrying in %ds: %s',
                            attempt + 1, max_attempts, wait, stderr[:200])
                time.sleep(wait)
                continue
            log.error('Regeneration CLI exited %d: %s', result.returncode, stderr[:400])
            return None

        text = result.stdout.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            log.error('Regeneration JSON parse failed: %s', exc)
            return None

        if isinstance(parsed, dict) and parsed.get('keyJudgment'):
            parsed.setdefault('id', domain_id)
            parsed.setdefault('num', domain.get('num', ''))
            parsed.setdefault('title', domain.get('title', domain_id))
            return parsed

        log.warning('Regeneration returned unexpected structure: %s', str(parsed)[:200])
        return None

    log.error('Regeneration failed after %d attempts', max_attempts)
    return None


def review_domain_section(domain: dict, section_num: int) -> dict | None:
    """
    Display a domain section and prompt for review action.
    Returns approved section dict, or None if regeneration requested.
    """
    colour = [RED, AMBER, GREEN, BLUE, CYAN][section_num % 5]

    print_header(
        f"DOMAIN {domain.get('num', '?')} — {domain.get('title', '?')}",
        colour=colour
    )

    # Key Judgment
    kj = domain.get('keyJudgment', {})
    print_section('KEY JUDGMENT', kj.get('text', '—'), colour=AMBER)
    print(f'{DIM}  Confidence: {kj.get("confidence", "?")} · {kj.get("probabilityRange", "")}{RESET}')
    print(f'{DIM}  Citations:  {format_citations(kj.get("citations", []))}{RESET}')
    print()

    # Body paragraphs (truncated for review speed)
    for i, para in enumerate(domain.get('bodyParagraphs', [])[:3], 1):
        label = para.get('subLabel') or f'PARAGRAPH {i}'
        text = para.get('text', '')
        if len(text) > 400:
            text = text[:400] + '…'
        print_section(label, text)
        print(f'{DIM}  Citations: {format_citations(para.get("citations", []))}{RESET}')

    print()

    while True:
        choice = input(
            f'{colour}[A]pprove  [E]dit key judgment  [R]egenerate  [S]kip  [Q]uit{RESET} › '
        ).strip().upper()

        if choice == 'A':
            print(f'{GREEN}✓ Approved{RESET}')
            return domain

        elif choice == 'E':
            print('Enter new key judgment text (press Enter twice to finish):')
            lines = []
            while True:
                line = input()
                if line == '' and lines:
                    break
                lines.append(line)
            new_text = ' '.join(lines).strip()
            if new_text:
                domain = dict(domain)
                kj = dict(kj)
                kj['text'] = new_text
                domain['keyJudgment'] = kj
            print(f'{GREEN}✓ Edited and approved{RESET}')
            return domain

        elif choice == 'R':
            print(f'{AMBER}↻ Regenerating section via Claude API…{RESET}')
            regenerated = _regenerate_domain(domain)
            if regenerated is not None:
                domain = regenerated
                print(f'{GREEN}✓ Regenerated — reviewing new draft{RESET}')
                # Re-display and re-prompt with the fresh draft
                return review_domain_section(domain, section_num)
            else:
                print(f'{AMBER}⚠ Regeneration failed — keeping original draft{RESET}')
                return domain

        elif choice == 'S':
            print(f'{DIM}→ Skipped (using draft as-is){RESET}')
            return domain

        elif choice == 'Q':
            print(f'{RED}✗ Review aborted{RESET}')
            sys.exit(0)

        else:
            print('Invalid choice. Enter A, E, R, S, or Q.')


def review_executive(executive: dict) -> dict:
    """Review executive assessment."""
    print_header('EXECUTIVE ASSESSMENT — BLUF + KEY JUDGMENTS', colour=AMBER)

    print_section('BLUF', executive.get('bluf', '—'), colour=AMBER)

    for i, kj in enumerate(executive.get('keyJudgments', []), 1):
        if isinstance(kj, dict):
            print(f'{DIM}{i}. [{kj.get("confidence", "?").upper()}] {kj.get("text", "")[:200]}{RESET}')
        else:
            # Placeholder draft stores key judgments as plain strings
            print(f'{DIM}{i}. {str(kj)[:200]}{RESET}')
    print()

    while True:
        choice = input('[A]pprove  [E]dit BLUF  [S]kip › ').strip().upper()
        if choice == 'A':
            print(f'{GREEN}✓ Approved{RESET}')
            return executive
        elif choice == 'E':
            print('Enter new BLUF (press Enter twice to finish):')
            lines = []
            while True:
                line = input()
                if line == '' and lines:
                    break
                lines.append(line)
            new_bluf = ' '.join(lines).strip()
            if new_bluf:
                executive = dict(executive)
                executive['bluf'] = new_bluf
            print(f'{GREEN}✓ Edited and approved{RESET}')
            return executive
        elif choice == 'S':
            return executive
        else:
            print('Invalid choice.')


def review_indicators(indicators: list[dict]) -> list[dict]:
    """Quick review of warning indicators. Returns approved (potentially edited) list."""
    print_header('WARNING INDICATORS', colour=AMBER)
    for wi in indicators:
        status = wi.get('status', '?')
        status_colour = RED if status == 'triggered' else (AMBER if status == 'elevated' else DIM)
        change = wi.get('change', '')
        change_suffix = f'  [{change.upper()}]' if change else ''
        print(f'  {status_colour}[{status.upper()}]{RESET}{change_suffix} {wi.get("indicator", "?")}')
        print(f'    {DIM}{wi.get("detail", "")[:120]}{RESET}')
    print()

    while True:
        choice = input(f'{AMBER}[A]pprove  [Q]uit › {RESET}').strip().upper()
        if choice == 'A':
            print(f'{GREEN}✓ Warning indicators approved{RESET}')
            return indicators
        elif choice == 'Q':
            print(f'{RED}✗ Review aborted{RESET}')
            sys.exit(0)
        else:
            print('Invalid choice. Enter A or Q.')


def run_review(draft: dict) -> dict | None:
    """
    Run the full review workflow for a complete cycle draft.
    Returns the approved cycle dict, or None if aborted.
    """
    print(f'\n{BOLD}{CYAN}CSE INTEL BRIEF — HUMAN REVIEW{RESET}')
    print(f'{DIM}Review each section. Target: ~10 minutes total.{RESET}\n')

    approved = dict(draft)

    # Review strategic header
    print_header('STRATEGIC HEADER', colour=RED)
    sh = draft.get('strategicHeader', {})
    print(f'{BOLD}{sh.get("headlineJudgment", "—")}{RESET}\n')
    print(f'{DIM}Trajectory: {sh.get("trajectoryRationale", "")[:200]}{RESET}\n')
    input('Press Enter to continue... ')

    # Review domains
    approved_domains = []
    for i, section in enumerate(draft.get('domains', [])):
        result = review_domain_section(section, i)
        approved_domains.append(result if result is not None else section)

    approved['domains'] = approved_domains

    # Review executive
    executive = review_executive(draft.get('executive', {}))
    approved['executive'] = executive

    # Review warning indicators
    indicators = review_indicators(draft.get('warningIndicators', []))
    approved['warningIndicators'] = indicators

    # Final confirmation
    print_header('REVIEW COMPLETE', colour=GREEN)
    print(f'  Domains reviewed: {len(approved_domains)}')
    print(f'  Warning indicators: {len(indicators)}')
    print(f'  Collection gaps: {len(draft.get("collectionGaps", []))}')
    print()

    final = input('[C]onfirm and write output  [A]bort › ').strip().upper()
    if final == 'C':
        print(f'{GREEN}✓ Cycle approved for output{RESET}\n')
        return approved
    else:
        print(f'{RED}✗ Aborted — no output written{RESET}\n')
        return None
