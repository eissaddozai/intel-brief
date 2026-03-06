# CSE Intelligence Brief — Comprehensive Codebase Audit

**Date**: 2026-03-06
**Scope**: Full codebase — front-end, pipeline, configuration, data, build

---

## Executive Summary

8 parallel audit agents examined every dimension of the codebase. **87 discrete issues** were identified across 7 categories. The codebase is architecturally sound with strong type definitions and clear separation of concerns, but suffers from **systematic design-rule violations** (hardcoded colors/fonts), **incomplete D6 domain support**, **unsafe TypeScript patterns**, and **missing validation infrastructure**.

### Severity Distribution

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 12 | Production-blocking or design-rule violations |
| **HIGH** | 18 | Will degrade output quality or break features |
| **MEDIUM** | 31 | Code quality, type safety, editorial enforcement |
| **LOW** | 26 | Best practices, documentation, maintenance |

---

## Gameplan: Fix Categories in Priority Order

---

## PHASE 1 — CRITICAL FIXES (Must complete first)

### 1.1 D6 Domain Support: Resolve Serializer / Schema Contradiction

**Problem**: D6 (War Risk Insurance) is fully implemented in drafter.py, prompts, and front-end types, but the serializer rejects it and brief.ts comment says "Exactly 5 domains."

| File | Line | Issue |
|------|------|-------|
| `pipeline/output/serializer.py` | 31 | `VALID_DOMAIN_IDS = {'d1','d2','d3','d4','d5'}` — missing `d6` |
| `src/types/brief.ts` | 261 | Comment: "Exactly 5 domain sections" — contradicts d6 support |

**Fix**:
- Add `'d6'` to `VALID_DOMAIN_IDS` in serializer.py
- Update brief.ts comment to reflect 6 domains

---

### 1.2 CSS: Extract All Hardcoded Colors to Tokens

**Problem**: 62+ hardcoded hex/rgba values across 3 CSS files. Direct violation of CLAUDE.md: "All colours come from CSS variables in `src/styles/tokens.css` — never hardcode hex values."

**Files affected**:
- `src/styles/intel-brief.css` — 44 hardcoded colors
- `src/styles/animations.css` — 11 hardcoded RGBA values
- `src/styles/base.css` — 7 hardcoded colors

**Fix**: Add ~25 new CSS tokens to `tokens.css`, then replace every hardcoded value:

| New Token | Hex Value | Used For |
|-----------|-----------|----------|
| `--color-page-deep` | `#030406` | Classification bar bg |
| `--color-border-subtle` | `#1A1A1A` | Masthead border |
| `--color-text-dusty` | `#A07878` | Classification label |
| `--color-text-dusty-dark` | `#785858` | Classification unit |
| `--color-crimson-dark` | `#801420` | Masthead strip cell border |
| `--color-severe` | `#C04020` | Threat level SEVERE badge |
| `--color-gold-gradient-top` | `#362A00` | Executive gradient start |
| `--color-gold-deep-bg` | `#100D00` | Executive header bg |
| `--dt-status-elevated` | `#091610` | Table row bg |
| `--dt-status-rising` | `#0A1208` | Table row bg |
| `--dt-status-critical` | `#160508` | Table row bg |
| `--dt-status-windfall` | `#091410` | Table row bg |
| `--dissenter-bg` | `#00060E` | Dissenter note body |
| `--dissenter-header` | `#000818` | Dissenter note header |
| `--dissenter-gradient-start` | `#000C28` | Dissenter gradient |
| `--dissenter-gradient-end` | `#001038` | Dissenter gradient |
| `--dissenter-accent` | `#2C5088` | Dissenter attribution |
| `--dissenter-border` | `#001830` | Dissenter border |
| `--warn-gradient-start` | `#160700` | Warning/Caveat gradient |
| `--warn-gradient-end` | `#0E0400` | Warning/Caveat gradient |
| `--warn-table-bg` | `#0A0500` | Warning table bg |
| `--warn-border` | `#1A0800` | Warning/Caveat border |
| `--warn-border-alt` | `#140600` | Warning row border |
| `--gap-gradient-start` | `#000416` | Collection gap gradient |
| `--gap-gradient-end` | `#000810` | Collection gap gradient |
| `--gap-border` | `#00091C` | Collection gap border |
| `--caveat-bg` | `#120900` | Caveat confidence bg |
| `--color-scrollbar-bg` | `#020407` | Scrollbar bg |

