"""Aperçu de la zone réelle d'un sort.

Le jeu dessine en rouge la zone du sort autour de la case visée. On lit ce rouge sur une
copie de l'écran, puis on envoie chaque case rouge là où la confusion la fait vraiment
tomber. Aucune donnée de sort : la forme vient du jeu lui-même.

Couleurs mesurées sur 37 images de combat (2560×1440) : le rouge de zone change selon la
case dessous. Les barres de PV des monstres, plus vives, sont exclues (vert trop bas).
"""

from __future__ import annotations

from typing import Iterable, NamedTuple

from .confusion import case_touchee

LARGEUR_MESUREE = 124.0     # largeur d'une case quand les seuils ont été mesurés (2560×1440)


class ImageEcran(NamedTuple):
    """Pixels BGRA, ligne par ligne, origine = coin haut gauche de la zone de jeu."""
    octets: bytes
    largeur: int
    hauteur: int


def pixel_zone(r: int, g: int, b: int) -> bool:
    """Rouge franc. La teinte exacte change avec l'éclairage de la carte : (209,80,72) chez les
    Pious, (210,42,43) ou (188,25,48) ailleurs. L'orange du placement, (233,88,15) à (254,137,45),
    a très peu de bleu : exclu par b ≥ g/2 (le rouge de zone a toujours b ≥ 0,69·g)."""
    return r >= 150 and r - g >= 85 and g <= 115 and b <= 110 and r - b >= 60 and 2 * b >= g


def _part(img: ImageEcran, cx: float, cy: float, demi_x: float, demi_y: float, n_x: int, n_y: int) -> float:
    """Part de pixels « zone » sur une petite grille de n_x × n_y points autour de (cx, cy)."""
    o, w, h = img.octets, img.largeur, img.hauteur
    total = oui = 0
    for i in range(n_x):
        x = int(cx - demi_x + 2 * demi_x * i / (n_x - 1))
        if not 0 <= x < w:
            continue
        for j in range(n_y):
            y = int(cy - demi_y + 2 * demi_y * j / (n_y - 1))
            if not 0 <= y < h:
                continue
            k = (y * w + x) * 4
            total += 1
            oui += pixel_zone(o[k + 2], o[k + 1], o[k])
    return oui / total if total else 0.0


def est_rouge(img: ImageEcran, cal, case: int) -> bool:
    """La couleur seule ne suffit pas (barres de PV, cercles des monstres : même rouge).
    On exige la FORME d'une case pleine : 3 coins du losange sur 4, ou le haut ET le bas.
    Une barre de PV est trop fine pour couvrir le haut et le bas ; un monstre ou la cible
    au centre cachent au plus un coin."""
    x, y = cal.pixel(case)
    s = cal.largeur / LARGEUR_MESUREE
    dx, dy = 0.3 * cal.largeur, 0.3 * cal.hauteur
    gauche, droite, haut, bas = (_part(img, cx, cy, 4 * s, 2 * s, 3, 3) >= 0.5
                                 for cx, cy in ((x - dx, y), (x + dx, y), (x, y - dy), (x, y + dy)))
    return (haut and bas) or (gauche + droite + haut + bas) >= 3


def cases_rouges(img: ImageEcran, cal, cases: Iterable[int]) -> set[int]:
    return {c for c in cases if est_rouge(img, cal, c)}


def zone_reelle(moi: int, rouges: Iterable[int], quarts: int, lignes_melee: int,
                jouable: set[int] | None = None) -> list[int]:
    """Cases où le sort tombe vraiment, triées ; celles hors grille ou hors carte disparaissent."""
    sortie = set()
    for c in rouges:
        t = case_touchee(moi, c, quarts, lignes_melee)
        if t is not None and (jouable is None or t in jouable):
            sortie.add(t)
    return sorted(sortie)
