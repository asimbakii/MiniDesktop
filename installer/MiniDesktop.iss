; MiniDesktop kurulum betiği (Inno Setup 6)
; Derleme: tools\build.ps1  (önce PyInstaller ile dist\MiniDesktop oluşturur)

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "MiniDesktop"
#define AppExe "MiniDesktop.exe"

[Setup]
AppId={{6F1D2B7A-4C3E-4E8B-9A57-2D1C0B3E9F41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=MiniDesktop
VersionInfoVersion={#AppVersion}
; Kullanıcı kurulumu: yönetici izni gerekmez
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=MiniDesktop-Setup-{#AppVersion}
SetupIconFile=..\app\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Güncelleme sırasında çalışan MiniDesktop'ı kapat
CloseApplications=force
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.AutoStart=Windows açılışında başlat (sistem tepsisinde)
english.AutoStart=Start with Windows (in system tray)
turkish.DesktopIcon=Masaüstü kısayolu oluştur
english.DesktopIcon=Create a desktop shortcut
turkish.LaunchApp=MiniDesktop'ı şimdi başlat
english.LaunchApp=Launch MiniDesktop now
turkish.RemoveData=MiniDesktop ayarlarını ve verilerini de silmek ister misin?%n(Eşli tabletler, Discord bağlantıları, komut ve snippet ayarları)%n%nTekrar kuracaksan "Hayır" de.
english.RemoveData=Also delete MiniDesktop settings and data?%n(Paired tablets, Discord connections, commands and snippets)%n%nChoose "No" if you plan to reinstall.

[Tasks]
Name: "autostart"; Description: "{cm:AutoStart}"
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\MiniDesktop\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Çalışan sunucuyu durdur ve Claude Code hook'larını kaldır
Filename: "{app}\{#AppExe}"; Parameters: "--shutdown"; Flags: runhidden waituntilterminated; RunOnceId: "StopServer"
Filename: "{app}\{#AppExe}"; Parameters: "--uninstall-hooks"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveHooks"
Filename: "{cmd}"; Parameters: "/c taskkill /f /im {#AppExe} >nul 2>&1"; Flags: runhidden waituntilterminated; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Güncelleme/yeniden kurulum: dosyalar kilitli kalmasın diye çalışan MiniDesktop'ı önce kapat
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Exe: String;
begin
  Exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(Exe) then
    Exec(Exe, '--shutdown', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{cmd}'), '/c taskkill /f /im {#AppExe} >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(800);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if MsgBox(CustomMessage('RemoveData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\MiniDesktop'), True, True, True);
end;
