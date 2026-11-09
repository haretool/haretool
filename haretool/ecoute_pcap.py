"""Écoute du trafic du jeu (TCP 5555) sur macOS et Linux, avec libpcap.

libpcap est la bibliothèque de capture standard (livrée avec macOS, présente sur
la plupart des Linux). On ouvre chaque carte réseau active avec le filtre « tcp port
5555 » ; les trames reçues passent par le même découpage que sous Windows
(extraire_paquet). Rien n'est lu dans le jeu. Droits de capture requis :
macOS = lancer en administrateur (sudo), Linux = capacité cap_net_raw (voir LISEZ-MOI).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading
from typing import Callable

from .ecoute import PORT, Dedoublonneur, Paquet, extraire_paquet

PCAP_IF_LOOPBACK = 0x1
PCAP_ERRBUF_SIZE = 256


class _Pkthdr(ctypes.Structure):
    # struct timeval (16 octets sur macOS et Linux 64 bits) puis caplen, len
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long),
                ("caplen", ctypes.c_uint32), ("len", ctypes.c_uint32)]


class _BpfProgram(ctypes.Structure):
    _fields_ = [("bf_len", ctypes.c_uint), ("bf_insns", ctypes.c_void_p)]


class _PcapIf(ctypes.Structure):
    pass


_PcapIf._fields_ = [("next", ctypes.POINTER(_PcapIf)), ("name", ctypes.c_char_p),
                    ("description", ctypes.c_char_p), ("addresses", ctypes.c_void_p), ("flags", ctypes.c_uint32)]

_lib = None


def _pcap():
    """La bibliothèque libpcap, chargée une fois (None si absente)."""
    global _lib
    if _lib is None:
        for nom in (ctypes.util.find_library("pcap"), "libpcap.so.1", "libpcap.so.0.8", "libpcap.so",
                    "/usr/lib/libpcap.dylib", "libpcap.A.dylib"):
            if not nom:
                continue
            try:
                lib = ctypes.CDLL(nom)
                break
            except OSError:
                continue
        else:
            return None
        lib.pcap_open_live.restype = ctypes.c_void_p
        lib.pcap_open_live.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        lib.pcap_compile.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BpfProgram), ctypes.c_char_p, ctypes.c_int,
                                     ctypes.c_uint32]
        lib.pcap_setfilter.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BpfProgram)]
        lib.pcap_freecode.argtypes = [ctypes.POINTER(_BpfProgram)]
        lib.pcap_next_ex.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(_Pkthdr)),
                                     ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
        lib.pcap_close.argtypes = [ctypes.c_void_p]
        lib.pcap_findalldevs.argtypes = [ctypes.POINTER(ctypes.POINTER(_PcapIf)), ctypes.c_char_p]
        lib.pcap_freealldevs.argtypes = [ctypes.POINTER(_PcapIf)]
        for f, args in (("pcap_create", [ctypes.c_char_p, ctypes.c_char_p]),
                        ("pcap_set_snaplen", [ctypes.c_void_p, ctypes.c_int]),
                        ("pcap_set_timeout", [ctypes.c_void_p, ctypes.c_int]),
                        ("pcap_set_immediate_mode", [ctypes.c_void_p, ctypes.c_int]),
                        ("pcap_activate", [ctypes.c_void_p])):
            if hasattr(lib, f):
                getattr(lib, f).argtypes = args
        if hasattr(lib, "pcap_create"):
            lib.pcap_create.restype = ctypes.c_void_p
        lib.pcap_geterr.restype = ctypes.c_char_p
        lib.pcap_geterr.argtypes = [ctypes.c_void_p]
        _lib = lib
    return _lib


def cartes(lib) -> list[str]:
    """Les cartes réseau à écouter : toutes sauf la boucle locale et la pseudo-carte « any »."""
    erreur = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
    liste = ctypes.POINTER(_PcapIf)()
    if lib.pcap_findalldevs(ctypes.byref(liste), erreur) != 0:
        raise OSError("liste des cartes réseau impossible : " + erreur.value.decode(errors="replace"))
    noms = []
    try:
        c = liste
        while c:
            nom = c.contents.name.decode(errors="replace")
            if not c.contents.flags & PCAP_IF_LOOPBACK and nom not in ("any", "lo") and not nom.startswith(
                    ("bluetooth", "dbus", "nflog", "nfqueue", "usbmon", "ap1", "awdl", "llw", "utun", "gif", "stf")):
                noms.append(nom)
            c = c.contents.next
    finally:
        lib.pcap_freealldevs(liste)
    return noms


def ouvrir(lib, nom: str, erreur) -> int | None:
    """Ouvre une carte en mode immédiat (chaque paquet livré tout de suite), sinon en mode classique."""
    if hasattr(lib, "pcap_create") and hasattr(lib, "pcap_set_immediate_mode"):
        p = lib.pcap_create(nom.encode(), erreur)
        if p:
            lib.pcap_set_snaplen(p, 65535)
            lib.pcap_set_timeout(p, 50)
            lib.pcap_set_immediate_mode(p, 1)
            if lib.pcap_activate(p) >= 0:
                return p
            erreur.value = (lib.pcap_geterr(p) or b"activation refusee")[:PCAP_ERRBUF_SIZE - 1]
            lib.pcap_close(p)
            return None
    return lib.pcap_open_live(nom.encode(), 65535, 0, 50, erreur) or None


def nettoyer(**_) -> None:
    """Rien à nettoyer hors Windows : la capture s'arrête avec le programme."""


