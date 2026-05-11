# DPIRD Field Mapping Tool

A desktop application for digitising and managing agricultural field trial plot boundaries over drone orthomosaic imagery. Built with [Streamlit](https://streamlit.io/) and Python geospatial libraries, it runs locally in your web browser with no cloud dependency.

Developed at the [Department of Primary Industries and Regional Development (DPIRD)](https://www.dpird.wa.gov.au/), Western Australia, as part of the [Australian Plant Phenomics Network (APPN)](https://www.plantphenomics.org.au/).

---

## Features

- **Generate Grid** — Create regular plot grids over drone orthomosaics by drawing a trial boundary and specifying banks, rows, buffer, and plot dimensions.
- **Edit Grid** — Interactive browser-based polygon editor with drag, vertex editing, multi-select, copy/paste, measurements, undo, and keyboard shortcuts.
- **Convert File** — Convert between Shapefile, GeoJSON, GeoPackage, and KML formats with optional CRS reprojection (GDA2020, GDA94, WGS 84, or custom EPSG).
- **Cropping Tool** — Crop rasters (orthophotos, DSMs, GeoTIFFs) to individual plot polygon boundaries, producing one file per plot.

All data is processed locally. No internet connection is required after installation.

---

## Quick Start

### Windows

1. Download and extract `DPIRD_Field_Mapping_Tool_windows_v1.6.0`.
2. Place [`Miniconda3-latest-Windows-x86_64.exe`](https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe) in the folder.
3. Double-click `Install_DPIRD_Tool.bat` and press `Y`.
4. Double-click `Run_DPIRD_Tool.bat` to launch.

### Linux / macOS

1. Download and extract `DPIRD_Field_Mapping_Tool_linux_v1.6.0`.
2. Ensure [Anaconda or Miniconda](https://docs.anaconda.com/miniconda/) is installed.
3. Run:
   ```bash
   chmod +x install_dpird_tool.sh run_dpird_tool.sh
   ./install_dpird_tool.sh
   ./run_dpird_tool.sh
   ```

The tool opens in your browser at [http://localhost:8501](http://localhost:8501).

---

## Repository Structure

```
├── DPIRD_Field_Mapping_Tool_windows_v1.6.0/   # Windows distribution
│   ├── app/
│   │   └── field_mapping_tool.py
│   ├── bin/
│   │   └── logo.png
│   ├── Install_DPIRD_Tool.bat
│   ├── Run_DPIRD_Tool.bat
│   └── readme.md
│
├── DPIRD_Field_Mapping_Tool_linux_v1.6.0/      # Linux / macOS distribution
│   ├── app/
│   │   └── field_mapping_tool.py
│   ├── bin/
│   │   └── logo.png
│   ├── install_dpird_tool.sh
│   ├── run_dpird_tool.sh
│   └── readme.md
│
├── LICENSE
└── README.md
```

The application code (`field_mapping_tool.py`) is identical across both distributions. The platform folders differ only in their installation and launch scripts.

---

## Requirements

| | Windows | Linux / macOS |
|---|---|---|
| **OS** | Windows 10+ (64-bit) | Ubuntu 20.04+, Fedora, macOS 11+ |
| **Python** | Bundled via Miniconda | User-installed Anaconda/Miniconda |
| **Disk space** | ~2 GB | ~2 GB |
| **Internet** | First-time setup only | First-time setup only |

### Dependencies

Installed automatically by the setup scripts:

**conda-forge:** numpy, pandas, geopandas, rasterio, fiona, shapely, pyproj, pillow, matplotlib, psutil

**pip:** streamlit, streamlit-folium, folium, leafmap, localtileserver, scooby

---

## Documentation

[DPIRD_Field_Mapping_Tool_Documentation.docx](https://github.com/appndpird/DPIRDFieldMappingTool/blob/main/DPIRD_Field_Mapping_Tool_Documentation.pdf) provides the full usage instructions for the tool.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Bipul Neupane, PhD**
Research Scientist, DPIRD Node
Australian Plant Phenomics Network (APPN)
Department of Primary Industries and Regional Development (DPIRD), Western Australia
[bipul.neupane@dpird.wa.gov.au](mailto:bipul.neupane@dpird.wa.gov.au)

## Contributor

Bipul Neupane: [Github](https://github.com/bipulneupane)

## Acknowledgements

The plot generation logic and parameters are inspired by FieldImageR and PlimanShiny Tools. The GUI was developed with the assistance of [Claude AI](https://claude.ai) by Anthropic. 
