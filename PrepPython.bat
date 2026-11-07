@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set PYV=3.12.8
if not exist "python\python.exe" goto get
"python\python.exe" -c "import tkinter, PIL.ImageTk, pystray, mss, tkinterdnd2, av"
if not errorlevel 1 goto ready
echo Existing python folder is old or broken, rebuilding.
rd /s /q "python"
:get
mkdir "_lay" 2>nul
echo Downloading Python %PYV% parts from python.org ...
for %%m in (core exe lib tcltk) do if not exist "_lay\%%m.msi" curl.exe -L --fail -o "_lay\%%m.msi" https://www.python.org/ftp/python/%PYV%/amd64/%%m.msi
for %%m in (core exe lib tcltk) do if not exist "_lay\%%m.msi" goto fail
mkdir "python"
for %%m in (core exe lib tcltk) do start /wait "" msiexec /a "%CD%\_lay\%%m.msi" /qn TARGETDIR="%CD%\python"
del /q "python\*.msi" 2>nul
rd /s /q "_lay"
rd /s /q "python\Lib\test" 2>nul
:deps
if not exist "python\pythonw.exe" goto fail
"python\python.exe" -m ensurepip --upgrade
"python\python.exe" -m pip install --disable-pip-version-check --no-warn-script-location -r requirements.txt
if errorlevel 1 goto fail
"python\python.exe" -c "import tkinter, PIL.ImageTk, pystray, mss, tkinterdnd2, av"
if errorlevel 1 goto fail
for %%d in (idlelib turtledemo lib2to3 ensurepip test) do rd /s /q "python\Lib\%%d" 2>nul
for /d %%d in ("python\Lib\site-packages\pip*" "python\Lib\site-packages\setuptools*") do rd /s /q "%%d"
rd /s /q "python\tcl\tk8.6\demos" 2>nul
rd /s /q "python\Scripts" 2>nul
:ready
echo Python lite ready.
exit /b 0
:fail
echo FAILED. Download core.msi exe.msi lib.msi tcltk.msi from python.org/ftp/python/%PYV%/amd64/ into folder _lay, then run again.
exit /b 1
