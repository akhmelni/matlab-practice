@echo off
rem Start the MATLAB Practice app (Windows). Opens it in your browser.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. See INSTALL.md.
  pause
  exit /b 1
)
uv run practice %*
if errorlevel 1 pause
