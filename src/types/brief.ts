/* ═══════════════════════════════════════════════════════════════════════════
   CSE INTELLIGENCE BRIEF — TYPE SCHEMA
   Single source of truth for all data structures.
   The pipeline's Python schema.json is generated from this file.
   ═══════════════════════════════════════════════════════════════════════════ */

// ── PRIMITIVE ENUMERATIONS ──────────────────────────────────────────────────

export type DomainId =
  | 'd1'  // Battlespace · Kinetic
  | 'd2'  // Escalation · Trajectory
  | 'd3'  // Energy · Economic
  | 'd4'  // Diplomatic · Political
  | 'd5'  // Cyber · Information Operations
  | 'd6'  // War Risk Insurance · Maritime Finance

export type TLPLevel = 'RED' | 'AMBER' | 'GREEN' | 'CLEAR'

export type ThreatLevel = 'CRITICAL' | 'SEVERE' | 'ELEVATED' | 'GUARDED' | 'LOW'

export type ThreatTrajectory = 'escalating' | 'stable' | 'de-escalating'

export type ConfidenceTier = 'high' | 'moderate' | 'low'

/** DIA-standard confidence language. Maps to rendered phrases and probability ranges.
 *  Use these values in the `language` field — never write confidence language as free
 *  text in ad-hoc ways. Per writing-voice rules, prefer source-attributed leads in
 *  paragraph text; confidence phrases appear mid-sentence or after evidentiary basis. */
export type ConfidenceLanguage =
  | 'almost-certainly'     // 95–99% | "We assess with high confidence…"
  | 'highly-likely'        // 75–95% | "We judge it highly likely…"
  | 'likely'               // 55–75% | "Available evidence suggests…"
  | 'possibly'             // 45–55% | "Reporting indicates, though corroboration is limited…"
  | 'unlikely'             // 20–45% | "We judge it unlikely, though we cannot exclude…"
  | 'almost-certainly-not' // 1–5%   | "We assess with high confidence this will not…"

export type SourceTier = 1 | 2 | 3

export type VerificationStatus =
  | 'confirmed'   // Tier 1 source; directly cited
  | 'reported'    // Tier 2 source; cite as "reported"
  | 'claimed'     // Tier 3 / unverified; cite as "claims" or "asserts"
  | 'disputed'    // Actively contradicted by Tier 1 source

export type ChangeDirection = 'up' | 'down' | 'neutral'

/** Warning indicator change since previous cycle. */
export type WIChange =
  | 'new-triggered'   // indicator was at watching/clear and is now triggered
  | 'newly-elevated'  // indicator was at watching/clear and is now elevated
  | 'elevated'        // legacy alias — same as newly-elevated
  | 'new'             // legacy alias — same as new-triggered
  | 'unchanged'       // no status change from previous cycle
  | 'downgraded'      // status reduced (triggered→elevated, elevated→watching)
  | 'cleared'         // previously triggered/elevated; now cleared

// ── SOURCE CITATION ─────────────────────────────────────────────────────────

export interface Citation {
  /** Outlet name: "AP", "Reuters", "CTP-ISW Evening Report" — not a URL */
  source: string
  tier: SourceTier
  verificationStatus: VerificationStatus
  /** ISO 8601 — displayed as "0620 UTC 15 Mar" */
  timestamp?: string
  url?: string
}

// ── FLASH POINTS ────────────────────────────────────────────────────────────

export interface FlashPoint {
  id: string
  /** ISO 8601 — displayed as "0430 UTC" */
  timestamp: string
  domain: DomainId
  /** ≤ 12 words */
  headline: string
  /** 1–2 sentences, BLUF construction */
  detail: string
  confidence: ConfidenceTier
  citations: Citation[]
}

// ── KEY JUDGMENT ────────────────────────────────────────────────────────────

export interface KeyJudgment {
  id: string
  domain: DomainId
  confidence: ConfidenceTier
  /** e.g. "55–75%" */
  probabilityRange: string
  language: ConfidenceLanguage
  /**
   * Full assessment sentence(s). Writing-voice preference: lead with a named source
   * when one is available ("CTP-ISW confirms X; this indicates Y"), reserving
   * confidence phrases for mid-sentence placement after the evidentiary basis.
   * Confidence phrases are still correct openers when no Tier 1 source leads.
   */
  text: string
  /** Evidence basis — named source, timestamp, corroboration level */
  basis: string
  citations: Citation[]
}

// ── KPI CELL ────────────────────────────────────────────────────────────────

