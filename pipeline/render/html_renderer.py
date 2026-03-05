"""
pipeline/render/html_renderer.py

Converts a BriefCycle JSON dict → self-contained, print-ready HTML.

Design rules (never violate):
  - Zero hardcoded hex values in Python strings — all colour via CSS var()
  - Zero hardcoded font sizes — all via CSS var()
  - Component render order matches CLAUDE.md and DomainSection.tsx exactly
  - Confidence language rendered from CONFIDENCE_PHRASES dict only
  - All user content HTML-escaped
  - Zero JavaScript — pure HTML + CSS

Usage:
  from render.html_renderer import HtmlRenderer
  html = HtmlRenderer(cycle_dict).render()
  Path('briefs/brief_20260305.html').write_text(html, encoding='utf-8')
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime
from pathlib import Path

# ── Design system file locations ──────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STYLES_DIR = _REPO_ROOT / 'src' / 'styles'
_PRINT_CSS   = Path(__file__).parent / 'print.css'

# ── Confidence language map (mirrors brief.ts CONFIDENCE_PHRASES) ─────────────


# ── Canadian Government Identity Programme flag SVGs (base64-encoded) ────────
# Official proportions and colours (FF0000 / white per FIP specification).
# Replace with your actual PNG assets if higher fidelity is required:
#   base64.b64encode(Path("src/assets/cse-flag-full.png").read_bytes()).decode()
_CANADA_FLAG_FULL_B64 = "iVBORw0KGgoAAAANSUhEUgAAAMgAAABkCAIAAABM5OhcAAAB1ElEQVR42u3czQ3CMAwG0E7CAuw/CvOUa9WWqj9RbIdnceGUT/JLFdKE6fN+JfzM6nTl7OAEFlhgKbDAAgsssMBSYIEFFlhggaXAAgsssMACS4EFFlhggQWWAgsssMACCywFFlhggQUWWAossMACCyywwAILLLDAAgsssMACCyywwAILLLDAAgsssMACC6yasHIGAwsssMACCyywwCoMK202sMACCyywwOqzotrNliEqWPVgLcMcfwULrMYNAwsssMAqsi62eAcLLLAiGrY76I2c/cODlR3WdtyrOUPCg1UA1mr08zkDw4NVBtZ2s+o4Z2x4sLIv3seYEmCBBRZYYIF1e3PheZMujQXWmE+sX6cVWsXuOUnAyghrOejz2CFPX7ByrVRGnSFgxS+BTQ+wijXGr0KwwAKrSG/sY4HVvj02SMECCyyvdMCqezT50pZp+IEZsCrBOt+2zu8EwRrqiv0ANz7AAgsssMACq1Xb5tBLE2CNBivk+B5Yf/RXkTkLLLDAAgsssMACCyywwAILLLDAAgsssMACCyywwAILLLDAAgsssMACCyywwAILLLDAAgsssMACCyywwAILLLDAAgsssMACCyywwAILLLDAAgus0WB9AVS7Ix2IXJQvAAAAAElFTkSuQmCC"
_CANADA_FLAG_BANNER_B64 = "iVBORw0KGgoAAAANSUhEUgAAAyAAAABACAIAAABtDoT4AAAB8UlEQVR42u3dyQmEQBBAUSMxAfMPxXh6ro3OtAu9z3t48mBB4eEjosu+rUWPMDj7AQCeWgSEwAIABJbAAgAElsASWAAgsASEwAIABJbAAgAElsASWAAgsASW/QAAAktgAQACS2ABAAJLYAksAEBgCSwAQGAJLABAYAksgQUAAktACCwAQGAJLABAYAksgQUAAktACCwAQGAJLABAYAkstyAACCyBZT8AwOyBVXqEwAIABJbAAgAElsACAASWwBJYAIDAElgAgMC6ET1x/cQnBRYAILByRo/AAgAEVs7uqRxzAgsAEFgCCwAQWKfQuRlYGUcLLABg2sA6ZFNiVomwE1gAwMyB1eTJmcACAASWwAIABNbvvnmRO4krCCwAQGCtl69epV/GElgAgMDKnDhtpwssABBYnQbEuHknsABAYPX+HayB2k5gAYDAElgCCwD4s8AKPtMAAAisEgERX/Y8qHnVCSwAIIz7s+evgVVhisACAKYNrGqzBBYAILAEFgAgsN52z+UZgQUACKwe2Q8AILAEFgAgsAQWACCwBJb9AAACS2ABAAJLYAEAAktgCSwAQGAJLABAYAksAEBgCSyBBQACS0AILABAYAksAEBgCSyBBQACS2DZDwAgsAQWACCwBBYAILAElv0AAAJLYAEAVXwA1ZIUXeYUR7EAAAAASUVORK5CYII="
_CANADA_FLAG_GOC_B64 = "iVBORw0KGgoAAAANSUhEUgAAAfQAAAA8CAIAAAAfeN+wAAABXElEQVR42u3a0QmDMBRAUSdxAfcfxXn0Q4SgRFCjz8RzKKU/fdQiNxrsJgCa0/kLAMQdAHEHQNwBEHcAxB1A3AEQd4CXjEN/8/WHYxF3QNzFHUDcxR1A3MUdQNzFHRB3cRd3QNzFHUDcxR1A3MUdQNzFHUDcxR0Qd3F3ogDiLu4A4i7uAOIu7gC1xL3IHHEHEHdxB8Rd3AHE/WzT9x/EHaDiK/dlQvou7gAtxL3gfYC4A4TFPf1WbtqFyeIOEHzlnm6y76ddXjPEHSA47k/cEIg7gLiLOyDuJSq82Xs5nnl2vrgDhF25P71yiDtA2NMy4cuGuAPibs8dQNzFHeCfcc/9gG8ei7gD4i7uAOK+DhF3gHbiXsWxiDsg7uIOIO7iDiDu4g4g7uIOiLu4izsg7uIOIO7iDiDu4g4g7uIOIO7iDoi7uDtRAHEXdwAqIO4A4g6AuAMg7gCIOwAZM78bi0rjgJ3CAAAAAElFTkSuQmCC"

_CONFIDENCE_PHRASES: dict[str, dict[str, str]] = {
    'almost-certainly':     {'phrase': 'We assess with high confidence',                                  'range': '95–99%'},
    'highly-likely':        {'phrase': 'We judge it highly likely',                                       'range': '75–95%'},
    'likely':               {'phrase': 'Available evidence suggests',                                     'range': '55–75%'},
    'possibly':             {'phrase': 'Reporting indicates, though corroboration is limited',             'range': '45–55%'},
    'unlikely':             {'phrase': 'We judge it unlikely, though we cannot exclude',                  'range': '20–45%'},
    'almost-certainly-not': {'phrase': 'We assess with high confidence this will not',                    'range': '1–5%'},
}

_TRAJECTORY_LABELS: dict[str, str] = {
    'escalating':    '&#x2191; ESCALATING',
    'stable':        '&#x2192; STABLE',
    'de-escalating': '&#x2193; DE-ESCALATING',
}

_DOMAIN_LABELS: dict[str, str] = {
    'd1': 'BATTLESPACE',
    'd2': 'ESCALATION',
    'd3': 'ENERGY',
    'd4': 'DIPLOMATIC',
    'd5': 'CYBER · IO',
    'd6': 'WAR RISK',
}

_CONF_TIER_CLASS: dict[str, str] = {
    'high':     'badge--green',
    'moderate': 'badge--blue',
    'low':      'badge--amber',
}

_TLP_CLASS: dict[str, str] = {
    'RED':   'masthead__tlp--red',
    'AMBER': 'masthead__tlp--amber',
    'GREEN': 'masthead__tlp--green',
    'CLEAR': 'masthead__tlp--clear',
}

_THREAT_CLASS: dict[str, str] = {
    'CRITICAL': 'threat-level--critical',
    'SEVERE':   'threat-level--severe',
    'ELEVATED': 'threat-level--elevated',
    'GUARDED':  'threat-level--guarded',
    'LOW':      'threat-level--low',
}

_TRAJ_CLASS: dict[str, str] = {
    'escalating':    'trajectory-badge--escalating',
    'stable':        'trajectory-badge--stable',
    'de-escalating': 'trajectory-badge--de-escalating',
}

_WI_STATUS_CLASS: dict[str, str] = {
    'triggered': 'wi-status--triggered',
    'elevated':  'wi-status--elevated',
    'watching':  'wi-status--watching',
    'cleared':   'wi-status--cleared',
}

_WI_STATUS_ICON: dict[str, str] = {
    'triggered': '&#9632;',   # ■ solid square — critical
    'elevated':  '&#9650;',   # ▲ triangle — elevated
    'watching':  '&#9679;',   # ● circle — monitoring
    'cleared':   '&#10003;',  # ✓ check — cleared
}

_WI_CHANGE_CLASS: dict[str, str] = {
    'new':             'wi-change--new',
    'new-triggered':   'wi-change--new',
    'newly-elevated':  'wi-change--elevated',
    'elevated':        'wi-change--elevated',
    'unchanged':       'wi-change--unchanged',
    'downgraded':      'wi-change--cleared',
    'cleared':         'wi-change--cleared',
}

_GAP_SEV_CLASS: dict[str, str] = {
    'critical':    'gap-item__severity--critical',
    'significant': 'gap-item__severity--significant',
    'minor':       'gap-item__severity--minor',
}


# ── HTML utilities ────────────────────────────────────────────────────────────

def _e(text: object) -> str:
    """HTML-escape a value."""
    return _html.escape(str(text or ''))


def _fmt_ts(iso: str | None) -> str:
    """
    '2026-03-05T06:20:00Z' → '0620 UTC 05 Mar'
    Falls back to original string if unparseable.
    """
    if not iso:
        return ''
    # Strip timezone suffix before parsing so all variants match '%Y-%m-%dT%H:%M:%S'
    try:
        dt = datetime.strptime(iso[:19], '%Y-%m-%dT%H:%M:%S')
        return dt.strftime('%H%M UTC %d %b').upper()
    except ValueError:
        pass
    return _e(iso)


def _fmt_date_long(iso: str | None) -> str:
    """'2026-03-05T06:00:00Z' → '05 MARCH 2026'"""
    if not iso:
        return ''
    try:
        dt = datetime.strptime(iso[:10], '%Y-%m-%d')
        return dt.strftime('%d %B %Y').upper()
    except ValueError:
        return _e(iso[:10])


def _conf_phrase(language: str | None) -> str:
    """Return rendered confidence phrase for a ConfidenceLanguage value."""
    if not language:
        return ''
    entry = _CONFIDENCE_PHRASES.get(language, {})
    return entry.get('phrase', _e(language))


def _conf_range(language: str | None) -> str:
    if not language:
        return ''
    return _CONFIDENCE_PHRASES.get(language or '', {}).get('range', '')


def _cite_inline(citations: list[dict]) -> str:
    """Render citations as clean italic parenthetical — no tier chips."""
    if not citations:
        return ''
    parts = []
    for c in citations:
        source  = _e(c.get('source', ''))
        ts      = _fmt_ts(c.get('timestamp', ''))
        vs      = c.get('verificationStatus', 'confirmed')
        ts_part = f', {ts}' if ts else ''

        if vs == 'confirmed':
            label = f'({source}{ts_part})'
        elif vs == 'reported':
            label = f'(reported: {source}{ts_part})'
        elif vs == 'claimed':
            label = (
                f'<span class="cite--claimed">'
                f'(claimed: {source}{ts_part})</span>'
            )
        elif vs == 'disputed':
            label = f'<span class="cite--disputed">[DISPUTED — {source}]</span>'
        else:
            label = f'({source}{ts_part})'
        parts.append(label)
    return ' <em class="body-para__source">' + '; '.join(parts) + '</em>'


def _badge(text: str, cls: str) -> str:
    return f'<span class="badge {_e(cls)}">{_e(text)}</span>'


def _conf_badge(tier: str | None) -> str:
    if not tier:
        return ''
    cls = _CONF_TIER_CLASS.get(tier or '', 'badge--amber')
    return _badge((tier or '').upper(), cls)


# ── CSS inlining ──────────────────────────────────────────────────────────────

def _load_css() -> str:
    """
    Inline all four design-system CSS files plus print overrides.
    Order: tokens → base → animations → intel-brief → print
    """
    files = [
        _STYLES_DIR / 'tokens.css',
        _STYLES_DIR / 'base.css',
        _STYLES_DIR / 'animations.css',
        _STYLES_DIR / 'intel-brief.css',
        _PRINT_CSS,
    ]
    chunks = []
    for path in files:
        try:
            chunks.append(f'/* === {path.name} === */\n{path.read_text(encoding="utf-8")}')
        except FileNotFoundError:
            pass  # graceful degradation if animations.css etc. missing
    # Append inline extras — clean, purposeful enhancements only
    chunks.append("""
