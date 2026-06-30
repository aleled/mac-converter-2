; MAC Address Converter - Inno Setup Installer Script
; Created: December 15, 2025

#define MyAppName "MAC Address Converter"
#define MyAppVersion "2.5.1"
#define MyAppPublisher "Alejandro Lichtenfeld"
#define MyAppURL "https://github.com/aleled/mac-converter-2"
#define MyAppExeName "MAC-Converter.exe"
#define MyAppIcon "icon-v1.png"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={{8F9A3B2C-1D4E-5F6A-7B8C-9D0E1F2A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MAC-Converter
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=installer-output
OutputBaseFilename=MAC-Converter-Setup-v{#MyAppVersion}
; SetupIconFile={#MyAppIcon}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon-v1.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; v2.5.1: remove the pre-v2.4.0 Startup-folder shortcut. That installer
; created "MAC Address Converter.lnk" via its [Tasks]/[Icons] sections,
; and the v2.4.0+ in-app autostart writes a DIFFERENT filename
; ("MAC-Converter.lnk"), so users who upgraded ended up with both
; shortcuts firing at boot — double-launched. The app also sweeps these
; at runtime, but doing it during install closes the bug immediately for
; users who run the installer.
Type: files; Name: "{userstartup}\MAC Address Converter.lnk"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    SettingsPath := ExpandConstant('{userappdata}\mac-converter-2');
    if MsgBox('Do you want to remove application settings and preferences?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      if DirExists(SettingsPath) then
        DelTree(SettingsPath, True, True, True);
    end;
  end;
end;
