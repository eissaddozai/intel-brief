#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# auto_cycle.sh — Automated multi-pass intelligence brief cycle
#
# Runs the full pipeline 2–3 times through Claude Code CLI:
#   Pass 1: Full workflow (ingest → triage → draft → publish)
#   Pass 2: Quality review + targeted redraft of weak sections
#   Pass 3: Final polish — voice/style sweep + export + commit
#
# Usage:
#   bash scripts/auto_cycle.sh              # 3 passes (default)
#   bash scripts/auto_cycle.sh 2            # 2 passes only
#   bash scripts/auto_cycle.sh 3 2025-03-15 # 3 passes, specific date
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

PASSES="${1:-3}"
TARGET_DATE="${2:-$(date -u +%Y-%m-%d)}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_ROOT/scratch/auto_cycle_logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/cycle_${TIMESTAMP}.log"

# ── Colours ──
RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
BLUE='\033[0;34m'
DIM='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${DIM}[$(date -u +%H:%M:%S)]${NC} $*" | tee -a "$LOG_FILE"; }
pass_header() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
  echo -e "${BOLD}  PASS $1 / $PASSES — $2${NC}" | tee -a "$LOG_FILE"
  echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
}

# ── Claude CLI runner ──
run_claude() {
  local prompt="$1"
  local label="$2"
  local pass_log="$LOG_DIR/${label}_${TIMESTAMP}.log"

  log "${BLUE}Starting: ${label}${NC}"

  claude -p \
    --dangerously-skip-permissions \
    --allowedTools "Bash Edit Write Read Glob Grep Skill Agent" \
    "$prompt" \
    2>&1 | tee "$pass_log"

  local exit_code=${PIPESTATUS[0]}

  if [ $exit_code -ne 0 ]; then
    log "${RED}WARN: ${label} exited with code ${exit_code} — continuing${NC}"
  else
    log "${GREEN}Done: ${label}${NC}"
  fi

  return 0  # Never abort the cycle
}

# ═══════════════════════════════════════════════════════════════════════════
# PASS 1: FULL WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════
pass_header 1 "FULL PIPELINE — INGEST → TRIAGE → DRAFT → PUBLISH"

PASS1_PROMPT="$(cat <<'PROMPT'
Execute /workflow for today's date. Run the complete pipeline:

1. /intel-ingest — fetch all sources
2. /intel-triage — parse, classify, assign confidence
3. /intel-draft — draft the full BriefCycle JSON following ALL rules in CLAUDE.md
4. /intel-publish — sync to src/data, build

Do not stop for confirmation. If any phase has errors, log them and continue.
Every fact must trace to a fetched source. No fabrication.
Save the brief to briefs/ with the standard filename format.
PROMPT
)"

run_claude "$PASS1_PROMPT" "pass1_workflow"

# Find the brief that was just created
LATEST_BRIEF=$(ls -t "$REPO_ROOT/briefs/CSE_Intel_Brief_"*.json 2>/dev/null | head -1)

if [ -z "$LATEST_BRIEF" ]; then
  log "${RED}ERROR: No brief produced in pass 1. Aborting.${NC}"
  exit 1
fi

BRIEF_NAME=$(basename "$LATEST_BRIEF")
log "${GREEN}Pass 1 produced: ${BRIEF_NAME}${NC}"

# ═══════════════════════════════════════════════════════════════════════════
# PASS 2: QUALITY REVIEW + TARGETED REDRAFT
# ═══════════════════════════════════════════════════════════════════════════
if [ "$PASSES" -ge 2 ]; then

pass_header 2 "QUALITY REVIEW + TARGETED REDRAFT"

PASS2_PROMPT="$(cat <<PROMPT
You are a senior intelligence editor reviewing the latest brief for quality.

Read the brief at: briefs/${BRIEF_NAME}
Read CLAUDE.md for all voice, style, and structural rules.
Read each prompt template in pipeline/draft/prompts/ for domain-specific requirements.

Perform this quality audit — check EVERY item:

## VOICE CHECKS
1. Grep the brief JSON for forbidden phrases: "kinetic activity", "threat actors",
   "threat landscape", "robust", "leverage", "we assess", "we judge", "we evaluate",
   "our assessment", "diplomatic efforts", "international community", "stakeholders",
   "going forward", "ongoing situation", "it should be noted", "importantly",
   "significantly", "notably", "complex situation", "paradigm shift", "game changer"
