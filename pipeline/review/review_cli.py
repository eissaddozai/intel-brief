"""
Human review CLI — mandatory step before cycle JSON is written.
Presents each domain section with source citations, quality warnings,
and word counts, then allows approval, editing, or regeneration.
Target: ~10 minutes per cycle.
"""

import logging
import sys
import textwrap
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Terminal colour codes (ANSI)
RED     = '\033[91m'
AMBER   = '\033[93m'
GREEN   = '\033[92m'
BLUE    = '\033[94m'
CYAN    = '\033[96m'
DIM     = '\033[2m'
BOLD    = '\033[1m'
RESET   = '\033[0m'

# Word limits per domain for display
DOMAIN_WORD_LIMITS = {
    'd1': 200, 'd2': 200, 'd3': 180, 'd4': 180, 'd5': 120, 'd6': 220,
}
KJ_WORD_LIMITS = {
    'd1': 30, 'd2': 35, 'd3': 30, 'd4': 35, 'd5': 25, 'd6': 35,
}

# Hard-fail quality rules (shown in red)
HARD_FAIL_RULES = {
    'FORBIDDEN_JARGON', 'INVALID_CONFIDENCE_LANGUAGE',
    'INVALID_CONFIDENCE_TIER', 'INVALID_VERIFICATION_STATUS',
    'INVALID_SOURCE_TIER', 'TIER_STATUS_MISMATCH', 'IRANIAN_STATE_MEDIA',
}


def _word_count(text: str) -> int:
    return len(text.split())


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


def _get_domain_warnings(all_warnings: list[dict], domain_id: str) -> list[dict]:
    """Filter quality warnings for a specific domain."""
    return [w for w in all_warnings if w.get('domain') == domain_id]


def _display_section_warnings(warnings: list[dict]) -> None:
    """Display quality warnings for a specific section during review."""
    if not warnings:
        print(f'  {GREEN}✓ Quality: clean{RESET}')
        return

    hard = [w for w in warnings if w.get('rule') in HARD_FAIL_RULES]
    soft = [w for w in warnings if w.get('rule') not in HARD_FAIL_RULES]

    if hard:
        print(f'  {RED}{BOLD}⚠ {len(hard)} HARD FAIL(S):{RESET}')
        for w in hard:
            print(f'    {RED}[{w["rule"]}]{RESET} {w.get("field", "?")}: {w.get("message", "")}')

    if soft:
        print(f'  {AMBER}△ {len(soft)} advisory issue(s):{RESET}')
        for w in soft:
            print(f'    {AMBER}[{w["rule"]}]{RESET} {w.get("field", "?")}: {w.get("message", "")}')

    print()


def _display_word_counts(domain: dict) -> None:
    """Display word counts vs limits for a domain section."""
    domain_id = domain.get('id', '?')
    body_limit = DOMAIN_WORD_LIMITS.get(domain_id)
    kj_limit = KJ_WORD_LIMITS.get(domain_id)

    # Body word count
    body_words = sum(
        _word_count(p.get('text', ''))
        for p in domain.get('bodyParagraphs', [])
    )

    # KJ word count
    kj_words = _word_count(domain.get('keyJudgment', {}).get('text', ''))

    # Colourize based on limit
    if body_limit:
        body_colour = RED if body_words > body_limit else (AMBER if body_words > body_limit * 0.9 else GREEN)
        print(f'  {DIM}Body words:{RESET} {body_colour}{body_words}/{body_limit}{RESET}', end='')
    else:
        print(f'  {DIM}Body words:{RESET} {body_words}', end='')

    if kj_limit:
        kj_colour = RED if kj_words > kj_limit else (AMBER if kj_words > kj_limit * 0.9 else GREEN)
        print(f'  {DIM}KJ words:{RESET} {kj_colour}{kj_words}/{kj_limit}{RESET}')
    else:
        print(f'  {DIM}KJ words:{RESET} {kj_words}')

    # Citation count
    total_citations = len(domain.get('keyJudgment', {}).get('citations', []))
    for para in domain.get('bodyParagraphs', []):
        total_citations += len(para.get('citations', []))
    print(f'  {DIM}Citations:{RESET} {total_citations}')

    # Paragraph count with sentence counts
    para_count = len(domain.get('bodyParagraphs', []))
    print(f'  {DIM}Paragraphs:{RESET} {para_count}')
    print()


