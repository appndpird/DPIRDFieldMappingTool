#!/usr/bin/env bash
# ============================================================
#  DPIRD Field Mapping Tool — Launch (Linux / macOS)
# ============================================================
#  Usage:
#    chmod +x run_dpird_tool.sh
#    ./run_dpird_tool.sh
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="dpird_field_tool"
APP_FILE="$SCRIPT_DIR/app/field_mapping_tool.py"
PORT=8501

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ---- Check conda ----
if ! command -v conda &> /dev/null; then
    echo -e "${RED}ERROR: conda not found. Run install_dpird_tool.sh first.${NC}"
    exit 1
fi

# ---- Check environment exists ----
if ! conda env list | grep -qw "$ENV_NAME"; then
    echo -e "${YELLOW}Environment '$ENV_NAME' not found. Running installer...${NC}"
    bash "$SCRIPT_DIR/install_dpird_tool.sh"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Installation failed.${NC}"
        exit 1
    fi
fi

# ---- Activate environment ----
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# ---- Check app file ----
if [ ! -f "$APP_FILE" ]; then
    echo -e "${RED}ERROR: App file not found at:${NC}"
    echo "  $APP_FILE"
    echo ""
    echo "  Make sure field_mapping_tool.py is in the app/ subfolder."
    exit 1
fi

# ---- Kill stale process on the port ----
if lsof -i ":$PORT" -sTCP:LISTEN -t &>/dev/null; then
    echo -e "  ${YELLOW}Closing previous session on port $PORT...${NC}"
    lsof -i ":$PORT" -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
    sleep 2
fi

# ---- Clear stale Streamlit cache ----
if [ -d "$HOME/.streamlit/cache" ]; then
    rm -rf "$HOME/.streamlit/cache"
fi

echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  DPIRD Field Mapping Tool${NC}"
echo -e "${BOLD}  Starting on http://localhost:$PORT${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""
echo "  To stop: press Ctrl+C in this terminal."
echo ""

# ---- Open browser after short delay ----
(sleep 4 && python -m webbrowser "http://localhost:$PORT") &

# ---- Launch Streamlit ----
streamlit run "$APP_FILE" \
    --server.headless true \
    --browser.gatherUsageStats false \
    --global.showWarningOnDirectExecution false \
    --server.port "$PORT"

echo ""
echo "  Application closed."
