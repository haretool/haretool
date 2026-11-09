import json
import time
from pathlib import Path

from haretool.protocole import Protocole, EMBARQUE, CLES

URL_MORTE = "http://127.0.0.1:9/protocole.json"   # port « discard » : refus immédiat


def test_embarque_valide():
    p = Protocole.depuis_fichier(EMBARQUE)
    assert set(p.messages) == set(CLES)
    assert p.reconnu("jnz") == "deplacement" and p.reconnu("zzz") is None
    assert p.champ("deplacement", "chemin") == [1]
    assert p.champ("notre_tour", "x") is None


def test_url_injoignable_rend_embarque(tmp_path):
    t = time.monotonic()
    p, origine = Protocole.charger(EMBARQUE, URL_MORTE, delai_s=3, dossier_cache=tmp_path)
    assert origine == "embarqué" and time.monotonic() - t < 3.5
    assert p.version == json.loads(EMBARQUE.read_text("utf-8"))["version"]


def test_url_absente_rend_embarque(tmp_path):
    assert Protocole.charger(EMBARQUE, None, dossier_cache=tmp_path)[1] == "embarqué"


def test_json_en_ligne_invalide_rend_embarque(tmp_path, monkeypatch):
    import haretool.protocole as mod
    monkeypatch.setattr(mod, "_telecharger", lambda url, delai: b"{pas du json")
    assert Protocole.charger(EMBARQUE, "https://x", dossier_cache=tmp_path)[1] == "embarqué"


def test_en_ligne_valide_est_mis_en_cache(tmp_path, monkeypatch):
    import haretool.protocole as mod
    donnees = json.loads(EMBARQUE.read_text("utf-8"))
    donnees["version"] = "2099-01-01"
    donnees["messages"]["deplacement"]["nom"] = "abc"
    monkeypatch.setattr(mod, "_telecharger", lambda url, delai: json.dumps(donnees).encode())
    p, origine = Protocole.charger(EMBARQUE, "https://x", dossier_cache=tmp_path)
    assert origine == "en ligne" and p.reconnu("abc") == "deplacement"
    # plus tard, hors ligne : le cache plus récent que l'embarqué est repris
    monkeypatch.undo()
    p2, origine2 = Protocole.charger(EMBARQUE, URL_MORTE, dossier_cache=tmp_path)
    assert origine2 == "cache" and p2.version == "2099-01-01"


def test_cache_plus_vieux_ignore(tmp_path):
    donnees = json.loads(EMBARQUE.read_text("utf-8"))
    donnees["version"] = "2000-01-01"
    (tmp_path / "protocole.json").write_text(json.dumps(donnees), "utf-8")
    assert Protocole.charger(EMBARQUE, None, dossier_cache=tmp_path)[1] == "embarqué"


def test_cle_manquante_invalide(tmp_path, monkeypatch):
    import haretool.protocole as mod
    donnees = json.loads(EMBARQUE.read_text("utf-8"))
    del donnees["messages"]["action"]
    monkeypatch.setattr(mod, "_telecharger", lambda url, delai: json.dumps(donnees).encode())
    assert Protocole.charger(EMBARQUE, "https://x", dossier_cache=tmp_path)[1] == "embarqué"


def test_ancien_fichier_sans_caracteristique_reste_valable():
    import json
    d = json.loads(EMBARQUE.read_text("utf-8"))
    del d["messages"]["caracteristique"]
    p = Protocole(d)
    assert p.messages["caracteristique"] is None and p.reconnu("jtk") is None