class Ecoute:
    """Lit les paquets du jeu en direct et appelle `sur_paquet` (depuis des threads à part)."""

    def __init__(self, sur_paquet: Callable[[Paquet], None]) -> None:
        self._sur_paquet = sur_paquet
        self._actif = False
        self._verrou = threading.Lock()
        self._dedoublon = Dedoublonneur()
        self._poignees: list[int] = []
        self._fils: list[threading.Thread] = []
        self.erreur: str | None = None

    def demarrer(self) -> None:
        lib = _pcap()
        if lib is None:
            raise OSError("libpcap introuvable (Linux : installer le paquet libpcap)")
        erreur = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
        refus = []
        for nom in cartes(lib):
            p = ouvrir(lib, nom, erreur)
            if not p:
                refus.append(f"{nom} : {erreur.value.decode(errors='replace')}")
                continue
            programme = _BpfProgram()
            if lib.pcap_compile(p, ctypes.byref(programme), f"tcp port {PORT}".encode(), 1, 0) == 0:
                lib.pcap_setfilter(p, ctypes.byref(programme))
                lib.pcap_freecode(ctypes.byref(programme))
            self._poignees.append(p)
        if not self._poignees:
            detail = "; ".join(refus) or "aucune carte réseau"
            raise OSError("capture refusée (droits de capture requis, voir LISEZ-MOI) : " + detail)
        self._actif = True
        for p in self._poignees:
            fil = threading.Thread(target=self._lire, args=(lib, p), name="ecoute", daemon=True)
            fil.start()
            self._fils.append(fil)

    def _lire(self, lib, p: int) -> None:
        entete = ctypes.POINTER(_Pkthdr)()
        donnees = ctypes.POINTER(ctypes.c_ubyte)()
        while self._actif:
            r = lib.pcap_next_ex(p, ctypes.byref(entete), ctypes.byref(donnees))
            if r == 0:
                continue                    # délai écoulé sans paquet
            if r < 0:
                if self._actif:
                    self.erreur = (lib.pcap_geterr(p) or b"").decode(errors="replace")
                return
            try:
                trame = ctypes.string_at(donnees, entete.contents.caplen)
                paquet = extraire_paquet(trame)
                if paquet is None or not paquet.charge or not self._dedoublon.nouveau(paquet):
                    continue
                self._sur_paquet(paquet)
            except Exception as e:          # une trame bizarre ne doit pas arrêter l'écoute
                self.erreur = repr(e)

    def arreter(self) -> None:
        with self._verrou:
            if not self._actif:
                return
            self._actif = False
        for fil in self._fils:          # chaque lecteur s'arrête au plus 50 ms après
            fil.join(timeout=1)
        self._fils = []
        lib = _pcap()
        for p in self._poignees:
            try:
                lib.pcap_close(p)
            except OSError:
                pass
        self._poignees = []
