"""Fenêtres du jeu sous macOS (liste des fenêtres du système, Quartz).

Le titre des fenêtres n'est lisible que si Haretool a l'autorisation
« Enregistrement de l'écran » ; sans elle, chaque fenêtre s'appelle « Dofus »
et l'association se fait par élimination (un seul compte, une seule fenêtre).
"""

from __future__ import annotations

from .fenetres import FenetreJeu

BARRE_DE_TITRE = 28          # points : hauteur de la barre de titre d'une fenêtre non plein écran
TAILLE_MIN = 200


def lister() -> list[FenetreJeu]:
    try:
        import Quartz
        from AppKit import NSScreen, NSWorkspace
    except Exception:
        return []
    try:
        infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID) or []
        devant = NSWorkspace.sharedWorkspace().frontmostApplication()
        pid_devant = int(devant.processIdentifier()) if devant else -1
        ecran = NSScreen.mainScreen().frame().size.height if NSScreen.mainScreen() else 0
        trouvees: list[FenetreJeu] = []
        for w in infos:
            proprietaire = str(w.get("kCGWindowOwnerName", "") or "")
            if "dofus" not in proprietaire.lower() or int(w.get("kCGWindowLayer", 0)) != 0:
                continue
            b = w.get("kCGWindowBounds") or {}
            x, y = int(b.get("X", 0)), int(b.get("Y", 0))
            largeur, hauteur = int(b.get("Width", 0)), int(b.get("Height", 0))
            if largeur < TAILLE_MIN or hauteur < TAILLE_MIN:
                continue
            if ecran and hauteur < ecran - 1:          # fenêtre avec barre de titre : la zone de jeu est dessous
                y, hauteur = y + BARRE_DE_TITRE, hauteur - BARRE_DE_TITRE
            titre = str(w.get("kCGWindowName") or proprietaire)
            trouvees.append(FenetreJeu(int(w.get("kCGWindowNumber", 0)), titre, (x, y, largeur, hauteur),
                                       not bool(w.get("kCGWindowIsOnscreen", False)),
                                       int(w.get("kCGWindowOwnerPID", -2)) == pid_devant))
        return trouvees
    except Exception:
        return []
