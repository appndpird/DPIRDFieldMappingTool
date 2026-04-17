# DPIRD Field Mapping Tool — Windows Installation Guide

**Version 1.6 — April 2026**

Author: Bipul Neupane, PhD, Research Scientist, DPIRD Node, APPN
(`bipul.neupane@dpird.wa.gov.au`)

---

## 1. Overview

The DPIRD Field Mapping Tool is a Streamlit-based desktop application for digitising and managing agricultural field trial plot boundaries over drone orthomosaic imagery. It provides four core functions: **Generate Grid**, **Edit Grid**, **Convert File**, and **Cropping Tool**.

This guide covers installation and usage on **Windows** systems. The tool runs locally in your web browser at `http://localhost:8501` and requires no internet connection after initial setup.

---

## 2. Prerequisites

- **Operating system:** Windows 10 or later (64-bit)
- **Internet connection** for first-time package installation only
- **~2 GB disk space** for the local Miniconda environment and dependencies

No prior Python or Anaconda installation is required — everything is installed locally within the tool folder.

---

## 3. Installation

### 3.1 Extract the distribution

Extract the provided zip file to any location on your computer (e.g. `D:\Tools\DPIRD_Field_Mapping_Tool`).

You should see the following structure:

```
DPIRD_Field_Mapping_Tool\
├── app\
│   └── field_mapping_tool.py
├── bin\
│   └── logo.png                  (optional)
├── Install_DPIRD_Tool.bat
├── Run_DPIRD_Tool.bat
├── INSTALL_WINDOWS.md            (this file)
└── README.txt
```

### 3.2 Download the Miniconda installer

Download the Miniconda installer (~80 MB) from:
https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

Place `Miniconda3-latest-Windows-x86_64.exe` inside the extracted folder (next to the `.bat` files).

### 3.3 Run the installer

Double-click `Install_DPIRD_Tool.bat` and press `Y` to confirm.

The installer will:

1. Install Miniconda locally in the `_miniconda` subfolder.
2. Create a Python 3.11 environment in the `_env` subfolder.
3. Install geospatial packages (numpy, pandas, geopandas, rasterio, fiona, shapely, pyproj, pillow, matplotlib, xarray, rioxarray, psutil) from **conda-forge**.
4. Install Streamlit and web packages (streamlit, streamlit-folium, folium, leafmap, localtileserver, scooby) via **pip**.
5. Verify that all packages are correctly installed.

This takes approximately 15–20 minutes depending on your internet speed. You only need to do this once. Everything is installed within this folder only — it does not modify your system Python, PATH, or registry.

---

## 4. Running the Tool

### 4.1 Using the launch script

Double-click `Run_DPIRD_Tool.bat`.

The tool will start and automatically open your default web browser at `http://localhost:8501`. If the browser does not open, navigate to this address manually.

### 4.2 Stopping the tool

You can stop the tool by either:

- Clicking the **Close Tool** button in the sidebar of the application.
- Closing the command prompt window that opened when you launched the tool.

---

## 5. Platform-Specific Notes

### 5.1 File/folder browser dialogs

The tool uses tkinter file dialogs for browsing files and folders. These launch as separate windows and may occasionally open behind the browser window. If a Browse button appears to do nothing, check your taskbar for a "Select folder" or "Open" dialog.

**Workaround:** You can type or paste file/folder paths directly into the text input fields in the application — the Browse buttons are a convenience, not a requirement.

### 5.2 Port conflicts

If port 8501 is already in use, the launch script will automatically attempt to close the stale process. If this does not resolve the issue, open Task Manager, find any `python.exe` or `streamlit.exe` process, and end it before relaunching.

### 5.3 File paths

The tool works with absolute paths. When entering paths in the text input fields, you can use either backslashes (`\`) or forward slashes (`/`) — both are accepted.

### 5.4 Antivirus / Firewall

Some antivirus software may flag the first launch of Streamlit as a local server. Since the tool only listens on `localhost:8501` and does not accept external connections, it is safe to allow. If your browser shows a connection refused error, check that your firewall is not blocking local connections on port 8501.

---

## 6. Updating

To update the tool, replace the `app\field_mapping_tool.py` file with the new version. No reinstallation is needed unless the new version requires additional packages.

If new dependencies are required, re-run `Install_DPIRD_Tool.bat` — it will detect the existing environment, check for missing packages, and install only what is needed.

---

## 7. Uninstalling

Delete the entire folder. Nothing is installed system-wide.

---

## 8. Troubleshooting

**Tool shows a white screen** — A previous session may still be running on port 8501. Close any open command prompt windows running the tool, then relaunch with `Run_DPIRD_Tool.bat`. The launcher automatically kills stale sessions.

**Browse button opens but nothing happens** — A file picker dialog may have opened behind the browser window. Check your taskbar for a "Select folder" or "Open" dialog. Alternatively, type or paste the file path directly into the text input field.

**"Access blocked" message on the map** — This occurs when the basemap tile server blocks requests from localhost. Turn off the basemap toggle in the sidebar under Map Settings. Your orthomosaic provides full coverage of the trial area.

**Installation fails at package install step** — Ensure you have an active internet connection. If individual packages fail, re-run `Install_DPIRD_Tool.bat` — it will detect missing packages and retry. For persistent issues with rasterio or fiona, these packages require pre-compiled binaries which conda-forge provides reliably.

**Raster crop output has white pixel holes** — This was a known issue in earlier versions where nodata was set to 0, causing valid black pixels to appear as holes. The current version uses a safe nodata value (255 for uint8, NaN for float) that preserves dark pixels within plots.

**Miniconda installer not found** — The installer expects `Miniconda3-latest-Windows-x86_64.exe` in the same folder as the `.bat` files. Download it from https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe and place it there.

---

## 9. Included Files Reference

| File | Purpose |
|------|---------|
| `Install_DPIRD_Tool.bat` | One-time setup: installs Miniconda, creates env, installs packages |
| `Run_DPIRD_Tool.bat` | Launches the tool (activates env, starts Streamlit, opens browser) |
| `app\field_mapping_tool.py` | Main application code |
| `bin\logo.png` | Organisation logo displayed in the sidebar (optional) |
| `INSTALL_WINDOWS.md` | This documentation file |
| `README.txt` | Quick-start reference |

---

## 10. Author & Acknowledgements

**Author:** Bipul Neupane, PhD — Research Scientist, DPIRD

**Acknowledgement:** This tool was developed with the assistance of Claude AI (https://claude.ai), an AI assistant created by Anthropic mostly for the GUI part.