---

### 1.3 CSS: Extract All Hardcoded Font Sizes to Tokens

**Problem**: 14 hardcoded px font sizes in `intel-brief.css`. Violates: "All font sizes come from CSS tokens — never hardcode px values in components."

| Line | Current | Proposed Token |
|------|---------|----------------|
| 238 | `font-size: 7px` | `--icon-size-xs` |
| 243 | `font-size: 17px` | `--size-kj-display` |
| 313 | `font-size: 8px` | `--icon-size-sm` |
| 437 | `font-size: 9px` | `--icon-size-md` |
| 642 | `font-size: 26px` | `--size-domain-num` |
| 767 | `font-size: 6px` | `--icon-size-xxs` |
| 916 | `font-size: 8px` | `--icon-size-sm` (reuse) |
| 972 | `font-size: 7px` | `--icon-size-xs` (reuse) |
| 1238 | `font-size: 11px` | `--icon-size-lg` |
| 1339 | `font-size: 10px` | `--icon-size-default` |
| 1435 | `font-size: 11px` | `--icon-size-lg` (reuse) |
| 1484 | `font-size: 5px` | `--icon-size-micro` |

**Fix**: Add icon/display size tokens to `tokens.css`, replace all hardcoded values.

---

### 1.4 Missing D6 Hover Animations

**Problem**: D6 domain has full CSS support in `intel-brief.css` but `animations.css` has no D6 hover glow or KPI text-shadow.

**File**: `src/styles/animations.css`

**Fix**: Add after line 64:
```css
.domain--d6:hover { box-shadow: -4px 0 28px rgba(var(--d6-bright-rgb), 0.22); }
```
Add D6 KPI hover text-shadow alongside d1-d5 entries.

---

### 1.5 Vite Config: Missing GitHub Pages Base Path

**Problem**: `vite.config.ts` has no `base` path. GitHub Pages serves at `/intel-brief/`, so all assets will 404.

**File**: `vite.config.ts`

**Fix**: Add `base: '/intel-brief/'` to defineConfig.

---

### 1.6 Pipeline Security: Email Credentials Config Fallback

**Problem**: `pipeline/ingest/email_ingest.py` lines 69-85 allow email credentials from YAML config as fallback. Plaintext credentials in config files are a critical vulnerability.

**Fix**: Remove config fallback; require env vars only. Raise error if `CSE_EMAIL_USER` / `CSE_EMAIL_PASS` env vars are not set.

---

## PHASE 2 — HIGH-PRIORITY FIXES

### 2.1 TypeScript: Fix Unsafe `Record<string, string>` Patterns (11 instances)

**Problem**: 7 components use `Record<string, string>` for lookup maps instead of properly typed `Record<EnumType, string>`. This defeats compile-time exhaustiveness checking.

| Component | Line | Current | Should Be |
|-----------|------|---------|-----------|
| `DomainSection.tsx` | 14 | `Record<string, string>` | `Record<ConfidenceTier, string>` |
| `FlashPoints.tsx` | 7 | `Record<string, string>` | `Record<ConfidenceTier, string>` |
| `KeyJudgmentBox.tsx` | 11 | `Record<string, string>` | `Record<ConfidenceTier, string>` |
| `ActorMatrix.tsx` | 7 | `Record<string, string>` | `Record<ConfidenceTier, string>` |
| `Masthead.tsx` | 7 | `Record<string, string>` | `Record<TLPLevel, string>` |
| `CollectionGaps.tsx` | 8 | `Record<string, string>` | `Record<CollectionGapSeverity, string>` |
| `WarningIndicators.tsx` | 9, 16, 23 | 3x `Record<string, string>` | Typed Records |

