# Fabrique le livrable : dist\Haretool.exe COMPILÉ en code machine (Nuitka, Python → C),
# sans bytecode Python à décompiler, docstrings retirées. Puis audit « aucune trace » et empreinte.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$version = "0.2.0"

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests en échec" }

python outils\fabriquer_icone.py | Out-Null

python -m nuitka --onefile --assume-yes-for-downloads `
    --enable-plugin=pyside6 `
    --windows-console-mode=disable --windows-uac-admin `
    --windows-icon-from-ico=haretool\icones\haretool.ico `
    --include-data-dir=haretool\donnees=haretool\donnees `
    --include-data-files=haretool\donnees\cartes.bin=haretool\donnees\cartes.bin `
    --include-data-dir=haretool\icones=haretool\icones `
    --include-data-dir=haretool\polices=haretool\polices `
    --python-flag=no_docstrings --python-flag=no_asserts `
    --nofollow-import-to=tkinter,UnityPy,pytest,PIL,fontTools `
    --onefile-tempdir-spec="{CACHE_DIR}\Haretool\$version" `
    --company-name=Haretool --product-name=Haretool --file-description=Haretool `
    --file-version=$version --product-version=$version `
    --output-dir=build-nuitka --output-filename=Haretool.exe `
    lancer.py
if ($LASTEXITCODE -ne 0) { throw "compilation en échec" }

New-Item -ItemType Directory -Force dist | Out-Null
Copy-Item build-nuitka\Haretool.exe dist\Haretool.exe -Force

$env:HARETOOL_AUDIT_EXE = "1"
python -m pytest -q tests\test_aucune_trace.py
if ($LASTEXITCODE -ne 0) { throw "audit en échec" }

$h = (Get-FileHash dist\Haretool.exe -Algorithm SHA256).Hash
"Haretool.exe  SHA-256 $h" | Out-File -Encoding ascii dist\SHA256.txt
Get-Content dist\SHA256.txt