2. Check every lead sentence — must be an analytical judgment, NOT a bare description.
   BAD: "Three BTGs were observed..." GOOD: "Offensive preparations appear underway..."
3. Check every hedged judgment has a "because" clause with evidence.
   BAD: "Escalation is likely." GOOD: "Escalation is likely, given IRGC repositioning (Reuters, 15 Mar)."
4. Check confidence language — only the 6 enum values are allowed, no ad-hoc hedging.
5. Check sentence discipline: noun+verb in first 6 words, 12-20 words average.

## STRUCTURAL CHECKS
6. Verify all 6 domains (d1–d6) are present with keyJudgment, bodyParagraphs, citations.
7. Verify warningIndicators has all 8 tripwires with status values.
8. Verify every citation has source (outlet name), tier, verificationStatus, timestamp.
9. Verify Iranian sources are marked "claimed" with "Iranian government asserts..." framing.
10. Verify collectionGaps matches actual data gaps from the triage phase.

## ANALYTICAL CHECKS
11. Check key judgments are genuine cross-domain synthesis, not just domain summaries.
12. Check the BLUF is judgment-first (not a summary of what the brief covers).
13. Check strategic header headline is exactly one sentence of strategic assessment.
14. Check flash points are Tier 1 only (or multi-Tier-2 corroborated).

For EVERY issue found:
- Fix it directly in the JSON file at briefs/${BRIEF_NAME}
- Also update the copy in src/data/ if it exists there

After all fixes, run:
  python scripts/export_brief.py briefs/${BRIEF_NAME}
  python scripts/sync_briefs.py
  npm run build

Report a summary of what you fixed.
PROMPT
)"

run_claude "$PASS2_PROMPT" "pass2_review"

log "${GREEN}Pass 2 complete — quality review and targeted fixes applied${NC}"

fi

# ═══════════════════════════════════════════════════════════════════════════
# PASS 3: FINAL POLISH + COMMIT
# ═══════════════════════════════════════════════════════════════════════════
if [ "$PASSES" -ge 3 ]; then

pass_header 3 "FINAL POLISH + EXPORT + COMMIT + PUSH"

PASS3_PROMPT="$(cat <<PROMPT
Final quality pass on the brief at: briefs/${BRIEF_NAME}

Read the brief. This is the LAST chance to catch issues before publication.

## POLISH TASKS

1. **Sentence-level edit**: Read every text field in the JSON. For each sentence:
   - Cut "it is", "there is", "there are" (sentence stretchers)
   - Replace nominalizations: "conduct an inspection" → "inspect", "make a decision" → "decide"
   - Ensure noun+verb appears within first 6 words
   - Target 12–20 words per sentence, averaging ~15
   - Limit 3+ syllable words to ~15% of total

2. **Temporal precision**: Every claim must have a UTC timestamp.
   Check for vague time references ("recently", "in recent days") and replace with
   specific timestamps from the source citations.

3. **Source attribution**: Every factual claim needs parenthetical citation at sentence end.
   Format: "(AP, 15 Mar 0620 UTC)" — outlet name + date + time.

4. **Cross-domain coherence**: Read the executive BLUF, then each domain.
   Ensure the BLUF reflects what the domains actually say. Fix any contradictions.

5. **Warning indicators consistency**: Each indicator's status must match the evidence
   in the corresponding domain section.

## EXPORT + PUBLISH

After all edits:

  python scripts/export_brief.py briefs/${BRIEF_NAME}
  python scripts/sync_briefs.py
  npm run build

## COMMIT + PUSH

Stage and commit all changes:

  git add briefs/ src/data/
  git commit -m "cycle: ${TARGET_DATE} — automated brief (3-pass)"
  git push origin main || (git pull origin main --rebase && git push origin main)

Report the final brief filename and a 3-line quality summary.
PROMPT
)"

run_claude "$PASS3_PROMPT" "pass3_polish"

log "${GREEN}Pass 3 complete — final polish, export, commit, push${NC}"

fi

# ═══════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  CYCLE COMPLETE — ${PASSES} passes${NC}"
echo -e "${DIM}  Brief: ${BRIEF_NAME}${NC}"
echo -e "${DIM}  Logs:  ${LOG_DIR}/${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
