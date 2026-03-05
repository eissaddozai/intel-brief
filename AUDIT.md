# Codebase Audit — CSE Intel Brief Workflow
**Branch:** `claude/audit-workflow-codebase-wRuCu`
**Date:** 2026-03-05
**Scope:** All workflow files (`.github/workflows/`), orchestration (`pipeline/main.py`,
`pipeline/agent_brief.py`), serializer, renderer, and TypeScript schema.

Findings are grouped by severity. File:line references are included throughout.

---

## CRITICAL

### 1. Duplicate daily schedule — two workflows fire simultaneously
**Files:** `.github/workflows/daily-brief.yml:7` · `.github/workflows/agent-brief.yml:8`

Both workflows declare `cron: '0 6 * * *'` with **different** concurrency groups
(`daily-brief` vs `agent-brief`), so both run concurrently every morning. They both
write to `cycles/` and `briefs/`, and both run `git push origin main`. This causes:
- Race condition in cycle numbering (both scan `cycles/` independently)
- Two consecutive force-push conflicts on `main`
- Duplicate artifact uploads per run

`agent-brief.yml` appears to be the superseded standalone workflow; `daily-brief.yml`
is the unified replacement (with a `mode` input that defaults to `agent`). The
`agent-brief.yml` schedule trigger should be removed or the entire file deleted.

---

### 2. `cmd_show` uses wrong field names for warning indicators
**File:** `pipeline/main.py:688–690`

```python
level = w.get('level', '?')                        # field does not exist
c = red if level == 'RED' else (yellow if level == 'AMBER' else green)
print(f'  {c(level)} {w.get("indicator","?")} — {w.get("assessment","")}')
#                                                         ^^^^^^^^^^
#                                                 field does not exist
```

The `WarningIndicator` schema (TypeScript `brief.ts:196–203`, Python prompt in
`agent_brief.py:718–724`) uses `status` (values: `watching/triggered/elevated/cleared`)
and `detail`. The `cmd_show` function references non-existent `level` and `assessment`
fields. Every `python pipeline/main.py show` invocation renders `?` for the level and
empty string for the assessment, regardless of actual data. Color-coding is also broken
(compares against `'RED'`/`'AMBER'` which never match actual values).

**Fix:** Replace `w.get('level', '?')` with `w.get('status', '?')`, replace the color
logic to map `triggered→red`, `elevated→yellow`, `watching/cleared→green`, and replace
`w.get("assessment","")` with `w.get("detail","")`.

---

## HIGH

### 3. `agent-brief.yml` commit message always shows wrong model
**File:** `.github/workflows/agent-brief.yml:93`

```bash
USED_MODEL="${MODEL:-claude-sonnet-4-6}"
git commit -m "cycle: ${CYCLE_DATE} — agent brief [${USED_MODEL}]"
```

The shell variable `$MODEL` is never set in this step. It was set implicitly in the
prior step's `run:` block as a local shell variable, but shell state does not persist
between steps. `${MODEL:-claude-sonnet-4-6}` always resolves to the fallback, so the
commit message always reads `[claude-sonnet-4-6]` even when `claude-opus-4-6` was used.

**Fix:** Either export the model to `$GITHUB_ENV` in the run step, or inline the
expression: `"${{ github.event.inputs.model || 'claude-sonnet-4-6' }}"`.

---

### 4. `serializer.py` `REQUIRED_META` incomplete — `subtitle` and `contextNote` not validated
**File:** `pipeline/output/serializer.py:30`

```python
REQUIRED_META = {'cycleId', 'cycleNum', 'classification', 'tlp', 'timestamp',
                 'region', 'analystUnit', 'threatLevel', 'threatTrajectory'}
```

The TypeScript `BriefCycle.meta` type (`src/types/brief.ts:220–241`) requires both
`subtitle` and `contextNote`. The `validate.yml` inline script does check `subtitle`
(line 83), but the Python serializer does not — a cycle missing `subtitle` passes
`write_cycle()` validation but would break the React front-end and HTML renderer.
`contextNote` is not checked anywhere in Python.

**Fix:** Add `'subtitle'` and `'contextNote'` to `REQUIRED_META`.

---

### 5. Unquoted user input in workflow shell steps — shell injection risk
**Files:** `.github/workflows/render-on-demand.yml:48–51` · `.github/workflows/daily-brief.yml:83,98`

In `render-on-demand.yml`:
```yaml
if [ -n "${{ github.event.inputs.cycle }}" ]; then
  CYCLE_ARG="--cycle ${{ github.event.inputs.cycle }}"
fi
python pipeline/main.py render $CYCLE_ARG
```

In `daily-brief.yml`:
```yaml
DATE_ARG="--date ${{ github.event.inputs.date }}"
```

GitHub Actions substitutes expressions before the shell executes. If an input contains
shell metacharacters (spaces, semicolons, backticks), the runner interprets them. While
`workflow_dispatch` requires write access (limiting the attacker surface), this pattern
is still a security anti-pattern. The same substitution in `validate.yml:53` (`cycle_arg
= "${{ github.event.inputs.cycle }}"`) could allow escape from the Python string literal
if the input contains `"` characters.

