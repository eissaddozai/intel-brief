# CSE Intelligence Brief — Claude Code Instructions

## What this is
Automated daily conflict intelligence brief for the Iran War File, with comprehensive Kurdish and Turkish dimension coverage.
Two components:
1. **Pipeline** (`pipeline/`) — Python OSINT collection → Claude API drafting → human review → cycle JSON
2. **Template** (`src/`) — React + TypeScript front-end that renders from cycle JSON

The pipeline feeds the template. The template is what the analyst receives.

---

## Design rules (NEVER violate)
- All colours come from CSS variables in `src/styles/tokens.css` — never hardcode hex values
- Domain accent colours follow the `d1/d2/d3/d4/d5/d6` prefix convention
- Domain mapping:
  - d1 = battlespace / kinetic / crimson
  - d2 = escalation / trajectory / amber
  - d3 = energy / economic / green
  - d4 = diplomatic / political / purple
  - d5 = cyber / IO / steel-blue
  - d6 = war risk insurance / maritime finance / teal
- Font stack: Palatino (display) / Georgia (body) / Trebuchet MS (UI) / IBM Plex Mono (data/timestamps)
- All font sizes come from CSS tokens — never hardcode px values in components

---

## Writing voice — professional intelligence standard

### Core principles
This brief aims for the highest standard of finished intelligence (FINTEL) writing. The standard is the UK Joint Intelligence Committee Assessments or the US National Intelligence Estimate — not a newspaper, not a blog, and not a government press release. Every sentence must convey analytical value. Atmospheric scene-setting, redundant attribution, and vaporous hedging have no place here.

### Source-attribution as the primary lead structure
The preferred lead structure for body paragraphs and key judgments is **source-attributed reporting followed by the analytical judgment**, not the reverse.

- PREFERRED: "AP's report of 14 Mar (1140 UTC) confirms three battalion-scale repositioning movements near Kherson — a disposition consistent with offensive preparation rather than defensive consolidation."
- PREFERRED: "CENTCOM's press statement of 0900 UTC 15 Mar confirms a strike on an IRGC Quds Force logistics hub in Deir ez-Zor; the targeting pattern indicates an effort to sever the Damascus-Baghdad-Tehran supply corridor rather than to achieve a stand-alone deterrent effect."
- AVOID AS SENTENCE-OPENER: "We assess with high confidence that..." — this formula buries the sourcing and makes the analyst the subject rather than the intelligence.
- AVOID AS SENTENCE-OPENER: "We judge it highly likely that..." — same issue.
- ACCEPTABLE MID-SENTENCE: "...a pattern that, available evidence suggests, indicates pre-attack staging." The confidence language belongs inside the sentence after the source evidence is established.

### Confidence language ladder (unchanged — from ConfidenceLanguage enum)
The six estimative phrases still govern the `language` field in JSON and appear in body text — they just should not be sentence-initial when a source citation provides better grounding.

| Enum value | Rendered phrase | Probability |
|---|---|---|
| `almost-certainly` | "We assess with high confidence…" | 95–99% |
| `highly-likely` | "We judge it highly likely…" | 75–95% |
| `likely` | "Available evidence suggests…" | 55–75% |
| `possibly` | "Reporting indicates, though corroboration is limited…" | 45–55% |
| `unlikely` | "We judge it unlikely, though we cannot exclude…" | 20–45% |
| `almost-certainly-not` | "We assess with high confidence this will not…" | 1–5% |

When no named Tier 1 source is available for the opening clause, the confidence phrase is the correct opener:
- "Available evidence suggests — based on Tier 2 reporting from Reuters (14 Mar) and ICG's latest Iran assessment — that the ceasefire framework has effectively collapsed."

### Lead sentence requirements
- Every paragraph's first sentence must characterise, assess, or interpret — it must not merely relay a fact
- A lead sentence that reads like a wire service dateline ("Three BTGs were observed near Kherson on Tuesday") is wrong even if it is accurate
- The analytical load must appear in the first sentence; supporting factual detail follows
- Exception: OBSERVED sub-sections may open with a factual statement if the source is Tier 1 and the assessment appears in the second sentence

### Paragraph structure
Every paragraph must contain at minimum:
- One sentence of analytical judgment (what it means)
- One sentence of evidential support (what confirms it, with source and timestamp)
- Minimum 2 sentences per paragraph; minimum 8 words per sentence
- Maximum 35 words per sentence (longer sentences lose precision)

