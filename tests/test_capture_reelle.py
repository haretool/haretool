"""Rejeu d'une vraie capture : 3 combats contre des Pious (jeu 3.7.13.17)."""
import json
import random
from pathlib import Path

import pytest

from haretool.apprendre import proposer
from haretool.combat import EtatCompte
from haretool.flux import Flux
from haretool.marques import marques, OptionsDessin
from haretool.protocole import Protocole, EMBARQUE
from haretool.terrain import jouables

FIXTURES_DIR = Path(__file__).parent / "fixtures"
if not (FIXTURES_DIR / "persos.json").is_file():
    pytest.skip("captures réelles non publiées (données de joueurs)", allow_module_level=True)
_PERSOS = json.loads((FIXTURES_DIR / "persos.json").read_text())
FIXTURE = FIXTURES_DIR / "combat-2026-11-09.json"
MOI = _PERSOS["perso_a"]
PIOUS = {236, 489, 490, 491, 493}


def messages():
    flux, sortie = {}, []
    for p in json.loads(FIXTURE.read_text())["paquets"]:
        for nom, valeur in flux.setdefault(p["sens"], Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
            sortie.append((p["t"], p["sens"], nom, valeur))
    return sortie


@pytest.fixture(scope="module")
def tous():
    return messages()


def rejouer(tous, est_harebourg=lambda m: False, sur_chaque=None, depuis=0):
    e = EtatCompte(Protocole.depuis_fichier(EMBARQUE), est_harebourg=est_harebourg)
    for i, (t, sens, nom, valeur) in enumerate(tous[depuis:]):
        e.appliquer(nom, valeur, t)
        if sur_chaque:
            sur_chaque(e, t, nom)
    return e


def test_moi_et_nom(tous):
    vus = set()
    e = rejouer(tous, sur_chaque=lambda e, t, n: vus.add(e.moi))
    assert e.moi == MOI and e.nom_perso
    assert vus <= {None, MOI}          # jamais un monstre


def test_trois_combats_et_leurs_pv(tous):
    debuts, fins = [], []

    def noter(e, t, nom):
        if nom == "jvj" and e.mon_tour:
            debuts.append(e.pv_debut_tour)
        if nom == "jwp":
            fins.append(e.en_combat)

    rejouer(tous, sur_chaque=noter)
    assert fins == [False, False, False]
    # PV de début de chacun de mes tours, déduits des messages du serveur
    assert debuts == [2225, 2192, 2211, 2187, 2164, 1849, 1782, 1694, 1587, 1491, 1849, 1724, 1620]


def test_carte_de_combat_connue(tous):
    cartes = set()
    rejouer(tous, sur_chaque=lambda e, t, n: e.en_combat and cartes.add(e.carte))
    assert cartes == {191105034, 191107080, 191107082}
    assert all(jouables(c) for c in cartes)


def test_monstres_des_fiches(tous):
    vus = set()
    rejouer(tous, sur_chaque=lambda e, t, n: vus.update(e.monstres.values()))
    assert vus == PIOUS


def test_morts_et_melee(tous):
    max_melee, morts = [0], set()

    def noter(e, t, nom):
        max_melee[0] = max(max_melee[0], e.lignes_melee)
        morts.update(e.morts)

    rejouer(tous, sur_chaque=noter)
    assert morts >= {-1, -2, -3, -4, -5} and max_melee[0] >= 1


def test_marques_quand_le_comte_est_la(tous):
    # On fait passer le Piou Violet pour le Comte : les marques doivent apparaître à mon tour.
    vus = []
    rejouer(tous, est_harebourg=lambda m: m == 236,
            sur_chaque=lambda e, t, n: e.mon_tour and vus.append(len(marques(e, OptionsDessin()))))
    assert max(vus) >= 3
    assert all(n == 0 for n in vus[:3])            # 1er combat : pas de Piou Violet


def test_etat_sans_pv_absolus_ne_dessine_rien(tous):
    depart = next(i for i, m in enumerate(tous) if m[2] == "jvi" and m[0] > 60)   # combat 2 déjà commencé
    vus = []
    rejouer(tous, est_harebourg=lambda m: m == 236, depuis=depart,
            sur_chaque=lambda e, t, n: t < 95 and vus.append(len(marques(e, OptionsDessin()))))
    assert vus and all(n == 0 for n in vus)


def test_apprendre_sur_la_vraie_capture(tous):
    rng = random.Random(7)
    brouille = {}
    recus = []
    for t, sens, nom, valeur in tous:
        if sens == "serveur->client" and 55 < t < 95:
            brouille.setdefault(nom, "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(4)))
            recus.append((t, brouille[nom], valeur))
    p = proposer(recus, [(58.7, 1849), (80.0, 1587)])["messages"]
    assert p["deplacement"]["nom"] == brouille["jnz"] and p["deplacement"]["champs"]["chemin"] == [1]
    assert p["combattants"]["nom"] == brouille["kjl"]
    assert p["combattants"]["champs"] == {"liste": [2], "id": [2], "case": [3], "monstre": None}
    assert p["pv_absolus"]["nom"] == brouille["kqo"]
    assert {p["pv_absolus"]["champs"]["courants"][0], p["pv_absolus"]["champs"]["max"][0]} == {1, 3}
    assert p["action"]["nom"] == brouille["jsq"]
    assert p["action"]["champs"]["degats_montant"] == [37, 6] and p["action"]["champs"]["degats_cible"] == [37, 5]


def test_pv_note_par_le_joueur_a_124_s(tous):
    # Le joueur a lu 1620 PV en jeu à 124,9 s (note tapée pendant la capture).
    vu = []
    rejouer(tous, sur_chaque=lambda e, t, n: t <= 124.87 and vu.append(e.pv))
    assert vu[-1] == 1620


SONGE = Path(__file__).parent / "fixtures" / "songe-2026-11-09.json"
PERSO_A, PERSO_B = _PERSOS["perso_a"], _PERSOS["perso_b"]


def messages_songe(flux_local):
    flux, sortie = {}, []
    for p in json.loads(SONGE.read_text())["paquets"]:
        if p["flux"] != flux_local:
            continue
        for nom, valeur in flux.setdefault(p["sens"], Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
            sortie.append((p["t"], p["sens"], nom, valeur))
    return sortie


def test_songe_pv_reels_et_erosion():
    # PV absolus du Songe : perso A à 55,5 s = 1472 PV, maximum érodé 3122 (il fait foi).
    vus = []
    rejouer(messages_songe(_PERSOS["flux_a"]),
            sur_chaque=lambda e, t, n: 55.4 < t < 55.6 and vus.append((e.pv, e.pv_max)))
    assert (1472, 3122) in vus


def test_songe_second_compte():
    tours = []
    e = rejouer(messages_songe(_PERSOS["flux_b"]),
                sur_chaque=lambda e, t, n: n == "jte" and tours.append((e.pv_debut_tour, e.pv_max)))
    assert e.moi == PERSO_B
    assert tours[0] == (1931, 3272)          # vie du Songe érodée (1899 hors Songe)
    from haretool.confusion import quarts
    assert quarts(*tours[0]) == 2


def test_songe_seul_tour_1_pv_du_jeu():
    """Songe en solo : pas de PV absolus, seulement la vitalité du Songe
    (+1480) et les coups reçus AVANT mon premier tour. Le jeu affichait 1257 / 3123
    (3123 = 3329 moins 206 d'érosion), et la confusion se lit sur ces PV-là."""
    fichier = Path(__file__).parent / "fixtures" / "songe-seul-2026-11-09.json"
    flux, tours = {}, []
    e = EtatCompte(Protocole.depuis_fichier(EMBARQUE), est_harebourg=lambda m: True)
    for p in json.loads(fichier.read_text())["paquets"]:
        for nom, valeur in flux.setdefault(p["sens"], Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
            e.appliquer(nom, valeur, p["t"])
            if nom == "jte":
                tours.append((e.pv_debut_tour, e.pv_max))
    assert tours[0] == (1257, 3123)
    from haretool.confusion import quarts
    assert quarts(*tours[0]) == 3


def test_songe_seul_tour_1_a_la_limite_maximum_erode():
    """Combat réel : 1416 PV, max 3329 − 190 d'érosion = 3139 → 45 % → 2 quarts.
    Avec le max sans érosion (42 %, 3 quarts) le 1er coup au contact partait à côté :
    la bonne case était celle à 2 quarts (539 pour le monstre en 512, moi en 525)."""
    fichier = Path(__file__).parent / "fixtures" / "songe-seul-limite-2026-11-09.json"
    flux, tours = {}, []
    e = EtatCompte(Protocole.depuis_fichier(EMBARQUE), est_harebourg=lambda m: True)
    for p in json.loads(fichier.read_text())["paquets"]:
        for nom, valeur in flux.setdefault(p["sens"], Flux()).ajouter(p["seq"], bytes.fromhex(p["hex"])):
            e.appliquer(nom, valeur, p["t"])
            if nom == "jte":
                tours.append((e.pv_debut_tour, e.pv_max, dict(e.positions)))
    pv, maxi, positions = tours[-1]
    assert (pv, maxi) == (1416, 3139)
    from haretool.confusion import quarts, case_a_cliquer
    assert quarts(pv, maxi) == 2
    assert case_a_cliquer(positions[MOI], 512, quarts(pv, maxi), 0) == 539