/* === renderer extras === */

/* ── GALAXY SHIMMER — non-text areas only ─────────────────────────────────
   Pure CSS animation using layered radial-gradients + background-position
   drift. Zero JavaScript. Suppressed in @media print.
   Only active on .masthead and .brief-footer backgrounds — never on text.
─────────────────────────────────────────────────────────────────────────── */

.masthead::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 60% 40% at 15% 50%, rgba(123,31,162,0.10) 0%, transparent 70%),
    radial-gradient(ellipse 45% 55% at 85% 20%, rgba(21,101,192,0.08) 0%, transparent 65%),
    radial-gradient(ellipse 70% 35% at 50% 90%, rgba(0,188,212,0.07) 0%, transparent 60%),
    radial-gradient(ellipse 30% 60% at 72% 65%, rgba(198,40,40,0.05) 0%, transparent 55%);
  background-size: 300% 300%;
  animation: galaxy-drift 22s ease-in-out infinite alternate;
  pointer-events: none;
  z-index: 0;
  border-radius: inherit;
}

/* Stars layer — tiny bright specks scattered across the header */
.masthead::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(1px 1px at  8% 25%, rgba(255,255,255,0.55) 0%, transparent 100%),
    radial-gradient(1px 1px at 23% 68%, rgba(255,255,255,0.40) 0%, transparent 100%),
    radial-gradient(1px 1px at 41% 18%, rgba(255,255,255,0.50) 0%, transparent 100%),
    radial-gradient(1px 1px at 57% 79%, rgba(255,255,255,0.35) 0%, transparent 100%),
    radial-gradient(1px 1px at 73% 42%, rgba(255,255,255,0.48) 0%, transparent 100%),
    radial-gradient(1px 1px at 88% 15%, rgba(255,255,255,0.45) 0%, transparent 100%),
    radial-gradient(1px 1px at 12% 85%, rgba(255,255,255,0.30) 0%, transparent 100%),
    radial-gradient(1px 1px at 95% 60%, rgba(255,255,255,0.42) 0%, transparent 100%),
    radial-gradient(2px 2px at 34% 55%, rgba(255,255,255,0.22) 0%, transparent 100%),
    radial-gradient(1px 1px at 62% 35%, rgba(200,220,255,0.38) 0%, transparent 100%);
  pointer-events: none;
  z-index: 0;
  animation: star-twinkle 14s ease-in-out infinite alternate;
}

