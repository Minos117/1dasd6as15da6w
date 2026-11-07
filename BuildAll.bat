@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call PrepPython.bat
if errorlevel 1 goto fail
call BuildExe.bat
if errorlevel 1 goto fail
if exist "ZeroTierOne.msi" goto ztok
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest 'https://download.zerotier.com/dist/ZeroTier%%20One.msi' -OutFile ZeroTierOne.msi"
if errorlevel 1 echo Download ZeroTier One.msi yourself, rename to ZeroTierOne.msi, put here. & goto fail
:ztok
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" echo Inno Setup 6 not found. & goto fail
"%ISCC%" ZaiaRemoteSetup.iss
if errorlevel 1 goto fail
echo Done. See Output\ZaiaRemoteSetup.exe
pause
exit /b 0
:fail
echo.
echo BUILD FAILED. Read the messages above.
pause
exit /b 1
