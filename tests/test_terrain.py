import json

from haretool import terrain
from haretool.terrain import jouables, bloque_vue, est_harebourg, nombre_de_cartes

CARTE_COMBAT = 191104008   # carte de combat relevée en jeu


def test_beaucoup_de_cartes():
    assert nombre_de_cartes() > 5000


def test_carte_de_combat_connue():
    j = jouables(CARTE_COMBAT)
    assert j is not None
    assert not any(n in j for n in range(14))          # rangée du haut : hors carte
    assert 60 <= len(j) <= 420              # arène de combat : 111 cases jouables relevées
    assert bloque_vue(CARTE_COMBAT) is not None


def test_carte_inconnue():
    assert jouables(1) is None and bloque_vue(1) is None


def test_comte():
    ids = [m["id"] for m in json.loads((terrain.DONNEES / "monstres_harebourg.json").read_text("utf-8"))]
    assert ids and all(est_harebourg(i) for i in ids)
    assert not est_harebourg(31)


def test_lecture_des_bits():
    brut = terrain._entete(1) + (7).to_bytes(4, "little") + bytes([0b101] + [0] * 69) + bytes([0b10] + [0] * 69)
    t = terrain.Terrain(brut)
    assert t.jouables(7) == frozenset({0, 2}) and t.bloque_vue(7) == frozenset({1})
