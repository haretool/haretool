# Fabrique dist\Haretool.exe : tests, puis PyInstaller, puis audit et empreinte SHA-256.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests en échec" }

python outils\fabriquer_icone.py | Out-Null

python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin `
    --name Haretool `
    --icon haretool\icones\haretool.ico `
    --version-file outils\version.txt `
    --add-data "haretool\donnees;haretool\donnees" `
    --add-data "haretool\icones;haretool\icones" `
    --add-data "haretool\polices;haretool\polices" `
    --exclude-module tkinter --exclude-module UnityPy --exclude-module pytest --exclude-module PIL --exclude-module fontTools `
    lancer.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller en échec" }

$env:HARETOOL_AUDIT_EXE = "1"
python -m pytest -q tests\test_aucune_trace.py
if ($LASTEXITCODE -ne 0) { throw "audit en échec" }

$h = (Get-FileHash dist\Haretool.exe -Algorithm SHA256).Hash
"Haretool.exe  SHA-256 $h" | Tee-Object dist\SHA256.txt
