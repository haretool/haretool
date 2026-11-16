"""Fenêtre transparente posée sur la zone de jeu d'un compte.

Toujours devant, sans cadre, et traversée par la souris : on clique dans le jeu
à travers elle. Seul le mode calibrage capte deux clics.
"""

from __future__ import annotations

import ctypes
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from .calibrage import Calibrage
from .capture_ecran import exclure_des_copies
from .fenetres import FenetreJeu
from .marques import Marque

ICONES = Path(__file__).parent / "icones"
TAILLE_ICONE = 0.8          # côté de l'icône, en hauteur de case
BLANC_ZONE = "#FFFFFF"      # contour des cases où le sort tombe vraiment

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000


@lru_cache(maxsize=64)
def icone_svg(forme: str, couleur: str) -> bytes:
    return (ICONES / f"{forme}.svg").read_bytes().replace(b"#COULEUR", couleur.encode("ascii"))


def geometrie(marque: Marque, cal: Calibrage, taille_icones: float = 1.0) -> tuple[QPolygonF | None, QRectF | None]:
    """Losange (pour un fond) ou rectangle de l'icône, en pixels de la zone de jeu."""
    cx, cy = cal.pixel(marque.case)
    largeur, hauteur = cal.taille_losange()
    if marque.forme == "losange":
        poly = QPolygonF([QPointF(cx, cy - hauteur / 2), QPointF(cx + largeur / 2, cy),
                          QPointF(cx, cy + hauteur / 2), QPointF(cx - largeur / 2, cy)])
        return poly, None
    cote = hauteur * TAILLE_ICONE * taille_icones
    return None, QRectF(cx - cote / 2, cy - cote / 2, cote, cote)


class Overlay(QWidget):
    def __init__(self) -> None:
        drapeaux = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if sys.platform != "win32":       # macOS / Linux : la souris traverse le dessin (Windows : _traversable)
            drapeaux |= Qt.WindowTransparentForInput
        super().__init__(None, drapeaux)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._marques: list[Marque] = []
        self._cal: Calibrage | None = None
        self._opacite = 0.85
        self._taille_icones = 1.0
        self._fenetre: FenetreJeu | None = None
        self._zone: list[int] = []
        self.exclue_des_copies = False     # vrai quand nos dessins n'apparaissent pas dans une copie d'écran

    # -------------------------------------------------------------- réglages

    def regler(self, opacite: float, taille_icones: float) -> None:
        self._opacite, self._taille_icones = opacite, taille_icones
        self.update()

    def suivre(self, f: FenetreJeu | None) -> None:
        """Se colle à la zone de jeu ; se cache si la fenêtre est réduite ou derrière."""
        self._fenetre = f
        if f is None or f.reduite or not f.devant:
            self.hide()
            return
        x, y, w, h = f.rect
        if self.geometry().getRect() != (x, y, w, h):
            self.setGeometry(x, y, w, h)
        if not self.isVisible():
            self.show()
            self._traversable()

    def afficher(self, marques: list[Marque], cal: Calibrage | None) -> None:
        if marques != self._marques or cal is not self._cal:
            self._marques, self._cal = marques, cal
            self.update()

    def afficher_zone(self, cases: list[int]) -> None:
        if cases != self._zone:
            self._zone = list(cases)
            self.update()

    # -------------------------------------------------------------- Windows

    def _traversable(self) -> None:
        """La souris passe à travers le dessin, et il ne prend jamais le focus."""
        if sys.platform != "win32" or not self.isVisible():
            return
        u32 = ctypes.windll.user32
        hwnd = int(self.winId())
        style = u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.exclue_des_copies = exclure_des_copies(hwnd)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._traversable()

    # -------------------------------------------------------------- dessin

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._cal is None:
            return
        p.setOpacity(self._opacite)
        for m in self._marques:
            poly, rect = geometrie(m, self._cal, self._taille_icones)
            if poly is not None:
                c = QColor(m.couleur)
                fond = QColor(c)
                fond.setAlpha(90)
                p.setBrush(QBrush(fond))
                p.setPen(QPen(c, 2.5))
                p.drawPolygon(poly)
            elif rect is not None:
                QSvgRenderer(QByteArray(icone_svg(m.forme, m.couleur))).render(p, rect)
        if self._zone:          # par-dessus tout le reste : case blanche pleine, fond semi-transparent
            p.setOpacity(1.0)
            fond = QColor(BLANC_ZONE)
            fond.setAlphaF(0.5 * self._opacite)       # suit le curseur « Opacité »
            p.setBrush(QBrush(fond))
            p.setPen(QPen(QColor(BLANC_ZONE), max(2.0, self._cal.hauteur / 18), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            l, h = self._cal.taille_losange()
            l, h = l * 0.46, h * 0.46      # un léger retrait : chaque case reste distincte
            for case in self._zone:
                cx, cy = self._cal.pixel(case)
                p.drawPolygon(QPolygonF([QPointF(cx, cy - h), QPointF(cx + l, cy),
                                         QPointF(cx, cy + h), QPointF(cx - l, cy)]))
        p.end()


def _demo() -> None:
    from .fenetres import lister
    from .marques import PALETTE_DEFAUT, ROUGE
    app = QApplication.instance() or QApplication(sys.argv)
    o = Overlay()
    marques = [Marque("losange", 300, PALETTE_DEFAUT[0]), Marque("losange", 330, PALETTE_DEFAUT[0]),
               Marque("losange", 274, PALETTE_DEFAUT[1]),
               Marque("epee", 330, PALETTE_DEFAUT[0]), Marque("indisponible", 274, ROUGE),
               Marque("hors_vue", 330, PALETTE_DEFAUT[0])]

    def tic():
        fenetres = lister()
        f = next((x for x in fenetres if x.devant), None)
        if f is None:
            ecran = app.primaryScreen().geometry()
            f = FenetreJeu(0, "démo", (ecran.x(), ecran.y(), ecran.width(), ecran.height()), False, True)
        w, h = f.rect[2], f.rect[3]
        o.afficher(marques, Calibrage(w / 2 - 6.5 * w / 15, h * 0.08, w / 15, w / 30))
        o.suivre(f)

    t = QTimer()
    t.timeout.connect(tic)
    t.start(200)
    tic()
    QTimer.singleShot(int(sys.argv[2]) * 1000 if len(sys.argv) > 2 else 20000, app.quit)
    app.exec()


if __name__ == "__main__" and "--demo" in sys.argv:
    _demo()
