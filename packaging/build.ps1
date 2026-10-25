# Build WispSign: zsign -> error codes -> notices -> UI -> PyInstaller -> installer.
# Outputs: dist\WispSign\WispSign.exe and dist\WispSign-Setup-<version>.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

function Invoke-Step([string]$label, [scriptblock]$step) {
    Write-Host "==> $label"
    & $step
    if ($LASTEXITCODE -ne 0) { throw "$label failed (exit $LASTEXITCODE)" }
}

Invoke-Step "fetch zsign" { & $python packaging/fetch_zsign.py }
Invoke-Step "export error codes" { & $python packaging/export_codes.py }
Invoke-Step "third-party notices" { & $python packaging/third_party.py notices build/notices/THIRD_PARTY_NOTICES.txt }
Invoke-Step "build UI" {
    Push-Location ui
    try { npm ci; if ($LASTEXITCODE -eq 0) { npm run build } } finally { Pop-Location }
}
Invoke-Step "PyInstaller" { & $python -m PyInstaller packaging/wispsign.spec --noconfirm --distpath dist --workpath build }

$version = (& $python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    foreach ($candidate in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $candidate) { $iscc = Get-Item $candidate; break }
    }
}
if ($iscc) {
    $isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
    Invoke-Step "Inno Setup" { & $isccPath "/DAppVersion=$version" packaging/installer.iss }
} else {
    Write-Warning "Inno Setup (iscc) not found - skipping the installer step. Only dist\WispSign\WispSign.exe was built."
}
Write-Host "Done. Version $version"
