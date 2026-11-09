from PySide6.QtWidgets import QApplication

from haretool import theme


def test_polices_embarquees():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    familles = theme.charger_polices()
    assert theme.TITRE in familles and theme.TEXTE in familles


def test_police_et_sa_note_de_licence_livrees():
    assert (theme.POLICES / "LISEZMOI.txt").is_file() and (theme.POLICES / "Outfit.ttf").is_file()


def test_icone_coiffe():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    assert not theme.icone().isNull()


def test_un_seul_accent():
    assert theme.ACCENT in theme.FEUILLE and theme.FEUILLE.count("#") > 10
