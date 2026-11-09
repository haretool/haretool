"""Ligne de vue entre deux cases, calculée en entiers dans le repère (u, v).

On suit le segment qui relie les centres des deux cases. Sur ce segment, la
frontière numéro i de l'axe u est franchie à la fraction (1 + 2i) sur (2 |du|),
celle de l'axe v à (1 + 2j) sur (2 |dv|). Pour savoir laquelle vient d'abord,
on compare (1 + 2i) |dv| et (1 + 2j) |du| : aucun nombre à virgule.
Égalité : le segment passe par un coin, on avance sur les deux axes à la fois
sans toucher les deux cases voisines du coin. Les extrémités ne comptent pas.
"""

from .grille import vers_uv, vers_case


def _signe(x: int) -> int:
    return (x > 0) - (x < 0)


def traversees(de: int, vers: int) -> list[int | None] | None:
    """Cases traversées entre `de` et `vers` (exclues), None si une extrémité est invalide.

    Une case traversée hors de la grille est rendue comme None.
    """
    pa, pb = vers_uv(de), vers_uv(vers)
    if pa is None or pb is None:
        return None
    du, dv = pb[0] - pa[0], pb[1] - pa[1]
    au, av = abs(du), abs(dv)
    su, sv = _signe(du), _signe(dv)
    u, v = pa
    i = j = 0
    cases: list[int | None] = []
    while i < au or j < av:
        if i < au and j < av:
            gauche, droite = (1 + 2 * i) * av, (1 + 2 * j) * au
        else:
            gauche, droite = (0, 1) if i < au else (1, 0)
        if gauche < droite:
            u += su
            i += 1
        elif gauche > droite:
            v += sv
            j += 1
        else:
            u += su
            v += sv
            i += 1
            j += 1
        if (u, v) != pb:
            cases.append(vers_case(u, v))
    return cases


def en_vue(de: int, vers: int, bloquantes: set[int]) -> bool:
    """Vrai si aucune case bloquante n'est sur le chemin. Inconnu → vrai (pas d'alerte à tort)."""
    chemin = traversees(de, vers)
    if chemin is None:
        return True
    return not any(n in bloquantes for n in chemin if n is not None)
