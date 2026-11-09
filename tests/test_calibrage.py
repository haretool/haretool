import pytest

from haretool.calibrage import Calibrage, Calibrages
from haretool.fenetres import FenetreJeu, associer, lister
from haretool.grille import vers_uv

L, H, X0, Y0 = 86.0, 43.0, 100.0, 50.0


def vrai_pixel(case):
    u, v = vers_uv(case)
    return X0 + (u - v) / 2 * L, Y0 + (u + v) * H / 2


def test_deux_points_donnent_toutes_les_cases():
    a, b = 300, 145
    cal = Calibrage.depuis_deux_points((a, vrai_pixel(a)), (b, vrai_pixel(b)))
    for n in (0, 13, 14, 280, 559):
        assert cal.pixel(n) == pytest.approx(vrai_pixel(n), abs=0.5)
    assert cal.taille_losange() == pytest.approx((L, H))


def test_meme_ligne_utilise_le_rapport_fixe():
    a, b = 280, 285          # même ligne : q identique
    cal = Calibrage.depuis_deux_points((a, vrai_pixel(a)), (b, vrai_pixel(b)))
    assert cal.pixel(0) == pytest.approx(vrai_pixel(0), abs=0.5)


def test_cases_trop_proches_refusees():
    with pytest.raises(ValueError):
        Calibrage.depuis_deux_points((300, vrai_pixel(300)), (301, vrai_pixel(301)))


def test_reglage_fin():
    cal = Calibrage.depuis_deux_points((300, vrai_pixel(300)), (145, vrai_pixel(145)))
    d = cal.decaler(2, -1)
    assert d.pixel(10) == pytest.approx((cal.pixel(10)[0] + 2, cal.pixel(10)[1] - 1))


def test_aller_retour_dict():
    cal = Calibrage.depuis_deux_points((300, vrai_pixel(300)), (145, vrai_pixel(145)))
    assert Calibrage.depuis_dict(cal.vers_dict()).pixel(77) == pytest.approx(cal.pixel(77))


def test_calibrage_par_taille():
    cal = Calibrage.depuis_deux_points((300, vrai_pixel(300)), (145, vrai_pixel(145)))
    c = Calibrages()
    c.poser(1920, 1080, cal)
    assert c.exact(1920, 1080) is not None and c.exact(1280, 720) is None
    c2 = Calibrages.depuis_dict(c.vers_dict())
    assert c2.pour(1920, 1080).pixel(10) == pytest.approx(cal.pixel(10))


def test_taille_inconnue_deduite_sans_recalibrer():
    """Fenêtre redimensionnée : la grille suit la hauteur et reste centrée."""
    c = Calibrages()
    c.poser(1920, 1080, Calibrage(328.0, 25.0, 93.0, 46.5))
    petit = c.pour(1280, 720)                      # même forme, 2/3 de la taille
    assert petit.largeur == pytest.approx(62.0) and petit.y0 == pytest.approx(25.0 * 2 / 3)
    assert petit.x0 - 640 == pytest.approx((328.0 - 960) * 2 / 3)
    large = c.pour(2560, 1080)                     # plus large, même hauteur : juste recentrée
    assert large.largeur == pytest.approx(93.0) and large.x0 == pytest.approx(328.0 + 320)


def test_premier_lancement_deja_calibre():
    """Sans aucun calibrage enregistré, la référence mesurée en jeu suffit."""
    c = Calibrages()
    assert c.pour(2560, 1440).largeur == pytest.approx(124.0)
    hd = c.pour(1920, 1080)
    assert hd.largeur == pytest.approx(124.0 * 0.75)
    # la grille reste centrée : le milieu de la grille tombe au milieu de l'écran (à ±1 %)
    xs = [hd.pixel(k)[0] for k in range(560)]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(960, rel=0.01)
    assert c.pour(0, 0) is None


def test_associer_insensible_a_la_casse():
    f = [FenetreJeu(1, "Bidule - Dofus", (0, 0, 10, 10), False, True),
         FenetreJeu(2, "Machin - Dofus", (0, 0, 10, 10), False, False)]
    assert associer("machin", f).hwnd == 2
    assert associer("Truc", f) is None and associer(None, f) is None


def test_lister_ne_plante_pas():
    assert isinstance(lister(), list)


def test_devine_le_monstre_clique():
    moi, monstres = 300, [145, 330, 412, 77]
    vrai = 412
    bruit = (3.0, -4.0)
    px2 = (vrai_pixel(vrai)[0] + bruit[0], vrai_pixel(vrai)[1] + bruit[1])
    cal, case = Calibrage.depuis_clics((moi, vrai_pixel(moi)), monstres, px2)
    assert case == vrai
    assert cal.taille_losange() == pytest.approx((L, H), rel=0.08)


def test_petit_ecart_horizontal_ne_fausse_plus_l_echelle():
    # cas réel : les deux cases n'ont qu'une demi-case d'écart en largeur
    a, b = 246, 413
    pa = vrai_pixel(a)
    pb = (vrai_pixel(b)[0] + 15, vrai_pixel(b)[1] - 5)      # clic 15 px à côté
    cal = Calibrage.depuis_deux_points((a, pa), (b, pb))
    assert cal.taille_losange() == pytest.approx((L, H), rel=0.1)


def test_aucun_monstre_assez_loin():
    with pytest.raises(ValueError):
        Calibrage.depuis_clics((300, vrai_pixel(300)), [301], vrai_pixel(301))