export interface KpiCell {
  domain: DomainId
  /** Displayed number: "14", "+3.2%", "$0.18/GRT" */
  number: string
  /** e.g. "STRIKES (24H)", "BRENT CRUDE (USD/bbl)" */
  label: string
  changeDirection?: ChangeDirection
}

// ── BODY PARAGRAPH ──────────────────────────────────────────────────────────

export interface BodyParagraph {
  /** If present, renders a sub-label row above this paragraph */
  subLabel?: string
  /** Controls sub-label colour: observed=dim, assessment=gold-dim */
  subLabelVariant?: 'observed' | 'assessment'
  text: string
  /** Displayed as monospace timestamp above paragraph: "As of 0600 UTC 15 Mar" */
  timestamp?: string
  citations: Citation[]
  confidenceLanguage?: ConfidenceLanguage
}

// ── DATA TABLE ──────────────────────────────────────────────────────────────

export interface TableRow {
  label: string
  values: string[]
  change?: ChangeDirection
  status?: 'critical' | 'elevated' | 'rising' | 'stable' | 'windfall'
}

export interface DataTable {
  caption: string
  headers: string[]
  rows: TableRow[]
  /** e.g. "USD/bbl", "USD/GRT/day" */
  unit?: string
}

// ── TIMELINE ────────────────────────────────────────────────────────────────

export interface TimelineEvent {
  /** ISO 8601 — displayed as "0230 UTC 15 Mar" */
  timestamp: string
  actor: string
  action: string
  confidence: ConfidenceTier
  domain: DomainId
  citations: Citation[]
}

// ── ACTOR MATRIX ────────────────────────────────────────────────────────────

export interface ActorMatrixRow {
  actor: string
  posture: string
  /**
   * Text description of change since previous cycle.
   * e.g. "unchanged", "hardening", "softening", "reversed", "newly-engaged"
   * Both `changeSincePrev` and `changeSincePrevCycle` are accepted in JSON
   * (the renderer reads `changeSincePrev` with fallback to `changeSincePrevCycle`).
   */
  changeSincePrev: string
  /** @deprecated Use changeSincePrev. Kept for backwards compat with existing cycle JSONs. */
  changeSincePrevCycle?: string
  assessment: string
  confidence: ConfidenceTier
  /** Optional lever/tool the actor wields (e.g. "Oil supply", "UNSC veto") */
  primaryLever?: string
}

// ── ANALYST NOTE ────────────────────────────────────────────────────────────

export interface AnalystNote {
  /** e.g. "ANALYTICAL NOTE — BATTLESPACE" */
  title: string
  /** e.g. "CYCLE 001 · 15 MARCH 2024" */
  cycleRef: string
  /** Explicit analytical reasoning. ≥ 2 sentences. */
  text: string
}

// ── DISSENTER NOTE ──────────────────────────────────────────────────────────

export interface DissenterNote {
  /** Anonymized: "ANALYST B", "ANALYST C" */
  analystId: string
  domain: DomainId
  /** Alternative analytical view with explicit reasoning. */
  text: string
}

// ── DOMAIN SECTION ──────────────────────────────────────────────────────────

export interface DomainSection {
  id: DomainId
  /** "01" through "06" */
  num: string
  /** e.g. "BATTLESPACE · KINETIC" */
  title: string
  /** The analytical question this section answers */
  assessmentQuestion: string
  confidence: ConfidenceTier
  keyJudgment: KeyJudgment
  bodyParagraphs: BodyParagraph[]
  tables?: DataTable[]
  timeline?: TimelineEvent[]
  actorMatrix?: ActorMatrixRow[]
  analystNote?: AnalystNote
  dissenterNote?: DissenterNote
}

// ── WARNING INDICATORS ──────────────────────────────────────────────────────

export interface WarningIndicator {
  id: string
  /** What we are watching for */
  indicator: string
  /** Primary domain — may be slash-separated for cross-domain indicators, e.g. "d1/d4" */
  domain: DomainId
  status: 'watching' | 'triggered' | 'elevated' | 'cleared'
  change: WIChange
  /** ≤ 100 words. Named source + timestamp. Explains why status was or was not triggered. */
  detail: string
}

// ── COLLECTION GAP ──────────────────────────────────────────────────────────

export type CollectionGapCategory =
  | 'source-outage'
  | 'terrain-denial'
  | 'signal-obscuration'
  | 'attribution-gap'
  | 'diplomatic-opacity'
  | 'kurdish-turkish-gap'

