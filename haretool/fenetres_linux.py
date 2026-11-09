"""Fenêtres du jeu sous Linux (X11, et XWayland sous Wayland).

Chaque fenêtre de la liste du gestionnaire de fenêtres (_NET_CLIENT_LIST) est
rattachée à son processus (_NET_WM_PID) ; on garde celles du jeu (Dofus).
"""

from __future__ import annotations

from .fenetres import FenetreJeu

_ecran = None


def _connexion():
    global _ecran
    if _ecran is None:
        from Xlib import display
        _ecran = display.Display()
    return _ecran


def _nom_processus(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/comm", encoding="utf-8", errors="replace") as f:
            return f.read().strip().lower()
    except OSError:
        return ""


def _est_le_jeu(fenetre, pid_atome, classe: str) -> bool:
    if "dofus" in classe:
        return True
    p = fenetre.get_full_property(pid_atome, 0)
    return bool(p and p.value and _nom_processus(int(p.value[0])).startswith("dofus"))


def lister() -> list[FenetreJeu]:
    try:
        from Xlib import X
        d = _connexion()
    except Exception:
        return []
    try:
        racine = d.screen().root
        atome = d.intern_atom
        liste = racine.get_full_property(atome("_NET_CLIENT_LIST"), X.AnyPropertyType)
        active = racine.get_full_property(atome("_NET_ACTIVE_WINDOW"), X.AnyPropertyType)
        id_actif = int(active.value[0]) if active and active.value else 0
        cachee = atome("_NET_WM_STATE_HIDDEN")
        trouvees: list[FenetreJeu] = []
        for wid in (liste.value if liste else []):
            f = d.create_resource_object("window", int(wid))
            try:
                classe = " ".join(f.get_wm_class() or ()).lower()
                if not _est_le_jeu(f, atome("_NET_WM_PID"), classe):
                    continue
                nom = f.get_full_property(atome("_NET_WM_NAME"), atome("UTF8_STRING"))
                titre = (nom.value.decode("utf-8", "replace") if nom and isinstance(nom.value, bytes)
                         else (f.get_wm_name() or "Dofus"))
                g = f.get_geometry()
                coin = racine.translate_coords(f, 0, 0)       # origine de la zone de jeu à l'écran
                etat = f.get_full_property(atome("_NET_WM_STATE"), X.AnyPropertyType)
                reduite = bool(etat and cachee in etat.value)
                trouvees.append(FenetreJeu(int(wid), str(titre), (coin.x, coin.y, g.width, g.height),
                                           reduite, int(wid) == id_actif))
            except Exception:
                continue
        return trouvees
    except Exception:
        return []