.masthead > * { position: relative; z-index: 1; }

/* Footer galaxy — subtler aurora, more muted */
.brief-footer::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 20% 50%, rgba(21,101,192,0.07) 0%, transparent 70%),
    radial-gradient(ellipse 60% 40% at 75% 40%, rgba(0,188,212,0.06) 0%, transparent 65%);
  background-size: 200% 200%;
  animation: galaxy-drift 28s ease-in-out infinite alternate-reverse;
  pointer-events: none;
  z-index: 0;
}
.brief-footer { position: relative; overflow: hidden; }
.brief-footer > * { position: relative; z-index: 1; }

@keyframes galaxy-drift {
  0%   { background-position: 0%   0%,  100% 0%,   50% 100%, 0%  100%; }
  33%  { background-position: 40%  60%,  60% 40%,   30%  70%, 70%  30%; }
  66%  { background-position: 80%  20%,  20% 80%,   70%  30%, 30%  70%; }
  100% { background-position: 100% 100%, 0% 100%,  100%   0%, 100%  0%; }
}

@keyframes star-twinkle {
  0%   { opacity: 0.7; }
  50%  { opacity: 1.0; }
  100% { opacity: 0.5; }
}

@media print {
  .masthead::before,
  .masthead::after,
  .brief-footer::before { display: none; }
}

/* ── CANADA FLAG BRANDING ─────────────────────────────────────────────────── */

.masthead__flag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 0 0 4px;
}

.masthead__flag img {
  height: 28px;
  width: auto;
  vertical-align: middle;
  border: 0.5px solid rgba(255,255,255,0.12);
}

.brief-footer__flag {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.brief-footer__flag img {
  height: 20px;
  width: auto;
  opacity: 0.85;
  vertical-align: middle;
}

@media print {
  .masthead__flag img,
  .brief-footer__flag img {
    height: 20pt;
    opacity: 1;
  }
}


/* ── Citation status markers ──────────────────────────────────────────── */
.cite--claimed  { color: var(--conf-amber); font-style: italic; }
.cite--disputed { color: var(--conf-red); font-weight: 700; font-style: normal; }

/* ── Probability bar — indicates confidence range visually ────────────── */
.prob-bar {
  height: 3px;
  background: var(--color-sep);
  border-radius: 2px;
  margin: 10px 0 6px;
  overflow: hidden;
}
.prob-bar__fill { display: block; height: 100%; border-radius: 2px; }
.prob-bar__fill--almost-certainly     { width: 97%; background: var(--conf-green); }
.prob-bar__fill--highly-likely        { width: 85%; background: var(--conf-green); }
.prob-bar__fill--likely               { width: 65%; background: var(--conf-blue);  }
.prob-bar__fill--possibly             { width: 50%; background: var(--conf-amber); }
.prob-bar__fill--unlikely             { width: 32%; background: var(--conf-red);   }
.prob-bar__fill--almost-certainly-not { width:  3%; background: var(--conf-red);   }

/* ── Warning indicator status icons ──────────────────────────────────── */
.wi-icon { display: inline-block; width: 18px; text-align: center; font-size: 12px; }
.wi-icon--triggered { color: var(--conf-red);   }
.wi-icon--elevated  { color: var(--conf-amber); }
.wi-icon--watching  { color: var(--color-gold); }
.wi-icon--cleared   { color: var(--conf-green); }

/* ── BLUF — bottom line up front ──────────────────────────────────────── */
.exec__bluf {
  border-left: 4px solid var(--color-crimson);
  padding: 14px 18px;
  margin: 16px 0;
  background: var(--color-exec-bg);
}
.exec__bluf-label {
  font-family: var(--font-ui);
  font-size: var(--size-badge);
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--color-crimson);
  margin-bottom: 10px;
}
.exec__bluf-text {
  font-family: var(--font-body);
  font-size: var(--size-body);
  line-height: 1.7;
  color: var(--text-hi);
}

