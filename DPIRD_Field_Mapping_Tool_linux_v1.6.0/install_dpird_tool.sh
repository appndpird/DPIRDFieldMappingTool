#!/usr/bin/env bash
# ============================================================
#  DPIRD Field Mapping Tool — Linux / macOS Setup
# ============================================================
#  Creates a conda environment and installs all dependencies.
#
#  Prerequisites:
#    - Anaconda or Miniconda installed and available on PATH
#    - Internet connection (first-time setup only)
#
#  Usage:
#    chmod +x install_dpird_tool.sh
#    ./install_dpird_tool.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="dpird_field_tool"
PYTHON_VER="3.11"
APP_FILE="$SCRIPT_DIR/app/field_mapping_tool.py"

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BOLD}================================================${NC}"
echo -e "${BOLD}  DPIRD Field Mapping Tool — Setup${NC}"
echo -e "${BOLD}================================================${NC}"
echo ""

# ---- Check conda is available ----
if ! command -v conda &> /dev/null; then
    echo -e "${RED}ERROR: conda not found on PATH.${NC}"
    echo ""
    echo "  Install Miniconda or Anaconda first:"
    echo "    https://docs.anaconda.com/miniconda/"
    echo ""
    exit 1
fi

echo -e "  conda found: $(conda --version)"

# ---- Check if environment already exists ----
if conda env list | grep -qw "$ENV_NAME"; then
    echo -e "  ${YELLOW}Environment '$ENV_NAME' already exists.${NC}"
    echo "  Checking packages..."

    # Activate and verify
    eval "$(conda shell.bash hook)"
    conda activate "$ENV_NAME"

    VERIFY="import numpy,pandas,PIL,shapely,pyproj,fiona,rasterio,geopandas,matplotlib,psutil,folium,streamlit,streamlit_folium,leafmap"
    if python -c "$VERIFY" 2>/dev/null; then
        echo -e "  ${GREEN}[OK] All packages present.${NC}"
        echo ""
        echo "  Run the tool with:  ./run_dpird_tool.sh"
        echo ""
        exit 0
    else
        echo "  Some packages missing. Will install them..."
    fi
else
    # ---- Create environment ----
    echo ""
    echo -e "  ${BOLD}[1/3] Creating conda environment '$ENV_NAME' (Python $PYTHON_VER)...${NC}"
    conda create -y -n "$ENV_NAME" python="$PYTHON_VER"
    echo -e "        ${GREEN}OK${NC}"
fi

# ---- Activate environment ----
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# ---- Install packages ----
echo ""
echo -e "  ${BOLD}[2/3] Installing geospatial packages (conda-forge)...${NC}"
echo "        This takes several minutes. Please be patient."
echo ""

conda install -y -c conda-forge --override-channels \
    numpy pandas geopandas rasterio fiona shapely pyproj \
    pillow matplotlib psutil

echo ""
echo -e "  ${BOLD}[3/3] Installing Streamlit and web packages (pip)...${NC}"
echo ""

pip install --quiet \
    streamlit streamlit-folium folium leafmap localtileserver scooby

# ---- Verify ----
echo ""
echo -e "  ${BOLD}--- Verifying ---${NC}"
echo ""

FAIL=0
for pkg in numpy pandas PIL shapely pyproj fiona rasterio geopandas matplotlib psutil folium streamlit streamlit_folium leafmap; do
    if python -c "import $pkg" 2>/dev/null; then
        echo -e "    $pkg ... ${GREEN}OK${NC}"
    else
        echo -e "    $pkg ... ${RED}MISSING${NC}"
        FAIL=1
    fi
done

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "  Final retry with pip..."
    pip install --quiet numpy pandas pillow shapely pyproj rasterio fiona \
        geopandas matplotlib psutil folium streamlit streamlit-folium leafmap \
        localtileserver scooby
    if ! python -c "$VERIFY" 2>/dev/null; then
        echo -e "  ${RED}ERROR: Some packages could not be installed.${NC}"
        exit 1
    fi
fi

# ---- Check app file exists ----
if [ ! -f "$APP_FILE" ]; then
    echo ""
    echo -e "  ${YELLOW}NOTE: App file not found at $APP_FILE${NC}"
    echo "  Make sure field_mapping_tool.py is in the app/ subfolder."
fi

echo ""
echo -e "${BOLD}================================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo ""
echo "  To run the tool:"
echo "    ./run_dpird_tool.sh"
echo ""
echo "  Or manually:"
echo "    conda activate $ENV_NAME"
echo "    streamlit run app/field_mapping_tool.py"
echo -e "${BOLD}================================================${NC}"
echo ""
