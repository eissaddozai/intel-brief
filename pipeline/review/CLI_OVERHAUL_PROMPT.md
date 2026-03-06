# COMPREHENSIVE OVERHAUL: CLI OPERATIONAL FLOW

## Context

You are working on the CSE Intelligence Brief pipeline — an automated daily conflict intelligence brief for the Iran War File. The pipeline has five stages: **Ingest → Triage → Draft → Review → Output**. The CLI entry point is `pipeline/main.py`, which exposes four subcommands (`run`, `check-sources`, `show`, `list`) and orchestrates the full pipeline. The interactive human review step lives in `pipeline/review/review_cli.py`. The serializer that validates and writes the final cycle JSON lives in `pipeline/output/serializer.py`. The drafter that calls the Claude API lives in `pipeline/draft/drafter.py`. Quality checks that catch writing violations live in `pipeline/draft/quality_checks.py`.

The pipeline currently works but operates with a flat, brittle, and operationally immature CLI flow. The review CLI is a minimal read-approve loop with no ability to navigate backward, compare against the previous cycle, edit body paragraphs, fix quality violations inline, or batch-operate on warnings. The main CLI lacks progress reporting, stage timing, resumability, and operational diagnostics. The `show` command is a basic dump with no filtering, diffing, or export capability. There is no `diff` command to compare two cycles. There is no `validate` command to run quality checks on an existing cycle without re-drafting. Error recovery is primitive — a crash mid-pipeline loses all progress and requires a full restart.

Your task is to perform a comprehensive, forceful overhaul of the entire CLI operational flow — `pipeline/main.py`, `pipeline/review/review_cli.py`, and any supporting modules that need to change — to bring it to production-grade operational quality. This is not a cosmetic polish. This is a structural rebuild of how the analyst interacts with the pipeline, how errors are surfaced and recovered, and how the operational tempo of daily brief production is supported.

---

## PART 1: MAIN CLI (`pipeline/main.py`) — OPERATIONAL HARDENING

### 1.1 Progress Reporting and Stage Timing

The current pipeline runs stages sequentially with `log.info()` calls that disappear into a scrolling terminal. An analyst running the pipeline at 0500 UTC before a ministerial briefing needs to know: which stage is running, how long it has taken, how long remains, and whether anything has gone wrong.

**Requirements:**

- Add a persistent status line at the bottom of the terminal showing: `[STAGE 3/5: DRAFT] d2/d6 — 47s elapsed — 2 quality warnings`. Update this line in-place using `\r` or ANSI cursor movement. Do not scroll it off the screen with log output.
- Print a stage-transition banner when each stage begins: `═══ STAGE 2: TRIAGE ═══ (14 items from ingest)`. Include the input size (item count) so the analyst knows what the stage is working with.
- At pipeline completion, print a timing summary table: each stage name, elapsed time, items in/out, and quality warning count. Example:

```
╔══════════════════════════════════════════════════════════════╗
║ PIPELINE COMPLETE — cycle006_20260306                       ║
╠══════════════╤════════╤═══════════╤═══════════╤═════════════╣
║ Stage        │ Time   │ Items In  │ Items Out │ Warnings    ║
╠══════════════╪════════╪═══════════╪═══════════╪═════════════╣
║ Ingest       │  12.3s │ —         │ 47        │ 2 (T1 fail) ║
║ Triage       │   1.1s │ 47        │ 38        │ 1 (thin d5) ║
║ Draft        │  94.7s │ 38        │ 6 domains │ 8 quality   ║
║ Review       │  7m32s │ 6 domains │ 6 approved│ 0           ║
║ Output       │   0.4s │ approved  │ cycle006  │ 0           ║
╠══════════════╧════════╧═══════════╧═══════════╧═════════════╣
║ Total: 9m21s  ·  Hard fails: 0  ·  Advisories: 11          ║
╚══════════════════════════════════════════════════════════════╝
```

### 1.2 Resumability and Crash Recovery

The current pipeline has no resumability. If the Claude API times out on domain d4 after successfully drafting d1–d3 (each costing ~$0.15 in API calls), the analyst must restart from scratch or manually invoke `--stage draft` and lose all d1–d3 results.