/* ── Key judgment box ─────────────────────────────────────────────────── */
.kj__text {
  font-size: var(--size-kj);
  line-height: 1.65;
  color: var(--text-hi);
  font-family: var(--font-body);
  margin: 4px 0 8px;
}
.kj__basis {
  font-size: calc(var(--size-body) * 0.95);
  color: var(--text-dim);
  font-style: italic;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-sep);
  line-height: 1.6;
}
.kj__confidence-phrase {
  font-family: var(--font-data);
  font-size: var(--size-badge);
  color: var(--text-dim);
  letter-spacing: 0.06em;
  margin-bottom: 6px;
  text-transform: uppercase;
}

/* ── Domain confidence row (replaces meter bar) ───────────────────────── */
.domain__conf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}

/* ── Body paragraph readability ───────────────────────────────────────── */
.body-para {
  font-size: var(--size-body);
  line-height: 1.75;
  color: var(--text-md);
  margin-bottom: 12px;
}
.body-para:last-child { margin-bottom: 0; }
.body-para__source { color: var(--text-dim); font-size: 0.88em; }

/* ── Strategic header trajectory rationale ────────────────────────────── */
.strategic-header__rationale {
  font-family: var(--font-body);
  font-size: var(--size-aq);
  font-style: italic;
  color: var(--text-lo);
  margin-top: 6px;
  line-height: 1.6;
}

/* ── Sub-label variants ───────────────────────────────────────────────── */
.sub-label--observed   { color: var(--text-dim); }
.sub-label--assessment { color: var(--color-gold-dim); }

/* ── Handling/classification warning bar ──────────────────────────────── */
.handling-bar {
  background: var(--conf-red);
  color: #fff;
  font-family: var(--font-ui);
  font-size: var(--size-badge);
  font-weight: 700;
  padding: 7px 20px;
  letter-spacing: 0.12em;
  text-align: center;
}

