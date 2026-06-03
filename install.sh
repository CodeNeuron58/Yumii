#!/bin/sh
# Yumi Installer for macOS / Linux
# Usage: curl -LsSf https://raw.githubusercontent.com/CodeNeuron58/Yumi/master/install.sh | sh

set -e

REPO="https://github.com/CodeNeuron58/Yumi.git"
PINK='\033[1;35m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo ""
printf "${PINK}  ________________________________________${NC}\n"
printf "${PINK}  |                                      |${NC}\n"
printf "${PINK}  |    Yumi  Installation Script        |${NC}\n"
printf "${PINK}  |    Real-Time AI Companion            |${NC}\n"
printf "${PINK}  |______________________________________|${NC}\n"
echo ""

# ── Step 1: Check Python ────────────────────────────────────────────────────
printf "${CYAN}[1/3] Checking Python version...${NC}\n"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON_CMD="$cmd"
            printf "    ${GREEN}Found Python $version${NC}\n"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    printf "  ${RED}ERROR: Python 3.12+ is required but not found.${NC}\n"
    printf "  ${YELLOW}Download from: https://python.org/downloads${NC}\n"
    echo ""
    exit 1
fi

# ── Step 2: Install uv if missing ───────────────────────────────────────────
printf "${CYAN}[2/3] Checking uv package manager...${NC}\n"

if ! command -v uv >/dev/null 2>&1; then
    printf "    ${YELLOW}Installing uv...${NC}\n"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for this session
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

    if ! command -v uv >/dev/null 2>&1; then
        echo ""
        printf "  ${RED}ERROR: uv installed but not found in PATH.${NC}\n"
        printf "  ${YELLOW}Restart your terminal and run: uv tool install git+${REPO}${NC}\n"
        exit 1
    fi
    printf "    ${GREEN}uv installed.${NC}\n"
else
    UV_VER=$(uv --version 2>&1)
    printf "    ${GREEN}Found $UV_VER${NC}\n"
fi

# ── Step 2.5: Ensure git is on PATH (needed by `uv tool install git+...`) ───
if ! command -v git >/dev/null 2>&1; then
    echo ""
    printf "  ${RED}ERROR: 'git' is required but not found on PATH.${NC}\n"
    printf "  ${YELLOW}Install Git, then re-run this installer:${NC}\n"
    printf "  ${YELLOW}  macOS:  brew install git${NC}\n"
    printf "  ${YELLOW}  Linux:  sudo apt-get install -y git  (or your distro's equivalent)${NC}\n"
    exit 1
else
    GIT_VER=$(git --version 2>&1)
    printf "    ${GREEN}Found $GIT_VER${NC}\n"
fi

# ── Step 3: Install Yumi ─────────────────────────────────────────────────────
printf "${CYAN}[3/3] Installing Yumi...${NC}\n"
printf "    ${GRAY}(Downloading CPU-only PyTorch + dependencies, this may take a few minutes)${NC}\n"

if ! uv tool install "git+${REPO}"; then
    echo ""
    printf "  ${RED}ERROR: Installation failed.${NC}\n"
    printf "  ${YELLOW}Try manually: uv tool install git+${REPO}${NC}\n"
    exit 1
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
printf "  ${GREEN}✅  Yumi has been installed!${NC}\n"
echo ""
printf "  Run her with:\n"
printf "      ${PINK}yumi${NC}\n"
echo ""
printf "  ${GRAY}GitHub:  https://github.com/CodeNeuron58/Yumi${NC}\n"
echo ""
