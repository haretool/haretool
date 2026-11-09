"""Grille de combat : 560 cases numérotées ligne par ligne (14 par ligne, 40 lignes).

Repère diagonal (u, v) : q = n // 14, r = n % 14, u + v = q, u - v = 2r + (q % 2).
Deux cases se touchent quand elles diffèrent d'exactement 1 sur u OU sur v.
"""

CASES = 560
LARGEUR = 14
LIGNES = 40


def vers_uv(case: int) -> tuple[int, int] | None:
    if not 0 <= case < CASES:
        return None
    q, r = divmod(case, LARGEUR)
    d = 2 * r + (q % 2)
    return (q + d) // 2, (q - d) // 2


def vers_case(u: int, v: int) -> int | None:
    q, d = u + v, u - v
    if not 0 <= q < LIGNES:
        return None
    reste = d - (q % 2)
    if reste % 2:
        return None
    r = reste // 2
    if not 0 <= r < LARGEUR:
        return None
    return q * LARGEUR + r


def rot_ccw(u: int, v: int) -> tuple[int, int]:
    """Quart de tour contre-horaire dans le repère (u, v)."""
    return v, -u


def adjacentes(a: int, b: int) -> bool:
    pa, pb = vers_uv(a), vers_uv(b)
    if pa is None or pb is None:
        return False
    return abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1
