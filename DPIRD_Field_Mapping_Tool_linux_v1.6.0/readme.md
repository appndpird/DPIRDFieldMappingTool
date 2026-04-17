# DPIRD Field Mapping Tool — Linux / macOS Installation Guide

**Version 1.6 — April 2026**

Author: Bipul Neupane, PhD, Research Scientist, DPIRD Node, APPN
(`bipul.neupane@dpird.wa.gov.au`)

---

## 1. Overview

The DPIRD Field Mapping Tool is a Streamlit-based desktop application for digitising and managing agricultural field trial plot boundaries over drone orthomosaic imagery. It provides four core functions: **Generate Grid**, **Edit Grid**, **Convert File**, and **Cropping Tool**.

This guide covers installation and usage on **Linux** and **macOS** systems. The tool runs locally in your web browser at `http://localhost:8501` and requires no internet connection after initial setup.

---

## 2. Prerequisites

- **Operating system:** Linux (Ubuntu 20.04+, Fedora, etc.) or macOS (11 Big Sur or later)
- **Anaconda or Miniconda** installed and available on your PATH
- **Internet connection** for first-time package installation only
- **~2 GB disk space** for the conda environment and dependencies

If you don't have conda installed, download Miniconda from: https://docs.anaconda.com/miniconda/

---

## 3. Installation

### 3.1 Extract the distribution

Extract the provided archive to any location on your system:

```bash
unzip DPIRD_Field_Mapping_Tool.zip -d ~/Tools/
cd ~/Tools/DPIRD_Field_Mapping_Tool
```

You should see the following structure:

```
DPIRD_Field_Mapping_Tool/
├── app/
│   └── field_mapping_tool.py
├── bin/
│   └── logo.png
├── install_dpird_tool.sh
├── run_dpird_tool.sh
├── INSTALL_LINUX_MACOS.md        (this file)
└── README.txt
```

Download and place Miniconda into the DPIRD_Field_Mapping_Tool folder from: https://docs.anaconda.com/miniconda/ if you do not have anaconda installed.

### 3.2 Make the scripts executable

```bash
chmod +x install_dpird_tool.sh run_dpird_tool.sh
```

### 3.3 Run the installer

```bash
./install_dpird_tool.sh
```

The installer will:

1. Create a conda environment named `dpird_field_tool` with Python 3.11.
2. Install geospatial packages (numpy, pandas, geopandas, rasterio, fiona, shapely, pyproj, pillow, matplotlib, psutil) from **conda-forge**.
3. Install Streamlit and web packages (streamlit, streamlit-folium, folium, leafmap, localtileserver, scooby) via **pip**.
4. Verify all packages imported correctly.

This takes approximately 10–15 minutes depending on your internet speed. You only need to run this once.

### 3.4 Manual installation (alternative)

If you prefer to set up the environment yourself:

```bash
# Create and activate the environment
conda create -n dpird_field_tool python=3.11 -y
conda activate dpird_field_tool

# Install geospatial stack from conda-forge
conda install -c conda-forge -y \
    numpy pandas geopandas rasterio fiona shapely pyproj \
    pillow matplotlib psutil

# Install Streamlit and web packages
pip install streamlit streamlit-folium folium leafmap localtileserver scooby
```

Verify the installation:

```bash
python -c "import numpy,pandas,PIL,shapely,pyproj,fiona,rasterio,geopandas,matplotlib,psutil,folium,streamlit,streamlit_folium,leafmap"
```

If this runs without errors, installation is complete.

---

## 4. Running the Tool

### 4.1 Using the launch script

```bash
./run_dpird_tool.sh
```

The script will activate the conda environment, launch Streamlit, and open your default browser at `http://localhost:8501`. If the browser does not open automatically, navigate to that address manually.

### 4.2 Running manually

```bash
conda activate dpird_field_tool
cd /path/to/DPIRD_Field_Mapping_Tool
streamlit run app/field_mapping_tool.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501
```

### 4.3 Stopping the tool

Either press **Ctrl+C** in the terminal where the tool is running, or click the **Close Tool** button in the application sidebar.

---

## 5. Platform-Specific Notes

### 5.1 File/folder browser dialogs

The tool uses **tkinter** file dialogs for browsing files and folders. On some Linux distributions, tkinter may not be installed by default. If the Browse buttons do not work:

**Ubuntu / Debian:**
```bash
sudo apt-get install python3-tk
```

**Fedora / RHEL:**
```bash
sudo dnf install python3-tkinter
```

**macOS:** tkinter is included with the Python from conda, so no additional installation is needed.

**Workaround:** If tkinter dialogs don't appear or open behind other windows, you can type or paste file/folder paths directly into the text input fields in the application — the Browse buttons are a convenience, not a requirement.

### 5.2 Display server (Linux)

The tkinter file dialogs require a display server (X11 or Wayland). If you are running on a headless server or via SSH without X-forwarding, the Browse buttons will not work. Use the text input fields to enter paths directly instead.

### 5.3 Port conflicts

If port 8501 is already in use, the launch script will attempt to kill the stale process. You can also specify a different port manually:

```bash
conda activate dpird_field_tool
streamlit run app/field_mapping_tool.py --server.port 8502
```

### 5.4 File paths

The tool works with absolute paths. When entering paths in the text input fields, use forward slashes (`/`) as path separators (the default on Linux and macOS).

---

## 6. Updating

To update the tool, replace the `app/field_mapping_tool.py` file with the new version. No reinstallation is needed unless the new version requires additional packages.

If new dependencies are required, rerun the installer:

```bash
./install_dpird_tool.sh
```

It will detect the existing environment, check for missing packages, and install only what's needed.

---

## 7. Uninstalling

Remove the conda environment and delete the tool folder:

```bash
conda env remove -n dpird_field_tool
rm -rf /path/to/DPIRD_Field_Mapping_Tool
```

---

## 8. Troubleshooting

**"conda not found"** — Ensure Anaconda/Miniconda is installed and `conda init` has been run for your shell. Restart your terminal after installation.

**White screen in browser** — A previous Streamlit session may still be running. Press Ctrl+C to stop it, then relaunch. Or kill it manually: `lsof -i :8501 -t | xargs kill -9`

**"Access blocked" on the map** — This occurs when basemap tile servers block localhost requests. Toggle the basemap **off** in the sidebar under Map Settings. Your orthomosaic provides full coverage.

**Browse button opens nothing** — See Section 5.1 above for tkinter installation. As a workaround, paste file paths directly into the text fields.

**rasterio/fiona import errors** — These packages require C libraries (GDAL, PROJ). Installing from conda-forge (as the installer does) handles these automatically. Avoid installing rasterio or fiona via pip on Linux unless you have the system libraries pre-installed.

**Permission denied on scripts** — Run `chmod +x install_dpird_tool.sh run_dpird_tool.sh` to make them executable.

---

## 9. Included Files Reference

| File | Purpose |
|------|---------|
| `install_dpird_tool.sh` | One-time setup: creates conda env and installs packages |
| `run_dpird_tool.sh` | Launches the tool (activates env, starts Streamlit, opens browser) |
| `app/field_mapping_tool.py` | Main application code |
| `bin/logo.png` | Organisation logo displayed in the sidebar (optional) |
| `INSTALL_LINUX_MACOS.md` | This documentation file |
| `README.txt` | Quick-start reference |

---

## 10. Author & Acknowledgements

**Author:** Bipul Neupane, PhD — Research Scientist, DPIRD

**Contributor** Bipul Neupane: [GitHub](https://github.com/bipulneupane).
