"""Outil de construction (non embarqué) : extrait des fichiers du jeu installés
les données dont Haretool a besoin, et les écrit dans haretool/donnees/.

- cartes.bin : pour chaque carte, les cases où l'on marche et celles qui
  bloquent la vue. Depuis la mise à jour du 06/10/2026, un combat se joue sur
  une carte de combat à part, dont le champ « mov » dit à lui seul si une case
  est jouable.
- monstres_harebourg.json : identifiants du Comte Harebourg (donjon et Songes).
- sorts_sans_ldv.json : sorts dont aucun niveau ne demande la ligne de vue
  (drapeau de valeur 4 à 0 sur tous les niveaux, portée max >= 1).

Usage : python outils/extraire_donnees.py [dossier Content du jeu]
Format de cartes.bin (compressé zlib) : "HTCB", nombre de cartes (u32), puis
par carte : id (u32), 70 octets « marchable », 70 octets « bloque la vue »
(un bit par case, case n = octet n // 8, bit n % 8).
"""
import json
import os
import struct
import sys
import time
import warnings
import zlib
from pathlib import Path

import UnityPy

warnings.filterwarnings("ignore")
UnityPy.config.FALLBACK_UNITY_VERSION = "6000.3.16f1"

SORTIE = Path(__file__).resolve().parent.parent / "haretool" / "donnees"
CASES = 560
DRAPEAU_LDV = 4


def contenu_par_defaut() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Ankama" / "Dofus-dofus3" / "Dofus_Data" / "StreamingAssets" / "Content"


def bits(valeurs) -> bytes:
    sortie = bytearray(CASES // 8)
    for n, v in enumerate(valeurs):
        if v:
            sortie[n // 8] |= 1 << (n % 8)
    return bytes(sortie)


def lire_textes(chemin: Path) -> dict[int, str]:
    """Textes du jeu : en-tête de 3 octets, nombre (u32), table (id, position), chaînes préfixées."""
    b = chemin.read_bytes()
    n = struct.unpack_from("<I", b, 3)[0]
    textes = {}
    for i in range(n):
        ident, pos = struct.unpack_from("<II", b, 7 + 8 * i)
        longueur = decalage = 0
        while True:
            c = b[pos]
            pos += 1
            longueur |= (c & 0x7F) << decalage
            decalage += 7
            if c < 0x80:
                break
        textes[ident] = b[pos:pos + longueur].decode("utf-8", "replace")
    return textes


def entrees(paquet: Path):
    env = UnityPy.load(str(paquet))
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            yield o.read_typetree()


def extraire_cartes(contenu: Path) -> int:
    cartes = {}
    paquets = sorted((contenu / "Map" / "Data").glob("mapdata_assets_world_*.bundle"))
    debut = time.time()
    for i, p in enumerate(paquets):
        for t in entrees(p):
            cellules = t.get("cellsData")
            if not cellules or len(cellules) != CASES:
                continue
            par_numero = sorted(cellules, key=lambda c: c["cellNumber"])
            if [c["cellNumber"] for c in par_numero] != list(range(CASES)):
                continue
            cartes[int(t["id"])] = (bits(c["mov"] for c in par_numero),
                                    bits(not c["los"] for c in par_numero))
        if i % 50 == 0:
            print(f"  {i}/{len(paquets)} paquets, {len(cartes)} cartes, {time.time() - debut:.0f} s")
    brut = b"HTCB" + struct.pack("<I", len(cartes))
    for ident in sorted(cartes):
        marche, vue = cartes[ident]
        brut += struct.pack("<I", ident) + marche + vue
    (SORTIE / "cartes.bin").write_bytes(zlib.compress(brut, 9))
    return len(cartes)


def extraire_monstres(contenu: Path, textes: dict[int, str]) -> list[dict]:
    trouves = []
    for t in entrees(contenu / "Data" / "data_assets_monstersdataroot.asset.bundle"):
        for r in t.get("references", {}).get("RefIds", []):
            d = r.get("data", {})
            nom = textes.get(d.get("nameId"), "")
            if nom.startswith("Comte Harebourg"):
                trouves.append({"id": d["id"], "nom": nom})
    (SORTIE / "monstres_harebourg.json").write_text(json.dumps(trouves, ensure_ascii=False, indent=1), "utf-8")
    return trouves


def extraire_sorts(contenu: Path) -> int:
    par_sort: dict[int, list[tuple[int, int]]] = {}
    for t in entrees(contenu / "Data" / "data_assets_spelllevelsdataroot.asset.bundle"):
        for r in t.get("references", {}).get("RefIds", []):
            d = r.get("data", {})
            if "spellId" in d:
                par_sort.setdefault(d["spellId"], []).append((d.get("m_flags", 0), d.get("range", 0)))
    sans = sorted(s for s, niveaux in par_sort.items()
                  if all(not f & DRAPEAU_LDV for f, _ in niveaux) and max(p for _, p in niveaux) >= 1)
    (SORTIE / "sorts_sans_ldv.json").write_text(json.dumps(sans), "utf-8")
    return len(sans)


def main() -> None:
    contenu = Path(sys.argv[1]) if len(sys.argv) > 1 else contenu_par_defaut()
    textes = lire_textes(contenu / "I18n" / "fr.bin")
    print("monstres :", extraire_monstres(contenu, textes))
    print("sorts sans ligne de vue :", extraire_sorts(contenu))
    print("cartes :", extraire_cartes(contenu))
    print("taille cartes.bin :", (SORTIE / "cartes.bin").stat().st_size, "octets")


if __name__ == "__main__":
    main()
