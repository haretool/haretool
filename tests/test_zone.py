from pathlib import Path

import pytest

from haretool.calibrage import REFERENCE
from haretool.confusion import case_a_cliquer, case_touchee
from haretool.grille import vers_uv
from haretool.zone import ImageEcran, cases_rouges, pixel_zone, zone_reelle

CAL = REFERENCE[1]


@pytest.mark.parametrize("q,m", [(0, 0), (1, 0), (2, 1), (3, 0), (3, 2)])
def test_case_touchee_inverse_case_a_cliquer(q, m):
    for cible in (272, 302, 330, 358, 244):
        clic = case_a_cliquer(300, cible, q, m)
        assert case_touchee(300, clic, q, m) == cible


def test_pixel_zone_mesures():
    assert pixel_zone(209, 80, 72)        # zone sur case bleue
    assert pixel_zone(242, 105, 73)       # zone sur case beige
    assert pixel_zone(210, 42, 43)        # zone vive (salle sombre)
    assert pixel_zone(188, 25, 48)
    assert not pixel_zone(254, 137, 45)   # placement orange (clair)
    assert not pixel_zone(233, 88, 15)    # placement orange (sombre)
    assert not pixel_zone(240, 220, 170)  # sol beige
    assert not pixel_zone(60, 70, 150)    # case bleue


def image_unie(couleur, cases=(), fond=(60, 70, 150), taille=(2560, 1440)):
    """Image BGRA : fond uni, et les losanges des `cases` remplis de `couleur`."""
    w, h = taille
    px = bytearray(bytes((fond[2], fond[1], fond[0], 255)) * (w * h))
    for c in cases:
        x0, y0 = CAL.pixel(c)
        for y in range(int(y0 - CAL.hauteur / 2), int(y0 + CAL.hauteur / 2)):
            demi = CAL.largeur / 2 * (1 - abs(y - y0) / (CAL.hauteur / 2))
            for x in range(int(x0 - demi), int(x0 + demi)):
                k = (y * w + x) * 4
                px[k:k + 3] = bytes((couleur[2], couleur[1], couleur[0]))
    return ImageEcran(bytes(px), w, h)


def test_barre_fine_meme_rouge_ignoree():
    """Une barre de PV a le même rouge, mais pas la forme d'une case."""
    w, h = 2560, 1440
    px = bytearray(bytes((150, 70, 60, 255)) * (w * h))
    x0, y0 = CAL.pixel(300)
    for y in range(int(y0) - 4, int(y0) + 4):
        for x in range(int(x0 - CAL.largeur / 2), int(x0 + CAL.largeur / 2)):
            k = (y * w + x) * 4
            px[k:k + 3] = bytes((71, 58, 242))
    assert cases_rouges(ImageEcran(bytes(px), w, h), CAL, range(560)) == set()


def test_cases_rouges_sur_image_synthetique():
    img = image_unie((209, 80, 72), cases=(300, 301, 330))
    assert cases_rouges(img, CAL, range(560)) == {300, 301, 330}


def test_zone_reelle_tourne_autour_de_moi():
    moi = 300
    rouges = [302, 303]
    attendu = sorted(case_touchee(moi, c, 1, 0) for c in rouges)
    assert zone_reelle(moi, rouges, 1, 0) == attendu
    assert zone_reelle(moi, rouges, 0, 0) == [302, 303]      # pas de rotation : la zone du jeu


def test_zone_reelle_retire_les_cases_hors_carte():
    moi = 300
    t = case_touchee(moi, 302, 2, 0)
    assert zone_reelle(moi, [302], 2, 0, jouable={1, 2}) == []
    assert zone_reelle(moi, [302], 2, 0, jouable={t}) == [t]


def test_demi_tour_symetrique():
    (mu, mv), (cu, cv) = vers_uv(300), vers_uv(302)
    assert vers_uv(zone_reelle(300, [302], 2, 0)[0]) == (2 * mu - cu, 2 * mv - cv)


# --- vraies images du jeu (16/11/2026, 2560×1440), jamais publiées ---
# zone  : combat Piou, éclairage clair (rouge de zone pâle)
# zone2 : salle sombre, Pandawa (rouge de zone vif) — c'est elle qui a cassé les premiers seuils

FIXTURES = Path(__file__).parent / "fixtures"
VUES = {   # image → cases rouges vérifiées à l'œil sur la capture
    "zone/013": set(), "zone/015": set(),                          # placement / pas de sort
    "zone/020": {315, 316, 317, 329, 330, 343, 345, 358, 371, 373},  # cercle autour du perso
    "zone/037": {340, 341, 342, 369},                              # petite croix + cible
    "zone/035": {275, 302, 303, 304, 331},                         # croix complète
    "zone2/023": set(),                                            # placement orange (salle sombre)
    "zone2/040": {232, 245, 246, 259, 260, 261, 273, 274, 288},    # cercle de 9
    "zone2/044": {287, 300, 301, 314, 315, 316, 328, 329, 343},
}


def charger(nom):
    from PySide6.QtGui import QImage
    q = QImage(str(FIXTURES / f"{nom}.png")).convertToFormat(QImage.Format_ARGB32)
    return ImageEcran(bytes(q.constBits())[: q.width() * q.height() * 4], q.width(), q.height())


@pytest.mark.skipif(not (FIXTURES / "zone").is_dir(), reason="captures du jeu non publiées")
@pytest.mark.parametrize("nom", sorted(VUES))
def test_vraies_images(nom):
    trouve = cases_rouges(charger(nom), CAL, range(560))
    attendu = VUES[nom]
    assert trouve - attendu == set(), "faux rouge"          # jamais de contour faux
    assert len(trouve & attendu) >= 0.7 * len(attendu)      # les cases sous un perso peuvent manquer


def test_cercle_isole_sous_un_monstre_ignore():
    """Le cercle rouge d'un monstre immobile (le Comte) ne doit pas laisser de case fantôme."""
    from haretool.zone import sans_cercles
    assert sans_cercles({455}, [455]) == set()
    assert sans_cercles({455, 304}, [455]) == {304}


def test_vraie_zone_sur_un_monstre_gardee():
    from haretool.grille import adjacentes
    from haretool.zone import sans_cercles
    voisine = next(c for c in range(560) if adjacentes(300, c))
    assert sans_cercles({300, voisine}, [300]) == {300, voisine}
    assert sans_cercles({300}, []) == {300}      # case vide : rien ne change
