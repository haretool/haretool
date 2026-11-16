"""Rejeu d'une vraie capture : Xélor niveau 10 (16/11/2026, jeu 3.7.13.17).

Ses sorts téléportent le monstre et échangent les places (téléfrag) avec son invocation :
les positions doivent suivre, sinon les cases à cliquer tournent autour d'une mauvaise case.
"""
import json
from pathlib import Path

import pytest

from haretool.combat import EtatCompte
from haretool.flux import Flux
from haretool.protocole import Protocole, EMBARQUE

FIXTURE = Path(__file__).parent / "fixtures" / "xelor-2026-11-16.json"
if not FIXTURE.is_file():
    pytest.skip("capture réelle non publiée (données de joueurs)", allow_module_level=True)


def etat_a(t_max):
    """État du combat juste après l'instant t_max (secondes depuis le début de la capture)."""
    e = EtatCompte(Protocole.depuis_fichier(EMBARQUE))
    flux = {}
    for p in json.loads(FIXTURE.read_text())["paquets"]:
        if p["t"] > t_max:
            break
        for nom, valeur in flux.setdefault((p["flux"], p["sens"]), Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
            if p["sens"] == "serveur->client":
                e.appliquer(nom, valeur, p["t"])
    return e


def test_teleportation_du_monstre():
    assert etat_a(146.0).positions[-1] == 314      # arrivé à pied en 314
    assert etat_a(147.0).positions[-1] == 260      # téléporté en 260
    assert etat_a(151.0).positions[-1] == 314      # puis renvoyé en 314


def test_echange_monstre_et_invocation():
    avant = etat_a(248.0)
    assert avant.positions[-1] == 246
    apres = etat_a(248.5)
    assert (apres.positions[-1], apres.positions[-2]) == (302, 246)
    retour = etat_a(251.5)
    assert (retour.positions[-1], retour.positions[-2]) == (246, 302)


def test_telefrag_du_xelor_avec_son_invocation():
    avant = etat_a(453.0)
    moi = avant.moi
    assert (avant.positions[moi], avant.positions[-2]) == (397, 314)
    apres = etat_a(453.5)
    assert (apres.positions[moi], apres.positions[-2]) == (314, 397)