### Temporal precision
- All kinetic, nuclear, and diplomatic claims require a UTC timestamp: "As of 0600 UTC 15 Mar"
- Market data requires date and source: "Brent at $94.20/bbl as of 0700 UTC 14 Mar (CNBC Energy)"
- "Today", "yesterday", "recently" are prohibited — use explicit dates

### Source attribution
- Parenthetical at sentence end: "(AP, 15 Mar 1140 UTC)" or "(CTP-ISW Evening Report, 15 Mar)"
- Named source always precedes the claim when the claim rests on a single source
- Do not write "sources report" or "it is reported" — name the source
- Iranian state media: "Iranian state media PressTV asserts..." — never cited as independent corroboration

### Sub-label conventions
- `observed` sub-labels: factual, sourced, Tier 1 or 2 — use for OBSERVED, STATE POSITIONS, JWC, PREMIUM MARKET, OBSERVED ACTIVITY
- `assessment` sub-labels: analytical judgment, explicitly hedged — use for ASSESSMENT, ALIGNMENT SHIFTS, CAPACITY & UNDERWRITER POSTURE, COLLECTION LIMITATION

### Dissenting views
- Go in `DissenterNote` blocks, attributed "ANALYST B" — never anonymously
- Dissenter notes must be substantive counter-assessments, not mere hedges

### Forbidden jargon (absolute prohibition)
Never use: "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb), "stakeholders", "international community", "diplomatic efforts", "going forward", "it is worth noting", "needless to say", "at this time", "remains to be seen", "fluid situation", "on the ground", "all options are on the table" (unless directly quoting a named state actor), "risk environment", "uncertain times", "volatile market"

---

## Professional writing manual — expanded standards

### Avoiding punchiness
Intelligence writing must be precise, not punchy. "Punchiness" — the tendency to write short, dramatic sentences that feel decisive but sacrifice nuance — is the enemy of analytical integrity.

- BAD (punchy): "Iran struck. Israel responded. War is coming."
- GOOD: "Iranian ballistic strikes on Israeli territory, confirmed by AP (15 Mar 0430 UTC), represent the first direct state-to-state exchange of the conflict; Israel's response, as assessed from force positioning reported by CTP-ISW (15 Mar 1200 UTC), is likely to be measured to avoid triggering Hezbollah's full-front activation threshold."

Criteria for avoiding punchiness:
1. Do not end a paragraph on a single dramatic claim without analytical qualification
2. Do not use sentence fragments as paragraph conclusions ("A dangerous moment.")
3. Do not use em-dashes for dramatic effect — use them only for grammatical clarity
4. Every claim of consequence must be followed immediately by the evidentiary basis

### Achieving maximal clarity
Clarity does not mean simplicity — it means the reader understands exactly what is claimed, on what evidence, with what degree of confidence, and what would change the assessment.

- State the claim completely in the first sentence: who did what, where, when, confirmed by whom
- State the analytical implication in the second sentence: what it means for the conflict trajectory
- State the confidence level and limiting factor in the third sentence if the claim is contested: "This assessment rests on Tier 2 reporting and may be revised if CTP-ISW confirms or denies in the evening report."
- Use the sub-label system consistently: readers must know at a glance whether they are reading fact or assessment

### Active vs. passive voice
- Prefer active voice when the actor is known: "CENTCOM confirmed a strike" not "A strike was confirmed"
- Use passive voice when the actor is unknown or deliberately unspecified: "The site was struck by an unidentified drone" is correct when attribution is unconfirmed
- Never use passive voice to avoid stating the actor when the actor is known

### Technical vocabulary
- Military terms: use standard NATO/STANAG terminology (BTG, brigade, battalion, fire support, CAS, SEAD)
- Financial terms: define on first use in each section (JWC = Joint War Committee; AWRP = Additional War Risk Premium; GRT = Gross Register Tonnage)
- Nuclear terms: use IAEA defined terms (enrichment to NN% U-235, not "near weapons-grade" without citation)
- Kurdish/Turkish terms: Peshmerga, HPG, PJAK, KRG, SDF, AANES, NES — define on first use in the executive section

### Numerical precision
- Never round numbers that are cited precisely: if AP reports "47 rockets", write "47 rockets" not "dozens" or "nearly 50"
- Express probabilities as ranges, not points: "55–75%" not "65%"
- Express market data to the precision of the cited source: if Marsh cites "$0.18/GRT/day", write "$0.18/GRT/day" not "approximately 18 cents"
- Express time to the nearest available precision: "0600 UTC" if the hour is confirmed; "morning UTC" if only the period is known