export interface CollectionGap {
  id: string
  domain: DomainId
  /** Gap category for triage and routing */
  category?: CollectionGapCategory
  /** What we don't know */
  gap: string
  /** Why it matters — which assessment is undermined and how */
  significance: string
  severity: 'critical' | 'significant' | 'minor'
  /** ID of the key judgment most at risk if this gap were filled, e.g. "kj-d1" */
  keyJudgmentAtRisk?: string | null
  /** Named source or source type that would close this gap */
  gapClosingSource?: string
}

// ── FULL BRIEF CYCLE ────────────────────────────────────────────────────────

export interface BriefCycle {
  meta: {
    /** e.g. "CSE-BRIEF-001-20240315" */
    cycleId: string
    /** e.g. "001" */
    cycleNum: string
    /** e.g. "PROTECTED B" */
    classification: string
    tlp: TLPLevel
    /** ISO 8601 — displayed as "0600 UTC · 15 MARCH 2024" */
    timestamp: string
    /** e.g. "Iran / Gulf Region / Eastern Mediterranean" */
    region: string
    /** e.g. "CSE Conflict Assessment Unit" */
    analystUnit: string
    threatLevel: ThreatLevel
    threatTrajectory: ThreatTrajectory
    subtitle: string
    /** Single-sentence framing note below distribution bar */
    contextNote: string
    /** Status strip cells — first is alert level, remainder are domain KPIs */
    stripCells: { top: string; bot: string }[]
  }

  strategicHeader: {
    /** The single most important analytical sentence this cycle */
    headlineJudgment: string
    /** 3–5 sentence explanation: primary evidence → key variable → tripwire → delta from prior */
    trajectoryRationale: string
  }

  /** ≤ 3 urgent items — component hides this section if array is empty */
  flashPoints: FlashPoint[]

  executive: {
    /** 2–4 sentences, bottom line up front, source-attributed first sentence */
    bluf: string
    /** 5–6 confidence-rated cross-domain assessments */
    keyJudgments: KeyJudgment[]
    /** 6 domain-coloured numbers (d1–d6); use null/"—" for absent domains */
    kpis: KpiCell[]
  }

  /** Domain sections — conditional on available intelligence, not always all 6 */
  domains: DomainSection[]

  warningIndicators: WarningIndicator[]

  collectionGaps: CollectionGap[]

  caveats: {
    cycleRef: string
    items: { label: string; text: string }[]
    confidenceAssessment: string
    dissenterNotes: DissenterNote[]
    sourceQuality: string
    handling: string
  }

  footer: {
    id: string
    classification: string
    sources: string
    handling: string
  }
}

// ── CONFIDENCE LANGUAGE MAP ─────────────────────────────────────────────────
// Used by components to render the correct phrase from the enum value.

export const CONFIDENCE_PHRASES: Record<ConfidenceLanguage, { phrase: string; range: string }> = {
  'almost-certainly':     { phrase: 'We assess with high confidence',                                   range: '95–99%' },
  'highly-likely':        { phrase: 'We judge it highly likely',                                        range: '75–95%' },
  'likely':               { phrase: 'Available evidence suggests',                                      range: '55–75%' },
  'possibly':             { phrase: 'Reporting indicates, though corroboration is limited',              range: '45–55%' },
  'unlikely':             { phrase: 'We judge it unlikely, though we cannot exclude',                   range: '20–45%' },
  'almost-certainly-not': { phrase: 'We assess with high confidence this will not',                     range: '1–5%'   },
}

export const TRAJECTORY_LABELS: Record<ThreatTrajectory, string> = {
  'escalating':    '↑ ESCALATING',
  'stable':        '→ STABLE',
  'de-escalating': '↓ DE-ESCALATING',
}

export const DOMAIN_LABELS: Record<DomainId, string> = {
  d1: 'BATTLESPACE',
  d2: 'ESCALATION',
  d3: 'ENERGY',
  d4: 'DIPLOMATIC',
  d5: 'CYBER · IO',
  d6: 'WAR RISK · INSURANCE',
}

/** Human-readable WI change labels for display. */
export const WI_CHANGE_LABELS: Partial<Record<WIChange, string>> = {
  'new-triggered':  '⚡ NEW — TRIGGERED',
  'newly-elevated': '↑ NEWLY ELEVATED',
  'elevated':       '↑ ELEVATED',
  'new':            '⚡ NEW',
  'unchanged':      '→ UNCHANGED',
  'downgraded':     '↓ DOWNGRADED',
  'cleared':        '✓ CLEARED',
}
