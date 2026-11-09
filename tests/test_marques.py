from types import SimpleNamespace

import pytest

from haretool import marques as mod
from haretool.marques import marques, OptionsDessin, Marque, ROUGE, BLEU_VUE, GRIS_ALLIE
from haretool.grille import vers_case
from haretool.confusion import case_a_cliquer

MOI = 42
A = vers_case(16, 4)
M1 = vers_case(18, 4)
M2 = vers_case(16, 8)
PAL = ["#111111", "#222222", "#333333"]


def etat(**k):
    base = dict(en_combat=True, harebourg_present=True, pv_debut_tour=1000, pv_max=1000, pv=1000,
                moi=MOI, positions={MOI: A, -1: M1, -2: M2, 7: vers_case(10, 10)}, morts=set(),
                ordre={-1: 0, -2: 1}, lignes_melee=0, carte=None, quarts_force=None)
    base.update(k)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def terrain_vide(monkeypatch):
    monkeypatch.setattr(mod, "jouables", lambda carte: None)
    monkeypatch.setattr(mod, "bloque_vue", lambda carte: None)


def opts(**k):
    return OptionsDessin(palette=PAL, **k)


def test_cas_normal():
    m = marques(etat(), opts())
    cible = case_a_cliquer(A, M1, 1, 0)
    assert Marque("losange", M1, PAL[0]) in m
    assert Marque("losange", cible, PAL[0]) in m and Marque("epee", cible, PAL[0]) in m
    assert len(m) == 9     # 3 marques par monstre et par allié


@pytest.mark.parametrize("champ,valeur", [("en_combat", False), ("harebourg_present", False),
                                          ("pv_debut_tour", None), ("moi", None)])
def test_rien_sans_les_conditions(champ, valeur):
    assert marques(etat(**{champ: valeur}), opts()) == []


def test_mob_mort_efface():
    e = etat(positions={MOI: A, -2: M2}, morts={-1})
    assert all(x.couleur != PAL[0] for x in marques(e, opts()))


def test_allie_case_bouclier_grise():
    # Un allié se vise comme un monstre (même confusion) : losange gris, bouclier, jamais d'épée.
    e = etat(positions={MOI: A, 7: M1})
    cible = case_a_cliquer(A, M1, 1, 0)
    assert marques(e, opts()) == [Marque("losange", M1, GRIS_ALLIE), Marque("losange", cible, GRIS_ALLIE),
                                  Marque("bouclier", cible, GRIS_ALLIE)]


def test_allies_masquables():
    e = etat(positions={MOI: A, 7: M1})
    assert marques(e, opts(montrer_allies=False)) == []


def test_allie_mort_efface():
    e = etat(positions={MOI: A, 7: M1}, morts={7})
    assert marques(e, opts()) == []


def test_moi_jamais_cible():
    e = etat(positions={MOI: A})
    assert marques(e, opts()) == []


def test_couleur_stable_apres_une_mort():
    e = etat(positions={MOI: A, -2: M2}, morts={-1})
    assert {x.couleur for x in marques(e, opts())} == {PAL[1]}


def test_hors_carte_deux_marques():
    e = etat(positions={MOI: vers_case(1, 0), -1: vers_case(3, 0)}, ordre={-1: 0}, pv_debut_tour=600)
    m = marques(e, opts())
    assert case_a_cliquer(vers_case(1, 0), vers_case(3, 0), 2, 0) is None
    assert m == [Marque("losange", vers_case(3, 0), PAL[0]), Marque("indisponible", vers_case(3, 0), ROUGE)]


def test_case_morte(monkeypatch):
    cible = case_a_cliquer(A, M1, 1, 0)
    monkeypatch.setattr(mod, "jouables", lambda carte: frozenset(range(560)) - {cible})
    m = [x for x in marques(etat(carte=5), opts()) if x.couleur in (PAL[0], ROUGE)]
    assert m == [Marque("losange", M1, PAL[0]), Marque("indisponible", M1, ROUGE)]


def test_carte_inconnue_pas_de_case_morte():
    assert not any(x.forme == "indisponible" for x in marques(etat(carte=5), opts()))


def test_monstre_derriere_un_obstacle(monkeypatch):
    # La vue se juge de MA case jusqu'au MONSTRE (règle validée en jeu le 23/09).
    from haretool.ldv import traversees
    cible = case_a_cliquer(A, M1, 1, 0)
    entre_moi_et_le_monstre = [n for n in traversees(A, M1) if n is not None]
    monkeypatch.setattr(mod, "jouables", lambda carte: frozenset(range(560)))
    monkeypatch.setattr(mod, "bloque_vue", lambda carte: frozenset(entre_moi_et_le_monstre[:1]))
    m = marques(etat(carte=5), opts())
    assert Marque("hors_vue", cible, BLEU_VUE) in m           # l'œil barré…
    assert Marque("epee", cible, PAL[0]) not in m             # … REMPLACE l'épée
    assert Marque("losange", cible, PAL[0]) in m
    m2 = marques(etat(carte=5), opts(montrer_ldv=False))
    assert Marque("epee", cible, PAL[0]) in m2 and not any(x.forme == "hors_vue" for x in m2)


def test_obstacle_entre_moi_et_la_case_a_cliquer_seulement(monkeypatch):
    from haretool.ldv import traversees
    cible = case_a_cliquer(A, M1, 1, 0)
    vers_monstre = {n for n in traversees(A, M1) if n is not None}
    seulement_case = [n for n in traversees(A, cible) if n is not None and n not in vers_monstre]
    monkeypatch.setattr(mod, "jouables", lambda carte: frozenset(range(560)))
    monkeypatch.setattr(mod, "bloque_vue", lambda carte: frozenset(seulement_case[:1]))
    assert Marque("epee", cible, PAL[0]) in marques(etat(carte=5), opts())


def test_un_autre_combattant_bloque_la_vue(monkeypatch):
    from haretool.ldv import traversees
    milieu = [n for n in traversees(A, M1) if n is not None][0]
    monkeypatch.setattr(mod, "jouables", lambda carte: frozenset(range(560)))
    monkeypatch.setattr(mod, "bloque_vue", lambda carte: frozenset())
    e = etat(carte=5, positions={MOI: A, -1: M1, 7: milieu})
    assert any(x.forme == "hors_vue" for x in marques(e, opts()))


def test_ordre_fonds_puis_icones():
    m = marques(etat(), opts())
    dernier_losange = max(i for i, x in enumerate(m) if x.forme == "losange")
    premiere_icone = min(i for i, x in enumerate(m) if x.forme != "losange")
    assert dernier_losange < premiere_icone


def test_options_losange_mob():
    m = marques(etat(), opts(montrer_losange_mob=False))
    assert Marque("losange", M1, PAL[0]) not in m and len(m) == 6     # 2 monstres + 1 allié, 2 marques chacun


def test_tranche_forcee_et_melee():
    m1 = marques(etat(quarts_force=2), opts())
    assert Marque("epee", case_a_cliquer(A, M1, 2, 0), PAL[0]) in m1
    m2 = marques(etat(lignes_melee=1), opts())        # 1 quart + 1 coup au contact = 2 quarts
    assert Marque("epee", case_a_cliquer(A, M1, 2, 0), PAL[0]) in m2
    m3 = marques(etat(lignes_melee=3), opts())        # 1 + 3 = tour complet : on tape directement
    assert Marque("epee", M1, PAL[0]) in m3
