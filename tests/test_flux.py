import json
import random
from pathlib import Path

import pytest

from haretool.flux import Flux
from haretool.protobuf import champs, varint_signe

FIXTURE = Path(__file__).parent / "fixtures" / "hors-combat-2026-11-09.json"
avec_capture = pytest.mark.skipif(not FIXTURE.is_file(), reason="capture réelle non publiée")


def tous():
    return json.loads(FIXTURE.read_text())["paquets"]


def paquets(sens):
    """Paquets d'un sens : (flux, seq, charge). La capture contient 4 connexions."""
    return [(p["flux"], p["seq"], bytes.fromhex(p["hex"])) for p in tous() if p["sens"] == sens]


def par_flux(sens, sauter=0, liste=None):
    """Un Flux par connexion ; `sauter` retire les N premiers paquets de chaque connexion."""
    flux, vus, noms = {}, {}, {}
    for fid, seq, charge in (liste if liste is not None else paquets(sens)):
        vus[fid] = vus.get(fid, 0) + 1
        if liste is None and vus[fid] <= sauter:
            continue
        noms.setdefault(fid, []).extend(n for n, _ in flux.setdefault(fid, Flux()).ajouter(seq, charge))
    return noms


def rejouer(sens, sauter=0, liste=None):
    return [n for liste_noms in par_flux(sens, sauter, liste).values() for n in liste_noms]


def test_champs_simples():
    # champ 1 varint 150, champ 2 "ab", champ 3 fixe 32 bits
    assert champs(bytes.fromhex("089601") + b"\x12\x02ab" + bytes.fromhex("1d01000000")) == \
        {1: [150], 2: [b"ab"], 3: [1]}


def test_champs_invalide():
    import pytest
    with pytest.raises(ValueError):
        champs(b"\x12\x05ab")


def test_varint_signe():
    assert varint_signe(0xFFFFFFFFFFFFFFFF) == -1 and varint_signe(5) == 5


@avec_capture
def test_flux_serveur_complet():
    noms = rejouer("serveur->client")
    assert len(noms) == 241 and noms.count("jnz") == 61


@avec_capture
def test_flux_client_complet():
    assert len(rejouer("client->serveur")) == 87


@avec_capture
def test_doublons_ignores():
    p = paquets("serveur->client")
    doubles = [x for x in p for _ in range(2)]
    assert par_flux("", liste=doubles) == par_flux("serveur->client")


@avec_capture
def test_desordre():
    p = paquets("serveur->client")
    rng = random.Random(4)
    melange = []
    for i in range(0, len(p), 3):
        bloc = p[i:i + 3]
        rng.shuffle(bloc)
        melange += bloc
    assert par_flux("", liste=melange) == par_flux("serveur->client")


@avec_capture
def test_flux_pris_au_milieu():
    # 5 paquets sautés au début de chaque connexion : on retombe sur ses pieds,
    # les messages lus sont exactement la fin de la liste complète.
    complet = par_flux("serveur->client")
    milieu = par_flux("serveur->client", sauter=5)
    for fid, noms in complet.items():
        assert milieu[fid] == noms[len(noms) - len(milieu[fid]):]
        assert len(milieu[fid]) >= len(noms) - 6


@avec_capture
def test_valeur_rendue_est_le_contenu():
    f = Flux()
    sortie = []
    for fid, seq, charge in paquets("serveur->client"):
        if fid == "s1":
            sortie += f.ajouter(seq, charge)
    nom, valeur = next(x for x in sortie if x[0] == "jnz")
    assert 1 in champs(valeur)
