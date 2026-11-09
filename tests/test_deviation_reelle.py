"""Chaque sort lancé dans les vraies captures : la case CLIQUÉE (message du client)
et la case d'ARRIVÉE (réponse du serveur) donnent la déviation réelle. Haretool doit la prévoir
pour TOUS les sorts (confusion envoyée par le jeu + 1 quart horaire par ligne au contact)."""
import json
from pathlib import Path

import pytest

from haretool.combat import EtatCompte, lire
from haretool.confusion import tranche_de, quarts_depuis_effet
from haretool.flux import Flux
from haretool.grille import vers_uv
from haretool.protobuf import champs
from haretool.protocole import Protocole, EMBARQUE

FIXTURES = Path(__file__).parent / "fixtures"
if not (FIXTURES / "persos.json").is_file():
    pytest.skip("captures réelles non publiées (données de joueurs)", allow_module_level=True)
CAPTURES = ["songe-2026-11-09.json", "songe-seul-2026-11-09.json", "songe-seul-limite-2026-11-09.json",
            "songe-bas-pv-2026-11-09.json", "songe-perte-pv-2026-11-09.json", "songe-melee-2026-11-09.json",
            "songe-melee-zero-2026-11-09.json"]


def _deviation(moi, clic, arrivee):
    a, c, r = vers_uv(moi), vers_uv(clic), vers_uv(arrivee)
    if None in (a, c, r):          # sort lancé sur une entité (pas de case)
        return None
    d, cible = (c[0] - a[0], c[1] - a[1]), (r[0] - a[0], r[1] - a[1])
    for k in range(4):
        if d == cible:
            return k
        d = (-d[1], d[0])
    return None


def sorts(nom_fichier):
    """(prévu, réel) pour chaque sort du perso suivi, flux par flux."""
    paquets = json.loads((FIXTURES / nom_fichier).read_text())["paquets"]
    for flux_id in sorted({p["flux"] for p in paquets}):
        flux, attente = {}, None
        e = EtatCompte(Protocole.depuis_fichier(EMBARQUE), est_harebourg=lambda m: True)
        for p in paquets:
            if p["flux"] != flux_id:
                continue
            for nom, valeur in flux.setdefault(p["sens"], Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
                if p["sens"].startswith("client"):
                    if nom == "jsr":
                        m = champs(valeur)
                        attente = (lire(m, [1]), lire(m, [2]))
                    continue
                if nom == "jsq" and attente and e.moi:
                    m = champs(valeur)
                    from haretool.combat import _id
                    if (_id(lire(m, [36])) == e.moi and lire(m, [2, 2, 2]) == attente[0]
                            and lire(m, [2, 5]) is not None):
                        moi, arrivee = e.positions.get(e.moi), lire(m, [2, 5])
                        t = tranche_de(e)
                        reel = _deviation(moi, attente[1], arrivee) if moi not in (attente[1], arrivee) else None
                        if reel is not None and t is not None:
                            yield (t + e.lignes_melee) % 4, reel
                        attente = None
                e.appliquer(nom, valeur, p["t"])


@pytest.mark.parametrize("nom_fichier", CAPTURES)
def test_chaque_sort_prevu(nom_fichier):
    resultats = list(sorts(nom_fichier))
    assert resultats, "aucun sort trouvé"
    assert all(prevu == reel for prevu, reel in resultats), resultats


def test_unites_des_effets_de_confusion():
    assert quarts_depuis_effet(770, 270) == 3      # 270° horaire
    assert quarts_depuis_effet(773, 90) == 3       # 90° contre-horaire = 3 quarts horaires
    assert quarts_depuis_effet(773, 180) == 2
    assert quarts_depuis_effet(773, 270) == 1
    assert quarts_depuis_effet(771, 1) == 1        # π/2 horaire
    assert quarts_depuis_effet(775, 6) == 1        # 6π/4 contre-horaire
    assert quarts_depuis_effet(1047, 10) is None
