#!/bin/sh
# Yumii installer for macOS / Linux.
#
#   curl -fsSL https://yumii.me/install.sh | bash
#
# Heads up: Yumii's desktop app ships for Windows today; the macOS and
# Linux shells are coming. This installs the backend so developers can
# work with it — the full desktop experience on this platform lands soon.

set -e

MAGENTA='\033[1;35m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m'

echo ""
printf "${MAGENTA}  Yumii — an AI companion for your desktop${NC}\n"
printf "${GRAY}  -----------------------------------------${NC}\n"
echo ""
printf "${YELLOW}  Note: the Yumii desktop app is Windows-only for now.${NC}\n"
printf "${YELLOW}  This installs the backend (for development); the macOS/Linux${NC}\n"
printf "${YELLOW}  desktop shells are on the roadmap.${NC}\n"
echo ""

# ── 1/2: uv ──────────────────────────────────────────────────────────────
printf "${CYAN}[1/2] Package manager (uv)...${NC}\n"
if command -v uv >/dev/null 2>&1; then
    printf "      ${GREEN}already installed.${NC}\n"
else
    printf "      ${GRAY}installing uv...${NC}\n"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        printf "  ${YELLOW}uv installed but not on PATH yet — open a new terminal and re-run.${NC}\n"
        exit 1
    fi
    printf "      ${GREEN}uv installed.${NC}\n"
fi

# ── 2/2: the Yumii backend (uv brings its own Python) ────────────────────
printf "${CYAN}[2/2] Yumii backend...${NC}\n"
printf "      ${GRAY}(first install downloads a few hundred MB — one-time)${NC}\n"
uv tool install --python 3.12 --upgrade yumii

echo ""
printf "  ${GREEN}Backend installed.${NC} Start it with:  ${MAGENTA}yumii server${NC}\n"
printf "  ${GRAY}(If 'yumii' isn't found, open a new terminal so PATH refreshes.)${NC}\n"
printf "  ${GRAY}Desktop app for this platform: watch https://yumii.me${NC}\n"
echo ""
