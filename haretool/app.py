"""Assemblage : écoute réseau → un état par compte → un overlay par fenêtre du jeu."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
import queue
import sys
import time

if sys.platform == "win32":
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")   # 1 pixel Qt = 1 pixel Windows
elif sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")   # X11/XWayland : l'overlay peut se placer sur le jeu

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer          # noqa: E402
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap, QColor, QPolygonF  # noqa: E402
from PySide6.QtCore import QPointF, Qt                                 # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon  # noqa: E402

from .calibrage import Calibrages                           # noqa: E402
from .comptes import Comptes, Compte                                   # noqa: E402
from .confusion import tranche_de                                      # noqa: E402
from .ecoute import Ecoute, nettoyer                                   # noqa: E402
from .fenetre_reglages import EtatAffiche, FenetreReglages             # noqa: E402
from .fenetres import FenetreJeu, associer, lister                     # noqa: E402
from .marques import marques                                           # noqa: E402
from .overlay import Overlay                                           # noqa: E402
from .protocole import EMBARQUE, URL_OFFICIELLE, Protocole                             # noqa: E402
from .reglages import Reglages                                         # noqa: E402
from .terrain import est_harebourg, jouables                           # noqa: E402
from .zone import cases_rouges, zone_reelle                            # noqa: E402
from . import capture_ecran, theme                                     # noqa: E402

journal = logging.getLogger("haretool")
ID_RACCOURCI = 0x4854
WM_HOTKEY = 0x0312
MODIFICATEURS = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "meta": 0x8}


def est_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def verrou_unique(nom: str = r"Local\HaretoolUnique"):
    """Rend une poignée si on est la seule copie lancée, None si une autre tourne déjà."""
    if sys.platform != "win32":
        import tempfile
        from PySide6.QtCore import QLockFile
        verrou = QLockFile(os.path.join(tempfile.gettempdir(), "haretool.verrou"))
        return verrou if verrou.tryLock(100) else None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wt.HANDLE
    poignee = k32.CreateMutexW(None, False, nom)
    if not poignee:
        return None
    if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
        k32.CloseHandle(poignee)
        return None
    return poignee


def relancer_en_admin() -> None:
    dossier = None
    if "__compiled__" in globals():          # exe compilé (Nuitka) : argv[0] = l'exe livré
        exe, params = os.path.abspath(sys.argv[0]), " ".join(f'"{a}"' for a in sys.argv[1:])
    elif getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe, params = sys.executable, "-m haretool " + " ".join(f'"{a}"' for a in sys.argv[1:])
        dossier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, dossier, 1)


def touche_windows(sequence: str) -> tuple[int, int] | None:
    """« Ctrl+Alt+H » → (modificateurs, code de touche) pour RegisterHotKey."""
    morceaux = [m.strip().lower() for m in sequence.split("+") if m.strip()]
    if not morceaux:
        return None
    mods = 0
    for m in morceaux[:-1]:
        if m not in MODIFICATEURS:
            return None
        mods |= MODIFICATEURS[m]
    touche = morceaux[-1].upper()
    if len(touche) == 1 and touche.isalnum():
        return mods, ord(touche)
    if touche.startswith("F") and touche[1:].isdigit() and 1 <= int(touche[1:]) <= 12:
        return mods, 0x70 + int(touche[1:]) - 1
    return None


class FiltreRaccourci(QAbstractNativeEventFilter):
    def __init__(self, rappel) -> None:
        super().__init__()
        self._rappel = rappel

    def nativeEventFilter(self, type_evenement, message):
        if type_evenement == b"windows_generic_MSG":
            m = wt.MSG.from_address(int(message))
            if m.message == WM_HOTKEY and m.wParam == ID_RACCOURCI:
                self._rappel()
                return True, 0
        return False, 0


class Application:
    def __init__(self, app: QApplication, essai: bool = False, capture: bool = False) -> None:
        self.app = app
        self.capture = [] if capture else None     # paquets bruts, écrits à la fermeture
        self._debut_capture = time.monotonic()
        self.essai = essai          # mode essai : chaque monstre compte comme le Comte
        self.reglages = Reglages.charger()
        self.calibrages = Calibrages.depuis_dict(self.reglages.reglage_fin)
        url = self.reglages.url_protocole or (None if os.environ.get("HARETOOL_HORS_LIGNE") else URL_OFFICIELLE)
        self.protocole, self.origine = Protocole.charger(EMBARQUE, url)
        self.comptes = Comptes(self.protocole, (lambda m: True) if essai else est_harebourg)
        self.file: queue.Queue = queue.Queue()
        self.ecoute = Ecoute(lambda p: self.file.put((p, time.monotonic())))
        self.en_pause = False

        self.fenetre = FenetreReglages(self.reglages)
        self.fenetre.setWindowIcon(theme.icone())
        self.fenetre.change.connect(self._reglages_changes)
        self.fenetre.melee_zero.connect(self._melee_zero)
        self.fenetre.forcer_tranche.connect(self._forcer)
        self.fenetre.ajuster.connect(self._ajuster)
        self.fenetre.pause.connect(lambda oui: (self.action_pause.setChecked(oui), self._pause(oui)))
        self.fenetre.apprendre.connect(self._apprendre)

        self.icone = QSystemTrayIcon(theme.icone())
        self.icone.setToolTip("Haretool (essai : tous les monstres)" if essai else "Haretool")
        menu = QMenu()
        menu.addAction(QAction("Réglages", menu, triggered=self.montrer_reglages))
        self.action_pause = QAction("Pause", menu, checkable=True, triggered=self._pause)
        menu.addAction(self.action_pause)
        menu.addSeparator()
        menu.addAction(QAction("Quitter", menu, triggered=self.quitter))
        self.icone.setContextMenu(menu)
        self.icone.activated.connect(lambda raison: raison == QSystemTrayIcon.Trigger and self.montrer_reglages())
        self._menu = menu

        self.filtre = FiltreRaccourci(self.montrer_reglages)
        app.installNativeEventFilter(self.filtre)
        self._poser_raccourci()

        self.minuteur_paquets = QTimer(timeout=self._traiter_paquets)
        self.minuteur_fenetres = QTimer(timeout=self._rafraichir)
        self.minuteur_zone = QTimer(timeout=self._apercu_zone)

    # -------------------------------------------------------------- vie

    def demarrer(self) -> None:
        try:
            self.ecoute.demarrer()
        except OSError as e:
            QMessageBox.critical(None, "Haretool", f"Impossible d'écouter le trafic du jeu :\n{e}")
            raise SystemExit(1)
        self.icone.show()
        self.fenetre.maj_protocole(self.protocole.version, self.origine, True)
        journal.info("écoute démarrée, protocole %s (%s), essai=%s", self.protocole.version, self.origine, self.essai)
        self.minuteur_paquets.start(30)
        self.minuteur_fenetres.start(200)
        if capture_ecran.disponible():
            self.minuteur_zone.start(100)
        self.montrer_reglages()          # à l'ouverture, la fenêtre est là (fermer = reste près de l'horloge)

    def ecrire_capture(self):
        """Écrit les paquets enregistrés (option --capture) ; rend le chemin du fichier."""
        if self.capture is None:
            return None
        from .protocole import dossier_reglages
        import json
        chemin = dossier_reglages() / time.strftime("capture-%Y%m%d-%H%M%S.json")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps({"source": "Haretool --capture", "paquets": self.capture}))
        journal.info("capture écrite : %s (%d paquets)", chemin, len(self.capture))
        return chemin

    def quitter(self) -> None:
        self.ecrire_capture()
        self.ecoute.arreter()
        try:
            ctypes.windll.user32.UnregisterHotKey(None, ID_RACCOURCI)
        except (AttributeError, OSError):
            pass
        self.icone.hide()
        self.app.quit()

    def montrer_reglages(self) -> None:
        self.fenetre.show()
        self.fenetre.raise_()
        self.fenetre.activateWindow()

    def _pause(self, oui: bool) -> None:
        self.en_pause = oui
        self.fenetre.regler_pause(oui)
        self._rafraichir()

    def _poser_raccourci(self) -> None:
        try:
            u32 = ctypes.windll.user32
        except AttributeError:
            return
        u32.UnregisterHotKey(None, ID_RACCOURCI)
        t = touche_windows(self.reglages.raccourci)
        if t:
            u32.RegisterHotKey(None, ID_RACCOURCI, t[0] | 0x4000, t[1])   # MOD_NOREPEAT

    def _reglages_changes(self) -> None:
        self._poser_raccourci()
        self._rafraichir()

    # -------------------------------------------------------------- données

    def _traiter_paquets(self) -> None:
        for _ in range(2000):
            try:
                p, t = self.file.get_nowait()
            except queue.Empty:
                break
            self.comptes.sur_paquet(p, t)
            if self.capture is not None:
                ip, port = (p.dst, p.dport) if p.sport == 5555 else (p.src, p.sport)
                self.capture.append({"t": round(t - self._debut_capture, 4),
                                     "sens": "serveur->client" if p.sport == 5555 else "client->serveur",
                                     "flux": f"{ip}:{port}", "seq": p.seq, "hex": p.charge.hex()})
        if self.ecoute.erreur:
            journal.warning("écoute : %s", self.ecoute.erreur)
            self.ecoute.erreur = None
        for c in self.comptes.oublier_inactifs(time.monotonic()):
            if c.overlay is not None:
                c.overlay.hide()
                c.overlay.deleteLater()

    def _fenetre_de(self, c: Compte, fenetres: list[FenetreJeu]) -> FenetreJeu | None:
        nom = c.etat.nom_perso
        choisi = self.reglages.association.get(nom) if nom else None
        if choisi:
            f = next((x for x in fenetres if x.titre == choisi), None)
            if f:
                return f
        f = associer(nom, fenetres)
        if f is None and len(fenetres) == 1 and len(self.comptes.comptes()) == 1:
            f = fenetres[0]
        return f

    def _rafraichir(self) -> None:
        fenetres = lister()
        etats = []
        ok = True
        options = self.reglages.options_dessin()
        for c in self.comptes.comptes():
            e = c.etat
            ok = ok and e.protocole_ok
            f = self._fenetre_de(c, fenetres)
            c.devant_reel = f is not None and f.devant and not f.reduite   # pour l'aperçu de zone
            if f is not None and self.fenetre.isActiveWindow():
                f = f._replace(devant=True)     # on règle : le dessin reste visible
            c.fenetre = f
            if c.overlay is None:
                c.overlay = Overlay()
            c.overlay.regler(self.reglages.opacite, self.reglages.taille_icones)
            nom = e.nom_perso or f"compte {c.cle[1]}"
            actif = self.reglages.actif_par_compte.get(nom, True) and not self.en_pause
            cal = self.calibrages.pour(f.rect[2], f.rect[3]) if f else None
            c.cal = cal
            dessin = marques(e, options) if actif else []
            if actif and dessin and cal is not None:
                c.overlay.afficher(dessin, cal)
                c.overlay.suivre(f)
            else:
                c.overlay.hide()
            tranche = tranche_de(e) if e.en_combat else None
            resume = (e.en_combat, e.moi, e.nom_perso, e.harebourg_present, len(dessin), cal is not None,
                      f.titre if f else None, e.carte, e.pv_debut_tour, e.pv_max, e.lignes_melee)
            if getattr(c, "_resume", None) != resume:
                c._resume = resume
                journal.info("compte %s : combat=%s moi=%s nom=%s comte=%s marques=%d calibré=%s fenêtre=%s carte=%s "
                             "pv_debut_tour=%s pv_max=%s mêlée=%s", c.cle[1], *resume)
            etats.append(EtatAffiche(f"{c.cle[0]}:{c.cle[1]}", nom, e.en_combat, tranche, e.lignes_melee,
                                     [x.titre for x in fenetres], self.reglages.association.get(nom),
                                     cal is not None, e.pv, e.pv_max,
                                     calibre_auto=bool(f) and self.calibrages.exact(f.rect[2], f.rect[3]) is None))
        self.fenetre.maj_comptes(etats)
        self.fenetre.maj_protocole(self.protocole.version, self.origine, ok)

    def _apercu_zone(self) -> None:
        """Lit la zone rouge que le jeu dessine et la redessine là où le sort tombe vraiment.
        Seulement si le jeu est vraiment devant et que nos dessins sont exclus de la copie
        d'écran : sinon on pourrait relire nos propres losanges (un contour faux est pire que rien)."""
        for c in self.comptes.comptes():
            o = c.overlay
            if o is None:
                continue
            zone: list[int] = []
            e, f, cal = c.etat, c.fenetre, c.cal
            if (self.reglages.apercu_zone and not self.en_pause and o.isVisible() and o.exclue_des_copies
                    and c.devant_reel and f is not None and cal is not None
                    and e.moi in e.positions):
                q = tranche_de(e)
                img = capture_ecran.copier(f.rect) if q is not None else None
                if img is not None:
                    jouable = jouables(e.carte)
                    rouges = cases_rouges(img, cal, jouable if jouable is not None else range(560))
                    zone = zone_reelle(e.positions[e.moi], rouges, q, e.lignes_melee, jouable)
                    if (sorted(rouges), zone) != getattr(c, "_zone_vue", None):
                        c._zone_vue = (sorted(rouges), zone)
                        if rouges:
                            journal.info("zone : moi=%s quarts=%s mêlée=%s rouges=%s → blanches=%s",
                                         e.positions[e.moi], q, e.lignes_melee, sorted(rouges), zone)
            o.afficher_zone(zone)

    def _compte(self, cle: str) -> Compte | None:
        return next((c for c in self.comptes.comptes() if f"{c.cle[0]}:{c.cle[1]}" == cle), None)

    def _melee_zero(self, cle: str) -> None:
        c = self._compte(cle)
        if c:
            c.etat.lignes_melee = 0
            self._rafraichir()

    def _forcer(self, cle: str, q: int) -> None:
        c = self._compte(cle)
        if c:
            c.etat.quarts_force = q
            self._rafraichir()

    def _ajuster(self, cle: str, dx: int, dy: int, echelle: float) -> None:
        """Réglage fin du calibrage de la fenêtre de ce compte (décalage en px, échelle)."""
        c = self._compte(cle)
        if c is None or c.fenetre is None:
            return
        w, h = c.fenetre.rect[2], c.fenetre.rect[3]
        cal = self.calibrages.pour(w, h)
        if cal is None:
            return
        self.calibrages.poser(w, h, cal.decaler(dx, dy, echelle))
        self.reglages.reglage_fin = self.calibrages.vers_dict()
        try:
            self.reglages.sauver()
        except OSError:
            pass
        self._rafraichir()

    def _apprendre(self) -> None:
        from .apprendre import lancer_depuis_application
        lancer_depuis_application(self)

def principal() -> int:
    if sys.platform == "win32" and not est_admin() and "--sans-admin" not in sys.argv:
        relancer_en_admin()
        return 0
    from .protocole import dossier_reglages
    dossier_reglages().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=dossier_reglages() / "journal.txt", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(message)s")
    verrou = verrou_unique()
    if sys.platform == "win32":
        # identité propre dans la barre des tâches : la coiffe, pas l'icône de Python
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Haretool.Outil")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    theme.charger_polices()
    app.setStyleSheet(theme.FEUILLE)
    app.setWindowIcon(theme.icone())
    if verrou is None:
        QMessageBox.information(None, "Haretool", "Haretool est déjà lancé (la coiffe du Comte, près de l'horloge).")
        return 0
    nettoyer()
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Haretool")
    a = Application(app, essai="--essai" in sys.argv, capture="--capture" in sys.argv)
    a.demarrer()
    return app.exec()
