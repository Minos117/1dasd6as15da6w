@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0python\pythonw.exe" (
  start "" "%~dp0python\pythonw.exe" "%~dp0ZaiaRemote.py" %*
) else (
  where pythonw >nul 2>nul
  if errorlevel 1 (echo Python not found. Run PrepPython.bat first. & pause & exit /b 1)
  python -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt"
  start "" pythonw "%~dp0ZaiaRemote.py" %*
)
exit /b 0
