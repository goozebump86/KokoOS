#!/usr/bin/env bash
# ==========================================
# KOKOOS AUTOMATED INSTALLER (Linux/macOS)
# ==========================================

set -e

# ── Colors ──────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   KOKOOS AUTOMATED INSTALLER (Linux)     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── STEP 1: Check Python Installation ──────────
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[❌] ERROR: Python 3 is not installed or not in PATH.${NC}"
    echo ""
    echo "Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

echo -e "${GREEN}[✅] Found Python:" $(python3 --version)
echo ""

# ── STEP 2: Create Virtual Environment ─────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[📦] Creating virtual environment in .venv ..."
    python3 -m venv .venv
    echo -e "${GREEN}[✅] Virtual environment created successfully."
else
    echo -e "${YELLOW}[ℹ️]  Virtual environment already exists in .venv"
fi

echo ""

# ── STEP 3: Activate Virtual Environment ───────
echo -e "${YELLOW}[🔧] Activating virtual environment ..."
source .venv/bin/activate

# ── STEP 4: Upgrade Pip & Install Dependencies ─
echo -e "${YELLOW}[📈] Upgrading pip ..."
python -m pip install --upgrade pip --quiet

echo ""
echo -e "${YELLOW}[⏳] Installing KOKOOS dependencies from requirements.txt ..."
echo "     This may take a few minutes, please be patient..."
echo ""
pip install -r requirements.txt
echo -e "${GREEN}[✅] All Python packages installed successfully."

echo ""

# ── STEP 5: Install Playwright Browsers ────────
echo -e "${YELLOW}[🌐] Installing Playwright browsers (needed for WebBrowserMCP & OutlookMCP) ..."
playwright install chromium
echo -e "${GREEN}[✅] Playwright browsers installed successfully."

echo ""

# ── INSTALLATION COMPLETE! ─────────────────────
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       INSTALLATION COMPLETE! 🎉          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}[📋] What's next?${NC}"
echo "──────────────────────────────────────"
echo ""
echo -e "  ${YELLOW}1️⃣${NC}  Activate the virtual environment (if needed):"
echo "      source .venv/bin/activate"
echo ""
echo -e "  ${YELLOW}2️⃣${NC}  Boot ALL KOKOOS servers at once:"
echo "      bash boot_koko.sh   (or ./boot_koko.bat)"
echo ""
echo -e "  ${YELLOW}3️⃣${NC}  Or run individual MCP servers:"
echo "      python CoderMCP.py             (Port 3020)"
echo "      python ComfyUIAudio.py         (Port 3018)"
echo "      python ComfyUIEdit.py          (Port 3017)"
echo "      python ComfyUIimage.py         (Port 3011)"
echo "      python DeepOSMCP.py            (Port 3022)"
echo "      python GmailMCP.py             (Port 3035)"
echo "      python hermes.py               (Main Shell)"
echo "      python JellyfinMCP.py          (Port 3010)"
echo "      python MemoryMCP.py            (Port 3021)"
echo "      python outlookmcp.py           (Port 3015)"
echo "      python WebBrowserMCP.py        (Port 3008)"
echo "      python YoutubePublisherMCP.py  (Port 3019)"
echo ""
echo -e "📝 ${YELLOW}NOTE:${NC} Edit .env file with your API keys before running!"
echo "       (Copy .env.example to .env if it doesn't exist)"
echo ""
