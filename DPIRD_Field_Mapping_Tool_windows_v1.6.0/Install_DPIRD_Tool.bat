@echo off
title DPIRD Field Mapping Tool - Setup
color 0A
echo.
echo  ================================================
echo    DPIRD Field Mapping Tool - First Time Setup
echo  ================================================
echo.

cd /d "%~dp0"

set "APP_DIR=%~dp0"
set "CONDA_DIR=%APP_DIR%_miniconda"
set "ENV_DIR=%APP_DIR%_env"
set "CONDA_EXE=%CONDA_DIR%\Scripts\conda.exe"
set "ACTIVATE=%CONDA_DIR%\Scripts\activate.bat"
set "PYTHON_EXE=%ENV_DIR%\python.exe"
set "STREAMLIT_EXE=%ENV_DIR%\Scripts\streamlit.exe"
set "MINICONDA_INSTALLER=Miniconda3-latest-Windows-x86_64.exe"
set "VERIFY=import numpy,pandas,PIL,shapely,pyproj,fiona,rasterio,geopandas,xarray,rioxarray,matplotlib,psutil,folium,streamlit,streamlit_folium,leafmap"

REM ---- Already fully installed? ----
if exist "%STREAMLIT_EXE%" (
    echo  Checking existing installation...
    "%PYTHON_EXE%" -c "%VERIFY%" 2>nul
    if not errorlevel 1 (
        echo  [OK] All packages present. Use "Run_DPIRD_Tool.bat" to launch.
        pause & exit /b
    )
    echo  Some packages missing. Will install them...
    goto :install_packages
)

REM ---- Check Miniconda installer ----
if not exist "%APP_DIR%%MINICONDA_INSTALLER%" (
    echo  ERROR: %MINICONDA_INSTALLER% not found!
    echo.
    echo  Download from:
    echo  https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
    echo.
    echo  Place it in: %APP_DIR%
    pause & exit /b 1
)

echo  This will install the tool and all dependencies locally.
echo  Internet connection required. Takes ~15-20 minutes.
echo  Everything is installed in this folder only.
echo.
set /p CONFIRM="  Proceed? (Y/N): "
if /i not "%CONFIRM%"=="Y" ( echo  Cancelled. & pause & exit /b )

REM ============ Step 1: Install Miniconda ============
if not exist "%CONDA_EXE%" (
    echo.
    echo  [1/3] Installing Miniconda locally...
    if exist "%CONDA_DIR%" (
        rmdir /s /q "%CONDA_DIR%" 2>nul
        timeout /t 2 /nobreak >nul
    )
    start /wait "" "%APP_DIR%%MINICONDA_INSTALLER%" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%CONDA_DIR%
    if not exist "%CONDA_EXE%" (
        echo  ERROR: Miniconda installation failed.
        pause & exit /b 1
    )
    echo         OK
) else (
    echo  [1/3] Miniconda already present.
)

echo        Accepting conda Terms of Service...
call "%ACTIVATE%" "%CONDA_DIR%"
call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >nul 2>&1
call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >nul 2>&1
call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 >nul 2>&1
echo         OK

REM ============ Step 2: Create environment ============
if not exist "%PYTHON_EXE%" (
    echo  [2/3] Creating Python 3.11 environment...
    call conda create -y -p "%ENV_DIR%" python=3.11
    if not exist "%ENV_DIR%\python.exe" (
        echo  ERROR: Environment creation failed.
        pause & exit /b 1
    )
    echo         OK
) else (
    echo  [2/3] Environment already exists.
)

REM ============ Step 3: Install packages ============
:install_packages
echo  [3/3] Installing packages...
echo        This takes several minutes. Please be patient.
echo.

call "%ACTIVATE%" "%ENV_DIR%"

echo        [conda] Core geospatial stack...
call conda install -y -c conda-forge --override-channels numpy pandas geopandas rasterio fiona shapely pyproj pillow matplotlib xarray rioxarray psutil

if errorlevel 1 (
    echo        conda had issues. Trying pip...
    pip install --no-warn-script-location numpy pandas pillow shapely pyproj rasterio fiona geopandas matplotlib xarray rioxarray psutil
)

echo.
echo        [pip] Streamlit and web packages...
pip install --no-warn-script-location streamlit streamlit-folium folium leafmap localtileserver scooby pyarmor

if errorlevel 1 (
    for %%p in (streamlit folium streamlit-folium leafmap localtileserver scooby pyarmor) do (
        pip install --no-warn-script-location %%p
    )
)

REM ============ Verify ============
echo.
echo  --- Verifying ---
echo.

set FAIL=0
for %%m in (numpy pandas PIL shapely pyproj fiona rasterio geopandas xarray rioxarray matplotlib psutil folium streamlit streamlit_folium leafmap) do (
    python -c "import %%m" 2>nul
    if errorlevel 1 (
        echo     %%m ... MISSING
        set FAIL=1
    ) else (
        echo     %%m ... OK
    )
)

if %FAIL%==1 (
    echo.
    echo  Final retry...
    pip install --no-warn-script-location numpy pandas pillow shapely pyproj rasterio fiona geopandas xarray rioxarray matplotlib psutil folium streamlit streamlit-folium leafmap localtileserver scooby
    python -c "%VERIFY%" 2>nul
    if errorlevel 1 (
        echo  ERROR: Some packages could not be installed.
        pause & exit /b 1
    )
)

echo.
echo  ================================================
echo    Installation complete!
echo    Double-click "Run_DPIRD_Tool.bat" to launch.
echo  ================================================
echo.
pause
