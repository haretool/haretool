"""Fenêtre de réglages sur une seule page, sur le modèle d'une fenêtre d'app sombre :
à gauche une fiche par compte (état, PV, fenêtre, calibrage et réglage fin ensemble),
à droite les bascules, l'affichage et la lecture du jeu.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QKeySequenceEdit, QLabel, QPushButton, QScrollArea, QSlider, QVBoxLayout,
                               QWidget)

from . import theme
from .reglages import Reglages

LARGEUR, HAUTEUR = 1040, 640
ICONES = theme.ICONES


@dataclass
class EtatAffiche:
    """Ce que la fenêtre montre d'un compte."""
    cle: str
    nom: str
    en_combat: bool
    tranche: int | None
    melee: int
    fenetres: list[str]
    fenetre_choisie: str | None
    calibre: bool
    pv: int | None = None
    pv_max: int | None = None
    calibre_auto: bool = False     # déduit de la taille de la fenêtre, jamais cliqué pour cette taille


def _repolir(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)


def _texte(t: str, nom: str | None = None) -> QLabel:
    l = QLabel(t)
    if nom:
        l.setObjectName(nom)
    return l


def _rang(*widgets, espace: int = 8) -> QHBoxLayout:
    """Une rangée : None = ressort, entier = espace fixe."""
    h = QHBoxLayout()
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(espace)
    for w in widgets:
        if w is None:
            h.addStretch(1)
        elif isinstance(w, int):
            h.addSpacing(w)
        else:
            h.addWidget(w)
    return h


def _section(titre: str) -> QLabel:
    return _texte(titre.upper(), "section")


def _trait() -> QFrame:
    t = QFrame()
    t.setObjectName("trait")
    t.setFixedHeight(1)
    return t


def _stat(titre: str) -> tuple[QWidget, QLabel]:
    """Une petite valeur avec son titre au-dessus (PV, Mêlée)."""
    boite = QWidget()
    v = QVBoxLayout(boite)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(3)
    v.addWidget(_texte(titre, "stat-titre"))
    valeur = _texte("—", "stat")
    valeur.setMinimumHeight(30)
    v.addWidget(valeur)
    return boite, valeur


