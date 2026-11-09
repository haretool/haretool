# Fabrique le livrable : dist\Haretool.exe COMPILÉ en code machine (Nuitka, Python → C),
# sans bytecode Python à décompiler, docstrings retirées. Puis audit « aucune trace » et empreinte.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$version = "0.2.0"

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests en échec" }

python outils\fabriquer_icone.py | Out-Null

python -m nuitka --standalone --assume-yes-for-downloads `
    --enable-plugin=pyside6 `
    --windows-console-mode=disable --windows-uac-admin `
    --windows-icon-from-ico=haretool\icones\haretool.ico `
    --include-data-dir=haretool\donnees=haretool\donnees `
    --include-data-files=haretool\donnees\cartes.bin=haretool\donnees\cartes.bin `
    --include-data-dir=haretool\icones=haretool\icones `
    --include-data-dir=haretool\polices=haretool\polices `
    --python-flag=no_docstrings --python-flag=no_asserts `
    --nofollow-import-to=tkinter,UnityPy,pytest,PIL,fontTools `
    --company-name=Haretool --product-name=Haretool --file-description=Haretool `
    --file-version=$version --product-version=$version `
    --output-dir=build-dossier --output-filename=Haretool.exe `
    lancer.py
if ($LASTEXITCODE -ne 0) { throw "compilation en échec" }

# livrable « dossier » : pas d'exe qui se décompresse lui-même (moins de fausses alertes)
$sortie = "dist-dossier\Haretool"
if (Test-Path dist-dossier) { Remove-Item -Recurse -Force dist-dossier }
New-Item -ItemType Directory -Force dist-dossier | Out-Null
Copy-Item -Recurse build-dossier\lancer.dist $sortie
Copy-Item outils\LISEZ-MOI.txt $sortie
Compress-Archive -Path $sortie -DestinationPath dist-dossier\Haretool-$version.zip -Force
$h = (Get-FileHash $sortie\Haretool.exe -Algorithm SHA256).Hash
$z = (Get-FileHash dist-dossier\Haretool-$version.zip -Algorithm SHA256).Hash
"Haretool.exe  SHA-256 $h`nHaretool-$version.zip  SHA-256 $z" | Out-File -Encoding ascii dist-dossier\SHA256.txt
Get-Content dist-dossier\SHA256.txt
