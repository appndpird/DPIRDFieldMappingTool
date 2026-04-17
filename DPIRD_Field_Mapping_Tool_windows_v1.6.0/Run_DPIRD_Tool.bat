@echo off
title DPIRD Field Mapping Tool
color 0B

cd /d "%~dp0"

set "APP_DIR=%~dp0"
set "ENV_DIR=%APP_DIR%_env"
set "PYTHON_EXE=%ENV_DIR%\python.exe"
set "STREAMLIT_EXE=%ENV_DIR%\Scripts\streamlit.exe"
set "APP_FILE=%APP_DIR%app\field_mapping_tool.py"
set "VERIFY=import numpy,pandas,PIL,shapely,pyproj,fiona,rasterio,geopandas,folium,streamlit,streamlit_folium,leafmap"

REM ---- Check installation ----
if not exist "%STREAMLIT_EXE%" (
    echo.
    echo  Not installed. Running installer...
    call "%APP_DIR%Install_DPIRD_Tool.bat"
    if not exist "%STREAMLIT_EXE%" (
        echo  Installation failed.
        pause
        exit /b 1
    )
)

REM ---- Kill stale process on port 8501 ----
netstat -aon 2>nul | findstr ":8501.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  Closing previous session on port 8501...
    for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":8501.*LISTENING"') do (
        taskkill /f /pid %%p >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

REM ---- Clear stale Streamlit cache ----
if exist "%USERPROFILE%\.streamlit\cache" rmdir /s /q "%USERPROFILE%\.streamlit\cache" 2>nul

REM ---- Dependency check ----
"%PYTHON_EXE%" -c "%VERIFY%" 2>nul
if errorlevel 1 (
    echo  Packages missing. Running installer...
    call "%APP_DIR%Install_DPIRD_Tool.bat"
    "%PYTHON_EXE%" -c "%VERIFY%" 2>nul
    if errorlevel 1 (
        echo  ERROR: Dependencies missing.
        pause
        exit /b 1
    )
)

echo.
echo  ============================================
echo    DPIRD Field Mapping Tool
echo    Starting...
echo  ============================================
echo.
echo  To stop: use the Close Tool button in the
echo  sidebar, or close this window.
echo.

REM ---- Open browser after delay ----
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8501"

REM ---- Launch Streamlit DIRECTLY on field_mapping_tool.py ----
"%STREAMLIT_EXE%" run "%APP_FILE%" --server.headless true --browser.gatherUsageStats false --global.showWarningOnDirectExecution false --server.port 8501

echo.
echo  Application closed.
pause
