---
name: intel-draft
description: "Phase 3 of the intelligence brief pipeline. Reads triaged items and drafts a complete BriefCycle JSON using Claude Code's native analytical capability. Triggered by /intel-draft or as step 3 of /workflow."
---

# Intel Draft — Analytical Drafting

**Invocation:** `/intel-draft`

Draft a complete CSE Intelligence Brief from triaged source items.

## Prerequisites

- `pipeline/.cache/tagged_YYYYMMDD.json` must exist (output of `/intel-triage`)
- Previous briefs in `briefs/` are used for delta context only (never as source material)

## Process

### 1. Load triaged items

Read `pipeline/.cache/tagged_YYYYMMDD.json`. Group items by `tagged_domains`.

### 2. Load previous brief for delta context

Read the most recent brief from `briefs/` to understand:
- Previous key judgments (for delta phrasing: "unchanged from previous cycle" vs "new assessment")
- Previous threat level and trajectory
- Previous warning indicator states

**NEVER copy content from previous briefs as new analysis.** Previous briefs are context only.

### 3. Draft each section

Read the prompt templates in `pipeline/draft/prompts/` for voice and structure guidance. These templates define the exact JSON schema, writing rules, confidence language, and attribution requirements for each section.

Draft in this order:
1. **Domain sections** (d1-d6) — one at a time, using only items tagged to that domain
2. **Flash Points** — extract from highest-urgency items across all domains
3. **Executive summary** — BLUF + key judgments synthesized from domain sections
4. **Strategic header** — headline judgment + one-line summary
5. **Warning indicators** — RED/AMBER/GREEN status for each indicator
6. **Collection gaps** — domains with thin coverage, failed Tier 1 sources
7. **Caveats** — confidence assessment, dissenter notes, source quality

### 4. ABSOLUTE RULES (from CLAUDE.md — violations cause rejection)

- **Every fact must trace to a specific triaged item.** No fabrication. No hallucination.
- **Lead sentences are assessments, not descriptions.** "We assess..." not "Three BTGs were observed..."
- **Use ONLY the 6 confidence phrases** from the confidence ladder. No ad-hoc hedging.
- **Temporal precision** on all kinetic claims: "As of 0600 UTC 15 Mar"
- **Source attribution** in parenthetical italic: "(AP, 15 Mar 0620 UTC)"
- **Iranian state media** = "Iranian government asserts" — never as factual input
- **Every paragraph >= 2 sentences.** No fragment leads.
- **Forbidden phrases:** "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb)

### 5. Assemble and validate

Build the complete BriefCycle JSON matching `src/types/brief.ts` schema. Required top-level keys:
- `meta` (cycleId, classification, tlp, timestamp, region, analystUnit, threatLevel, threatTrajectory, subtitle, contextNote, stripCells)
- `strategicHeader` (headlineJudgment, oneLineSummary)
- `flashPoints` (array)
- `executive` (bluf, keyJudgments, kpis)
- `domains` (array of 6 domain sections)
- `warningIndicators` (array)
- `collectionGaps` (array)
- `caveats` (cycleRef, items, confidenceAssessment, dissenterNotes, sourceQuality, handling)
- `footer` (id, classification, sources, handling)

### 6. Save output

Save to `briefs/CSE_Intel_Brief_YYYYMMDD_HHMMSS.json` where the timestamp ensures uniqueness across runs.

The `cycleId` in `meta` must match the filename stem.

## Prompt Templates (reference only — do not modify)

Located at `pipeline/draft/prompts/`:
- `battlespace.md` (d1), `escalation.md` (d2), `energy.md` (d3)
- `diplomatic.md` (d4), `cyber.md` (d5), `war_risk.md` (d6)
- `executive.md`, `strategic_header.md`, `flash_points.md`
- `warning_indicators.md`, `collection_gaps.md`

## Output Contract

- **Input:** `pipeline/.cache/tagged_YYYYMMDD.json`
- **Output:** `briefs/CSE_Intel_Brief_YYYYMMDD_HHMMSS.json`
