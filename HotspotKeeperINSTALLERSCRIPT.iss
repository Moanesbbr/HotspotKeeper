; HotspotKeeper Installer Script
; Inno Setup Script

#define MyAppName "HotspotKeeper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Moanesbbr"
#define MyAppURL "https://github.com/Moanesbbr/HotspotKeeper"
#define MyAppExeName "HotspotKeeper.exe"

[Setup]
; App Identity
AppId={{B39065C2-5018-432D-8A76-D4F082EF284D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Privileges - REQUIRED for hotspot management
PrivilegesRequired=admin

; Output
OutputDir=output
OutputBaseFilename=HotspotKeeper-Setup-{#MyAppVersion}
SetupIconFile=C:\dev\personal\auto-hotspot\assets\icon.ico

; Compression
Compression=lzma2
SolidCompression=yes

; UI
WizardStyle=modern
DisableProgramGroupPage=yes

; License
LicenseFile=C:\dev\personal\auto-hotspot\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start with Windows"; GroupDescription: "Additional options:"

[Files]
Source: "C:\dev\personal\auto-hotspot\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\dev\personal\auto-hotspot\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\dev\personal\auto-hotspot\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\dev\personal\auto-hotspot\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop Icon (checked by default)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Startup (optional)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Run the app after installation with admin privileges
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent shellexec

[Code]
// Custom message for admin requirement
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsAdminInstallMode then
  begin
    MsgBox('HotspotKeeper requires administrator privileges to manage Windows Mobile Hotspot.' + #13#10#13#10 + 
           'Please run the installer as Administrator.', mbError, MB_OK);
    Result := False;
  end;
end;

// Run the app as administrator after installation
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // App will request admin privileges automatically via its run_as_admin() function
    // No need to force elevation here since the app handles it
  end;
end;
