<#
    Builds the Windows program and its installer, from a clean checkout.

    Run in PowerShell from the desktop\ folder:

        .\packaging\build_windows.ps1

    Produces
      dist\TenPercentPharmacy\TenPercentPharmacy.exe   (the program)
      packaging\output\TenPercentPharmacy-Setup-1.0.0.exe   (the installer)
#>

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Python virtual environment" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt --quiet

Write-Host "==> Tests" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed — build stopped." }

Write-Host "==> Application icon" -ForegroundColor Cyan
.\.venv\Scripts\python.exe packaging\make_icon.py

Write-Host "==> Building the program" -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
.\.venv\Scripts\pyinstaller.exe packaging\pharmacy.spec --noconfirm --clean

Write-Host "==> Building the installer" -ForegroundColor Cyan
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc packaging\installer.iss
    Write-Host "Installer: packaging\output\" -ForegroundColor Green
} else {
    Write-Warning "Inno Setup 6 was not found, so only the program folder was built."
    Write-Warning "Install it from https://jrsoftware.org/isdl.php and run this again."
}

Write-Host "==> Done. Program: dist\TenPercentPharmacy\TenPercentPharmacy.exe" -ForegroundColor Green
