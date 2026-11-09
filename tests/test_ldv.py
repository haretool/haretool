import inspect

from haretool import ldv
from haretool.ldv import traversees, en_vue
from haretool.grille import vers_case


def c(u, v):
    n = vers_case(u, v)
    assert n is not None, (u, v)
    return n


A = c(16, 4)


def test_contact_rien_entre():
    for b in (c(17, 4), c(16, 5), c(15, 4), c(16, 3), A):
        assert traversees(A, b) == []
        assert en_vue(A, b, set())


def test_ligne_droite():
    assert traversees(A, c(20, 4)) == [c(17, 4), c(18, 4), c(19, 4)]
    assert traversees(A, c(16, 8)) == [c(16, 5), c(16, 6), c(16, 7)]


def test_obstacle_sur_la_ligne_ou_a_cote():
    assert not en_vue(A, c(20, 4), {c(18, 4)})
    assert en_vue(A, c(20, 4), {c(18, 5), c(18, 3)})


def test_diagonale_parfaite_coins_ne_bloquent_pas():
    assert traversees(A, c(19, 7)) == [c(17, 5), c(18, 6)]
    assert en_vue(A, c(19, 7), {c(17, 4), c(16, 5), c(18, 5), c(17, 6)})
    assert not en_vue(A, c(19, 7), {c(18, 6)})


def test_passage_par_un_coin_hors_diagonale():
    # (0,0)→(3,1) relatif : franchissements u et v simultanés à mi-chemin
    assert traversees(A, c(19, 5)) == [c(17, 4), c(18, 5)]


def test_biais():
    assert traversees(A, c(19, 6)) == [c(17, 4), c(17, 5), c(18, 5), c(18, 6)]
    assert traversees(A, c(18, 5)) == [c(17, 4), c(17, 5)]


def test_extremites_exclues():
    b = c(20, 4)
    assert en_vue(A, b, {A, b})


def test_symetrique():
    for b in (c(19, 6), c(20, 7), c(13, 9), c(18, 1)):
        assert sorted(traversees(A, b)) == sorted(traversees(b, A))


def test_case_invalide():
    assert traversees(-1, A) is None
    assert en_vue(-1, A, set())   # inconnu : jamais d'avertissement à tort


def test_entiers_seulement():
    source = inspect.getsource(ldv)
    assert "float" not in source and "/" not in source