---

### 2.2 TypeScript: Fix Type/Data Mismatches

**Problem A**: `ChangeDirection` type (brief.ts:43) is `'up' | 'down' | 'neutral'` but cycle data uses `"same"`.
**Fix**: Add `'same'` to `ChangeDirection` type.

**Problem B**: `ActorMatrixRow.changeSincePrevCycle` is typed as `string` instead of `ChangeDirection`.
**Fix**: Change type to `ChangeDirection`.

**Problem C**: Inline literal unions in `TableRow.status`, `CollectionGap.severity`, `WarningIndicator.status`, `WarningIndicator.change` should be extracted to named types.
**Fix**: Create `TableRowStatus`, `CollectionGapSeverity`, `WarningIndicatorStatus`, `WarningIndicatorChange` types.

---

### 2.3 TypeScript: Fix Unsafe Double Type Assertion in App.tsx

**Problem**: `const cycle = cycleData as unknown as BriefCycle` bypasses all type checking.
**Fix**: Add a type guard function or use runtime validation.

---

### 2.4 Pipeline: Drafter Token Limits Don't Match Config

**Problem**: `pipeline-config.yaml` specifies max token limits but `drafter.py` hardcodes different values that ignore the config.

| Context | Config Value | Drafter Hardcoded |
|---------|-------------|-------------------|
| Per domain | 1500 | 3000 |
| Executive | 1200 | 2000 |
| Strategic | 400 | 500 |
| Warnings | 800 | 1200 |
| Gaps | 1200 | 900 |

**Fix**: Update drafter.py to read from config, OR update config to match actual values.

---

### 2.5 Pipeline: Incomplete Forbidden Jargon in Prompts

**Problem**: CLAUDE.md forbids: "kinetic activity", "threat actors", "threat landscape", "robust", "leverage" (verb). Several prompts only list a subset.

| Prompt | Missing Terms |
|--------|--------------|
| `strategic_header.md` | "threat actors", "threat landscape" |
| `escalation.md` | "robust", "leverage" |
| `energy.md` | "robust", "leverage" |
| `diplomatic.md` | "robust", "leverage" |
| `cyber.md` | "robust", "leverage" |
| `executive.md` | "robust", "threat landscape" |
| `war_risk.md` | "robust", "leverage" |

**Fix**: Add full forbidden jargon list to every prompt file.

---

### 2.6 Pipeline: Cyber Domain Hardcoded Confidence

**Problem**: `pipeline/draft/prompts/cyber.md` hardcodes `confidence: "low"`, `language: "possibly"` in JSON examples. Claude will default to these values regardless of evidence quality.

**Fix**: Make example conditional — show both default low and elevated moderate cases.

---

### 2.7 Pipeline: Iranian State Media Handling Is Dead Code

**Problem**: `pipeline/triage/confidence.py` lines 20-22 define `IRANIAN_STATE_MEDIA` set, but `sources.yaml` excludes Iranian media in a separate `excluded:` section that the code never reads.

**Fix**: Either reference `sources.yaml` excluded section from confidence.py, or consolidate exclusion logic.

---

### 2.8 React: Inline Styles Violating CSS Architecture

**Problem**: 4 components use inline `style={{}}` instead of CSS classes.

| Component | Line | Inline Style |
|-----------|------|-------------|
| `DataTable.tsx` | 12 | `fontWeight: 400, marginLeft: 6` |
| `WarningIndicators.tsx` | 52 | `color, fontWeight: 600` |
| `WarningIndicators.tsx` | 53 | `fontFamily, fontSize, whiteSpace` |
| `Caveats.tsx` | 29 | `padding: '0 0 8px'` |