def review_domain_section(domain: dict, section_num: int,
                           quality_warnings: list[dict] | None = None) -> dict | None:
    """
    Display a domain section and prompt for review action.
    Returns approved section dict, or None if regeneration requested.
    """
    # 6 domain colours: d1=red, d2=amber, d3=green, d4=blue, d5=cyan, d6=cyan
    DOMAIN_COLOURS = [RED, AMBER, GREEN, BLUE, CYAN, CYAN]
    colour = DOMAIN_COLOURS[section_num % len(DOMAIN_COLOURS)]

    print_header(
        f"DOMAIN {domain.get('num', '?')} — {domain.get('title', '?')}",
        colour=colour
    )

    # Word counts and metrics
    _display_word_counts(domain)

    # Per-domain quality warnings
    domain_id = domain.get('id', '?')
    if quality_warnings is not None:
        dw = _get_domain_warnings(quality_warnings, domain_id)
        _display_section_warnings(dw)

    # Key Judgment
    kj = domain.get('keyJudgment', {})
    print_section('KEY JUDGMENT', kj.get('text', '—'), colour=AMBER)
    print(f'{DIM}  Confidence: {kj.get("confidence", "?")} · {kj.get("probabilityRange", "")}{RESET}')
    print(f'{DIM}  Basis:      {kj.get("basis", "(no basis)")[:200]}{RESET}')
    print(f'{DIM}  Citations:  {format_citations(kj.get("citations", []))}{RESET}')
    print()

    # Body paragraphs
    for i, para in enumerate(domain.get('bodyParagraphs', []), 1):
        label = para.get('subLabel') or f'PARAGRAPH {i}'
        variant = para.get('subLabelVariant', '')
        variant_tag = f' [{variant.upper()}]' if variant else ''
        text = para.get('text', '')
        wc = _word_count(text)
        if len(text) > 500:
            text = text[:500] + '…'
        print(f'{colour}{BOLD}{label}{variant_tag}{RESET} {DIM}({wc} words){RESET}')
        for line in textwrap.wrap(text, width=76):
            print(f'  {line}')
        print(f'{DIM}  Citations: {format_citations(para.get("citations", []))}{RESET}')
        print()

    # Dissenter note
    dissenter = domain.get('dissenterNote')
    if dissenter:
        print(f'{AMBER}{BOLD}DISSENTER NOTE ({dissenter.get("analystId", "?")}):{RESET}')
        for line in textwrap.wrap(dissenter.get('text', ''), width=76):
            print(f'  {line}')
        print()

    # Analyst note
    analyst = domain.get('analystNote')
    if analyst:
        print(f'{CYAN}{BOLD}ANALYST NOTE — {analyst.get("title", "")}:{RESET}')
        for line in textwrap.wrap(analyst.get('text', ''), width=76):
            print(f'  {line}')
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