class FicheCompte(QFrame):
    """Un compte, tout au même endroit : état, PV, fenêtre, confusion, calibrage, réglage fin."""

    def __init__(self, parent: "FenetreReglages", etat: EtatAffiche) -> None:
        super().__init__()
        self.setObjectName("fiche")
        self._parent, self.cle = parent, etat.cle
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(12)

        # ---- ligne 1 : interrupteur + nom, état à droite
        self.actif = QCheckBox(etat.nom)
        self.actif.setObjectName("nom")
        self.actif.setToolTip("Dessiner pour ce compte")
        self.actif.setChecked(parent.reglages.actif_par_compte.get(etat.nom, True))
        self.actif.toggled.connect(lambda val: parent._actif(self.actif.text(), val))
        self.etat = _texte("", "etat")
        v.addLayout(_rang(self.actif, None, self.etat))

        # ---- ligne 2 : PV, mêlée, fenêtre | confusion forcée, mêlée à 0
        pv_boite, self.pv = _stat("PV")
        melee_boite, self.melee = _stat("Mêlée")
        fen_boite = QWidget()
        fv = QVBoxLayout(fen_boite)
        fv.setContentsMargins(0, 0, 0, 0)
        fv.setSpacing(3)
        fv.addWidget(_texte("Fenêtre du jeu", "stat-titre"))
        self.fenetre = QComboBox()
        self.fenetre.setFixedWidth(170)
        self.fenetre.setToolTip("Fenêtre du jeu de ce perso")
        self.fenetre.activated.connect(lambda i: parent._associer(self.actif.text(), self.fenetre.itemText(i)))
        fv.addWidget(self.fenetre)
        self.forcer = QComboBox()
        self.forcer.addItems(["Forcer…", "1 quart", "2 quarts", "3 quarts"])
        self.forcer.setToolTip("Forcer la confusion si le jeu l'a mal lue")
        self.forcer.activated.connect(self._forcer)
        zero = QPushButton("Mêlée à 0")
        zero.clicked.connect(lambda: parent.melee_zero.emit(self.cle))
        ligne2 = _rang(pv_boite, 22, melee_boite, 22, fen_boite, None, self.forcer, zero)
        ligne2.setAlignment(self.forcer, Qt.AlignBottom)
        ligne2.setAlignment(zero, Qt.AlignBottom)
        v.addLayout(ligne2)

        v.addWidget(_trait())

        # ---- ligne 3 : calibrage + réglage fin
        self.point_calibre = QLabel()
        self.point_calibre.setObjectName("voyant")
        self.point_calibre.setFixedSize(8, 8)
        self.calibre = _texte("", "doux")
        self.boutons_reglage = {}
        fleches = []
        for nom, texte, dx, dy, echelle, aide in (
                ("gauche", "←", -2, 0, 1.0, "Décaler le dessin vers la gauche"),
                ("droite", "→", 2, 0, 1.0, "Décaler le dessin vers la droite"),
                ("haut", "↑", 0, -2, 1.0, "Décaler le dessin vers le haut"),
                ("bas", "↓", 0, 2, 1.0, "Décaler le dessin vers le bas"),
                ("moins", "−", 0, 0, 0.99, "Cases plus petites"),
                ("plus", "+", 0, 0, 1.01, "Cases plus grandes")):
            b = QPushButton(texte)
            b.setObjectName("fleche")
            b.setFixedSize(30, 28)
            b.setToolTip(aide)
            b.setAutoRepeat(True)
            b.clicked.connect(lambda _=False, a=(dx, dy, echelle): parent.ajuster.emit(self.cle, *a))
            fleches.append(b)
            self.boutons_reglage[nom] = b
        ligne3 = _rang(self.point_calibre, 2, self.calibre, None, _texte("Réglage fin", "stat-titre"), 6, *fleches, espace=4)
        v.addLayout(ligne3)
        self.maj(etat)

    def _forcer(self, i: int) -> None:
        if i > 0:
            self._parent.forcer_tranche.emit(self.cle, i)
        self.forcer.setCurrentIndex(0)

    def maj(self, e: EtatAffiche) -> None:
        if self.actif.text() != e.nom:
            self.actif.setText(e.nom)
        self.pv.setText(f"{e.pv} / {e.pv_max}" if e.en_combat and e.pv is not None and e.pv_max else "—")
        if not e.en_combat:
            texte = "connecté"
        elif e.tranche is None:
            texte = "en combat"
        else:
            texte = f"confusion {e.tranche} quart{'s' if e.tranche > 1 else ''}"
        self.etat.setText(texte)
        actif = bool(e.en_combat and e.tranche is not None)
        if self.etat.property("actif") != actif:
            self.etat.setProperty("actif", actif)
            _repolir(self.etat)
        self.melee.setText(str(e.melee) if e.en_combat else "—")
        self.calibre.setText(("Calibré automatiquement" if e.calibre_auto else "Calibré, avec ton réglage fin") if e.calibre
                            else "En attente de la fenêtre du jeu")
        if self.point_calibre.property("on") != e.calibre:
            self.point_calibre.setProperty("on", e.calibre)
            _repolir(self.point_calibre)
        choix = ["(automatique)"] + e.fenetres
        if [self.fenetre.itemText(i) for i in range(self.fenetre.count())] != choix:
            self.fenetre.clear()
            self.fenetre.addItems(choix)
        self.fenetre.setCurrentText(e.fenetre_choisie or "(automatique)")

    def detruire(self) -> None:
        self.deleteLater()


class Bascule(QPushButton):
    """Grande touche allumée / éteinte : icône, nom, voyant vert quand elle est allumée."""

    def __init__(self, icone: str, texte: str, aide: str, allume: bool) -> None:
        super().__init__(texte)
        self.setObjectName("bascule")
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setIcon(QIcon(str(ICONES / icone)))
        self.setIconSize(QSize(26, 26))
        self.setToolTip(aide)
        self.voyant = QLabel(self)
        self.voyant.setObjectName("voyant")
        self.voyant.setFixedSize(7, 7)
        self.toggled.connect(self._peindre)
        self.setChecked(allume)
        self._peindre(allume)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.voyant.move(self.width() - 16, 9)

    def _peindre(self, oui: bool) -> None:
        self.voyant.setProperty("on", oui)
        _repolir(self.voyant)


