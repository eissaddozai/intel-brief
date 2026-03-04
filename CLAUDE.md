# CSE Intelligence Brief — Claude Code Instructions

## What this is
Automated daily conflict intelligence brief for the Iran War File.
Two components:
1. **Pipeline** (`pipeline/`) — Python OSINT collection → Claude API drafting → human review → cycle JSON
2. **Template** (`src/`) — React + TypeScript front-end that renders from cycle JSON

The pipeline feeds the template. The template is what the analyst receives.

---

## Design rules (NEVER violate)
- All colours come from CSS variables in `src/styles/tokens.css` — never hardcode hex values
- Domain accent colours follow the `d1/d2/d3/d4/d5` prefix convention
- Domain mapping: d1=battlespace/crimson · d2=escalation/amber · d3=energy/green · d4=diplomatic/purple · d5=cyber/steel-blue
- Font stack: Palatino (display) / Georgia (body) / Trebuchet MS (UI) / IBM Plex Mono (data/timestamps)
- All font sizes come from CSS tokens — never hardcode px values in components

---

## Writing voice (NEVER violate — applies to all content in cycle JSON files)
- Every paragraph ≥ 2 sentences; no fragment leads
- **Lead sentences are assessments, not factual descriptions**
  - BAD: "Three BTGs were observed near Kherson."
  - GOOD: "We assess offensive preparations are underway; three BTGs have repositioned near Kherson."
- Use confidence language from the `ConfidenceLanguage` enum — no ad-hoc hedging phrases
- Temporal precision on all kinetic claims: "As of 0600 UTC 15 Mar"
- Source attribution in parenthetical italic at sentence end: "(AP, 15 Mar 0620 UTC)"
- Distinguish OBSERVED (Tier 1 facts) from ASSESSMENT (analytical judgment) with explicit sub-labels
- Dissenting views go in `DissenterNote` blocks, attributed "ANALYST B" — never anonymously
- Forbidden jargon: "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb)

---

## Source hierarchy (critical for pipeline quality)
- **Tier 1** (AP, Reuters, AFP, CTP-ISW, IAEA, CENTCOM, UKMTO) = factual floor; cite directly
- **Tier 2** = interpretation layer; cite as "reported" not "confirmed"
- **Iranian state media** = "Iranian government asserts" — never as factual input; never `verification: "confirmed"`
- If AP has not reported something, it is unconfirmed in this brief

---

## Confidence language ladder (from ConfidenceLanguage enum)
| Enum value | Rendered phrase | Probability |
|---|---|---|
| `almost-certainly` | "We assess with high confidence…" | 95–99% |
| `highly-likely` | "We judge it highly likely…" | 75–95% |
| `likely` | "Available evidence suggests…" | 55–75% |
| `possibly` | "Reporting indicates, though corroboration is limited…" | 45–55% |
| `unlikely` | "We judge it unlikely, though we cannot exclude…" | 20–45% |
| `almost-certainly-not` | "We assess with high confidence this will not…" | 1–5% |

---

## Component render order (NEVER reorder)
Domain section render sequence (exact):
1. `domain__gradient`
2. `domain__header` (number · title · confidence badge)
3. `domain__aq` (assessment question bar)
4. `.kj` (key judgment box)
5. `.body-wrap` (sub-labeled paragraphs)
6. Optional: `DataTable`, `Timeline`, `ActorMatrix`
7. Optional: `AnalystNote`
8. Optional: `DissenterNote`
9. `.section-end` (thick + thin rules)

Wrapper: `<section class="domain domain--{id}">`

---

## CSS architecture
```
src/styles/
  tokens.css       ← :root block; all design tokens; edit here to change colours/sizes
  base.css         ← body, html, scanline overlay, scrollbar, selection, vignette
  animations.css   ← keyframes and transition utilities
  intel-brief.css  ← all component BEM classes
```
`main.tsx` imports all four in order: tokens → base → animations → intel-brief.

---

## Pipeline architecture
```
pipeline/
  ingest/
    sources.yaml         ← source registry (tier, domain, method, URL) — editorial judgment lives here
    rss_ingest.py        ← feedparser RSS collection
    scraper.py           ← Playwright for JS-rendered live blogs (CNN, CNBC, NBC, CBS)
    email_ingest.py      ← IMAP parser for CFR Daily Brief
  triage/
    classifier.py        ← domain tagging + verification-status flagging
    novelty.py           ← diff against previous cycle to flag new vs. repeated information
    confidence.py        ← maps source tier to confidence tier
  draft/
    prompts/             ← one .md prompt template per domain; this is where analytical voice is encoded
    drafter.py           ← Claude API calls with structured JSON output
  review/
    review_cli.py        ← mandatory human review before cycle JSON is written
  output/
    serializer.py        ← assembles and validates final BriefCycle JSON
  main.py                ← orchestrator
pipeline-config.yaml     ← API keys, schedule, email settings (use env vars for secrets)
```

---

## Data conventions
- All content in `src/data/cycle[NNN].json` (front-end dev) or `cycles/` (pipeline output)
- Schema enforced by `src/types/brief.ts` (TypeScript) and `pipeline/output/schema.json` (Python validation)
- `ConfidenceLanguage` enum controls all estimative phrasing — never write confidence phrases as free text
- `VerificationStatus` must always be set: Tier 1 sources → `confirmed`; Tier 2 → `reported`; Tier 3 → `claimed`
- `Citation.source` should be the outlet name, not a URL: "AP", "Reuters", "CTP-ISW Evening Report"

---

## Commands
```bash
# Front-end
npm run dev              # Vite dev server — loads src/data/cycle001.json by default
npm run build            # Production build

# Pipeline — run from repo root
python pipeline/main.py                    # Full cycle: ingest → triage → draft → review → output
python pipeline/main.py --stage ingest     # Ingestion only; saves to pipeline/.cache/
python pipeline/main.py --stage triage     # Triage from last ingest cache
python pipeline/main.py --stage draft      # Draft from last triage output
python pipeline/main.py --stage review     # Open review CLI against last draft
python pipeline/main.py --stage output     # Write approved draft to cycles/

# Pipeline with specific date (for backfill)
python pipeline/main.py --date 2024-03-15
```

---

## Adding a new domain
1. Add `d6` tokens to `src/styles/tokens.css` (fill, shadow, deep, bright, body, grad)
2. Add `.domain--d6` CSS blocks to `intel-brief.css` (header, aq, kj, body-wrap, section-end)
3. Add `'d6'` to `DomainId` type in `src/types/brief.ts`
4. Add source entries with `domains: [d6]` in `pipeline/ingest/sources.yaml`
5. Add `pipeline/draft/prompts/newdomain.md`
6. Update `DomainSection.tsx` if any domain-specific rendering logic is needed
