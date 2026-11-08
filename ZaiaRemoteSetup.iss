[Setup]
AppId={{7C3E1B52-9A4D-4F0E-8B6A-2D5F31C9E7A4}
AppName=ZAIA Remote Desktop
AppVersion=2.0.1
DefaultDirName={autopf}\ZaiaRemote
DefaultGroupName=ZAIA Remote Desktop
SetupIconFile=zaia.ico
UninstallDisplayIcon={app}\zaia.ico
OutputDir=Output
OutputBaseFilename=ZaiaRemoteSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"

[Files]
Source: "ZaiaRemote.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "ZaiaRemote.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "zaia.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "zaia_logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "ZeroTierOne.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not ZtInstalled
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ZAIA Remote Desktop"; Filename: "{app}\ZaiaRemote.exe"; WorkingDir: "{app}"; IconFilename: "{app}\zaia.ico"
Name: "{commondesktop}\ZAIA Remote Desktop"; Filename: "{app}\ZaiaRemote.exe"; WorkingDir: "{app}"; IconFilename: "{app}\zaia.ico"

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\ZeroTierOne.msi"" /qn /norestart"; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated; Check: not ZtInstalled; StatusMsg: "Installing ZeroTier..."
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$f='{commonappdata}\ZeroTier\One\authtoken.secret'; for($i=0;$i -lt 40 -and !(Test-Path $f);$i++){{Start-Sleep 1}; if(Test-Path $f){{icacls $f /grant '*S-1-5-32-545:R'}"""; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated; StatusMsg: "Setting ZeroTier permission..."
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""ZAIA Remote"""; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""ZAIA Remote"" dir=in action=allow protocol=UDP localport=47101 profile=any"; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""ZAIA Remote"" dir=in action=allow protocol=TCP localport=47102 profile=any"; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated
Filename: "schtasks.exe"; Parameters: "/Create /TN ""ZAIA Remote"" /TR ""\""{app}\python\pythonw.exe\"" \""{app}\ZaiaRemote.py\"" --silent"" /SC ONLOGON /RU ""BUILTIN\Users"" /RL HIGHEST /F"; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Set-ScheduledTask -TaskName 'ZAIA Remote' -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)"""; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated; StatusMsg: "Setting startup task..."
Filename: "{app}\ZaiaRemote.exe"; WorkingDir: "{app}"; Description: "เปิดโปรแกรมทันที"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""ZAIA Remote"" /F"; RunOnceId: "ZaiaTask"; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""ZAIA Remote"""; RunOnceId: "ZaiaFw"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"

[Code]
function ZtInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf}\ZeroTier\One\zerotier-cli.bat'));
end;
