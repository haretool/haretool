"""Passage d'une case de la grille à un pixel de la fenêtre du jeu.

À l'écran : x = x0 + e·L, y = y0 + q·H/2, avec e = (u − v)/2 et q = u + v.
La forme des cases est fixe (deux fois plus larges que hautes, H = L/2) : deux
clics (case connue, pixel cliqué) donnent l'échelle L par moindres carrés.
"""

from __future__ import annotations

from .grille import vers_uv

DISTANCE_MIN = 3
LARGEUR_MIN, LARGEUR_MAX = 20.0, 400.0     # largeur plausible d'une case à l'écran (px)
CASE_CENTRALE = 280


def _eq(case: int) -> tuple[float, int]:
    uv = vers_uv(case)
    if uv is None:
        raise ValueError(f"case {case} hors grille")
    u, v = uv
    return (u - v) / 2, u + v


class Calibrage:
    def __init__(self, x0: float, y0: float, largeur: float, hauteur: float) -> None:
        self.x0, self.y0, self.largeur, self.hauteur = x0, y0, largeur, hauteur

    @staticmethod
    def _ajuster(a: tuple[int, tuple[float, float]], case_b: int, pb: tuple[float, float]):
        """Échelle par moindres carrés, forme des cases fixée (2:1) : (calibrage, écart en cases)."""
        (ca, (xa, ya)) = a
        ua, ub = vers_uv(ca), vers_uv(case_b)
        if ua is None or ub is None:
            raise ValueError("case hors grille")
        if abs(ua[0] - ub[0]) + abs(ua[1] - ub[1]) < DISTANCE_MIN:
            raise ValueError("cases trop proches pour calibrer")
        (ea, qa), (eb, qb) = _eq(ca), _eq(case_b)
        de, dq4 = eb - ea, (qb - qa) / 4          # x = e·L, y = q·L/4 (H = L/2)
        dx, dy = pb[0] - xa, pb[1] - ya
        largeur = (de * dx + dq4 * dy) / (de * de + dq4 * dq4)
        if largeur <= 0:
            raise ValueError("clics incohérents")
        ecart = ((dx - de * largeur) ** 2 + (dy - dq4 * largeur) ** 2) ** 0.5 / largeur
        cal = Calibrage(xa - ea * largeur, ya - qa * largeur / 4, largeur, largeur / 2)
        return cal, ecart

    @classmethod
    def depuis_deux_points(cls, a: tuple[int, tuple[float, float]],
                           b: tuple[int, tuple[float, float]]) -> "Calibrage":
        return cls._ajuster(a, b[0], b[1])[0]

    @classmethod
    def depuis_clics(cls, moi: tuple[int, tuple[float, float]], cases_monstres: list[int],
                     pixel_monstre: tuple[float, float]) -> tuple["Calibrage", int]:
        """Le 2e clic vise UN des monstres, sans dire lequel : on garde celui qui colle le mieux."""
        meilleur = None
        for case in cases_monstres:
            try:
                cal, ecart = cls._ajuster(moi, case, pixel_monstre)
            except ValueError:
                continue
            if not LARGEUR_MIN <= cal.largeur <= LARGEUR_MAX:
                continue
            if meilleur is None or ecart < meilleur[0]:
                meilleur = (ecart, cal, case)
        if meilleur is None:
            raise ValueError("aucun monstre assez loin pour calibrer")
        return meilleur[1], meilleur[2]

    def pixel(self, case: int) -> tuple[float, float]:
        e, q = _eq(case)
        return self.x0 + e * self.largeur, self.y0 + q * self.hauteur / 2

    def taille_losange(self) -> tuple[float, float]:
        return self.largeur, self.hauteur

    def decaler(self, dx: float, dy: float, echelle: float = 1.0) -> "Calibrage":
        """Réglage fin : décalage en pixels, et échelle autour de la case centrale."""
        cx, cy = self.pixel(CASE_CENTRALE)
        nl, nh = self.largeur * echelle, self.hauteur * echelle
        e, q = _eq(CASE_CENTRALE)
        return Calibrage(cx + dx - e * nl, cy + dy - q * nh / 2, nl, nh)

    def vers_dict(self) -> dict:
        return {"x0": self.x0, "y0": self.y0, "largeur": self.largeur, "hauteur": self.hauteur}

    @classmethod
    def depuis_dict(cls, d: dict) -> "Calibrage":
        return cls(float(d["x0"]), float(d["y0"]), float(d["largeur"]), float(d["hauteur"]))


REFERENCE = ((2560, 1440), Calibrage(440.4, 28.3, 124.0, 62.0))
"""Grille calée sur le damier d'une image du jeu en combat (plein écran 2560×1440,
réglage automatique sur les cases claires et foncées, à ±0,5 px)."""


def mettre_a_l_echelle(cal: Calibrage, depuis: tuple[int, int], vers: tuple[int, int]) -> Calibrage:
    """Le jeu garde la grille à la même place quand la fenêtre change de taille :
    elle grandit avec la HAUTEUR de la zone de jeu et reste centrée en largeur
    (caméra à hauteur fixe). Un calibrage mesuré à une taille donne donc toutes les autres."""
    (w0, h0), (w1, h1) = depuis, vers
    s = h1 / h0
    return Calibrage(w1 / 2 + (cal.x0 - w0 / 2) * s, cal.y0 * s, cal.largeur * s, cal.hauteur * s)


class Calibrages:
    """Un calibrage par taille de zone de jeu (largeur × hauteur).

    Une taille jamais calibrée se déduit d'une taille connue (sinon de la référence
    embarquée) : plus besoin de calibrer, ni au premier lancement, ni après avoir
    redimensionné la fenêtre du jeu."""

    def __init__(self) -> None:
        self._par_taille: dict[str, Calibrage] = {}

    @staticmethod
    def _cle(largeur: int, hauteur: int) -> str:
        return f"{largeur}x{hauteur}"

    def poser(self, largeur: int, hauteur: int, cal: Calibrage) -> None:
        self._par_taille[self._cle(largeur, hauteur)] = cal

    def exact(self, largeur: int, hauteur: int) -> Calibrage | None:
        """Le calibrage enregistré pour cette taille précise, sans déduction."""
        return self._par_taille.get(self._cle(largeur, hauteur))

    def pour(self, largeur: int, hauteur: int) -> Calibrage | None:
        if largeur <= 0 or hauteur <= 0:
            return None
        cal = self.exact(largeur, hauteur)
        if cal is not None:
            return cal
        connus = []
        for cle, c in self._par_taille.items():
            try:
                w, h = (int(x) for x in cle.split("x"))
            except ValueError:
                continue
            if w > 0 and h > 0:
                connus.append(((w, h), c))
        # la taille connue la plus proche en hauteur : la moins extrapolée
        depuis, cal = min(connus, key=lambda t: abs(t[0][1] - hauteur)) if connus else REFERENCE
        return mettre_a_l_echelle(cal, depuis, (largeur, hauteur))

    def vers_dict(self) -> dict:
        return {k: c.vers_dict() for k, c in self._par_taille.items()}

    @classmethod
    def depuis_dict(cls, d: dict | None) -> "Calibrages":
        c = cls()
        for k, v in (d or {}).items():
            try:
                c._par_taille[k] = Calibrage.depuis_dict(v)
            except (KeyError, TypeError, ValueError):
                pass
        return c
