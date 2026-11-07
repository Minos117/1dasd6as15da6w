@echo off
cd /d "%~dp0"
if exist "python\python.exe" ("python\python.exe" MakeRelease.py %*) else (python MakeRelease.py %*)
pause