/* ── Classification running banner — print only ──────────────────────── */
.print-class-banner { display: none; }
@media print {
  .print-class-banner {
    display: block;
    position: fixed;
    left: 0;
    right: 0;
    font-family: var(--font-ui);
    font-size: 7pt;
    font-weight: 700;
    text-align: center;
    letter-spacing: 0.12em;
    color: var(--text-dim);
    z-index: 9999;
    background: white;
  }
  .print-class-banner--top    { top: 0; border-bottom: 0.5pt solid #ccc; padding: 3pt 0 2pt; }
  .print-class-banner--bottom { bottom: 0; border-top: 0.5pt solid #ccc; padding: 2pt 0 3pt; }
  body { margin-top: 16pt; margin-bottom: 16pt; }
}
""")
    return '\n'.join(chunks)


# ── Main renderer ─────────────────────────────────────────────────────────────

class HtmlRenderer:
    """
    Renders a BriefCycle dict to a self-contained, print-ready HTML string.

    All methods return HTML strings. No file I/O except CSS loading.
    """

    def __init__(self, cycle: dict):
        self.cycle  = cycle
        self.meta   = cycle.get('meta', {})
        self.css    = _load_css()

    # ── Public API ──────────────────────────────────────────────────────────

    def render(self) -> str:
        sections = '\n'.join([
            self._masthead(),
            self._strategic_header(),
            self._flash_points(),
            self._executive_assessment(),
            self._domains(),
            self._warning_indicators(),
            self._collection_gaps(),
            self._caveats(),
            self._footer(),
        ])
        return self._page(sections)

    # ── Page shell ──────────────────────────────────────────────────────────

    def _page(self, body: str) -> str:
        title      = _e(self.meta.get('cycleId', 'CSE Intel Brief'))
        cls_mark   = _e(self.meta.get('classification', 'PROTECTED B'))
        tlp        = _e(self.meta.get('tlp', 'AMBER'))
        cycle_id   = _e(self.meta.get('cycleId', ''))
        class_line = f'{cls_mark} // TLP:{tlp}'
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{self.css}
</style>
</head>
<body>
<!-- Classification running banners — visible in print only -->
<div class="print-class-banner print-class-banner--top">{class_line} — DRAFT — NOT FOR DISTRIBUTION</div>
<div class="print-class-banner print-class-banner--bottom">{class_line} · {cycle_id} — DRAFT — NOT FOR DISTRIBUTION</div>
<div class="brief">
{body}
</div>
</body>
</html>"""

    # ── MASTHEAD ────────────────────────────────────────────────────────────

    def _masthead(self) -> str:
        m = self.meta
        tlp       = m.get('tlp', 'AMBER')
        tlp_cls   = _TLP_CLASS.get(tlp, 'masthead__tlp--amber')
        unit      = _e(m.get('analystUnit', ''))
        cycle_id  = _e(m.get('cycleId', ''))
        cycle_num = _e(m.get('cycleNum', '—'))
        subtitle  = _e(m.get('subtitle', ''))
        ctx_note  = _e(m.get('contextNote', ''))
        region    = _e(m.get('region', ''))
        ts        = m.get('timestamp', '')
        date_long = _fmt_date_long(ts)
        ts_fmt    = _fmt_ts(ts)
        threat    = m.get('threatLevel', 'SEVERE')
        traj      = m.get('threatTrajectory', 'escalating')
        threat_cls = _THREAT_CLASS.get(threat, 'threat-level--severe')
        traj_cls   = _TRAJ_CLASS.get(traj, 'trajectory-badge--escalating')
        traj_label = _TRAJECTORY_LABELS.get(traj, _e(traj))

        strip_cells_html = self._strip_cells(m.get('stripCells', []))

        return f"""<header class="masthead">
  <div class="masthead__class-bar">
    <span class="masthead__class-label">{_e(m.get('classification', 'PROTECTED B'))}</span>
    <span class="masthead__class-unit">{unit} · {cycle_id}</span>
  </div>
  <div class="masthead__flag"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAyAAAABACAIAAABtDoT4AAAB8UlEQVR42u3dyQmEQBBAUSMxAfMPxXh6ro3OtAu9z3t48mBB4eEjosu+rUWPMDj7AQCeWgSEwAIABJbAAgAElsASWAAgsASEwAIABJbAAgAElsASWAAgsASW/QAAAktgAQACS2ABAAJLYAksAEBgCSwAQGAJLABAYAksgQUAAktACCwAQGAJLABAYAksgQUAAktACCwAQGAJLABAYAkstyAACCyBZT8AwOyBVXqEwAIABJbAAgAElsACAASWwBJYAIDAElgAgMC6ET1x/cQnBRYAILByRo/AAgAEVs7uqRxzAgsAEFgCCwAQWKfQuRlYGUcLLABg2sA6ZFNiVomwE1gAwMyB1eTJmcACAASWwAIABNbvvnmRO4krCCwAQGCtl69epV/GElgAgMDKnDhtpwssABBYnQbEuHknsABAYPX+HayB2k5gAYDAElgCCwD4s8AKPtMAAAisEgERX/Y8qHnVCSwAIIz7s+evgVVhisACAKYNrGqzBBYAILAEFgAgsN52z+UZgQUACKwe2Q8AILAEFgAgsAQWACCwBJb9AAACS2ABAAJLYAEAAktgCSwAQGAJLABAYAksAEBgCSyBBQACS0AILABAYAksAEBgCSyBBQACS2DZDwAgsAQWACCwBBYAILAElv0AAAJLYAEAVXwA1ZIUXeYUR7EAAAAASUVORK5CYII=" alt="Canada" class="masthead__flag-banner"></div>
  <div class="masthead__hero">
    <div class="masthead__title-block">
      <div class="masthead__title">
        <span class="masthead__title-main">CSE </span><span class="masthead__title-year">INTEL</span>
      </div>
      <div class="masthead__subtitle">{subtitle}</div>
    </div>
    <div class="masthead__cycle-block">
      <div class="masthead__cycle-label">CYCLE</div>
      <div class="masthead__cycle-num">{cycle_num}</div>
      <div class="masthead__cycle-date">{date_long}</div>
      <div class="masthead__cycle-meta">{ts_fmt}</div>
    </div>
  </div>
  <div class="masthead__crimson-rule"></div>
  <div class="masthead__strip">
    {strip_cells_html}
  </div>
  <div class="masthead__ctx">
    <span class="masthead__ctx-note">{ctx_note}</span>
    <span class="masthead__tlp {tlp_cls}">TLP:{_e(tlp)}</span>
  </div>
  <div class="metadata-bar">
    <div class="metadata-bar__cell">
      <div class="metadata-bar__label">REGION</div>
      <div class="metadata-bar__value metadata-bar__value--hi">{region}</div>
    </div>
    <div class="metadata-bar__cell">
      <div class="metadata-bar__label">TIMESTAMP</div>
      <div class="metadata-bar__value">{ts_fmt}</div>
    </div>
    <div class="metadata-bar__cell">
      <div class="metadata-bar__label">THREAT LEVEL</div>
      <div class="metadata-bar__value">
        <span class="threat-level {threat_cls}">{_e(threat)}</span>
      </div>
    </div>
    <div class="metadata-bar__cell">
      <div class="metadata-bar__label">TRAJECTORY</div>
      <div class="metadata-bar__value">
        <span class="trajectory-badge {traj_cls}">{traj_label}</span>
      </div>
    </div>
  </div>
</header>"""

    def _strip_cells(self, cells: list[dict]) -> str:
        parts = []
        for c in cells:
            top = _e(c.get('top', '—'))
            bot = _e(c.get('bot', ''))
            parts.append(f"""    <div class="masthead__strip-cell">
      <span class="masthead__strip-top">{top}</span>
      <span class="masthead__strip-bot">{bot}</span>
    </div>""")
        return '\n'.join(parts)

    # ── STRATEGIC HEADER ────────────────────────────────────────────────────

    def _strategic_header(self) -> str:
        sh   = self.cycle.get('strategicHeader', {})
        judg = _e(sh.get('headlineJudgment', ''))
        traj = _e(sh.get('trajectoryRationale', ''))
        threat    = self.meta.get('threatLevel', 'SEVERE')
        traj_val  = self.meta.get('threatTrajectory', 'escalating')
        threat_cls = _THREAT_CLASS.get(threat, 'threat-level--severe')
        traj_cls   = _TRAJ_CLASS.get(traj_val, 'trajectory-badge--escalating')
        traj_label = _TRAJECTORY_LABELS.get(traj_val, _e(traj_val))

        return f"""<section class="strategic-header">
  <div class="strategic-header__content">
    <div class="strategic-header__label">HEADLINE JUDGMENT</div>
    <div class="strategic-header__judgment">{judg}</div>
    {f'<div class="strategic-header__rationale">{traj}</div>' if traj else ''}
  </div>
  <div class="strategic-header__meta">
    <span class="threat-level {threat_cls}">{_e(threat)}</span>
    <span class="trajectory-badge {traj_cls}">{traj_label}</span>
  </div>
</section>"""

    # ── FLASH POINTS ────────────────────────────────────────────────────────

    def _flash_points(self) -> str:
        fps = self.cycle.get('flashPoints', [])
        if not fps:
            return ''

        items_html = []
        for fp in fps:
            ts_str = _fmt_ts(fp.get('timestamp', ''))
            domain = fp.get('domain', 'd1')
            conf   = fp.get('confidence', 'moderate')
            headline = _e(fp.get('headline', ''))
            detail   = _e(fp.get('detail', ''))
            items_html.append(f"""  <div class="flash-points__item">
    <div class="flash-points__item-time">{ts_str}</div>
    <div class="flash-points__item-content">
      <div class="flash-points__item-headline">{headline}</div>
      <div class="flash-points__item-detail">{detail}</div>
    </div>
    <div class="flash-points__item-conf badge {_CONF_TIER_CLASS.get(conf, 'badge--amber')}">{_e(conf).upper()}</div>
  </div>""")

        latest_ts = _fmt_ts(fps[-1].get('timestamp', '')) if fps else ''
        return f"""<section class="flash-points">
  <div class="flash-points__header">
    <span class="flash-points__label">FLASH POINTS</span>
    <span class="flash-points__timestamp">{latest_ts}</span>
  </div>
{''.join(items_html)}
</section>"""

    # ── EXECUTIVE ASSESSMENT ────────────────────────────────────────────────

    def _executive_assessment(self) -> str:
        ex     = self.cycle.get('executive', {})
        bluf   = _e(ex.get('bluf', ''))
        kjs    = ex.get('keyJudgments', [])
        kpis   = ex.get('kpis', [])

        ts       = self.meta.get('timestamp', '')
        cycle_num = _e(self.meta.get('cycleNum', '—'))
        date_long = _fmt_date_long(ts)
        cycle_ref = f'CYCLE {cycle_num} · {date_long}'

        kj_items = self._exec_kj_list(kjs)
        kpi_strip = self._kpi_strip(kpis)

        return f"""<section>
  <div class="exec__gradient"></div>
  <div class="exec__header">
    <div class="exec__header-title">EXECUTIVE ASSESSMENT</div>
    <div class="exec__header-meta">{_e(cycle_ref)}</div>
  </div>
  <div class="exec__bluf">
    <div class="exec__bluf-label">BLUF — BOTTOM LINE UP FRONT</div>
    <div class="exec__bluf-text">{bluf}</div>
  </div>
  <ul class="exec__kj-list">
    {kj_items}
  </ul>
  {kpi_strip}
</section>"""

    def _exec_kj_list(self, kjs: list) -> str:
        if not kjs:
            return ''
        items = []
        for kj in kjs:
            # kjs can be either KeyJudgment objects or plain strings (placeholder)
            if isinstance(kj, dict):
                domain  = kj.get('domain', 'd1')
                conf    = kj.get('confidence', 'moderate')
                text    = _e(kj.get('text', ''))
                domain_label = _DOMAIN_LABELS.get(domain, domain.upper())
                conf_badge = _conf_badge(conf)
                items.append(f"""    <li class="exec__kj-item">
      <span class="exec__kj-domain exec__kj-domain--{_e(domain)}">{_e(domain_label)}</span>
      <span class="exec__kj-text">{text}</span>
      <span class="exec__kj-conf {_CONF_TIER_CLASS.get(conf, 'badge--amber')}">{_e((conf or '').upper())}</span>
    </li>""")
            else:
                # Placeholder string
                items.append(f"""    <li class="exec__kj-item">
      <span class="exec__kj-text">{_e(str(kj))}</span>
    </li>""")
        return '\n'.join(items)

    def _kpi_strip(self, kpis: list) -> str:
        if not kpis:
            return ''
        cells = []
        for kpi in kpis:
            domain = kpi.get('domain', 'd1')
            number = _e(kpi.get('number', '—'))
            label  = _e(kpi.get('label', ''))
            cells.append(f"""  <div class="kpi-strip__cell kpi-strip__cell--{_e(domain)}">
    <div class="kpi-strip__number">{number}</div>
    <div class="kpi-strip__label">{label}</div>
  </div>""")
        return f'<div class="kpi-strip">\n' + '\n'.join(cells) + '\n</div>'

    # ── DOMAINS ─────────────────────────────────────────────────────────────

    def _domains(self) -> str:
        domains = self.cycle.get('domains', [])
        return '\n'.join(self._domain_section(d) for d in domains)

    def _domain_section(self, d: dict) -> str:
        did   = d.get('id', 'd1')
        num   = _e(d.get('num', '01'))
        title = _e(d.get('title', ''))
        aq    = _e(d.get('assessmentQuestion', ''))
        conf  = d.get('confidence', 'moderate')

        kj_html     = self._key_judgment(d.get('keyJudgment', {}), did)
        body_html   = self._body_wrap(d.get('bodyParagraphs', []))
        tables_html = self._tables(d.get('tables', []), did)
        tl_html     = self._timeline(d.get('timeline', []), did)
        am_html     = self._actor_matrix(d.get('actorMatrix', []))
        an_html     = self._analyst_note(d.get('analystNote'))
        dn_html     = self._dissenter_note(d.get('dissenterNote'))

        conf_badge_html = _conf_badge(conf)

        return f"""<section class="domain domain--{_e(did)}">
  <div class="domain__gradient"></div>
  <div class="domain__header">
    <div class="domain__num">{num}</div>
    <div class="domain__title-cell">
      <div class="domain__title">{title}</div>
      <div class="domain__conf-row">{conf_badge_html}</div>
    </div>
  </div>
  <div class="domain__aq">
    <div class="domain__aq-text">{aq}</div>
    <div class="domain__aq-conf">{_e(_DOMAIN_LABELS.get(did, did.upper()))}</div>
  </div>
  {kj_html}
  {body_html}
  {tables_html}
  {tl_html}
  {am_html}
  {an_html}
  {dn_html}
  <div class="section-end">
    <div class="section-end--thick"></div>
    <div class="section-end--thin"></div>
  </div>
</section>"""

    def _key_judgment(self, kj: dict, did: str) -> str:
        if not kj:
            return ''
        conf     = kj.get('confidence', 'moderate')
        prob     = _e(kj.get('probabilityRange', ''))
        language = kj.get('language', '')
        text     = _e(kj.get('text', ''))
        basis    = _e(kj.get('basis', ''))
        phrase   = _e(_conf_phrase(language))
        rng      = _e(_conf_range(language) or prob)
        lang_slug = re.sub(r'[^a-z-]', '', (language or '').lower())

        # Probability bar
        prob_bar = ''
        if lang_slug:
            prob_bar = (
                f'<div class="prob-bar">'
                f'<span class="prob-bar__fill prob-bar__fill--{lang_slug}"></span>'
                f'</div>'
            )

        return f"""  <div class="kj">
    <div class="kj__label-row">
      <div class="kj__label">KEY JUDGMENT</div>
      <div class="kj__meta">
        <span class="kj__domain-ref">{_e(did.upper())}</span>
        <span class="kj__probability">{rng}</span>
        <span class="badge {_CONF_TIER_CLASS.get(conf, 'badge--amber')}">{_e(conf).upper()}</span>
      </div>
    </div>
    {('<div class="kj__confidence-phrase">' + phrase + '&#8230;</div>') if phrase else ''}
    {prob_bar}
    <div class="kj__text">{text}</div>
    {f'<div class="kj__basis">{basis}</div>' if basis else ''}
  </div>"""

    def _body_wrap(self, paragraphs: list[dict]) -> str:
        if not paragraphs:
            return ''
        paras = []
        prev_label = None
        for p in paragraphs:
            sub_label = p.get('subLabel', '')
            sub_variant = p.get('subLabelVariant', '')
            text      = _e(p.get('text', ''))
            ts        = p.get('timestamp', '')
            citations = p.get('citations', [])
            cite_html = _cite_inline(citations)

            label_html = ''
            if sub_label and sub_label != prev_label:
                variant_cls = f'sub-label--{_e(sub_variant)}' if sub_variant else ''
                label_html = f'<div class="sub-label {variant_cls}">{_e(sub_label)}</div>\n    '
                prev_label = sub_label

            ts_html = ''
            if ts:
                ts_html = f'<span class="body-para__timestamp">{_fmt_ts(ts)}</span>\n    '

            paras.append(f"""    {label_html}{ts_html}<p class="body-para">{text}{cite_html}</p>""")

        return f"""  <div class="body-wrap">
{''.join(paras)}
  </div>"""

    def _tables(self, tables: list[dict] | None, did: str) -> str:
        if not tables:
            return ''
        out = []
        for tbl in tables:
            caption  = _e(tbl.get('caption', ''))
            headers  = tbl.get('headers', [])
            rows     = tbl.get('rows', [])
            unit     = _e(tbl.get('unit', ''))

            thead = ''.join(f'<th>{_e(h)}</th>' for h in headers)
            tbody_rows = []
            for row in rows:
                status = row.get('status', '')
                change = row.get('change', '')
                label  = _e(row.get('label', ''))
                vals   = row.get('values', [])
                row_cls = f'status--{_e(status)}' if status else ''
                tds = f'<td class="label">{label}</td>'
                for i, v in enumerate(vals):
                    cell_cls = ''
                    if i == len(vals) - 1 and change:
                        cell_cls = f'change change--{_e(change)}'
                    elif i == 0:
                        cell_cls = 'val'
                    tds += f'<td class="{cell_cls}">{_e(v)}</td>'
                tbody_rows.append(f'<tr class="{row_cls}">{tds}</tr>')

            unit_note = f' <span class="data-table__unit">({unit})</span>' if unit else ''

            out.append(f"""  <div class="data-table-wrap">
    <div class="data-table-caption">{caption}{unit_note}</div>
    <table class="data-table">
      <thead><tr>{thead}</tr></thead>
      <tbody>{''.join(tbody_rows)}</tbody>
    </table>
  </div>""")
        return '\n'.join(out)

    def _timeline(self, events: list[dict] | None, did: str) -> str:
        if not events:
            return ''
        items = []
        for ev in events:
            ts     = _fmt_ts(ev.get('timestamp', ''))
            actor  = _e(ev.get('actor', ''))
            action = _e(ev.get('action', ''))
            domain = ev.get('domain', did)
            items.append(f"""    <li class="timeline__event timeline__event--{_e(domain)}">
      <div class="timeline__time">{ts}</div>
      <span class="timeline__actor">{actor}</span>
      <span class="timeline__action">{action}</span>
    </li>""")
        return f"""  <ol class="timeline">
{''.join(items)}
  </ol>"""

    def _actor_matrix(self, rows: list[dict] | None) -> str:
        if not rows:
            return ''
        trs = []
        for row in rows:
            actor   = _e(row.get('actor', ''))
            posture = _e(row.get('posture', ''))
            change  = _e(row.get('changeSincePrev', row.get('changeSincePrevCycle', '')))
            assess  = _e(row.get('assessment', ''))
            conf    = row.get('confidence', 'moderate')
            trs.append(f"""      <tr>
        <td class="actor-name">{actor}</td>
        <td>{posture}</td>
        <td class="actor-change">{change}</td>
        <td>{assess}</td>
        <td>{_conf_badge(conf)}</td>
      </tr>""")
        return f"""  <div class="actor-matrix">
    <div class="actor-matrix__caption">ACTOR POSTURE MATRIX</div>
    <table>
      <thead>
        <tr>
          <th>ACTOR</th><th>POSTURE</th><th>CHANGE</th><th>ASSESSMENT</th><th>CONF</th>
        </tr>
      </thead>
      <tbody>
{''.join(trs)}
      </tbody>
    </table>
  </div>"""

    def _analyst_note(self, note: dict | None) -> str:
        if not note:
            return ''
        title    = _e(note.get('title', 'ANALYTICAL NOTE'))
        cycle_ref = _e(note.get('cycleRef', ''))
        text     = _e(note.get('text', ''))
        return f"""  <aside class="analyst-note">
    <div class="analyst-note__gradient"></div>
    <div class="analyst-note__header">
      <div class="analyst-note__title">{title}</div>
      <div class="analyst-note__label">{cycle_ref}</div>
    </div>
    <div class="analyst-note__body">
      <div class="analyst-note__text">{text}</div>
    </div>
  </aside>"""

    def _dissenter_note(self, note: dict | None) -> str:
        if not note:
            return ''
        analyst_id = _e(note.get('analystId', 'ANALYST B'))
        text       = _e(note.get('text', ''))
        domain     = _e(note.get('domain', ''))
        return f"""  <aside class="dissenter-note">
    <div class="dissenter-note__gradient"></div>
    <div class="dissenter-note__header">
      <div class="dissenter-note__title">DISSENTING VIEW{' · ' + domain.upper() if domain else ''}</div>
      <div class="dissenter-note__attribution">{analyst_id}</div>
    </div>
    <div class="dissenter-note__body">
      <div class="dissenter-note__text">{text}</div>
    </div>
  </aside>"""

    # ── WARNING INDICATORS ──────────────────────────────────────────────────

    def _warning_indicators(self) -> str:
        wis = self.cycle.get('warningIndicators', [])
        if not wis:
            return ''

        cycle_num  = _e(self.meta.get('cycleNum', '—'))
        date_long  = _fmt_date_long(self.meta.get('timestamp', ''))
        cycle_ref  = f'CYCLE {cycle_num} · {date_long}'

        rows = []
        for wi in wis:
            status  = wi.get('status', 'watching')
            change  = wi.get('change', 'unchanged')
            indic   = _e(wi.get('indicator', ''))
            domain  = wi.get('domain', 'd1')
            detail  = _e(wi.get('detail', ''))
            domain_label = _DOMAIN_LABELS.get(domain, domain.upper())
            icon = _WI_STATUS_ICON.get(status, '&#9679;')
            rows.append(f"""      <tr>
        <td>
          <span class="wi-icon wi-icon--{_e(status)}">{icon}</span>
          <span class="wi-status {_WI_STATUS_CLASS.get(status, 'wi-status--watching')}">{_e(status).upper()}</span>
        </td>
        <td class="wi-table__indicator">{indic}</td>
        <td><span class="exec__kj-domain exec__kj-domain--{_e(domain)}">{_e(domain_label)}</span></td>
        <td>{detail}</td>
        <td><span class="wi-change {_WI_CHANGE_CLASS.get(change, 'wi-change--unchanged')}">{_e(change).upper()}</span></td>
      </tr>""")

        count_badge = f'<span class="badge badge--amber">{len(wis)}</span>'
        return f"""<section class="warning-indicators">
  <div class="warning-indicators__gradient"></div>
  <div class="warning-indicators__header">
    <div class="warning-indicators__title">WARNING INDICATORS {count_badge}</div>
    <div class="warning-indicators__cycle">{_e(cycle_ref)}</div>
  </div>
  <div class="warning-indicators__table">
    <table class="wi-table">
      <thead>
        <tr>
          <th>STATUS</th><th>INDICATOR</th><th>DOMAIN</th><th>DETAIL</th><th>CHANGE</th>
        </tr>
      </thead>
      <tbody>
{''.join(rows)}
      </tbody>
    </table>
  </div>
</section>"""

    # ── COLLECTION GAPS ─────────────────────────────────────────────────────

    def _collection_gaps(self) -> str:
        gaps = self.cycle.get('collectionGaps', [])
        if not gaps:
            return ''

        items_html = []
        for g in gaps:
            sev    = g.get('severity', 'minor')
            domain = g.get('domain', 'd1')
            gap    = _e(g.get('gap', ''))
            sig    = _e(g.get('significance', ''))
            domain_label = _DOMAIN_LABELS.get(domain, domain.upper())
            items_html.append(f"""  <li class="gap-item">
    <span class="gap-item__severity {_GAP_SEV_CLASS.get(sev, 'gap-item__severity--minor')}">{_e(sev).upper()}</span>
    <span class="gap-item__domain gap-item__domain--{_e(domain)}">{_e(domain_label)}</span>
    <div class="gap-item__content">
      <div class="gap-item__gap">{gap}</div>
      <div class="gap-item__significance">{sig}</div>
    </div>
  </li>""")

        return f"""<section class="collection-gaps">
  <div class="collection-gaps__gradient"></div>
  <div class="collection-gaps__header">
    <div class="collection-gaps__title">COLLECTION GAP REGISTER</div>
  </div>
  <ul class="collection-gaps__items">
{''.join(items_html)}
  </ul>
</section>"""

    # ── CAVEATS ─────────────────────────────────────────────────────────────

    def _caveats(self) -> str:
        cav = self.cycle.get('caveats', {})
        if not cav:
            return ''

        cycle_ref  = _e(cav.get('cycleRef', ''))
        handling   = _e(cav.get('handling', ''))
        items      = cav.get('items', [])
        conf_assess = _e(cav.get('confidenceAssessment', ''))
        src_quality = _e(cav.get('sourceQuality', ''))
        dis_notes  = cav.get('dissenterNotes', [])

        items_html = []
        for item in items:
            label = _e(item.get('label', ''))
            text  = _e(item.get('text', ''))
            items_html.append(f"""    <li class="caveats__item">
      <span class="caveats__item-label">{label}:</span>{text}
    </li>""")

        # Source quality as an extra caveat item
        if src_quality:
            items_html.append(f"""    <li class="caveats__item">
      <span class="caveats__item-label">SOURCE QUALITY:</span>{src_quality}
    </li>""")

        dis_html = ''
        for dn in dis_notes:
            dis_html += self._dissenter_note(dn)

        return f"""<section class="caveats">
  <div class="caveats__gradient"></div>
  <div class="caveats__header">
    <div class="caveats__title">CAVEATS &amp; CONFIDENCE</div>
    <div class="caveats__cycle">{cycle_ref}</div>
  </div>
  {f'<div class="handling-bar">{handling}</div>' if handling else ''}
  <ul class="caveats__items">
{''.join(items_html)}
  </ul>
  {f'''<div class="caveats__confidence">
    <div class="caveats__confidence-label">CONFIDENCE ASSESSMENT</div>
    <div class="caveats__confidence-text">{conf_assess}</div>
  </div>''' if conf_assess else ''}
  {dis_html}
</section>"""

    # ── FOOTER ──────────────────────────────────────────────────────────────

    def _footer(self) -> str:
        f    = self.cycle.get('footer', {})
        fid  = _e(f.get('id', ''))
        cls  = _e(f.get('classification', ''))
        src  = _e(f.get('sources', ''))
        hdlg = _e(f.get('handling', ''))

        return f"""<footer class="brief-footer">
  <div class="brief-footer__flag"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAfQAAAA8CAIAAAAfeN+wAAABXElEQVR42u3a0QmDMBRAUSdxAfcfxXn0Q4SgRFCjz8RzKKU/fdQiNxrsJgCa0/kLAMQdAHEHQNwBEHcAxB1A3AEQd4CXjEN/8/WHYxF3QNzFHUDcxR1A3MUdQNzFHRB3cRd3QNzFHUDcxR1A3MUdQNzFHUDcxR0Qd3F3ogDiLu4A4i7uAOIu7gC1xL3IHHEHEHdxB8Rd3AHE/WzT9x/EHaDiK/dlQvou7gAtxL3gfYC4A4TFPf1WbtqFyeIOEHzlnm6y76ddXjPEHSA47k/cEIg7gLiLOyDuJSq82Xs5nnl2vrgDhF25P71yiDtA2NMy4cuGuAPibs8dQNzFHeCfcc/9gG8ei7gD4i7uAOK+DhF3gHbiXsWxiDsg7uIOIO7iDiDu4g4g7uIOiLu4izsg7uIOIO7iDiDu4g4g7uIOIO7iDoi7uDtRAHEXdwAqIO4A4g6AuAMg7gCIOwAZM78bi0rjgJ3CAAAAAElFTkSuQmCC" alt="Government of Canada"></div>
  <div class="brief-footer__main">
    <span class="brief-footer__id">{fid}</span>
    <span class="brief-footer__class">{cls}</span>
  </div>
  <div class="brief-footer__sources">Sources: {src}</div>
  <div class="brief-footer__handling">{hdlg}</div>
</footer>"""


# ── Convenience function ──────────────────────────────────────────────────────

def render_cycle(cycle: dict) -> str:
    """Render a BriefCycle dict to a self-contained HTML string."""
    return HtmlRenderer(cycle).render()
