"""Habillage de Haretool : couleurs, police embarquée, feuille de style Qt.

Fenêtre sombre sans cadre, coins arrondis, liseré clair ; cartes plus sombres ;
un accent lime (interrupteurs, état en combat, bouton principal brillant) ;
police Outfit (polices/, licence OFL).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase, QIcon, QPixmap

POLICES = Path(__file__).parent / "polices"
ICONES = Path(__file__).parent / "icones"

FOND = "#1C2124"
FOND_HAUT = "#262B2F"
CARTE = "#181C1F"
TETE = "#2A3034"
LIGNE = "#4B5054"
LIGNE_HAUTE = "#585D61"
TEXTE_CLAIR = "#EEF0EC"
TITRE_GRIS = "#D3D7D2"
DOUX = "#9EA5A1"
PALE = "#6E7672"
ACCENT = "#E2F27C"
SUR_ACCENT = "#16181A"
ALERTE = "#E5484D"
TRAIT = "rgba(255,255,255,28)"
TRAIT_DOUX = "rgba(255,255,255,16)"

# compatibilité avec le reste du code
CARTE_CREUSE = FOND_HAUT
ENCRE = TEXTE_CLAIR
ENCRE_DOUCE = DOUX
TRAIT_FORT = LIGNE

POLICE = "Outfit"
TITRE = TEXTE = POLICE

_chargees = False


def charger_polices() -> list[str]:
    """Charge la police embarquée (une fois) et rend les familles disponibles."""
    global _chargees
    familles: set[str] = set()
    if not _chargees:
        for f in sorted(POLICES.glob("*.ttf")):
            ident = QFontDatabase.addApplicationFont(str(f))
            if ident >= 0:
                familles.update(QFontDatabase.applicationFontFamilies(ident))
        _chargees = True
    return sorted(familles) or [POLICE]


def icone() -> QIcon:
    """L'icône de l'outil : la coiffe du Comte Harebourg (toutes les tailles du .ico, nette
    dans la barre des tâches comme près de l'horloge)."""
    ico = ICONES / "haretool.ico"
    return QIcon(str(ico)) if ico.is_file() else QIcon(QPixmap(str(ICONES / "coiffe.png")))


def _url(nom: str) -> str:
    return (ICONES / nom).as_posix()


def feuille() -> str:
    return f"""
QWidget {{ color: {TEXTE_CLAIR}; font-family: "{POLICE}"; font-size: 13px; background: transparent; }}
QFrame#fenetre {{
    background: qlineargradient(x1:0, y1:0, x2:0.55, y2:1, stop:0 {FOND_HAUT}, stop:0.45 {FOND}, stop:1 #171B1E);
    border: 1px solid rgba(255,255,255,110); border-radius: 14px;
}}
QPushButton#bascule {{ background: rgba(16,19,21,165); border: 1px solid rgba(255,255,255,56); border-radius: 11px; padding: 0; }}
QPushButton#bascule:checked {{ border: 2px solid rgba(226,242,124,220);
    background: qradialgradient(cx:0.5, cy:0.4, radius:0.7, stop:0 rgba(226,242,124,90), stop:1 rgba(16,19,21,190)); }}
QLabel#voyant {{ background: #4A5156; border-radius: 3px; }}
QLabel#voyant[on="true"] {{ background: #40D48A; }}
QFrame#carte, QFrame#fiche {{ background: rgba(24,28,31,200); border: 1px solid rgba(255,255,255,28); border-radius: 18px; }}
QFrame#fiche:hover {{ border-color: rgba(255,255,255,48); }}
QFrame#trait {{ background: #2E3438; border: none; }}
QLabel#section {{ color: #9AA298; font-size: 11px; font-weight: 500; letter-spacing: 1.5px; }}
QLabel#stat-titre {{ color: {PALE}; font-size: 11.5px; }}
QLabel#stat {{ color: {TEXTE_CLAIR}; font-size: 16px; font-weight: 500; }}
QLabel#petit {{ color: {PALE}; font-size: 11.5px; }}
QPushButton#bascule {{ text-align: left; padding: 0 14px; font-size: 13.5px; font-weight: 500; color: {DOUX}; }}
QPushButton#bascule:checked {{ color: {TEXTE_CLAIR}; }}
QWidget#corps {{ background: transparent; }}
QFrame#entete {{ min-height: 40px; max-height: 40px; border-bottom: 1px solid #2E3438; }}
QLabel#entete-texte {{ color: #9AA298; font-size: 12px; font-weight: 500; }}
QFrame#ligne {{ min-height: 60px; border-bottom: 1px solid {FOND_HAUT}; }}
QFrame#ligne:hover {{ background: {FOND_HAUT}; }}
QLabel#fort {{ font-size: 13.5px; font-weight: 500; color: {TEXTE_CLAIR}; }}
QCheckBox#nom {{ font-size: 16px; font-weight: 500; color: {TEXTE_CLAIR}; }}
QLabel#doux {{ color: {DOUX}; font-size: 13px; }}
QLabel#vide {{ color: {DOUX}; font-size: 13.5px; padding: 44px 20px;
    border: 1px dashed rgba(255,255,255,40); border-radius: 18px; }}
QLabel#titre-barre {{ color: {DOUX}; font-size: 12px; font-weight: 500; }}
QPushButton#reduire {{ background: transparent; border: none; color: {DOUX}; font-size: 16px; padding: 0; }}
QPushButton#reduire:hover {{ color: {TEXTE_CLAIR}; }}
QPushButton#fermer {{ background: {ALERTE}; border: none; border-radius: 5px; color: white;
    font-size: 12px; font-weight: 900; padding: 0; }}
QPushButton#fermer:hover {{ background: #F2545B; }}
QGroupBox {{
    background: {CARTE}; border: 1px solid {TRAIT_DOUX}; border-radius: 18px;
    margin-top: 24px; padding: 16px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; top: 2px; padding: 0 4px;
    font-size: 13px; font-weight: 500; color: {TITRE_GRIS};
}}
QLabel#etat {{ color: {DOUX}; }}
QLabel#etat[actif="true"] {{ color: {SUR_ACCENT}; background: {ACCENT}; border-radius: 9px;
    padding: 3px 10px; font-weight: 500; }}
QLabel#protocole-ko {{ color: {ALERTE}; font-weight: 500; }}
QPushButton {{
    background: {TETE}; color: {TEXTE_CLAIR}; border: 1px solid {LIGNE};
    border-radius: 10px; padding: 5px 12px; font-weight: 500;
}}
QPushButton:hover {{ border-color: {LIGNE_HAUTE}; background: #30373B; }}
QPushButton:pressed {{ background: {FOND}; }}
QPushButton#fleche {{ font-family: "Segoe UI Symbol", "Segoe UI"; font-size: 14px; padding: 2px 0; }}
QPushButton#principal {{
    color: #3b4a12; font-weight: 900; border: 2px solid #1d2412; border-radius: 12px; padding: 6px 16px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E9F78E, stop:0.5 #C9E24A, stop:1 #A8C62C);
}}
QPushButton#principal:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F1FCA8, stop:0.5 #D9EE6A, stop:1 #B6D33A); }}
QComboBox, QKeySequenceEdit, QLineEdit, QSpinBox {{
    background: {TETE}; color: {TEXTE_CLAIR}; border: 1px solid {LIGNE}; border-radius: 10px; padding: 4px 8px;
}}
QComboBox {{ padding-right: 28px; }}
QComboBox:hover {{ border-color: {LIGNE_HAUTE}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 26px;
    border: none; background: transparent; }}
QComboBox::down-arrow {{ image: url("{_url('chevron.svg')}"); width: 12px; height: 12px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBox QAbstractItemView {{ background: {FOND}; color: {TEXTE_CLAIR}; border: 1px solid {LIGNE};
    selection-background-color: {ACCENT}; selection-color: {SUR_ACCENT}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 30px; height: 16px; image: url("{_url('interrupteur-non.svg')}"); }}
QCheckBox::indicator:checked {{ image: url("{_url('interrupteur-oui.svg')}"); }}
QSlider::groove:horizontal {{ height: 4px; background: {LIGNE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: {TEXTE_CLAIR}; }}
QScrollBar:vertical {{ width: 8px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {LIGNE}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMenu {{ background: {FOND}; color: {TEXTE_CLAIR}; border: 1px solid {TRAIT}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: {SUR_ACCENT}; }}
QToolTip {{ background: {FOND}; color: {TEXTE_CLAIR}; border: 1px solid {LIGNE}; }}
QMessageBox {{ background: {FOND}; }}
QMessageBox QLabel {{ color: {TEXTE_CLAIR}; }}
QColorDialog {{ background: {FOND}; }}
"""


FEUILLE = feuille()
