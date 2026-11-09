import pytest

from haretool.confusion import quarts, case_a_cliquer
from haretool.grille import vers_uv, vers_case


@pytest.mark.parametrize("pct,q", [(100, 1), (90, 1), (89, 3), (75, 3), (74, 2), (45, 2),
                                   (44, 3), (30, 3), (29, 1), (0, 1)])
def test_tranches(pct, q):
    assert quarts(pct, 100) == q


def test_pourcentage_arrondi_vers_le_bas():
    assert quarts(899, 1000) == 3   # 89,9 % → tranche 89–75


def test_pv_max_nul_ne_plante_pas():
    assert quarts(0, 0) == 1


def test_melee_ajoute_un_quart():
    assert case_a_cliquer(300, 302, 3, 1) == 302      # 3 quarts + 1 ligne au contact = tour complet


def test_demi_tour_symetrique():   # 2 quarts : la case opposée par rapport à moi
    (mu, mv), (cu, cv) = vers_uv(300), vers_uv(302)
    assert vers_uv(case_a_cliquer(300, 302, 2, 0)) == (2 * mu - cu, 2 * mv - cv)


def test_hors_grille_rend_none():
    assert case_a_cliquer(0, 28, 2, 0) is None


def test_un_quart_comme_le_simulateur():
    # Règle de référence : un monstre à
    # 3 cases sur +u, confusion d'un quart → il faut viser 3 cases sur -v.
    moi = vers_case(10, 5)
    cible = vers_case(13, 5)
    assert vers_uv(case_a_cliquer(moi, cible, 1, 0)) == (10, 2)


def test_melee_au_dela_de_quatre_boucle():
    assert case_a_cliquer(300, 302, 1, 5) == case_a_cliquer(300, 302, 1, 1)


def _arrivee(moi, clic, quarts_horaires):
    """Où le jeu fait arriver un sort cliqué en `clic` (déviation horaire autour de moi)."""
    (mu, mv), (cu, cv) = vers_uv(moi), vers_uv(clic)
    du, dv = cu - mu, cv - mv
    for _ in range(quarts_horaires % 4):
        du, dv = -dv, du
    return vers_case(mu + du, mv + dv)


def test_couples_reels_clic_arrivee():
    """Cases cliquées (message du client) et cases d'arrivée (réponse du serveur),
    captures réelles : (moi, clic, arrivée, tranche, lignes au contact avant le sort)."""
    reels = [
        (525, 511, 540, 2, 0), (525, 540, 511, 2, 0),      # tranche 2
        (525, 512, 511, 2, 1), (525, 511, 539, 2, 1),      # même tour, après 1 coup au contact
        (512, 526, 498, 3, 0), (512, 498, 498, 3, 1),      # tranche 3, puis 1 coup
        (512, 526, 525, 3, 2), (512, 525, 497, 3, 2),      # puis 2 coups
    ]
    for moi, clic, arrivee, tranche, melee in reels:
        assert _arrivee(moi, clic, tranche + melee) == arrivee
        # et la case que montre l'outil fait bien arriver le sort sur la cible
        assert _arrivee(moi, case_a_cliquer(moi, arrivee, tranche, melee), tranche + melee) == arrivee
