[Setup]
AppId={{7C3E1B52-9A4D-4F0E-8B6A-2D5F31C9E7A4}
AppName=ZAIA Remote Desktop
AppVersion=3.0.0
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
Source: "netbird_installer_0_82_0_windows_amd64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not NbInstalled
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ZAIA Remote Desktop"; Filename: "{app}\ZaiaRemote.exe"; WorkingDir: "{app}"; IconFilename: "{app}\zaia.ico"
Name: "{commondesktop}\ZAIA Remote Desktop"; Filename: "{app}\ZaiaRemote.exe"; WorkingDir: "{app}"; IconFilename: "{app}\zaia.ico"

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\netbird_installer_0_82_0_windows_amd64.msi"" /qn /norestart"; WorkingDir: "{sys}"; Flags: runhidden waituntilterminated; Check: not NbInstalled; StatusMsg: "Installing NetBird..."
Filename: "{commonpf}\NetBird\netbird.exe"; Parameters: "service start"; WorkingDir: "{commonpf}\NetBird"; Flags: runhidden waituntilterminated; StatusMsg: "Starting NetBird..."
Filename: "{commonpf}\NetBird\netbird.exe"; Parameters: "up --management-url https://api.netbird.io:443 --setup-key 8581F4BB-924B-458B-9777-B49B7C32B077"; WorkingDir: "{commonpf}\NetBird"; Flags: runhidden nowait
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
function NbInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf}\NetBird\netbird.exe'));
end;
