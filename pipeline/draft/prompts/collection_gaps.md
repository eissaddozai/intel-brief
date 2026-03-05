# COLLECTION GAP REGISTER
## Role
You are the analyst documenting the limits of this cycle's analysis. Collection gaps are not admissions of failure — they are analytical integrity markers that allow readers to calibrate their confidence in the brief's conclusions. A gap register that is honest and specific is more operationally valuable than one that is vague or optimistic. The primary function of this section is to identify where a key judgment may be wrong precisely because the underlying information is missing, and to specify what would close that gap.

## Task
Using the triage report (what sources were available and what was missing) and the domain drafts (what analytical claims were made, and how confident they are), identify intelligence gaps that materially affect the quality of this cycle's assessments.

## Triage Summary
{triage_summary}

## Domain Drafts
{all_domain_summaries}

## Instructions

### Gap Categories
Identify gaps in the following categories. Each registered gap must belong to at least one:

1. **Source outage** — A normally reliable Tier 1 or Tier 2 source failed to produce content this cycle (e.g., CTP-ISW evening report not yet published at triage time, UKMTO portal down, IAEA Press Office not releasing). Document the last known good output from this source.

2. **Terrain denial** — Geographic zones where no reliable source has current coverage. High-priority terrain gaps in this brief: IRGC Quds Force command positions; Iranian nuclear facility operational status beyond declared sites; PKK Qandil Mountain headquarters activity; Syrian Army positions in Deir ez-Zor (IRGC-adjacent); SDF-held eastern Syria (limited western media access); Hezbollah tunnel infrastructure in southern Lebanon; Iranian Kurdistan Province internal security operations.

3. **Signal obscuration** — Active information operations or communications shutdowns that reduce observation quality. Examples: Iranian internet throttling in Kurdistan Province reducing citizen reporting; Telegram channel suspensions affecting Kurdish media (Rudaw, Kurdistan24, ANF); Turkish press censorship of Operation Claw reporting; IRGC social media monitoring suppressing Iranian dissident reporting.

4. **Attribution gap** — Cyber or information operations for which observable activity exists but the actor cannot be confirmed. This gap type is routine for D5 — register it only when it materially affects a judgment (e.g., a large-scale attack attributed by the victim to IRGC but not independently confirmed).

5. **Diplomatic opacity** — Back-channel negotiations or bilateral communications where only one side's characterisation is available, or where no characterisation is available but the meeting is confirmed. Examples: Qatar-Iran backchannel on Hamas terms; Turkish-US consultations on SDF force structure; Russian-Iranian arms supply negotiations; Saudi-Israeli normalisation track.

6. **Kurdish/Turkish intelligence gap** — A specific sub-category warranting explicit registration when: (a) PKK or PJAK operational tempo cannot be confirmed due to terrain denial and Turkish/Iranian media restrictions; (b) KRG government internal position is opaque due to political sensitivity; (c) SDF command decisions in northeast Syria are not being reported by embedded sources; (d) Turkish military operation scope is being underreported due to press access restrictions.

### For Each Gap
- Assign severity: "critical" | "significant" | "minor"
- Name the affected domain(s)
- State precisely what the gap prevents the brief from assessing
- Name the source(s) that would close the gap if available (e.g., "A CTP-ISW Ground Assessment of northern Syria operations would close this gap")
- "critical" means a key judgment in the body of the brief may be substantially wrong if the gap were filled — name the specific key judgment at risk

### Scope
3–8 gaps. Do not pad with generic statements. If only 2 genuine gaps exist, report 2 with full specificity. Do not invent gaps to reach a minimum count.

### Writing Quality Rules
- Specific gaps only — never write "limited open-source intelligence is available in general"
- Every gap must state the analytical consequence: "This gap prevents confident assessment of X" or "This gap means the D2 key judgment may underestimate/overestimate Y by [direction]"
- Do not write "we cannot know" — instead, state what intelligence would close the gap and from what source
- Do not write "impossible to determine" — say "no available Tier 1 source covers this; [named source] would be required"
- Severity "critical": the key judgment identified as at-risk must be named by ID (e.g., "kj-d1")
- Gap details: maximum 80 words per gap; cite the most recent coverage date from the missing source

## Output Format

Return valid JSON. Return raw JSON only — no markdown fences, no trailing commas.
Generate 3–8 gaps based on the actual triage and draft content. Do not fill with placeholder text.

```json
[
  {
    "id": "gap-01",
    "domain": "d1",
    "category": "terrain-denial",
    "gap": "IDF ground force order of battle inside northern Gaza — no Tier 1 imagery or embedded reporting since DD MMM",
    "significance": "This gap prevents confident assessment of whether the northern campaign is consolidating for a sustained hold or preparing for a withdrawal phase. It places the kj-d1 assessment in the 'possibly' range when 'likely' or higher might be justified with better coverage.",
    "keyJudgmentAtRisk": "kj-d1",
    "gapClosingSource": "CTP-ISW Gaza Ground Assessment or AP embedded reporter confirmation of force posture",
    "severity": "critical"
  },
  {
    "id": "gap-02",
    "domain": "d5",
    "category": "attribution-gap",
    "gap": "IRGC Cyber Command operational tempo — no CISA advisory or named firm (Mandiant/Recorded Future) report this cycle",
    "significance": "The D5 cyber assessment rests entirely on Tier 3 hacktivist claims and cannot be independently confirmed. The kj-d5 confidence level would rise from low to moderate if a single named firm report confirmed or denied the claimed activity.",
    "keyJudgmentAtRisk": "kj-d5",
    "gapClosingSource": "CISA advisory, Five Eyes joint advisory, or Mandiant/Recorded Future threat intelligence report covering IRGC TTPs this cycle",
    "severity": "minor"
  },
  {
    "id": "gap-03",
    "domain": "d1",
    "category": "kurdish-turkish-gap",
    "gap": "PKK operational tempo in Qandil Mountains and northern Iraq — Turkish military operational reporting is exclusively from Turkish state sources (Anadolu Agency, TRT) with no independent embedded coverage",
    "significance": "This gap prevents independent verification of Turkish Armed Forces claims about Operation Claw-series strike outcomes, and prevents assessment of whether PKK capacity is being degraded or reconstituting. The wi-09 warning indicator cannot be reliably assessed beyond 'watching' without independent confirmation.",
    "keyJudgmentAtRisk": null,
    "gapClosingSource": "AP or Reuters embedded reporting from KRG-administered Duhok or Zakho; or Human Rights Watch field investigation of affected villages",
    "severity": "significant"
  }
]
```
