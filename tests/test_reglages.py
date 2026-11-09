import json

from haretool.reglages import Reglages
from haretool.marques import PALETTE_DEFAUT


def test_defauts_si_absent(tmp_path):
    r = Reglages.charger(tmp_path / "reglages.json")
    assert r.opacite == 0.85 and r.raccourci == "Ctrl+Alt+H" and r.palette == PALETTE_DEFAUT
    assert len(r.palette) == 8


def test_aller_retour(tmp_path):
    f = tmp_path / "reglages.json"
    r = Reglages(opacite=0.5, actif_par_compte={"Perso": False}, reglage_fin={"1920x1080": {"x0": 1}})
    r.sauver(f)
    r2 = Reglages.charger(f)
    assert r2.opacite == 0.5 and r2.actif_par_compte == {"Perso": False}
    assert r2.reglage_fin == {"1920x1080": {"x0": 1}}


def test_fichier_corrompu(tmp_path):
    f = tmp_path / "reglages.json"
    f.write_text("{pas du json", "utf-8")
    r = Reglages.charger(f)
    assert r.opacite == 0.85
    assert (tmp_path / "reglages.json.bak").read_text("utf-8") == "{pas du json"


def test_cle_inconnue_ignoree(tmp_path):
    f = tmp_path / "reglages.json"
    f.write_text(json.dumps({"opacite": 0.4, "truc": 1}), "utf-8")
    r = Reglages.charger(f)
    assert r.opacite == 0.4 and not hasattr(r, "truc")


def test_mauvais_type_remplace_par_defaut(tmp_path):
    f = tmp_path / "reglages.json"
    f.write_text(json.dumps({"opacite": "beaucoup", "palette": []}), "utf-8")
    r = Reglages.charger(f)
    assert r.opacite == 0.85 and r.palette == PALETTE_DEFAUT


def test_options_dessin():
    o = Reglages(montrer_ldv=False).options_dessin()
    assert o.montrer_ldv is False and o.palette == PALETTE_DEFAUT


def test_boutons_de_reglage_fin(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from haretool.fenetre_reglages import FenetreReglages, EtatAffiche
    app = QApplication.instance() or QApplication([])  # noqa: F841
    w = FenetreReglages(Reglages())
    w.maj_comptes([EtatAffiche("k", "Perso1", True, 1, 0, ["Perso1 - Dofus"], None, True)])
    recus = []
    w.ajuster.connect(lambda cle, dx, dy, e: recus.append((cle, dx, dy, e)))
    boutons = w._lignes["k"].boutons_reglage
    for nom in ("haut", "bas", "gauche", "droite", "plus", "moins"):
        boutons[nom].click()
    assert recus == [("k", 0, -2, 1.0), ("k", 0, 2, 1.0), ("k", -2, 0, 1.0), ("k", 2, 0, 1.0),
                     ("k", 0, 0, 1.01), ("k", 0, 0, 0.99)]


def test_ligne_compte_montre_pv_et_suit_le_nom(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from haretool.fenetre_reglages import FenetreReglages, EtatAffiche
    app = QApplication.instance() or QApplication([])  # noqa: F841
    w = FenetreReglages(Reglages())
    w.maj_comptes([EtatAffiche("k", "compte 56148", True, None, 0, [], None, True)])
    w.maj_comptes([EtatAffiche("k", "Perso2", True, 2, 0, [], None, True, pv=2185, pv_max=3297)])
    ligne = w._lignes["k"]
    assert ligne.actif.text() == "Perso2"
    assert ligne.pv.text() == "2185 / 3297" and ligne.etat.text() == "confusion 2 quarts"
    assert ligne.calibre.text() == "Calibré, avec ton réglage fin"


def test_option_allies():
    assert Reglages().montrer_allies is True
    assert Reglages(montrer_allies=False).options_dessin().montrer_allies is False


def test_fenetre_taille_fixe_sans_logo_ni_nom(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication, QLabel
    from haretool.fenetre_reglages import FenetreReglages, EtatAffiche
    app = QApplication.instance() or QApplication([])  # noqa: F841
    w = FenetreReglages(Reglages())
    taille = w.size()
    w.maj_comptes([EtatAffiche(str(i), f"Perso{i}", False, None, 0, [], None, True) for i in range(8)])
    assert w.minimumSize() == w.maximumSize() and w.size() == taille
    textes = [l.text() for l in w.findChildren(QLabel)]
    assert not any("Haretool" in t for t in textes) and "Haretool" not in w.windowTitle()
    assert all(l.pixmap().isNull() for l in w.findChildren(QLabel))