def review_executive(executive: dict, quality_warnings: list[dict] | None = None) -> dict:
    """Review executive assessment."""
    print_header('EXECUTIVE ASSESSMENT — BLUF + KEY JUDGMENTS', colour=AMBER)

    # Quality warnings for executive
    if quality_warnings is not None:
        ew = _get_domain_warnings(quality_warnings, 'executive')
        _display_section_warnings(ew)

    # BLUF with word count
    bluf = executive.get('bluf', '—')
    bluf_wc = _word_count(bluf)
    print(f'{AMBER}{BOLD}BLUF{RESET} {DIM}({bluf_wc} words){RESET}')
    for line in textwrap.wrap(bluf, width=76):
        print(f'  {line}')
    print()

    # Key judgments
    kjs = executive.get('keyJudgments', [])
    print(f'{DIM}Key Judgments: {len(kjs)} (target: 4–6){RESET}')
    for i, kj in enumerate(kjs, 1):
        conf = kj.get('confidence', '?').upper()
        lang = kj.get('language', '?')
        domain = kj.get('domain', '?')
        text = kj.get('text', '')[:250]
        print(f'  {i}. {DIM}[{conf} · {lang} · {domain}]{RESET} {text}')
    print()

    # KPIs
    kpis = executive.get('kpis', [])
    print(f'{DIM}KPIs: {len(kpis)} (target: 5){RESET}')
    for kpi in kpis:
        direction = {'up': '↑', 'down': '↓', 'neutral': '→'}.get(kpi.get('changeDirection', ''), '?')
        print(f'  {direction} {kpi.get("domain", "?")} — {kpi.get("number", "?")} ({kpi.get("label", "")})')
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

    triggered = [wi for wi in indicators if wi.get('status') == 'triggered']
    elevated = [wi for wi in indicators if wi.get('status') == 'elevated']
    watching = [wi for wi in indicators if wi.get('status') == 'watching']
    cleared = [wi for wi in indicators if wi.get('status') == 'cleared']

    print(f'  {DIM}Summary: {RED}{len(triggered)} triggered{RESET} · '
          f'{AMBER}{len(elevated)} elevated{RESET} · '
          f'{DIM}{len(watching)} watching · {GREEN}{len(cleared)} cleared{RESET}')
    print()

    for wi in indicators:
        status = wi.get('status', '?')
        if status == 'triggered':
            status_colour = RED
        elif status == 'elevated':
            status_colour = AMBER
        elif status == 'cleared':
            status_colour = GREEN
        else:
            status_colour = DIM

        change = wi.get('change', 'unchanged')
        change_marker = ''
        if change == 'new':
            change_marker = f' {RED}★ NEW{RESET}'
        elif change == 'elevated':
            change_marker = f' {AMBER}↑ ELEVATED{RESET}'
        elif change == 'cleared':
            change_marker = f' {GREEN}↓ CLEARED{RESET}'

        print(f'  {status_colour}[{status.upper():>9}]{RESET} {wi.get("indicator", "?")}{change_marker}')
        detail = wi.get('detail', '')
        if detail:
            for line in textwrap.wrap(detail, width=70):
                print(f'    {DIM}{line}{RESET}')
    print()

    choice = input('[A]pprove  [S]kip › ').strip().upper()
    return indicators


def display_quality_warnings(draft: dict) -> None:
    """Surface quality warning summary from the draft pipeline to the reviewer."""
    warnings = draft.get('_qualityWarnings', [])
    if not warnings:
        print(f'{GREEN}✓ Quality gate: all checks passed — no issues found{RESET}\n')
        return

    hard = [w for w in warnings if w.get('rule') in HARD_FAIL_RULES]
    soft = [w for w in warnings if w.get('rule') not in HARD_FAIL_RULES]

    print(f'{RED}{"─" * 80}{RESET}')
    print(f'{RED}{BOLD} QUALITY GATE: {len(warnings)} ISSUE(S) DETECTED{RESET}')
    if hard:
        print(f'{RED}{BOLD} ⚠ {len(hard)} HARD FAIL(S) — will block output if not resolved{RESET}')
    print(f'{RED}{"─" * 80}{RESET}')

    # Group by domain
    domains_seen: dict[str, list[dict]] = {}
    for w in warnings:
        d = w.get('domain', '?')
        domains_seen.setdefault(d, []).append(w)

    for domain, dw in sorted(domains_seen.items()):
        d_hard = [w for w in dw if w.get('rule') in HARD_FAIL_RULES]
        d_soft = [w for w in dw if w.get('rule') not in HARD_FAIL_RULES]
        marker = f'{RED}✗{RESET}' if d_hard else f'{AMBER}△{RESET}'
        print(f'  {marker} {BOLD}{domain}{RESET}: {len(d_hard)} hard, {len(d_soft)} advisory')
        for w in d_hard[:3]:
            print(f'      {RED}[{w["rule"]}]{RESET} {w.get("field", "?")}: {w.get("message", "")[:100]}')
        for w in d_soft[:2]:
            print(f'      {AMBER}[{w["rule"]}]{RESET} {w.get("field", "?")}: {w.get("message", "")[:100]}')
        remaining = len(dw) - min(len(d_hard), 3) - min(len(d_soft), 2)
        if remaining > 0:
            print(f'      {DIM}... and {remaining} more{RESET}')

    print(f'{RED}{"─" * 80}{RESET}')
    print(f'{AMBER}Review flagged sections carefully before approving.{RESET}\n')


