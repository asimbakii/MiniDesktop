# MiniDesktop paketleme: PyInstaller ile exe, Inno Setup ile MiniDesktop-Setup.exe uretir.
#   powershell -ExecutionPolicy Bypass -File tools\build.ps1
param([switch]$NoInstaller)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
function Say($m) { Write-Host "[build] $m" -ForegroundColor Cyan }

# 1) Ortam
if (-not (Test-Path $py)) { & (Join-Path $PSScriptRoot 'setup.ps1') }
Say 'Derleme paketleri yukleniyor...'
& $py -m pip install --disable-pip-version-check -q -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'pip install basarisiz' }

# 2) Surum (installer ve exe icin)
$version = (Get-Content (Join-Path $root 'VERSION') -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $version) { $version = '1.0.0' }
Say "Surum: $version"

# 3) PyInstaller
$dist = Join-Path $root 'dist'
$work = Join-Path $root 'build\pyinstaller'
Remove-Item (Join-Path $dist 'MiniDesktop') -Recurse -Force -ErrorAction SilentlyContinue
Say 'PyInstaller calisiyor (birkac dakika surebilir)...'
& $py -m PyInstaller --noconfirm --clean --log-level WARN `
    --windowed --name MiniDesktop `
    --icon (Join-Path $root 'app\icon.ico') `
    --distpath $dist --workpath $work --specpath (Join-Path $root 'build') `
    --paths (Join-Path $root 'server') --paths (Join-Path $root 'app') `
    --add-data "$(Join-Path $root 'web');web" `
    --add-data "$(Join-Path $root 'server\admin.html');server" `
    --add-data "$(Join-Path $root 'app\icon.ico');app" `
    --collect-all winrt `
    --collect-submodules uvicorn `
    --collect-submodules pycaw `
    --hidden-import pystray._win32 `
    --hidden-import main `
    --hidden-import control `
    (Join-Path $root 'app\launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller basarisiz' }

# 4) Discord Social SDK koprusu (derlenmisse pakete ekle)
$bridge = Join-Path $root 'bridge\build\dcbridge.exe'
if (Test-Path $bridge) {
    $dst = Join-Path $dist 'MiniDesktop\bridge'
    New-Item -ItemType Directory -Force $dst | Out-Null
    Copy-Item $bridge $dst
    Copy-Item (Join-Path $root 'bridge\build\discord_partner_sdk.dll') $dst
    # SDK'nın açık kaynak lisans bildirimleri DLL ile birlikte dağıtılmalı
    $notices = Get-ChildItem (Join-Path $root 'bridge\sdk') -Recurse -Filter 'License-Notices.txt' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($notices) { Copy-Item $notices.FullName (Join-Path $dst 'Discord-Social-SDK-License-Notices.txt') }
    Say 'Discord Social SDK koprusu eklendi.'
} else {
    Say 'Not: bridge\build\dcbridge.exe yok; arkadas listesi ozelligi pakette olmayacak (bridge\derle.bat).'
}

# 5) Inno Setup
if ($NoInstaller) { Say "Tamam: $dist\MiniDesktop\MiniDesktop.exe"; return }
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup bulunamadi: winget install JRSoftware.InnoSetup' }
Say 'Kurulum dosyasi olusturuluyor...'
& $iscc /Q "/DAppVersion=$version" (Join-Path $root 'installer\MiniDesktop.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup basarisiz' }
Say "Tamam: $dist\MiniDesktop-Setup-$version.exe"
