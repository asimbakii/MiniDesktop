# MiniDesktop kurulumu: Python 3.11+ bul (yoksa kur), sanal ortami olustur, paketleri yukle.
param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
$req = Join-Path $root 'requirements.txt'
$PyVersion = '3.11.9'

function Say($msg) { Write-Host "[MiniDesktop] $msg" }

# Bir python komutu 3.11+ mi? (Microsoft Store'un sahte python.exe kisayolu bos doner, elenir)
function Test-Python([string[]]$cmd) {
    try {
        $exe = $cmd[0]; $pre = @($cmd | Select-Object -Skip 1)
        $out = & $exe @pre -c "import sys; print(sys.executable if sys.version_info >= (3, 11) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path $out.Trim())) { return $out.Trim() }
    } catch {}
    return $null
}

function Find-Python {
    $candidates = @(
        @('py', '-3.11'), @('py', '-3'), @('python'), @('python3'),
        @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"),
        @("$env:ProgramFiles\Python311\python.exe")
    )
    foreach ($c in $candidates) {
        if ($c[0] -like '*\*' -and -not (Test-Path $c[0])) { continue }
        if ($c[0] -notlike '*\*' -and -not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $p = Test-Python $c
        if ($p) { return $p }
    }
    return $null
}

function Install-Python {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say "Python $PyVersion winget ile kuruluyor (yonetici izni gerekmez)..."
        winget install --exact --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0 -or (Find-Python)) { return }
        Say "winget basarisiz oldu, python.org yukleyicisi deneniyor..."
    }
    $url = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-amd64.exe"
    $exe = Join-Path $env:TEMP "python-$PyVersion-amd64.exe"
    Say "Indiriliyor: $url"
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
    Say "Python $PyVersion sessiz kuruluyor..."
    $p = Start-Process -FilePath $exe -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1', 'Include_test=0' -Wait -PassThru
    Remove-Item $exe -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { throw "Python yukleyicisi hata verdi (kod $($p.ExitCode))." }
}

# 1) Python
$python = Find-Python
if (-not $python) {
    Say 'Python 3.11 veya ustu bulunamadi.'
    Install-Python
    # Yeni PATH bu pencerede yok: bilinen kurulum yerlerine tekrar bak
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $python = Find-Python
    if (-not $python) { throw 'Python kuruldu ama bulunamadi. Bilgisayari yeniden baslatip tekrar dene.' }
}
Say "Python: $python"

# 2) Sanal ortam
if (-not (Test-Path $venvPy)) {
    Say 'Sanal ortam olusturuluyor (.venv)...'
    & $python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Sanal ortam olusturulamadi.' }
}

# 3) Paketler
Say 'Paketler yukleniyor/guncelleniyor...'
& $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $venvPy -m pip install --disable-pip-version-check -q -r $req
if ($LASTEXITCODE -ne 0) { throw 'Paketler yuklenemedi. Internet baglantini kontrol et.' }
Say 'Kurulum tamam.'