def run_review(draft: dict, prev_cycle: dict | None = None, session_file: Path | None = None) -> dict | None:
    """
    Run the full review workflow for a complete cycle draft.
    Returns the approved cycle dict, or None if aborted.

    Args:
        draft: The cycle draft dict to review.
        prev_cycle: Previous cycle dict for delta context (optional).
        session_file: Path to save/resume review session (optional).
    """
    print(f'\n{BOLD}{CYAN}CSE INTEL BRIEF — HUMAN REVIEW{RESET}')
    print(f'{DIM}Review each section. Target: ~10 minutes total.{RESET}\n')

    # Surface quality warnings before review begins
    display_quality_warnings(draft)
    quality_warnings = draft.get('_qualityWarnings', [])

    approved = dict(draft)

    # Review strategic header
    print_header('STRATEGIC HEADER', colour=RED)

    # Strategic header quality warnings
    sh_warnings = _get_domain_warnings(quality_warnings, 'strategicHeader')
    _display_section_warnings(sh_warnings)

    sh = draft.get('strategicHeader', {})
    threat = sh.get('threatLevel', '?')
    trajectory = sh.get('threatTrajectory', '?')
    print(f'{BOLD}[{threat} · {trajectory.upper()}]{RESET}')
    print(f'{BOLD}{sh.get("headlineJudgment", "—")}{RESET}\n')
    rationale = sh.get('trajectoryRationale', '')
    for line in textwrap.wrap(rationale, width=76):
        print(f'{DIM}{line}{RESET}')
    print()
    input('Press Enter to continue... ')

    # Review domains
    approved_domains = []
    for i, section in enumerate(draft.get('domains', [])):
        result = review_domain_section(section, i, quality_warnings=quality_warnings)
        approved_domains.append(result if result is not None else section)

    approved['domains'] = approved_domains

    # Review executive
    executive = review_executive(draft.get('executive', {}), quality_warnings=quality_warnings)
    approved['executive'] = executive

    # Review warning indicators
    indicators = review_indicators(draft.get('warningIndicators', []))
    approved['warningIndicators'] = indicators

    # Collection gaps quick view
    gaps = draft.get('collectionGaps', [])
    if gaps:
        print_header('COLLECTION GAPS', colour=DIM)
        for gap in gaps:
            severity = gap.get('severity', '?')
            sev_colour = RED if severity == 'critical' else (AMBER if severity == 'significant' else DIM)
            print(f'  {sev_colour}[{severity.upper():>11}]{RESET} {gap.get("domain", "?")} — {gap.get("gap", "")[:120]}')
        print()

    # Final confirmation with summary
    print_header('REVIEW COMPLETE', colour=GREEN)

    hard_fails = [w for w in quality_warnings if w.get('rule') in HARD_FAIL_RULES]
    advisories = [w for w in quality_warnings if w.get('rule') not in HARD_FAIL_RULES]

    print(f'  Domains reviewed:      {len(approved_domains)}')
    print(f'  Warning indicators:    {len(indicators)}')
    print(f'  Collection gaps:       {len(gaps)}')
    print(f'  Quality hard fails:    {RED if hard_fails else GREEN}{len(hard_fails)}{RESET}')
    print(f'  Quality advisories:    {AMBER if advisories else GREEN}{len(advisories)}{RESET}')

    if hard_fails:
        print(f'\n  {RED}{BOLD}⚠ WARNING: {len(hard_fails)} hard fail(s) will block serializer output.{RESET}')
        print(f'  {RED}Resolve forbidden jargon and invalid enum values before confirming.{RESET}')

    print()

    final = input('[C]onfirm and write output  [A]bort › ').strip().upper()
    if final == 'C':
        print(f'{GREEN}✓ Cycle approved for output{RESET}\n')
        return approved
    else:
        print(f'{RED}✗ Aborted — no output written{RESET}\n')
        return None
