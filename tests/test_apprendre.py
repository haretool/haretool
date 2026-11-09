"""Le mode apprendre retrouve les messages par leur forme, sans connaître leurs noms."""
import random

from haretool.apprendre import proposer
from haretool.grille import vers_case

from pb import msg, Empaquete

MOI, ALLIE = 101, 202
A, B = vers_case(16, 4), vers_case(10, 10)


def combat_brouille(graine=1):
    """Un combat fabriqué : noms au hasard, numéros de champs « nouveaux »."""
    rng = random.Random(graine)
    noms = {k: "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(3))
            for k in ("pv", "cmb", "dep", "act", "tour", "bruit", "ping")}
    t, sortie = 0.0, []

    def envoyer(cle, valeur, dt=0.3):
        nonlocal t
        t += dt
        sortie.append((t, noms[cle], valeur))

    for i in range(20):
        envoyer("ping", msg({1: i, 2: 12345}))
    envoyer("pv", msg({4: 3000, 2: 4200, 6: 77}))
    envoyer("cmb", msg({5: [{3: MOI, 6: A, 9: 1}, {3: ALLIE, 6: B, 9: 1},
                            {3: -1, 6: vers_case(18, 4), 9: 3416}, {3: -2, 6: vers_case(16, 9), 9: 31}]}))
    lectures = [(t + 0.1, 3000)]
    ids = [MOI, -1, ALLIE, -2]
    pv = 3000
    for tour in range(4):
        for ident in ids:
            envoyer("tour", msg({8: ident, 1: tour}))
            depart = A if ident == MOI else vers_case(18, 4)
            chemin = Empaquete([depart, depart + 14, depart + 28 if tour % 2 else depart + 15])
            envoyer("dep", msg({2: chemin, 7: ident}))
            if ident < 0:
                coup = 100 + 37 * tour
                pv -= coup
                envoyer("act", msg({11: ident, 21: 3, 30: {2: coup, 3: 4, 8: MOI}}))
            else:
                envoyer("act", msg({11: ident, 21: 3, 30: {2: 55, 3: 1, 8: -1}}))
            envoyer("bruit", msg({1: rng.randrange(1000), 3: rng.randrange(560)}))
    lectures.append((t + 0.1, pv))
    return noms, sortie, lectures


def test_retrouve_les_messages_essentiels():
    noms, messages, lectures = combat_brouille()
    p = proposer(messages, lectures)["messages"]
    assert p["deplacement"]["nom"] == noms["dep"]
    assert p["deplacement"]["champs"]["chemin"] == [2] and p["deplacement"]["champs"]["acteur"] == [7]
    assert p["combattants"]["nom"] == noms["cmb"]
    assert p["combattants"]["champs"]["liste"] == [5]
    assert p["combattants"]["champs"]["id"] == [3] and p["combattants"]["champs"]["case"] == [6]
    assert p["pv_absolus"]["nom"] == noms["pv"] and p["pv_absolus"]["champs"]["courants"] == [4]
    assert p["pv_absolus"]["champs"]["max"] == [2]
    assert p["action"]["nom"] == noms["act"]
    assert p["action"]["champs"]["degats_montant"] == [30, 2] and p["action"]["champs"]["degats_cible"] == [30, 8]


def test_debut_de_tour_au_mieux():
    noms, messages, lectures = combat_brouille(3)
    p = proposer(messages, lectures)["messages"]
    assert p["debut_tour"] is None or p["debut_tour"]["nom"] == noms["tour"]


def test_sans_combat_rien_d_invente():
    p = proposer([(0.1, "abc", msg({1: 5}))], [])["messages"]
    assert all(v is None for v in p.values())
