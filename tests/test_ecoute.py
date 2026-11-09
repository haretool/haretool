import struct
import sys

import pytest

from haretool import ecoute
from haretool.ecoute import extraire_paquet, Paquet, cle_connexion, Dedoublonneur


def trame(sport=5555, dport=50123, proto=6, ethertype=0x0800, charge=b"\x05abcde", seq=1234):
    tcp = struct.pack("!HHIIBBHHH", sport, dport, seq, 0, 5 << 4, 0x18, 1024, 0, 0)
    total = 20 + len(tcp) + len(charge)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0, 0, 64, proto, 0,
                     bytes([3, 4, 5, 6]), bytes([10, 0, 0, 2]))
    eth = b"\x11" * 6 + b"\x22" * 6 + struct.pack("!H", ethertype)
    return b"\x00" * 24 + eth + ip + tcp + charge


def test_extraire_paquet_serveur_vers_client():
    p = extraire_paquet(trame())
    assert p == Paquet("3.4.5.6", 5555, "10.0.0.2", 50123, 1234, b"\x05abcde")


def test_cle_connexion_cote_local():
    p = extraire_paquet(trame())
    assert cle_connexion(p) == ("10.0.0.2", 50123)
    q = Paquet("10.0.0.2", 50123, "3.4.5.6", 5555, 9, b"x")
    assert cle_connexion(q) == ("10.0.0.2", 50123)


def test_pas_tcp_ou_autre_port():
    assert extraire_paquet(trame(proto=17)) is None
    assert extraire_paquet(trame(sport=443, dport=50123)) is None
    assert extraire_paquet(trame(ethertype=0x86DD)) is None
    assert extraire_paquet(b"\x00" * 30) is None


def test_ip_tronquee_coupe_le_bourrage():
    # trame Ethernet minimale : bourrage après la fin IP, ne doit pas entrer dans la charge
    t = trame(charge=b"") + b"\x00" * 6
    p = extraire_paquet(t)
    assert p is not None and p.charge == b""


def test_dedoublonnage():
    d = Dedoublonneur()
    p = extraire_paquet(trame())
    assert d.nouveau(p) and not d.nouveau(p)
    assert d.nouveau(p._replace(seq=1235))


@pytest.mark.skipif(sys.platform != "win32", reason="capture Windows (pktmon)")
def test_nettoyage_session_orpheline():
    appels = []
    ecoute.nettoyer(executer=lambda args: appels.append(("pktmon", *args)),
                    arreter_session=lambda nom: appels.append(("etw-stop", nom)))
    assert appels == [("etw-stop", "HaretoolEcoute"), ("pktmon", "stop"), ("pktmon", "filter", "remove")]


@pytest.mark.skipif(sys.platform != "win32", reason="capture Windows (pktmon)")
def test_arreter_idempotent(monkeypatch):
    appels = []
    monkeypatch.setattr(ecoute, "nettoyer", lambda **k: appels.append(1))
    e = ecoute.Ecoute(lambda p: None)
    e.arreter()
    e.arreter()
    assert appels == []          # jamais démarrée : rien à arrêter
    e._actif = True
    e.arreter()
    e.arreter()
    assert appels == [1]


@pytest.mark.skipif(sys.platform != "win32", reason="capture Windows (pktmon)")
def test_livraison_rapide_en_millisecondes():
    pr = ecoute._proprietes(rapide=True)
    assert pr.p.LogFileMode & 0x10 and pr.p.FlushTimer == ecoute.LIVRAISON_MS
    lent = ecoute._proprietes(rapide=False)
    assert not lent.p.LogFileMode & 0x10 and lent.p.FlushTimer == 1


@pytest.mark.skipif(sys.platform != "win32", reason="capture Windows (pktmon)")
def test_journal_pktmon_hors_du_dossier_courant(monkeypatch):
    appels = []
    monkeypatch.setattr(ecoute, "_pktmon", lambda args: appels.append(args) or 1)
    monkeypatch.setattr(ecoute, "nettoyer", lambda **k: None)
    e = ecoute.Ecoute(lambda p: None)
    import pytest
    with pytest.raises(OSError):
        e.demarrer()
    monkeypatch.setattr(ecoute, "_pktmon", lambda args: appels.append(args) or (1 if args[0] == "start" else 0))
    with pytest.raises(OSError):
        e.demarrer()
    depart = next(a for a in appels if a[0] == "start")
    assert "--file-name" in depart
    import tempfile
    assert depart[depart.index("--file-name") + 1].startswith(tempfile.gettempdir())


def test_trame_linux_cuite_reconnue():
    """Sous Linux, la pseudo-carte peut livrer un en-tête « SLL » de 16 octets au lieu
    d'Ethernet (14) : le type 0x0800 est alors 2 octets plus loin, le découpage le trouve quand même."""
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + 20 + 3, 0, 0, 64, 6, 0, bytes([1, 2, 3, 4]), bytes([10, 0, 0, 2]))
    tcp = struct.pack("!HHIIBBHHH", 5555, 50000, 77, 0, 5 << 4, 0x18, 1000, 0, 0)
    sll = bytes([0, 0, 0, 1, 0, 6]) + bytes([0xAA]) * 8 + bytes([0x08, 0x00])
    p = extraire_paquet(sll + ip + tcp + b"abc")
    assert p is not None and p.sport == 5555 and p.seq == 77 and p.charge == b"abc"


def test_ecoute_pcap_sans_bibliotheque(monkeypatch):
    from haretool import ecoute_pcap
    monkeypatch.setattr(ecoute_pcap, "_pcap", lambda: None)
    e = ecoute_pcap.Ecoute(lambda p: None)
    with pytest.raises(OSError, match="libpcap"):
        e.demarrer()
    e.arreter()          # sans effet, ne plante pas