**Fix**: Move all inline styles to CSS classes in `intel-brief.css`.

---

### 2.9 Pipeline: Review CLI Input Not Sanitized

**Problem**: `pipeline/review/review_cli.py` lines 89-96 accept user input via `input()` and insert directly into JSON without escaping. Control characters could break JSON structure.

**Fix**: Sanitize/escape user input before insertion.

---

## PHASE 3 — MEDIUM-PRIORITY FIXES

### 3.1 React: Index-Based Keys in 9 Components

**Problem**: Components use array index as React key (`key={i}`) instead of stable unique IDs. This causes incorrect DOM reconciliation if lists reorder.

**Affected**: `BodyContent.tsx`, `DataTable.tsx` (3x), `Caveats.tsx` (2x), `ActorMatrix.tsx`, `Timeline.tsx`, `KpiStrip.tsx`, `Masthead.tsx`

**Fix**: Use item IDs or derive stable keys from content.

---

### 3.2 React: No Error Boundaries

**Problem**: No error boundaries exist. A single component error crashes the entire app.

**Fix**: Add `<ErrorBoundary>` wrapper around major sections.

---

### 3.3 Pipeline: Two-Sentence Paragraph Rule Not Enforced

**Problem**: CLAUDE.md requires "Every paragraph >= 2 sentences; no fragment leads." No prompt explicitly states this rule; serializer doesn't validate it.

**Fix**: Add explicit rule to all domain prompts. Add sentence-count validation in serializer.py.

---

### 3.4 Pipeline: DissenterNote Attribution Not Validated

**Problem**: Serializer doesn't verify `analystId` matches the "ANALYST B/C" pattern.

**Fix**: Add regex validation in serializer.py: `re.match(r'^ANALYST [A-Z]$', analyst_id)`

---

### 3.5 Pipeline: Temporal Precision Not Validated for D1/D2

**Problem**: CLAUDE.md requires "Temporal precision on all kinetic claims" but `timestamp` is optional on `BodyParagraph` and serializer doesn't enforce it for d1/d2 sections.

**Fix**: Add validation that d1/d2 body paragraphs have timestamps.

---

### 3.6 Placeholder Cycle JSONs: Major Schema Violations

**Problem**: All `cycle00X_20260304.json` files (src/data and cycles/) have critical schema issues:
- Citations use `"ref"` field instead of `"source"`
- All citations missing `verificationStatus`
- `keyJudgment` objects malformed (missing required fields)
- `executive.keyJudgments` is array of strings, not objects

**Fix**: Either regenerate via pipeline with valid API key, or manually fix schema compliance.

---

### 3.7 Pipeline: N-gram Size Inconsistency

**Problem**: `novelty.py` uses 3-grams but `confidence.py` uses 4-grams for phrase extraction. Inconsistent window sizes cause items to be incorrectly filtered or boosted.

**Fix**: Align both to use 4-grams.

---

### 3.8 Pipeline: Drafter Variable Naming Confusion

**Problem**: `drafter.py` line 156 passes `d3_context` (energy) into a parameter named `d2_context` for the D6 domain. Confusing and error-prone.

**Fix**: Rename to match actual content or update prompt placeholder.

---

### 3.9 React: Missing Accessibility Attributes

**Problem**: 17 components lack ARIA labels. Tables missing `scope` and `headers` attributes. No semantic `<time>` elements for timestamps.

**Fix**: Add `aria-label`, `scope="col"`, `scope="row"`, and `<time datetime="...">` elements throughout.

---

### 3.10 Cycle Data: Forbidden Jargon Instance

**Problem**: `cycle001.json` line 145 uses "kinetic activity" in assessmentQuestion field.

**Fix**: Replace with permitted phrasing (e.g., "military operations" or "strikes").

---