---

## Kurdish and Turkish dimension — standing coverage requirement

This brief covers the Kurdish and Turkish dimension as a **mandatory cross-domain thread**, not an occasional footnote. The following actors and dynamics must be monitored every cycle:

### Key actors
- **PKK** (Kurdistan Workers' Party / Partiya Karkerên Kurdistanê) — designated terrorist org by Turkey, US, EU; armed wing HPG
- **PJAK** (Party of Free Life of Kurdistan) — Iran-focused PKK affiliate; armed wing HBKM; operates from Qandil Mountains
- **KRG** (Kurdistan Regional Government of Iraq) — semi-autonomous, Erbil capital; President Barzani (KDP); PM Barzani (KDP)
- **Peshmerga** — KRG armed forces; KDP forces vs. PUK forces have separate command structures
- **SDF** (Syrian Democratic Forces) — US-backed coalition dominated by YPG (Kurdish); governs AANES/Rojava
- **YPG/YPJ** — Kurdish armed groups in northeast Syria; Turkey designates as PKK terrorist extension
- **HDP/DEM Party** — Legal pro-Kurdish political party in Turkey; target of state closure proceedings
- **IRGC Quds Force** — maintains relationships with PKK-adjacent groups in Iraq/Syria for leverage against Turkey
- **Turkish Armed Forces** — Operating under "Operation Claw" series in northern Iraq; regular drone/air strikes in KRG territory
- **KDPI** (Kurdistan Democratic Party of Iran) — exiled Iranian Kurdish party; offices in KRG; targets of IRGC strikes
- **Komala** — Iranian Kurdish left-wing party; operates from KRG; IRGC cross-border target

### Standing coverage requirements by domain
- **D1 (Battlespace)**: Any Turkish airstrike in KRG territory; any PKK/PJAK armed activity; any SDF-ISIS engagement; any IRGC strike on KDPI/Komala offices in KRG
- **D2 (Escalation)**: Kurdish uprising risk in Iran (PJAK mobilisation, civil protest in Kurdistan Province); Turkish-US tensions over SDF arming
- **D3 (Energy)**: Kirkuk-Ceyhan pipeline status and throughput; KRG oil export volumes; Turkish blockade of KRG oil exports via Ceyhan (ongoing legal dispute)
- **D4 (Diplomatic)**: Turkish-KRG coordination on PKK; US-Turkey tensions over SDF; KRG-Baghdad federal disputes; KDPI-Iran diplomatic pressure on KRG to expel parties; HDP political suppression in Turkey
- **D5 (Cyber/IO)**: IRGC surveillance of Iranian Kurdish diaspora; Turkish Cyber Command operations; Kurdish hacktivist activity; Telegram channel shutdowns affecting Kurdish media
- **D6 (War Risk)**: Ceyhan terminal throughput disruptions due to PKK/Turkish operations; Kurdish crude export premium implications; Kirkuk-Ceyhan pipeline war risk status

### Source priority for Kurdish/Turkish dimension
- Rudaw, Kurdistan24, KirkukNow: Tier 2 "reported" for KRG-area events
- ANF News: Tier 3 "claimed" — PKK-aligned; only for PKK's own statements
- SOHR: Tier 2 "reported" for northeast Syria events — single-source caveat always
- KHRN, Bianet: Tier 2 "reported" for human rights documentation
- Turkish MoD / Anadolu Agency: Tier 2 for confirmed operation launches; Tier 3 for operational success claims

---

## Source hierarchy (critical for pipeline quality)
- **Tier 1** (AP, Reuters, AFP, CTP-ISW, IAEA, CENTCOM, UKMTO, Lloyd's Market Bulletins, P&I club circulars) = factual floor; cite directly
- **Tier 2** = interpretation layer; cite as "reported" not "confirmed"
- **Iranian state media** = "Iranian government asserts" — never as factual input; never `verification: "confirmed"`
- **PKK-affiliated sources** (ANF, HPG communiqués) = "PKK-affiliated [source] claims" — never factual input without Tier 1/2 corroboration
- If AP has not reported something, it is unconfirmed in this brief

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

### PDF suitability
The HTML output is designed for high-fidelity PDF conversion via:
- **Chromium headless** (`--print-to-pdf`): recommended path; preserves all CSS custom properties, gradients, and colour accuracy
- **wkhtmltopdf**: supported via `pipeline/render/print.css`; use `--page-size Letter --print-media-type`
- **Firefox print dialog**: functional; some gradient rendering differences

The `pipeline/render/print.css` file contains all print-specific overrides:
- Classification banners: top and bottom, fixed position in screen view → static in print (handled by `@page` margins)
- Domain gradients: hidden in print (`display: none`); replaced by coloured left borders per domain
- All transitions and animations: disabled in print
- Type: Georgia serif at 10pt for body; colour-adjusted for ink printing (dark-on-white)
- Page breaks: controlled via `break-before`/`break-inside`/`break-after` properties

### Embedding the CSE corporate logo in the PDF header
To add the CSE logo to the masthead and PDF output:

1. **Provide the logo file**: Place your logo file at `src/assets/cse-logo.svg` (SVG preferred for crispness at all PDF resolutions) or `src/assets/cse-logo.png` (PNG at minimum 300 DPI for print quality). The file should be added to the repository.

2. **Reference in the Masthead component**: Open `src/components/Masthead.tsx` and add an `<img>` tag:
   ```tsx
   import cseLogo from '../assets/cse-logo.svg';
   // Then inside the masthead JSX:
   <img src={cseLogo} alt="CSE" className="masthead__logo" />
   ```

3. **Style the logo**: Add to `src/styles/intel-brief.css`:
   ```css
   .masthead__logo {
     height: 36px;
     width: auto;
     opacity: 0.88;
   }
   @media print {
     .masthead__logo { height: 28pt; opacity: 1; }
   }
   ```

4. **PDF running header**: For a persistent logo on every PDF page (not just page 1), it must be placed in the `@page` margin box — this requires a CSS Paged Media processor (Prince XML or Weasyprint). Chromium's `--print-to-pdf` does not support `@page` margin content. With Chromium, the logo will appear only on the first page masthead.

To provide the logo: commit `src/assets/cse-logo.svg` (or `.png`) to the repository and Claude Code will integrate it.

---

## Pipeline architecture
```
pipeline/
  ingest/
    sources.yaml         ← source registry (tier, domain, method, URL) — editorial judgment lives here
    rss_ingest.py        ← feedparser RSS collection
    scraper.py           ← Playwright for JS-rendered live blogs
    email_ingest.py      ← IMAP parser for CFR Daily Brief
  triage/
    classifier.py        ← domain tagging + verification-status flagging
    novelty.py           ← diff against previous cycle to flag new vs. repeated information
    confidence.py        ← maps source tier to confidence tier
  draft/
    prompts/             ← one .md prompt template per domain; analytical voice is encoded here
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
- `ConfidenceLanguage` enum controls all estimative phrasing — never write confidence phrases as free text in ad-hoc ways
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

# PDF generation (Chromium headless — recommended)
chromium --headless --print-to-pdf=brief.pdf --print-to-pdf-no-header http://localhost:5173

# PDF generation (wkhtmltopdf)
wkhtmltopdf --page-size Letter --print-media-type --margin-top 1.1in --margin-bottom 1.0in http://localhost:5173 brief.pdf
```

---

## Domain conditionality
Domains are conditional on available intelligence — not every brief will include all six sections. A domain section should be produced **only when** that cycle's ingestion has surfaced material relevant to it:
- **D5 (Cyber/IO)** is the most frequently absent — include only if a CISA advisory, named firm report, or confirmed incident exists
- **D6 (War Risk Insurance)** is omitted if no JWC changes, premium movements, or P&I circulars surfaced
- **D3 (Energy)** may be brief or absent in cycles where Brent is flat and Hormuz traffic is nominal
- When a domain is absent, the executive section KPI strip should use `null` or `"—"` for that domain's cell
- The pipeline drafter will still receive the prompt for every domain, but the drafter should return `null` if source material is genuinely insufficient — the reviewer CLI will then suppress that domain from the output

---

## Adding a new domain
1. Add `d7` tokens to `src/styles/tokens.css` (fill, shadow, deep, bright, body, grad)
2. Add `.domain--d7` CSS blocks to `intel-brief.css` (header, aq, kj, body-wrap, section-end)
3. Add `'d7'` to `DomainId` type in `src/types/brief.ts`
4. Add source entries with `domains: [d7]` in `pipeline/ingest/sources.yaml`
5. Add `pipeline/draft/prompts/newdomain.md`
6. Update `DomainSection.tsx` if domain-specific rendering logic is needed