**Requirements:**

- Implement a checkpoint system. After each domain is drafted, write it to a partial checkpoint file: `.cache/checkpoint_YYYYMMDD.json`. Structure: `{"completed_domains": ["d1", "d2", "d3"], "sections": {...}, "timestamp": "..."}`.
- On `--stage draft` or full run, check for an existing checkpoint. If found, print: `Checkpoint found: d1, d2, d3 already drafted (94.7s ago). Resume? [Y/n]`. If yes, skip completed domains and continue from d4.
- Add a `--no-resume` flag to force a clean start (discarding checkpoint).
- Add a `--resume` flag to auto-accept checkpoint without prompting.
- On successful draft completion, delete the checkpoint file (it's no longer needed).

### 1.3 New Subcommand: `validate`

There is currently no way to run quality checks on an existing cycle JSON without re-drafting it. An analyst who hand-edits a cycle file (fixing a typo, adjusting a confidence rating) has no way to verify they haven't introduced a forbidden phrase or broken a word limit.

**Requirements:**

- Add `python pipeline/main.py validate [path]` subcommand.
- If no path given, validate the latest cycle (`cycles/latest.json`).
- Run both structural validation (`serializer.validate()`) and content quality checks (`quality_checks.validate_cycle()`).
- Print results grouped by domain, with hard fails in red and advisories in amber.
- Print a summary line: `PASS: 0 hard fails, 7 advisories` or `FAIL: 3 hard fails — cycle would be blocked by serializer`.
- Exit code 0 if no hard fails, exit code 1 if any hard fails. This enables CI integration: `python pipeline/main.py validate && echo "OK"`.

### 1.4 New Subcommand: `diff`

Analysts need to compare the current cycle against the previous one to understand what changed — which domains shifted confidence, which warning indicators changed status, whether the threat trajectory moved.

**Requirements:**

- Add `python pipeline/main.py diff [cycle_a] [cycle_b]` subcommand.
- If only one argument, diff it against the previous cycle (by cycle number).
- If no arguments, diff latest against its predecessor.
- Output a structured diff showing:
  - **Threat level / trajectory change**: `ELEVATED → SEVERE (↑)`, `stable → escalating (↑)`
  - **Domain confidence changes**: `d1: moderate → high (↑)`, `d3: high → high (→)`
  - **Warning indicator status changes**: `wi-03: watching → triggered (★ NEW)`
  - **KPI delta**: `BRENT: $91.80 → $94.20 (+$2.40)`
  - **Key judgment text diff**: Show the previous and current KJ text side-by-side for each domain where it changed. Use red/green colouring for removed/added text.
  - **New/removed collection gaps**: List any gaps that appeared or were resolved.
- Keep the output concise — this is a delta summary, not a full dump. Target: fits on one screen (40 lines).

### 1.5 Enhanced `show` Command

The current `show` command dumps every domain section to the terminal with no filtering, no pagination, and no way to focus on a single domain.

**Requirements:**

- Add `--domain d3` flag to show only one domain section.
- Add `--section executive|strategic|indicators|gaps|caveats` to show only that section.
- Add `--json` flag to output raw JSON (for piping to `jq`).
- Add `--export html` to render the cycle as a standalone HTML file (using the same CSS tokens from `src/styles/tokens.css` inlined). This enables sharing a brief with someone who doesn't have the dev server running.
- Add word counts and quality warnings inline when displaying domain sections (reuse the `_display_word_counts` logic from review_cli).

### 1.6 Enhanced `check-sources` Command

**Requirements:**

- Add `--domain d3` flag to check only sources tagged to a specific domain.
- Add `--tier 1` flag to check only Tier 1 sources (the ones that matter most).
- Add `--fix` flag that, when a source returns 404, searches for the correct URL using a web search and suggests an update to `sources.yaml`.
- Add a freshness check: for RSS sources, report the timestamp of the most recent item in the feed. If it's older than 48 hours, flag as `STALE`.

### 1.7 Operational Ergonomics

- Add `--quiet` flag to suppress all output except errors and the final output path. For CI/cron use.
- Add `--verbose` flag to show full debug logging (API request/response sizes, triage scores, novelty scores per item).
- Add `--dry-run` flag for the `run` command that executes ingest and triage but prints what the draft stage WOULD do (domains, item counts, context sources) without calling the Claude API. This lets the analyst verify source coverage before spending API credits.
- Default to coloured output when stdout is a TTY; disable colour when piped. The current `_USE_COLOUR` check exists but is not consistently applied.

---

## PART 2: REVIEW CLI (`pipeline/review/review_cli.py`) — INTERACTIVE OVERHAUL

The review CLI is the most critical human touchpoint in the entire pipeline. An analyst spends 7–12 minutes here every morning. The current implementation is a forward-only read-approve loop with no ability to navigate backward, compare against the previous cycle, edit anything except the key judgment text, or fix quality warnings inline. This is operationally unacceptable for daily production use.

### 2.1 Navigation and Session State

**Requirements:**

- Replace the current forward-only flow with a **section navigator**. After the initial quality warning summary, present a navigation menu:

```
╔══ REVIEW SESSION ══════════════════════════════════════════╗
║  [H] Strategic Header     SEVERE · ESCALATING             ║
║  [1] D1 Battlespace       ✓ approved                      ║
║  [2] D2 Escalation        △ 2 advisories                  ║
║  [3] D3 Energy            ✗ 1 HARD FAIL                   ║
║  [4] D4 Diplomatic        · pending                       ║
║  [5] D5 Cyber             · pending                       ║
║  [6] D6 War Risk          · pending                       ║
║  [E] Executive            · pending                       ║
║  [W] Warning Indicators   2 triggered · 1 elevated        ║
║  [G] Collection Gaps      1 critical · 2 significant      ║
║  [Q] Quality Summary      3 hard · 8 advisory             ║
║  ──────────────────────────────────────────────────────────║
║  [F] Finalize (approve all pending as-is)                 ║
║  [X] Abort                                                ║
╚════════════════════════════════════════════════════════════╝
```

- The analyst can jump to any section in any order. Status badges update in real-time (approved / pending / hard fail / advisories).
- After reviewing a section, return to the navigator — not to the next section. The analyst controls the flow.
- Sections with hard fails should be visually prominent (red, blinking if terminal supports it).
- `[F] Finalize` approves all still-pending sections as-is and proceeds to output. But it MUST warn if any hard fails remain: `⚠ 1 HARD FAIL in D3 — serializer will reject. Fix before finalizing.`

### 2.2 Previous Cycle Comparison (Delta View)

The analyst needs to see what changed from the previous cycle while reviewing. Currently, the review CLI shows only the current draft with no context about what the previous cycle said.

**Requirements:**

- Load the previous cycle (from `cycles/latest.json`) at review start.
- For each domain section, show a **delta strip** above the key judgment:

```
┌─ DELTA vs CYCLE 005 ──────────────────────────────────────┐
│ Confidence: moderate → high (↑)                           │
│ KJ changed: YES                                           │
│ Body words: 142 → 178 (+36)                               │
│ Citations: 4 → 6 (+2)                                     │
│ Prev KJ: "Available evidence suggests the Bekaa           │
│   Valley strikes represent calibrated escalation..."      │
└───────────────────────────────────────────────────────────┘
```

- For warning indicators, show the previous status alongside the current: `[WATCHING → TRIGGERED] ★ NEW`.
- For the executive BLUF, show the previous BLUF in dim text below the current one, so the analyst can see how the assessment evolved.

### 2.3 Inline Editing

The current review CLI only allows editing the key judgment text. Analysts frequently need to fix body paragraph text (correcting a source attribution, adjusting a confidence phrase, fixing a factual error caught during review). Currently, the only option is to edit the raw JSON file after the review — which bypasses the quality gate.

**Requirements:**

- Expand edit capabilities to cover: key judgment text, key judgment basis, body paragraph text (by paragraph number), BLUF text, headline judgment, trajectory rationale, warning indicator detail text, and collection gap descriptions.
- When editing, show the current text and a clear prompt. Accept multi-line input (Enter twice to finish, same pattern as current KJ edit).
- After any inline edit, **re-run quality checks on the edited field** and immediately surface any new warnings. Example: analyst edits a body paragraph and accidentally introduces "kinetic activity" → immediately show: `⚠ FORBIDDEN_JARGON: "kinetic activity" detected in edited text. Fix before approving.`
- Add a `[V] View raw JSON` option for any section, for analysts who want to inspect the full data structure.

### 2.4 Batch Quality Fix Mode

When a draft comes back with 8+ quality warnings, stepping through each section and fixing them individually is tedious. The analyst needs a quality-focused review mode.

**Requirements:**

- Add `[Q] Quality Summary` to the navigator. This mode shows ALL quality warnings across the entire cycle, grouped by severity (hard fails first, then advisories), with the ability to jump directly to the offending section.
- For each warning, show: `[3] D3.bodyParagraphs[1] FORBIDDEN_JARGON: "kinetic activity" found`. Pressing `3` jumps to D3's review screen with the offending paragraph highlighted.
- After fixing a warning (via inline edit), the warning list should update immediately — don't force the analyst to return to quality summary to see if the fix worked.
- Track fix count: `Fixed 4/8 warnings this session. 4 remaining (0 hard fails).`

### 2.5 Quick Approve and Keyboard Shortcuts

**Requirements:**

- Add `[F] Finalize` — approve all remaining pending sections as-is without stepping through each one. Intended for cycles where the draft is clean (0 hard fails, few advisories) and the analyst trusts the quality gate.
- Add `[A] Approve all` within a domain section — approves the entire section without reading each paragraph. Shows a 1-line summary: `D3 ENERGY: 178 words, 6 citations, moderate confidence, 0 warnings. Approve? [Y/n]`
- Single-key navigation everywhere. No need to press Enter after single-character commands (if terminal supports raw input via `tty` / `curses`). Fall back to Enter-required input if raw mode is unavailable.
- Add `[P] Previous` to go back to the previously viewed section from the navigator.

### 2.6 Review Session Persistence

If the analyst's terminal crashes mid-review (SSH disconnect, power failure), all review progress is lost.

**Requirements:**

- Auto-save review state to `.cache/review_session_YYYYMMDD.json` after every section approval/edit.
- State includes: which sections are approved, which are edited, edit history, and the current modified draft dict.
- On review start, check for an existing session. If found: `Review session found (d1–d3 approved, d4 in progress). Resume? [Y/n]`.
- Add `--no-resume-review` flag to discard saved session and start fresh.

---

## PART 3: CROSS-CUTTING IMPROVEMENTS

### 3.1 Configuration Validation

The current `load_config()` silently returns `{}` on any error. This means a misconfigured `pipeline-config.yaml` (wrong IMAP host, missing API key reference) is not caught until the relevant stage fails mid-execution.

**Requirements:**

- Add a `_validate_config()` function called at startup (before any stage runs).
- Check: API key is set (or env var exists), IMAP credentials are present (if email ingest is enabled), output directory is writable, `sources.yaml` exists and parses.
- Print a config summary at startup: `Config: API=✓ IMAP=✗ (no credentials) Sources=47 enabled Output=cycles/`.
- If API key is missing and `--stage` is `draft` or full run: fail immediately with a clear message, not 90 seconds later when the draft stage tries to call Claude.

### 3.2 Logging Architecture

The current logging goes to stderr with timestamps. In production, the analyst needs both: a clean terminal experience (status lines, coloured output) AND a persistent log file for post-mortem analysis if something goes wrong.

**Requirements:**

- Add a file handler that writes to `.cache/pipeline_YYYYMMDD_HHMMSS.log` with full debug-level output (every API call, every triage score, every quality warning).
- Terminal output should show INFO and above, with colour.
- Log file should show DEBUG and above, no colour (strip ANSI codes).
- At pipeline completion, print: `Full log: .cache/pipeline_20260306_050012.log`.

### 3.3 Drafter Error Recovery

The current drafter has a binary outcome: success or complete failure. If the Claude API returns malformed JSON for one domain (which happens ~5% of the time), the entire draft stage fails.

**Requirements:**

- Implement per-domain retry: if `call_claude()` returns unparseable JSON, retry once with a shorter `max_tokens` and a prepended instruction: `Your previous response was not valid JSON. Return ONLY the JSON object, no markdown fences, no commentary.`
- If retry also fails, log the raw response to `.cache/failed_response_d3_YYYYMMDD.txt` for debugging, and continue drafting the remaining domains. Mark the failed domain as `_draft_failed: true` in the checkpoint.
- In the review CLI, show failed domains prominently: `D3 ENERGY — ✗ DRAFT FAILED (JSON parse error). [R]egenerate or [S]kip.`

### 3.4 The `--watch` Mode

For analysts who want to run the pipeline on a schedule (every 6 hours) without a cron job:

**Requirements:**

- Add `python pipeline/main.py run --watch --interval 6h` mode.
- Runs the full pipeline immediately, then sleeps for the interval, then runs again.
- On each cycle: send a terminal notification (`\a` bell) when review is ready.
- If `--auto-approve` is combined with `--watch`, the pipeline runs fully unattended and writes cycles on schedule.
- Print a countdown timer during the sleep period: `Next cycle in 5h42m. Press Ctrl+C to exit.`

---

## PART 4: IMPLEMENTATION PRIORITIES

If you cannot complete everything in a single pass, prioritize in this order:

1. **Review CLI navigator** (2.1) — the single highest-impact change for daily operational use
2. **Inline editing** (2.3) — eliminates the most common workflow friction
3. **Progress reporting** (1.1) — operational visibility
4. **Resumability** (1.2) — crash recovery for expensive API calls
5. **Validate command** (1.3) — enables CI integration and post-edit verification
6. **Diff command** (1.4) — analytical continuity between cycles
7. **Previous cycle comparison in review** (2.2) — context during review
8. **Quality fix mode** (2.4) — efficiency for high-warning-count drafts
9. **Review session persistence** (2.6) — crash recovery for review sessions
10. **Drafter error recovery** (3.3) — resilience against API failures
11. **Everything else** — operational polish

---

## CONSTRAINTS

- Do not break the existing `--auto-approve` and `--demo` flags. CI/CD pipelines depend on them.
- Do not change the cycle JSON schema (`src/types/brief.ts`). The front-end renders from this schema.
- Do not change the prompt files in `pipeline/draft/prompts/`. They were recently overhauled.
- Do not change `pipeline/draft/quality_checks.py`. It was recently overhauled.
- All new CLI features must degrade gracefully in non-TTY environments (piped output, CI runners). No crashes if `curses` is unavailable — fall back to simple `input()`.
- Preserve the `--stage` flag for running individual stages. The new features should integrate with, not replace, the existing stage-isolation capability.
- All terminal output uses ANSI colour codes with the existing `_USE_COLOUR` / TTY detection pattern. No external dependencies for terminal rendering (no `rich`, no `click`, no `blessed`). Use only stdlib (`curses`, `shutil.get_terminal_size`, `sys.stdout.isatty()`).
- The review CLI must remain usable over SSH with a basic VT100 terminal. No mouse input, no full-screen TUI. Keyboard-driven, line-based interaction with ANSI colour.

---

## DEFINITION OF DONE

The overhaul is complete when:

1. An analyst can run the full pipeline with live progress reporting and a timing summary at completion.
2. A crash mid-draft resumes from the last completed domain without re-calling the API.
3. The review CLI presents a navigator that allows non-linear section review with status badges.
4. The analyst can edit key judgments, body paragraphs, BLUF text, and warning indicator details inline — with immediate quality re-validation.
5. `python pipeline/main.py validate` runs quality checks on any existing cycle JSON and returns a clear pass/fail.
6. `python pipeline/main.py diff` shows a concise delta between two cycles.
7. All new features degrade gracefully in non-TTY environments.
8. No regressions in `--auto-approve --demo` mode.
