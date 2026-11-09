"""Garde : aucun mot interdit dans les fichiers suivis par git, ni dans l'exe fabriqué.

Les mots sont stockés à l'envers pour que ce fichier ne se signale pas lui-même.
"""
import os
import re
import subprocess
import zlib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
BARRE = chr(92)
INTERDITS = [m[::-1] for m in ("inmo", "adirf", "tcejni", "pc2li", "kooh", "inmo" + BARRE + ":f")]

# Dans l'exe entier (bibliothèques comprises), on cherche des MOTS ENTIERS : les
# bibliothèques contiennent des noms de jours, de fabricants… On cherche aussi le
# chemin du compte Windows de la machine de fabrication. Seul contexte toléré : un
# symbole du moteur C++ de Microsoft (« ... callsig »).
EXE_MOTS = [m[::-1] for m in ("inmo", "adirf", "pc2li")]
EXE_CHEMINS = [m[::-1] for m in ("inmo" + BARRE + ":f", "ruetasilitu" + BARRE + "sresu")]
TOLERE = re.compile(re.escape(EXE_MOTS[0]) + " callsig")


BINAIRES = {".ttf", ".png", ".ico", ".bin"}


def traces_exe(texte: str) -> list[str]:
    bas = TOLERE.sub("", texte.lower())
    sortie = [m for m in EXE_MOTS if re.search(r"(?<![a-z])" + m + r"(?![a-z])", bas)]
    return sortie + [m for m in EXE_CHEMINS if m in bas]


def fichiers_suivis():
    sortie = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=RACINE, capture_output=True, text=True, check=True).stdout
    return [RACINE / l for l in sortie.splitlines() if l]


def mots_trouves(texte: str, mots=INTERDITS):
    bas = texte.lower()
    return [m for m in mots if m in bas]


def test_traces_exe_mots_entiers():
    m = EXE_MOTS[0]
    assert traces_exe("fri" + "day " + m + "tel " + m + " callsig") == []
    assert traces_exe("x " + m.upper() + " y") == [m]
    assert traces_exe("c:" + BARRE + EXE_CHEMINS[1] + BARRE + "appdata") == [EXE_CHEMINS[1]]


def test_aucun_mot_interdit():
    fautes = {}
    for f in fichiers_suivis():
        if not f.is_file():
            continue
        contenu = f.read_bytes()
        if f.suffix.lower() in BINAIRES:   # noms de glyphes, pixels… : règle de l'exe
            trouves = traces_exe(contenu.decode("latin-1")) + mots_trouves(f.name)
        else:
            trouves = mots_trouves(contenu.decode("utf-8", "ignore")) + mots_trouves(f.name)
        if trouves:
            fautes[str(f.relative_to(RACINE))] = trouves
    assert fautes == {}


def _contenus_exe(exe: Path):
    """(nom, octets) de tout ce que l'exe contient, archives Python décompressées.

    Exe compilé (Nuitka) : l'exe livré + chaque fichier du dossier autonome dont il est fait
    (build-nuitka/lancer.dist), le code de l'outil étant compilé dans le binaire principal."""
    yield "exe", exe.read_bytes()
    autonome = RACINE / "build-nuitka" / "lancer.dist"
    if autonome.is_dir():
        for f in sorted(autonome.rglob("*")):
            if f.is_file():
                yield f.relative_to(autonome).as_posix(), f.read_bytes()
        return
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    archive = CArchiveReader(str(exe))
    for nom in archive.toc:
        try:
            donnees = archive.extract(nom)
        except (zlib.error, ValueError, KeyError):
            continue
        if not donnees:
            continue
        yield nom, donnees
        if nom.startswith("PYZ"):
            chemin = RACINE / "build" / "audit.pyz"
            chemin.parent.mkdir(exist_ok=True)
            chemin.write_bytes(donnees)
            pyz = ZlibArchiveReader(str(chemin))
            for module in pyz.toc:
                try:
                    yield "pyz:" + module, pyz.extract(module, raw=True)
                except (zlib.error, ValueError, KeyError, TypeError):
                    continue


@pytest.mark.skipif(os.environ.get("HARETOOL_AUDIT_EXE") != "1", reason="audit de l'exe : construire.ps1")
def test_exe_sans_trace():
    exe = RACINE / "dist" / "Haretool.exe"
    assert exe.is_file()
    fautes = {}
    vus = 0
    noms = []
    for nom, donnees in _contenus_exe(exe):
        vus += 1
        noms.append(nom.replace(BARRE, "/"))
        texte = donnees.decode("latin-1") + donnees.decode("utf-16-le", "ignore")
        if nom.startswith("pyz:haretool"):
            trouves = mots_trouves(texte) + mots_trouves(nom)
        else:
            trouves = traces_exe(texte) + traces_exe(nom)
        if trouves:
            fautes[nom] = sorted(set(trouves))
    assert vus > (50 if (RACINE / "build-nuitka" / "lancer.dist").is_dir() else 100)   # l'exe a bien été ouvert
    for attendu in ("haretool/polices/Outfit.ttf", "haretool/polices/LISEZMOI.txt",
                    "haretool/icones/interrupteur-oui.svg",
                    "haretool/icones/coiffe.png", "haretool/donnees/cartes.bin"):
        assert attendu in noms, attendu
    assert fautes == {}
