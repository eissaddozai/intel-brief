"""
Human review CLI — mandatory step before cycle JSON is written.
Presents each domain section with source citations and allows approval, editing, or regeneration.
Target: ~10 minutes per cycle.
"""

import json
import logging
import sys
import textwrap

log = logging.getLogger(__name__)

# Terminal colour codes (ANSI) — disabled when not writing to a terminal
_USE_COLOUR = sys.stdout.isatty()
_DOMAIN_COLOURS = ['\033[91m', '\033[93m', '\033[92m', '\033[94m', '\033[96m', '\033[1m']

def _c(code: str, text: str) -> str:
    return f'\033[{code}m{text}\033[0m' if _USE_COLOUR else text

RED   = _c('91', '')[:6] if _USE_COLOUR else ''
AMBER = _c('93', '')[:6] if _USE_COLOUR else ''
GREEN = _c('92', '')[:6] if _USE_COLOUR else ''
BLUE  = _c('94', '')[:6] if _USE_COLOUR else ''
CYAN  = _c('96', '')[:6] if _USE_COLOUR else ''
DIM   = _c('2',  '')[:5] if _USE_COLOUR else ''
BOLD  = _c('1',  '')[:4] if _USE_COLOUR else ''
RESET = '\033[0m' if _USE_COLOUR else ''

# Convenience wrappers — these work correctly even with empty ANSI strings
def _red(t: str) -> str:   return f'\033[91m{t}\033[0m' if _USE_COLOUR else t
def _amber(t: str) -> str: return f'\033[93m{t}\033[0m' if _USE_COLOUR else t
def _green(t: str) -> str: return f'\033[92m{t}\033[0m' if _USE_COLOUR else t
def _dim(t: str) -> str:   return f'\033[2m{t}\033[0m'  if _USE_COLOUR else t
def _bold(t: str) -> str:  return f'\033[1m{t}\033[0m'  if _USE_COLOUR else t
def _cyan(t: str) -> str:  return f'\033[96m{t}\033[0m' if _USE_COLOUR else t


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


def review_domain_section(domain: dict, section_num: int) -> dict | None:
    """
    Display a domain section and prompt for review action.
    Returns approved section dict, or None if regeneration requested.
    """
    colour = _DOMAIN_COLOURS[section_num % 6] if _USE_COLOUR else ''

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
            print(f'{AMBER}↻ Marked for regeneration{RESET}')
            return None  # Caller handles regeneration

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
        # keyJudgments may be strings or dicts depending on drafter output
        if isinstance(kj, str):
            kj_text = kj[:200]
            kj_conf = '?'
        else:
            kj_text = kj.get('text', str(kj))[:200]
            kj_conf = kj.get('confidence', '?')
        print(f'{DIM}{i}. [{kj_conf.upper()}] {kj_text}{RESET}')
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
    """Quick review of warning indicators."""
    print_header('WARNING INDICATORS', colour=AMBER)
    for wi in indicators:
        level = wi.get('level', wi.get('status', '?'))
        level_upper = (level or '?').upper()
        level_colour = '\033[91m' if _USE_COLOUR and level_upper in ('RED', 'TRIGGERED') else (
                       '\033[93m' if _USE_COLOUR and level_upper == 'AMBER' else '')
        reset = '\033[0m' if _USE_COLOUR else ''
        print(f'  {level_colour}[{level_upper}]{reset} {wi.get("indicator", "?")}')
        assessment = wi.get('assessment', wi.get('detail', ''))
        print(f'    {DIM}{assessment[:120]}{RESET}')
    print()

    while True:
        choice = input('[A]pprove  [E]dit  [S]kip › ').strip().upper()
        if choice in ('A', 'S'):
            return indicators
        elif choice == 'E':
            print('Enter index of indicator to edit (1-based) or 0 to cancel:')
            try:
                idx = int(input('Index: ').strip())
                if 1 <= idx <= len(indicators):
                    ind = dict(indicators[idx - 1])
                    new_assessment = input('New assessment (blank to keep): ').strip()
                    if new_assessment:
                        ind['assessment'] = new_assessment
                        indicators = list(indicators)
                        indicators[idx - 1] = ind
                        print(f'{GREEN}✓ Indicator {idx} updated{RESET}')
            except (ValueError, IndexError):
                print('Invalid selection.')
        else:
            print('Invalid choice.')


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
    print(f'  Caveats:         {len(draft.get("caveats", {}).get("items", []))}')
    print()

    final = input('[C]onfirm and write output  [A]bort › ').strip().upper()
    if final == 'C':
        print(f'{GREEN}✓ Cycle approved for output{RESET}\n')
        return approved
    else:
        print(f'{RED}✗ Aborted — no output written{RESET}\n')
        return None