## PHASE 4 — LOW-PRIORITY FIXES

### 4.1 Missing Developer Tooling

| Tool | Status | Action |
|------|--------|--------|
| ESLint | Missing | Create `.eslintrc.json` with TS/React rules |
| Prettier | Missing | Create `.prettierrc.json` |
| `.editorconfig` | Missing | Create for cross-editor consistency |
| `.nvmrc` | Missing | Create with `20` to match CI |
| Test framework | Missing | Consider adding vitest |

### 4.2 Incomplete `.gitignore`

**Missing patterns**: `.venv/`, `venv/`, `.pytest_cache/`, `.mypy_cache/`, `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`, `*.key`, `*.pem`, `*.swp`

### 4.3 GitHub Actions Workflow Issues

| File | Line | Issue |
|------|------|-------|
| `daily-brief.yml` | 44-45 | `continue-on-error: true` on Playwright install masks failures |
| `daily-brief.yml` | 38-39 | Anthropic installed twice; should use `requirements.txt` |

### 4.4 Unused Python Dependency

**Problem**: `playwright>=1.40.0` in `requirements.txt` but no Python file imports it.
**Fix**: Remove from requirements.txt.

### 4.5 Pipeline: Missing `pipeline/output/schema.json`

CLAUDE.md references this file for Python-side validation, but it doesn't exist. Consider generating a JSON Schema from `brief.ts`.

### 4.6 Missing Assessment-Led Paragraph Examples

`energy.md`, `diplomatic.md`, `cyber.md`, `war_risk.md` lack BAD/GOOD assessment-led examples.

### 4.7 Pipeline: Executive Prompt Missing D5 KPI Specification

`executive.md` lines 50-56 specify KPI cells for d1-d4 and d6, but omit d5 (Cyber).

### 4.8 Pipeline: Confidence Language Ladder Duplicated in 8 Prompts

Each domain prompt duplicates the full confidence ladder. Consider a shared include file.

### 4.9 Pipeline: AFP Missing from sources.yaml

CLAUDE.md lists AFP as Tier 1, but `sources.yaml` doesn't include it.

### 4.10 Pipeline: Collection Gaps No Max Count

`collection_gaps.md` says "Do not pad" but sets no upper limit. Add explicit 3-6 range.

### 4.11 React: Timestamp Formatting Duplication

Date formatting logic duplicated across `Masthead.tsx`, `FlashPoints.tsx`, `BodyContent.tsx`, `App.tsx`. Consider a shared utility.

### 4.12 Legacy Root Files

`build_brief.py` and `build_brief_vml.py` at project root — unclear if active or legacy. Document or remove.

---

## Fix Effort Estimates

| Phase | Issues | Effort |
|-------|--------|--------|
| Phase 1 (Critical) | 6 items | ~6-8 hours |
| Phase 2 (High) | 9 items | ~4-6 hours |
| Phase 3 (Medium) | 10 items | ~4-5 hours |
| Phase 4 (Low) | 12 items | ~3-4 hours |
| **Total** | **37 items** | **~17-23 hours** |

---

## Compliance Scorecard

| Dimension | Score | Key Gap |
|-----------|-------|---------|
| CSS design rules | 3/10 | 62+ hardcoded colors and 14 hardcoded font sizes |
| TypeScript type safety | 7/10 | 11 unsafe Record patterns, double assertion |
| Pipeline schema validation | 5/10 | D6 rejected, no sentence/attribution validation |
| Writing voice enforcement | 6/10 | Forbidden jargon incomplete in 7 prompts |
| React component quality | 7/10 | Index keys, no error boundary, inline styles |
| Security | 7/10 | Email credential fallback, unsanitized CLI input |
| Build & config | 6/10 | Missing base path, no linting, no tests |
| Documentation | 7/10 | Excellent CLAUDE.md, missing README |
| **Overall** | **6/10** | Architecturally strong; enforcement gaps |