**Fix:** Assign inputs to environment variables and reference via `$VAR`:
```yaml
env:
  INPUT_CYCLE: ${{ github.event.inputs.cycle }}
run: |
  if [ -n "$INPUT_CYCLE" ]; then
    CYCLE_ARG="--cycle $INPUT_CYCLE"
  fi
```

---

### 6. `--dangerously-skip-permissions` with web-fetched content in prompts
**File:** `pipeline/agent_brief.py:306`

```python
cmd += ['--dangerously-skip-permissions']
```

Every `_call_claude` invocation includes this flag. Prompts sent to Claude contain
content fetched directly from external websites (`_domain_content_block` embeds raw
fetched text). A malicious actor who can control content on any source in `sources.yaml`
could embed prompt injection instructions. With `--dangerously-skip-permissions`, Claude
is permitted to execute arbitrary shell commands, write files, and make network requests
within the GitHub Actions runner.

This is a known trade-off for CI use, but there is no sandboxing, no prompt injection
filtering, and no content sanitization beyond HTML-stripping. The risk should be
explicitly documented and mitigated (e.g., fetch content to a file; pass only a
summarized/filtered form to Claude).

---

## MEDIUM

### 7. `_build_placeholder_draft` produces schema-invalid `keyJudgment` objects
**File:** `pipeline/main.py:242–251`

```python
'keyJudgment': {
    'text': f'{len(items)} items collected...',
    'confidence': confidence,           # valid ConfidenceTier
    'probabilityRange': 'placeholder',  # NOT a valid value
    'corroborated': bool(tier1),        # NOT a schema field
    # MISSING: id, domain, language, basis, citations
},
```

Required `KeyJudgment` fields per `brief.ts:74–86`: `id`, `domain`, `confidence`,
`probabilityRange`, `language`, `text`, `basis`, `citations`. Placeholder keyJudgments
are missing five required fields and include one non-schema field. The `validate.yml`
script does not catch this because it only checks `kj.get("text")` being non-empty
and skips the `language` check when `lang` is `None`.

---

### 8. `validate.yml` silently passes missing `language` field on key judgments
**File:** `.github/workflows/validate.yml:122–125`

```python
lang = kj.get("language")
if lang and lang not in VALID_CONFIDENCE:
    errors.append(...)
```

If `language` is absent (e.g., from a placeholder draft), no error is raised. But
`KeyJudgment.language` is a required field in the TypeScript type and in the domain
subagent schema. The condition should be:
```python
if not lang:
    errors.append(f"Domain {d.get('id')}: keyJudgment.language is missing")
elif lang not in VALID_CONFIDENCE:
    errors.append(f"Domain {d.get('id')}: invalid confidence language '{lang}'")
```

---

### 9. `daily-brief.yml` commit step: unquoted `$(basename $LATEST)`
**File:** `.github/workflows/daily-brief.yml:121`

```bash
cp "$LATEST" "src/data/$(basename $LATEST)"
```

`$LATEST` inside `$(basename ...)` is unquoted. If the filename contains spaces or
glob characters, word splitting would produce unexpected results. Should be:
```bash
cp "$LATEST" "src/data/$(basename "$LATEST")"
```

---

### 10. `deploy.yml`: glob failure if `briefs/` contains only non-HTML files
**File:** `.github/workflows/deploy.yml:50–56`

```bash
if [ -d briefs ] && [ "$(ls -A briefs)" ]; then
  mkdir -p dist/briefs
  cp briefs/*.html dist/briefs/
```

`ls -A briefs` returns true if the directory is non-empty regardless of file type.
If `briefs/` contains only a `.gitkeep` or other non-HTML file, the `cp briefs/*.html`
glob expansion fails and the step exits with an error. Fix:
```bash
if compgen -G "briefs/*.html" > /dev/null 2>&1; then
```

---

### 11. `validate.yml` does not validate `executive.keyJudgments`
**File:** `.github/workflows/validate.yml:111–113`

The inline script only validates `executive.bluf`:
```python
if not cycle.get("executive", {}).get("bluf"):
    errors.append("executive.bluf is empty")
```

`serializer.py:91–92` validates both `bluf` and `keyJudgments`, but the standalone
workflow validator misses `keyJudgments`. A cycle committed directly (bypassing the
pipeline serializer) could have an empty `keyJudgments` array and pass `validate.yml`.

---

## LOW

### 12. `DomainSection.num` type comment is stale
**File:** `src/types/brief.ts:179`

```typescript
/** "01" through "05" */
num: string
```

There are now six domains (`d1`–`d6`). The comment should read `"01" through "06"`.

---

### 13. Caveats text hardcodes wrong subagent count
**File:** `pipeline/agent_brief.py:919`

```python
f'Produced by 10 parallel {model} CLI subagents. '
```

The module docstring (line 6–40) correctly states 17 subagents across 4 phases (6
domain + 6 voice review + 1 editorial + 4 synthesis = 17). The caveats text should
reflect the actual architecture.

---

### 14. Redundant `sys.path.insert` in `run_agent_brief`
**File:** `pipeline/agent_brief.py:965`