class FenetreReglages(QWidget):
    melee_zero = Signal(str)
    forcer_tranche = Signal(str, int)
    ajuster = Signal(str, int, int, float)    # compte, décalage x, décalage y, échelle
    apprendre = Signal()
    pause = Signal(bool)
    change = Signal()          # un réglage a changé (déjà sauvé)

    def __init__(self, reglages: Reglages) -> None:
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.reglages = reglages
        self.setWindowTitle("Réglages")
        self.setFixedSize(LARGEUR, HAUTEUR)
        self._prise: QPoint | None = None
        self._lignes: dict[str, FicheCompte] = {}

        dehors = QVBoxLayout(self)
        dehors.setContentsMargins(0, 0, 0, 0)
        cadre = QFrame()
        cadre.setObjectName("fenetre")
        dehors.addWidget(cadre)
        grille = QGridLayout(cadre)
        grille.setContentsMargins(26, 14, 26, 24)
        grille.setHorizontalSpacing(22)
        grille.setVerticalSpacing(10)

        # ---- barre du haut : titre de section à gauche, réduire et fermer à droite
        self.titre_comptes = _section("Comptes")
        reduire = QPushButton("–")
        reduire.setObjectName("reduire")
        reduire.setFixedSize(22, 22)
        reduire.setToolTip("Réduire")
        reduire.clicked.connect(self.showMinimized)
        fermer = QPushButton("✕")
        fermer.setObjectName("fermer")
        fermer.setFixedSize(20, 20)
        fermer.setToolTip("Fermer (l'outil reste près de l'horloge)")
        fermer.clicked.connect(self.hide)
        grille.addLayout(_rang(self.titre_comptes, None, reduire, 8, fermer, espace=0), 0, 0, 1, 2)

        # ---- à gauche : une fiche par compte, qui défile s'il y en a beaucoup
        defile = QScrollArea()
        defile.setWidgetResizable(True)
        defile.setFrameShape(QFrame.NoFrame)
        defile.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        contenu = QWidget()
        contenu.setObjectName("corps")
        self.liste = QVBoxLayout(contenu)
        self.liste.setContentsMargins(0, 0, 6, 0)
        self.liste.setSpacing(12)
        self.liste.setAlignment(Qt.AlignTop)
        self.aucun = _texte("Aucun compte connecté pour l'instant : lance le jeu.", "vide")
        self.aucun.setAlignment(Qt.AlignCenter)
        self.liste.addWidget(self.aucun)
        defile.setWidget(contenu)
        grille.addWidget(defile, 1, 0)

        # ---- à droite : bascules, affichage, lecture du jeu
        droite = QVBoxLayout()
        droite.setContentsMargins(0, 0, 0, 0)
        droite.setSpacing(12)
        self.bascule_dessin = Bascule("bascule-dessin.png", "  Dessin", "Dessin sur le jeu (éteint = pause)", True)
        self.bascule_dessin.toggled.connect(lambda oui: self.pause.emit(not oui))
        self.bascule_allies = Bascule("bascule-allies.svg", "  Alliés", "Cases pour viser les alliés",
                                      reglages.montrer_allies)
        self.bascule_allies.toggled.connect(lambda oui: self._poser("montrer_allies", oui))
        droite.addLayout(_rang(self.bascule_dessin, self.bascule_allies, espace=10))
        droite.addWidget(self._carte_affichage())
        droite.addWidget(self._carte_jeu())
        droite.addStretch(1)
        colonne = QWidget()
        colonne.setFixedWidth(340)
        colonne.setLayout(droite)
        grille.addWidget(colonne, 1, 1)
        grille.setColumnStretch(0, 1)
        grille.setRowStretch(1, 1)

    # -------------------------------------------------------------- cartes de droite

    @staticmethod
    def _carte(titre: str) -> tuple[QFrame, QGridLayout]:
        carte = QFrame()
        carte.setObjectName("carte")
        g = QGridLayout(carte)
        g.setContentsMargins(18, 14, 18, 16)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(9)
        g.addWidget(_section(titre), 0, 0, 1, 3)
        return carte, g

    def _carte_affichage(self) -> QFrame:
        carte, g = self._carte("Affichage")
        r = self.reglages
        rang = 1
        for nom, texte, mini, maxi, val in (("opacite", "Opacité", 20, 100, r.opacite),
                                            ("taille_icones", "Icônes", 50, 200, r.taille_icones)):
            valeur = _texte(f"{int(val * 100)} %", "doux")
            valeur.setFixedWidth(44)
            valeur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            s = self._curseur(mini, maxi, int(val * 100), valeur, nom)
            g.addWidget(_texte(texte, "fort"), rang, 0)
            g.addWidget(s, rang, 1)
            g.addWidget(valeur, rang, 2)
            setattr(self, "opacite" if nom == "opacite" else "taille", s)
            rang += 1
        for nom, texte, aide in (("montrer_losange_mob", "Losange sous les cibles", None),
                                 ("montrer_ldv", "Cibles hors de vue", "Œil barré sur les cibles hors de vue"),
                                 ("montrer_avertissements", "Avertissements", "Case morte, hors carte")):
            c = QCheckBox()
            c.setChecked(getattr(r, nom))
            c.toggled.connect(lambda val, n=nom: self._poser(n, val))
            l = _texte(texte, "fort")
            if aide:
                l.setToolTip(aide)
                c.setToolTip(aide)
            g.addWidget(l, rang, 0, 1, 2)
            g.addWidget(c, rang, 2, Qt.AlignRight)
            rang += 1
        couleurs = QWidget()
        ch = QHBoxLayout(couleurs)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(6)
        ch.addStretch(1)
        self._boutons_couleur = []
        for i in range(len(r.palette)):
            b = QPushButton()
            b.setObjectName("pastille")
            b.setFixedSize(22, 22)
            b.setToolTip("Changer la couleur")
            b.clicked.connect(lambda _=False, k=i: self._couleur(k))
            ch.addWidget(b)
            self._boutons_couleur.append(b)
        self._peindre_couleurs()
        g.addWidget(_texte("Couleurs", "fort"), rang, 0)
        g.addWidget(couleurs, rang, 1, 1, 2)
        rang += 1
        self.raccourci = QKeySequenceEdit(r.raccourci)
        self.raccourci.setFixedWidth(150)
        self.raccourci.setToolTip("Raccourci pour ouvrir ces réglages")
        self.raccourci.editingFinished.connect(
            lambda: self._poser("raccourci", self.raccourci.keySequence().toString() or "Ctrl+Alt+H"))
        g.addWidget(_texte("Raccourci", "fort"), rang, 0)
        g.addWidget(self.raccourci, rang, 1, 1, 2, Qt.AlignRight)
        g.setColumnStretch(1, 1)
        return carte

    def _carte_jeu(self) -> QFrame:
        carte, g = self._carte("Lecture du jeu")
        self.protocole = _texte("—", "fort")
        self.protocole.setWordWrap(True)
        g.addWidget(self.protocole, 1, 0, 1, 3)
        b = QPushButton("Mode apprendre")
        b.setObjectName("principal")
        b.setToolTip("Après une mise à jour du jeu, si plus rien ne s'affiche")
        b.clicked.connect(self.apprendre.emit)
        g.addWidget(b, 2, 0, 1, 3)
        aide = _texte("Après une mise à jour du jeu, si plus rien ne s'affiche.", "petit")
        aide.setWordWrap(True)
        g.addWidget(aide, 3, 0, 1, 3)
        return carte

    # -------------------------------------------------------------- déplacer la fenêtre sans cadre

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and e.position().y() < 50:
            self._prise = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._prise is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._prise)

    def mouseReleaseEvent(self, e) -> None:
        self._prise = None

    # -------------------------------------------------------------- outils

    def _curseur(self, mini, maxi, valeur, etiquette: QLabel, nom: str) -> QSlider:
        s = QSlider(Qt.Horizontal)
        s.setRange(mini, maxi)
        s.setValue(valeur)

        def rappel(v: int) -> None:
            etiquette.setText(f"{v} %")
            self._poser(nom, v / 100)
        s.valueChanged.connect(rappel)
        return s

    def _poser(self, nom: str, valeur) -> None:
        setattr(self.reglages, nom, valeur)
        self._sauver()

    def _sauver(self) -> None:
        try:
            self.reglages.sauver()
        except OSError:
            pass
        self.change.emit()

    def _peindre_couleurs(self) -> None:
        for b, c in zip(self._boutons_couleur, self.reglages.palette):
            b.setStyleSheet(f"background:{c}; border:2px solid #101315; border-radius:11px;")

    def _couleur(self, i: int) -> None:
        c = QColorDialog.getColor(QColor(self.reglages.palette[i]), self, "Couleur du monstre")
        if c.isValid():
            self.reglages.palette[i] = c.name().upper()
            self._peindre_couleurs()
            self._sauver()

    def _actif(self, nom: str, v: bool) -> None:
        self.reglages.actif_par_compte[nom] = v
        self._sauver()

    def _associer(self, nom: str, titre: str) -> None:
        if titre == "(automatique)":
            self.reglages.association.pop(nom, None)
        else:
            self.reglages.association[nom] = titre
        self._sauver()

    # -------------------------------------------------------------- mises à jour

    def regler_pause(self, en_pause: bool) -> None:
        self.bascule_dessin.blockSignals(True)
        self.bascule_dessin.setChecked(not en_pause)
        self.bascule_dessin._peindre(not en_pause)
        self.bascule_dessin.blockSignals(False)

    def maj_comptes(self, etats: list[EtatAffiche]) -> None:
        vus = set()
        for e in etats:
            vus.add(e.cle)
            if e.cle in self._lignes:
                self._lignes[e.cle].maj(e)
            else:
                fiche = FicheCompte(self, e)
                self._lignes[e.cle] = fiche
                self.liste.addWidget(fiche)
        for cle in list(self._lignes):
            if cle not in vus:
                self._lignes.pop(cle).detruire()
        self.aucun.setVisible(not self._lignes)
        n = len(self._lignes)
        self.titre_comptes.setText(f"COMPTES · {n}" if n else "COMPTES")

    def maj_protocole(self, version: str, origine: str, ok: bool) -> None:
        nom = "fort" if ok else "protocole-ko"
        texte = f"Messages du jeu : version {version} ({origine})" + ("" if ok else " — à mettre à jour")
        if self.protocole.text() != texte:
            self.protocole.setText(texte)
            self.protocole.setObjectName(nom)
            _repolir(self.protocole)
