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
 *  Always use these values — never write confidence language as free text. */
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
  /** Full assessment sentence(s). Must begin with a confidence phrase. */
  text: string
  /** Evidence basis: "(satellite imagery, diplomatic reporting, 14 Mar)" */
  basis: string
  citations: Citation[]
}

// ── KPI CELL ────────────────────────────────────────────────────────────────

export interface KpiCell {
  domain: DomainId
  /** Displayed number: "14", "+3.2%", "↑ HIGH" */
  number: string
  /** e.g. "INCIDENT COUNT", "BRENT ΔΔ 24H" */
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
  /** e.g. "USD/bbl", "USD bn" */
  unit?: string
}

// ── TIMELINE ────────────────────────────────────────────────────────────────

export interface TimelineEvent {
  /** Displayed: "0230 UTC" */
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
  changeSincePrevCycle: string
  assessment: string
  confidence: ConfidenceTier
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
  domain: DomainId
  status: 'watching' | 'triggered' | 'cleared' | 'elevated'
  change: 'new' | 'elevated' | 'unchanged' | 'cleared'
  detail: string
}

// ── COLLECTION GAP ──────────────────────────────────────────────────────────

export interface CollectionGap {
  id: string
  domain: DomainId
  /** What we don't know */
  gap: string
  /** Why it matters for assessment quality */
  significance: string
  severity: 'critical' | 'significant' | 'minor'
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
    /** 6 cells for status strip: first cell is alert level, rest are domain KPIs */
    stripCells: { top: string; bot: string }[]
  }

  strategicHeader: {
    /** The single most important analytical sentence this cycle */
    headlineJudgment: string
    trajectoryRationale: string
  }

  /** ≤ 3 urgent items — component hides this section if array is empty */
  flashPoints: FlashPoint[]

  executive: {
    /** 2–4 sentences, bottom line up front */
    bluf: string
    /** 4–6 confidence-rated assessments */
    keyJudgments: KeyJudgment[]
    /** 5 domain-coloured numbers */
    kpis: KpiCell[]
  }

  /** 6 domain sections in order: d1, d2, d3, d4, d5, d6 */
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