```python
sys.path.insert(0, str(PIPELINE_DIR))
from render.html_renderer import render_cycle
```

`pipeline/main.py:38` already inserts `PIPELINE_DIR` into `sys.path` before importing
`agent_brief`. This second insert is harmless but redundant.

---

### 15. Redundant lambda in `fetch_all_sources`
**File:** `pipeline/agent_brief.py:257`

```python
for sid, content in pool.map(lambda s: _fetch_one(s), fetchable):
```

The lambda wraps a direct call with no transformation. Should be:
```python
for sid, content in pool.map(_fetch_one, fetchable):
```

---

### 16. Initial `cycleId` assignment in `run_agent_brief` is dead code
**File:** `pipeline/agent_brief.py:882`

```python
'cycleId': f'CSE-BRIEF-AGENT-{date_str}',   # set here
...
cycle['meta']['cycleId'] = f'cycle{cycle_num:03d}_{date_str}'  # immediately overwritten at line 952
```

The initial value is always overwritten before the cycle is written to disk. The first
assignment serves no purpose.

---

### 17. `_fmt_ts` format string slicing is a no-op
**File:** `pipeline/render/html_renderer.py:130`

```python
for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S+00:00', '%Y-%m-%dT%H:%M:%S'):
    try:
        dt = datetime.strptime(iso[:19], fmt[:len(fmt)])
```

`fmt[:len(fmt)]` is always the full `fmt` string — slicing to its own length is
identity. Additionally, `iso[:19]` strips the timezone suffix (`Z` or `+00:00`) before
passing to `strptime`, which means the first format `'%Y-%m-%dT%H:%M:%SZ'` will never
match because the `Z` is removed from the input but still required by the format string.
Only the third format (`'%Y-%m-%dT%H:%M:%S'`) will reliably match.

---

## SCHEMA / TYPE CONSISTENCY

### 18. `_build_placeholder_draft` `language` field absent — validator passes silently
Covered in finding #7 and #8 above. The combined effect is that placeholder drafts
produced when the Claude API is unavailable will fail the TypeScript compiler and the
React renderer, but pass the Python `validate()` call in the serializer.

### 19. `agent_brief.py` cycle numbering not synchronized with `serializer.py`
**Files:** `pipeline/agent_brief.py:943–950` · `pipeline/output/serializer.py:36–47`

Both modules independently scan `cycles/` to derive the next cycle number. If both
are invoked concurrently (e.g., by the two conflicting scheduled workflows in finding
#1), they will compute the same number and one will silently overwrite the other's
output. The concurrency group on each workflow prevents this within a single workflow,
but not across the two duplicate schedules.

---

## SUMMARY TABLE

| # | Severity  | File(s)                                     | Issue                                              |
|---|-----------|---------------------------------------------|----------------------------------------------------|
| 1 | CRITICAL  | agent-brief.yml · daily-brief.yml           | Duplicate `0 6 * * *` schedule, different groups  |
| 2 | CRITICAL  | pipeline/main.py:688–690                    | `cmd_show` uses wrong warning indicator field names|
| 3 | HIGH      | agent-brief.yml:93                          | `$MODEL` undefined in commit step                  |
| 4 | HIGH      | pipeline/output/serializer.py:30            | `subtitle`/`contextNote` absent from `REQUIRED_META` |
| 5 | HIGH      | render-on-demand.yml · daily-brief.yml      | Unquoted user inputs — shell injection risk        |
| 6 | HIGH      | pipeline/agent_brief.py:306                 | `--dangerously-skip-permissions` + web content     |
| 7 | MEDIUM    | pipeline/main.py:242–251                    | Placeholder `keyJudgment` missing required fields  |
| 8 | MEDIUM    | validate.yml:122–125                        | Missing `language` silently passes validation      |
| 9 | MEDIUM    | daily-brief.yml:121                         | Unquoted `$(basename $LATEST)`                     |
|10 | MEDIUM    | deploy.yml:50–56                            | Glob failure if no `.html` files in `briefs/`      |
|11 | MEDIUM    | validate.yml:111–113                        | `executive.keyJudgments` not validated             |
|12 | LOW       | src/types/brief.ts:179                      | Stale `num` comment ("05" should be "06")          |
|13 | LOW       | pipeline/agent_brief.py:919                 | Caveats text: "10 parallel" should be "17"         |
|14 | LOW       | pipeline/agent_brief.py:965                 | Redundant `sys.path.insert`                        |
|15 | LOW       | pipeline/agent_brief.py:257                 | Redundant lambda wrapping `_fetch_one`             |
|16 | LOW       | pipeline/agent_brief.py:882                 | Dead initial `cycleId` assignment                  |
|17 | LOW       | pipeline/render/html_renderer.py:130        | `_fmt_ts` format loop: no-op slice + broken first format |
|18 | SCHEMA    | pipeline/main.py:242 + validate.yml:122     | Placeholder keyJudgment fails TypeScript, passes Python |
|19 | SCHEMA    | agent_brief.py:943 + serializer.py:36       | Cycle numbering not synchronized across modules    |
