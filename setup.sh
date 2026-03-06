#!/usr/bin/env bash
# ============================================================
# CSE Intel Brief — Environment Setup Script
# ============================================================
# Usage:
#   ./setup.sh              # core install only
#   ./setup.sh --full       # core + lxml + jsonschema
#   ./setup.sh --dev        # core + dev tools + linting
#   ./setup.sh --js         # core + Playwright (+ chromium browser)
#   ./setup.sh --all        # everything above
#   ./setup.sh --check      # verify environment without installing
# ============================================================

set -euo pipefail

# ── Colours ─────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERR ]${RESET}  $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; echo "────────────────────────────────────────────"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

MODE_FULL=false
MODE_DEV=false
MODE_JS=false
MODE_CHECK=false

for arg in "$@"; do
    case "$arg" in
        --full)  MODE_FULL=true ;;
        --dev)   MODE_DEV=true  ;;
        --js)    MODE_JS=true   ;;
        --all)   MODE_FULL=true; MODE_DEV=true; MODE_JS=true ;;
        --check) MODE_CHECK=true ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# ====/p' "$0" | head -12
            exit 0 ;;
        *) error "Unknown flag: $arg"; exit 1 ;;
    esac
done

# ── Check mode ───────────────────────────────────────────────
if $MODE_CHECK; then
    header "Environment check"
    PASS=0; FAIL=0

    check_cmd() {
        local name="$1" cmd="${2:-$1}"
        if command -v "$cmd" &>/dev/null; then
            ok "$name: $(command -v "$cmd")"
            ((PASS++)) || true
        else
            warn "$name: NOT FOUND"
            ((FAIL++)) || true
        fi
    }

    check_python() {
        if command -v python3 &>/dev/null; then
            local ver
            ver="$(python3 --version 2>&1)"
            local major minor
            major="$(python3 -c 'import sys; print(sys.version_info.major)')"
            minor="$(python3 -c 'import sys; print(sys.version_info.minor)')"
            if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
                ok "Python: $ver"
                ((PASS++)) || true
            else
                error "Python: $ver — requires 3.11+"
                ((FAIL++)) || true
            fi
        else
            error "Python3: NOT FOUND"
            ((FAIL++)) || true
        fi
    }

    check_pymod() {
        local name="$1" mod="${2:-$1}"
        local python="${VENV_DIR}/bin/python3"
        [[ ! -x "$python" ]] && python="python3"
        if "$python" -c "import $mod" &>/dev/null 2>&1; then
            local ver
            ver="$("$python" -c "import $mod; print(getattr($mod, '__version__', 'installed'))" 2>/dev/null)"
            ok "  python: $name ($ver)"
            ((PASS++)) || true
        else
            warn "  python: $name — NOT installed"
            ((FAIL++)) || true
        fi
    }

    check_python
    check_cmd "pip3" "pip3"
    check_cmd "Claude CLI" "claude"

    echo ""
    info "Checking virtual environment: $VENV_DIR"
    if [[ -d "$VENV_DIR" ]]; then
        ok "venv exists"
    else
        warn "venv not found — run ./setup.sh to create it"
    fi

    echo ""
    info "Python package status:"
    check_pymod "requests"
    check_pymod "bs4" "bs4"
    check_pymod "yaml"
    check_pymod "anyio"
    check_pymod "claude_agent_sdk"

    echo ""
    info "Optional packages:"
    check_pymod "lxml"
    check_pymod "jsonschema"
    check_pymod "playwright"

    echo ""
    if [[ "$FAIL" -eq 0 ]]; then
        ok "All checks passed ($PASS/$((PASS+FAIL)))"
    else
        warn "$FAIL check(s) failed — run ./setup.sh to install missing deps"
        exit 1
    fi
    exit 0
fi

# ── Python version gate ──────────────────────────────────────
header "CSE Intel Brief — Environment Setup"
info "Repo root: $REPO_ROOT"

if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install Python 3.11+ before running this script."
    exit 1
fi

PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
if [[ "$PY_MAJOR" -lt 3 || "$PY_MINOR" -lt 11 ]]; then
    error "Python 3.11+ required. Found: $(python3 --version)"
    exit 1
fi
ok "Python $(python3 --version) — OK"

# ── Virtual environment ──────────────────────────────────────
header "Virtual environment"
if [[ -d "$VENV_DIR" ]]; then
    info "Existing venv found at $VENV_DIR"
else
    info "Creating venv at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
    ok "venv created"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python3"

