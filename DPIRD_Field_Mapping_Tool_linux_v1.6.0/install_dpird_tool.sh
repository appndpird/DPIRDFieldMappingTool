#!/usr/bin/env bash
# ============================================================
#  DPIRD Field Mapping Tool — Linux / macOS Setup
# ============================================================
#  Creates a conda environment with Python, then installs all
#  packages via pip (much faster than conda-forge).
#
#  Prerequisites:
#    - Anaconda or Miniconda installed and available on PATH
#    - Internet connection (first-time setup only)
#
#  Usage:
#    chmod +x install_dpird_tool.sh
#    ./install_dpird_tool.sh
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ENV_NAME="dpird_field_tool"
PYTHON_VER="3.11"
APP_FILE="$SCRIPT_DIR/app/field_mapping_tool.py"
VERIFY="import numpy,pandas,PIL,shapely,pyproj,fiona,rasterio,geopandas,matplotlib,psutil,folium,streamlit,streamlit_folium,leafmap"

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
    echo "  After installing, run:  conda init bash"
    echo "  Then restart your terminal."
    echo ""
    read -p "  Press Enter to exit..." _
    exit 1
fi

echo -e "  conda found: $(conda --version)"

# ---- Initialise conda for this shell session ----
eval "$(conda shell.bash hook)" 2>/dev/null || true

# ---- Check if environment already exists ----
ENV_EXISTS=0
if conda env list 2>/dev/null | grep -qw "$ENV_NAME"; then
    ENV_EXISTS=1
fi

if [ "$ENV_EXISTS" -eq 1 ]; then
    echo -e "  ${YELLOW}Environment '$ENV_NAME' already exists.${NC}"
    echo "  Checking packages..."

    conda activate "$ENV_NAME" 2>/dev/null || true

    if python -c "$VERIFY" 2>/dev/null; then
        echo -e "  ${GREEN}[OK] All packages present.${NC}"
        echo ""
        echo "  Run the tool with:  ./run_dpird_tool.sh"
        echo ""
        read -p "  Press Enter to exit..." _
        exit 0
    else
        echo "  Some packages missing. Will install them..."
    fi
else
    # ---- Create environment ----
    echo ""
    echo -e "  ${BOLD}[1/2] Creating conda environment '$ENV_NAME' (Python $PYTHON_VER)...${NC}"
    conda create -y -n "$ENV_NAME" python="$PYTHON_VER"
    if [ $? -ne 0 ]; then
        echo -e "  ${RED}ERROR: Environment creation failed.${NC}"
        read -p "  Press Enter to exit..." _
        exit 1
    fi
    echo -e "        ${GREEN}OK${NC}"
fi

# ---- Activate environment ----
conda activate "$ENV_NAME" 2>/dev/null || true

# Verify activation worked
ACTIVE_ENV=$(python -c "import sys; print(sys.prefix)" 2>/dev/null || echo "")
if [[ "$ACTIVE_ENV" != *"$ENV_NAME"* ]]; then
    echo -e "  ${RED}ERROR: Could not activate environment '$ENV_NAME'.${NC}"
    echo "  Try running:  conda init bash  (then restart terminal)"
    read -p "  Press Enter to exit..." _
    exit 1
fi

# ---- Install all packages via pip ----
echo ""
echo -e "  ${BOLD}[2/2] Installing all packages (pip)...${NC}"
echo "        This takes a few minutes."
echo ""

pip install \
    numpy pandas "geopandas>=0.14" "shapely>=2.0" pyproj \
    rasterio fiona pillow matplotlib psutil \
    streamlit streamlit-folium folium leafmap localtileserver scooby

if [ $? -ne 0 ]; then
    echo ""
    echo -e "  ${YELLOW}Some packages failed. Retrying one by one...${NC}"
    echo ""
    for pkg in numpy pandas "geopandas>=0.14" "shapely>=2.0" pyproj \
               rasterio fiona pillow matplotlib psutil \
               streamlit streamlit-folium folium leafmap localtileserver scooby; do
        pip install "$pkg" 2>/dev/null || echo -e "    ${RED}Failed: $pkg${NC}"
    done
fi

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
    echo -e "  ${RED}ERROR: Some packages could not be installed.${NC}"
    echo "  Check the error messages above."
    echo ""
    echo "  If rasterio or fiona failed, you may need to install"
    echo "  GDAL system libraries first:"
    echo "    macOS:  brew install gdal"
    echo "    Ubuntu: sudo apt-get install gdal-bin libgdal-dev"
    echo ""
    read -p "  Press Enter to exit..." _
    exit 1
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
read -p "  Press Enter to close..." _
