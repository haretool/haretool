from haretool.grille import vers_uv, vers_case, rot_ccw, adjacentes, CASES


def test_aller_retour():
    assert all(vers_case(*vers_uv(n)) == n for n in range(CASES))


def voisins(n):
    return sorted(m - n for m in range(CASES) if adjacentes(n, m))


def test_voisins_valent_13_14_15():  # pas de déplacement mesurés en jeu
    assert voisins(300) == [-14, -13, 14, 15]   # ligne impaire (q = 21)
    assert voisins(290) == [-15, -14, 13, 14]   # ligne paire (q = 20)


def test_hors_grille():
    assert vers_uv(560) is None and vers_uv(-1) is None and vers_case(-5, -5) is None


def test_rot_ccw_quatre_fois_identite():
    assert rot_ccw(*rot_ccw(*rot_ccw(*rot_ccw(3, -2)))) == (3, -2)


def test_rot_ccw_formule():
    assert rot_ccw(3, -2) == (-2, -3)


def test_adjacentes_hors_grille_faux():
    assert not adjacentes(0, -1) and not adjacentes(559, 560)
