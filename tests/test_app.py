from haretool.comptes import Comptes
from haretool.ecoute import Paquet
from haretool.protocole import Protocole, EMBARQUE
from haretool.grille import vers_case

from pb import msg, varint

SERVEUR = "3.4.5.6"


def trame(nom: str, valeur: bytes) -> bytes:
    env = msg({3: {1: {1: b"type.ankama.com/" + nom.encode(), 2: valeur}}})
    return varint(len(env)) + env


def combat(moi: int, pv: int):
    """Messages d'un petit combat vu par un compte."""
    a, m = vers_case(16, 4), vers_case(17, 4)
    return [("kqo", msg({3: pv, 1: 4000})),
            ("kjl", msg({2: [{2: moi, 3: a}, {2: -1, 3: m}]})),
            ("jvj", msg({3: moi})),
            ("zzt", b""),
            ("jsq", msg({36: -1, 37: {6: 300, 5: moi}})),
            ("jsq", msg({36: moi, 37: {6: 50, 5: -1}}))]


def paquets(port: int, messages, seq0: int = 1000):
    seq, sortie = seq0, []
    for nom, valeur in messages:
        charge = trame(nom, valeur)
        sortie.append(Paquet(SERVEUR, 5555, "10.0.0.2", port, seq, charge))
        seq += len(charge)
    return sortie


def resume(e):
    return (e.pv, e.pv_max, e.en_combat, dict(e.positions), e.pv_debut_tour)


def nouveaux():
    import json
    d = json.loads(EMBARQUE.read_text("utf-8"))
    d["messages"]["notre_tour"] = {"nom": "zzt", "champs": {}}
    return Comptes(Protocole(d), est_harebourg=lambda m: False)


def test_deux_connexions_etats_independants():
    pa, pb = paquets(50001, combat(11, 3000)), paquets(50002, combat(22, 1000))
    seul_a, seul_b, ensemble = nouveaux(), nouveaux(), nouveaux()
    for p in pa:
        seul_a.sur_paquet(p, 0)
    for p in pb:
        seul_b.sur_paquet(p, 0)
    for x, y in zip(pa, pb):
        ensemble.sur_paquet(y, 0)
        ensemble.sur_paquet(x, 0)
    par_cle = {c.cle: c.etat for c in ensemble.comptes()}
    assert len(par_cle) == 2
    assert resume(par_cle[("10.0.0.2", 50001)]) == resume(seul_a.comptes()[0].etat)
    assert resume(par_cle[("10.0.0.2", 50002)]) == resume(seul_b.comptes()[0].etat)
    assert par_cle[("10.0.0.2", 50001)].pv == 2700


def test_connexion_rouverte_et_ancienne_oubliee():
    c = nouveaux()
    for p in paquets(50001, combat(11, 3000)):
        c.sur_paquet(p, 0)
    for p in paquets(50009, combat(11, 3000)):
        c.sur_paquet(p, 30)
    c.oublier_inactifs(61)
    assert [x.cle[1] for x in c.comptes()] == [50009]
    c.oublier_inactifs(100)
    assert c.comptes() == []


def test_sens_client_vers_serveur_meme_compte():
    c = nouveaux()
    for p in paquets(50001, combat(11, 3000)):
        c.sur_paquet(p, 0)
    envoi = trame("jok", b"")
    c.sur_paquet(Paquet("10.0.0.2", 50001, SERVEUR, 5555, 77, envoi), 1)
    assert len(c.comptes()) == 1


def test_raccourci_windows():
    from haretool.app import touche_windows
    assert touche_windows("Ctrl+Alt+H") == (0x3, ord("H"))
    assert touche_windows("Shift+F5") == (0x4, 0x74)
    assert touche_windows("Bidule+X") is None and touche_windows("") is None


def test_enregistreur_voit_les_messages():
    c = nouveaux()
    vus = []
    c.enregistreur = lambda cle, sens, nom, valeur, t: vus.append((sens, nom))
    for p in paquets(50001, combat(11, 3000)):
        c.sur_paquet(p, 0)
    assert ("recu", "kqo") in vus and len(vus) == 6


def test_mode_essai_tout_monstre_compte(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from haretool.app import Application
    app = QApplication.instance() or QApplication([])
    a = Application(app, essai=True)
    assert a.comptes._est_harebourg(31)
    b = Application(app)
    assert not b.comptes._est_harebourg(31)
    a.icone.hide()
    b.icone.hide()


def test_une_seule_copie_a_la_fois():
    import uuid
    from haretool.app import verrou_unique
    nom = "HaretoolTest-" + uuid.uuid4().hex
    premier = verrou_unique(nom)
    assert premier is not None
    assert verrou_unique(nom) is None


def test_reglage_fin_deplace_le_calibrage(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from haretool.app import Application
    from haretool.calibrage import Calibrage
    from haretool.fenetres import FenetreJeu
    app = QApplication.instance() or QApplication([])
    a = Application(app)
    for p in paquets(50001, combat(11, 3000)):
        a.comptes.sur_paquet(p, 0)
    c = a.comptes.comptes()[0]
    c.fenetre = FenetreJeu(1, "x", (0, 0, 1920, 1080), False, True)
    a.calibrages.poser(1920, 1080, Calibrage(100.0, 50.0, 86.0, 43.0))
    a._ajuster(f"{c.cle[0]}:{c.cle[1]}", 2, -2, 1.0)
    nouveau = a.calibrages.pour(1920, 1080)
    assert nouveau.pixel(280)[0] == 102.0 and nouveau.pixel(280)[1] == Calibrage(100.0, 50.0, 86.0, 43.0).pixel(280)[1] - 2
    assert "1920x1080" in a.reglages.reglage_fin
    a.icone.hide()


def test_enregistrement_brut_des_paquets(monkeypatch, tmp_path):
    import json
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from haretool.app import Application
    app = QApplication.instance() or QApplication([])
    a = Application(app, capture=True)
    for p in paquets(50001, combat(11, 3000)):
        a.file.put((p, 1.5))
    a._traiter_paquets()
    chemin = a.ecrire_capture()
    d = json.loads(chemin.read_text())
    assert len(d["paquets"]) == len(combat(11, 3000)) and d["paquets"][0]["flux"] == "10.0.0.2:50001"
    assert d["paquets"][0]["sens"] == "serveur->client" and d["paquets"][0]["hex"]
    a.icone.hide()
