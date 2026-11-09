import pytest

from haretool.calibrage import Calibrage
from haretool.marques import Marque
from haretool.overlay import geometrie, icone_svg

CAL = Calibrage(100.0, 50.0, 86.0, 43.0)


def test_losange_centre_sur_la_case():
    poly, icone = geometrie(Marque("losange", 300, "#FF0000"), CAL)
    cx, cy = CAL.pixel(300)
    xs = [p.x() for p in poly]
    ys = [p.y() for p in poly]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(cx) and (min(ys) + max(ys)) / 2 == pytest.approx(cy)
    assert max(xs) - min(xs) == pytest.approx(86.0) and max(ys) - min(ys) == pytest.approx(43.0)
    assert icone is None


def test_icone_centree_et_a_l_echelle():
    _, r1 = geometrie(Marque("epee", 300, "#FF0000"), CAL, taille_icones=1.0)
    _, r2 = geometrie(Marque("epee", 300, "#FF0000"), CAL, taille_icones=1.5)
    cx, cy = CAL.pixel(300)
    assert r1.center().x() == pytest.approx(cx) and r1.center().y() == pytest.approx(cy)
    assert r2.width() == pytest.approx(r1.width() * 1.5)
    assert r1.width() == pytest.approx(r1.height())


def test_oeil_barre_prend_la_place_de_l_epee():
    _, epee = geometrie(Marque("epee", 300, "#FF0000"), CAL)
    _, oeil = geometrie(Marque("hors_vue", 300, "#1565C0"), CAL)
    assert oeil == epee


def test_icone_coloree():
    svg = icone_svg("epee", "#12AB34")
    assert b"#12AB34" in svg and b"#COULEUR" not in svg