# Upgrade pip silently
"$PIP" install --quiet --upgrade pip setuptools wheel
ok "pip/setuptools/wheel up to date"

# ── Core install ─────────────────────────────────────────────
header "Installing core dependencies"
"$PIP" install --quiet -r "$REPO_ROOT/requirements.txt"
ok "Core dependencies installed"

# ── Optional: full ───────────────────────────────────────────
if $MODE_FULL || $MODE_DEV; then
    header "Installing recommended optional packages"
    "$PIP" install --quiet lxml jsonschema
    ok "lxml + jsonschema installed"
fi

# ── Optional: dev ────────────────────────────────────────────
if $MODE_DEV; then
    header "Installing development tools"
    "$PIP" install --quiet -r "$REPO_ROOT/requirements-dev.txt"
    ok "Dev tools installed (pytest, ruff, mypy, rich)"
fi

# ── Optional: playwright ─────────────────────────────────────
if $MODE_JS; then
    header "Installing Playwright (JS-rendered site support)"
    "$PIP" install --quiet "playwright>=1.44.0,<2.0"
    info "Installing Chromium browser binary (~300 MB)..."
    "$VENV_DIR/bin/playwright" install chromium
    ok "Playwright + Chromium installed"
    echo ""
    info "Playwright enables scraping of:"
    info "  - iras_war_risk   (IRAS — Cloudflare-protected)"
    info "  - moodys_shipping (Moody's Analytics — JS gated)"
    info "  - swissre_sigma   (Swiss Re Sigma — AJAX paginated)"
fi

# ── Claude CLI check ─────────────────────────────────────────
header "Claude CLI check"
if command -v claude &>/dev/null; then
    CLAUDE_VER="$(claude --version 2>/dev/null || echo 'unknown')"
    ok "Claude CLI found: $CLAUDE_VER"
    info "Testing claude_agent_sdk import..."
    if "$PYTHON" -c "from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage" &>/dev/null 2>&1; then
        ok "claude_agent_sdk importable"
    else
        warn "claude_agent_sdk import failed — the pipeline will use placeholder drafts"
        warn "If claude-agent-sdk is not in PyPI yet, install from the Claude Code SDK:"
        warn "  npm install -g @anthropic-ai/claude-code   # installs the CLI"
        warn "  pip install claude-agent-sdk               # installs the Python bindings"
    fi
else
    warn "Claude CLI (claude) not found on PATH"
    warn "The pipeline will run in placeholder mode without live AI drafting."
    warn ""
    warn "To install Claude Code CLI:"
    warn "  npm install -g @anthropic-ai/claude-code"
    warn "  # or: see https://docs.anthropic.com/claude-code"
fi

# ── Pipeline config check ────────────────────────────────────
header "Pipeline configuration check"
CONFIG="$REPO_ROOT/pipeline-config.yaml"
if [[ -f "$CONFIG" ]]; then
    ok "pipeline-config.yaml found"
else
    warn "pipeline-config.yaml not found — creating from template..."
    cat > "$CONFIG" <<'YAML'
# CSE Intel Brief — Pipeline Configuration
# Copy this file and fill in your credentials.
# NEVER commit API keys or passwords to git.

# Email ingestion (CFR Daily Brief)
email:
  host: "imap.gmail.com"
  port: 993
  username: ""        # set via env: INTEL_EMAIL_USER
  password: ""        # set via env: INTEL_EMAIL_PASS
  folder: "INBOX"
  subject_filter: "CFR"

# Pipeline behaviour
pipeline:
  max_items_per_domain: 15
  novelty_threshold: 0.35
  auto_approve: false
  demo_mode: false
YAML
    ok "Created pipeline-config.yaml template"
    warn "Fill in your email credentials before running ingest"
fi

# ── Activation hint ──────────────────────────────────────────
header "Setup complete"
echo ""
echo -e "  ${BOLD}Activate the environment:${RESET}"
echo -e "    source $VENV_DIR/bin/activate"
echo ""
echo -e "  ${BOLD}Run the pipeline (demo mode — no external calls):${RESET}"
echo -e "    python pipeline/main.py run --demo --auto-approve"
echo ""
echo -e "  ${BOLD}Run full source check:${RESET}"
echo -e "    python pipeline/main.py check-sources"
echo ""
echo -e "  ${BOLD}Verify this environment:${RESET}"
echo -e "    ./setup.sh --check"
echo ""
if $MODE_DEV; then
    echo -e "  ${BOLD}Run tests:${RESET}"
    echo -e "    pytest"
    echo ""
fi
