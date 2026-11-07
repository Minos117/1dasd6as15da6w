@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set CSC=%windir%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%windir%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:winexe /out:ZaiaRemote.exe /win32icon:zaia.ico Launcher.cs
exit /b %errorlevel%
