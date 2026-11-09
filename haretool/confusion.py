"""Confusion du Comte Harebourg : de combien de quarts de tour les sorts dévient.

La tranche se lit sur les PV au début du tour du perso (maximum érodé). Chaque ligne
de dégâts infligée au contact pendant ce tour AJOUTE un quart horaire : mesuré
sur les cases cliquées et les cases d'arrivée envoyées par le jeu (3 → 0 → 1, 2 → 3).
"""

from .grille import vers_uv, vers_case, rot_ccw

# (pourcentage minimal, quarts horaires), du haut vers le bas
TRANCHES = ((90, 1), (75, 3), (45, 2), (30, 3), (0, 1))


# Le jeu envoie la confusion elle-même, au début de chaque tour, comme un effet sur le perso
# (mêmes unités que les guides) : action → (sens, quarts par unité). Horaire = +, contre = −.
EFFETS_CONFUSION = {770: (1, 1 / 90), 771: (1, 1), 772: (1, 1 / 2),
                    773: (-1, 1 / 90), 774: (-1, 1), 775: (-1, 1 / 2)}


def quarts_depuis_effet(action: int, valeur: int) -> int | None:
    """Quarts horaires d'un effet de confusion (ex. 773 = 90 → 90° contre-horaire → 3)."""
    if action not in EFFETS_CONFUSION or not isinstance(valeur, int):
        return None
    sens, par_unite = EFFETS_CONFUSION[action]
    return round(sens * valeur * par_unite) % 4


def tranche_de(etat) -> int | None:
    """Quarts horaires du tour : correction à la main, sinon la confusion envoyée par le jeu,
    sinon le tableau des PV (repli)."""
    if getattr(etat, "quarts_force", None) is not None:
        return etat.quarts_force
    confusion = getattr(etat, "confusion", None) or {}
    if etat.moi in confusion:
        return confusion[etat.moi]
    if etat.pv_debut_tour is not None and etat.pv_max:
        return quarts(etat.pv_debut_tour, etat.pv_max)
    return None


def quarts(pv: int, pv_max: int) -> int:
    pct = (pv * 100) // pv_max if pv_max > 0 else 0
    for seuil, q in TRANCHES:
        if pct >= seuil:
            return q
    return TRANCHES[-1][1]


def case_a_cliquer(moi: int, cible: int, quarts: int, lignes_melee: int) -> int | None:
    """Case où cliquer pour toucher `cible`, ou None si elle sort de la grille."""
    pm, pc = vers_uv(moi), vers_uv(cible)
    if pm is None or pc is None:
        return None
    du, dv = pc[0] - pm[0], pc[1] - pm[1]
    for _ in range((quarts + lignes_melee) % 4):
        du, dv = rot_ccw(du, dv)
    return vers_case(pm[0] + du, pm[1] + dv)
