"""Écoute du trafic du jeu (TCP 5555) avec l'outil réseau intégré à Windows.

pktmon capture les paquets ; on s'abonne nous-mêmes, en temps réel, au journal
d'événements Windows (ETW) qu'il alimente : l'événement 160 porte le contenu du
paquet. Rien n'est lu dans le jeu. Droits administrateur requis.
"""

from __future__ import annotations

import atexit
import collections
import ctypes
import ctypes.wintypes as wt
import ipaddress
import struct
import os
import subprocess
import sys
import tempfile
import threading
from typing import Callable, NamedTuple

PORT = 5555
SESSION = "HaretoolEcoute"
EVENEMENT_CONTENU = 160
LIVRAISON_MS = 50         # Windows livre les événements par lots : toutes les 50 ms
SANS_FENETRE = 0x08000000


class Paquet(NamedTuple):
    src: str
    sport: int
    dst: str
    dport: int
    seq: int
    charge: bytes


def extraire_paquet(donnees: bytes) -> Paquet | None:
    """Trouve, dans le contenu d'un événement, une trame Ethernet + IPv4 + TCP du port du jeu."""
    for k in range(0, min(len(donnees) - 34, 200)):
        if donnees[k + 12:k + 14] != b"\x08\x00" or donnees[k + 14] & 0xF0 != 0x40 or donnees[k + 23] != 6:
            continue
        ip = k + 14
        ihl = (donnees[ip] & 15) * 4
        longueur_ip = struct.unpack_from("!H", donnees, ip + 2)[0]
        if ihl < 20 or len(donnees) < ip + ihl + 20:
            continue
        sport, dport, seq = struct.unpack_from("!HHI", donnees, ip + ihl)
        if PORT not in (sport, dport):
            return None
        doff = (donnees[ip + ihl + 12] >> 4) * 4
        fin = min(len(donnees), ip + longueur_ip) if longueur_ip else len(donnees)
        src = str(ipaddress.IPv4Address(donnees[ip + 12:ip + 16]))
        dst = str(ipaddress.IPv4Address(donnees[ip + 16:ip + 20]))
        return Paquet(src, sport, dst, dport, seq, bytes(donnees[ip + ihl + doff:fin]))
    return None


def cle_connexion(p: Paquet) -> tuple[str, int]:
    """(IP locale, port local) : une clé par connexion, donc par compte."""
    return (p.dst, p.dport) if p.sport == PORT else (p.src, p.sport)


class Dedoublonneur:
    """Un même paquet est vu par plusieurs composants réseau : on n'en garde qu'un."""

    def __init__(self, memoire: int = 4096) -> None:
        self._vus: set = set()
        self._ordre: collections.deque = collections.deque()
        self._memoire = memoire

    def nouveau(self, p: Paquet) -> bool:
        cle = (p.sport, p.dport, p.seq, len(p.charge))
        if cle in self._vus:
            return False
        self._vus.add(cle)
        self._ordre.append(cle)
        if len(self._ordre) > self._memoire:
            self._vus.discard(self._ordre.popleft())
        return True


# ---------------------------------------------------------------- Windows (ETW)

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


FOURNISSEUR = GUID(0x4D4F80D9, 0xC8BD, 0x4D73, (ctypes.c_ubyte * 8)(0xBB, 0x5B, 0x19, 0xC9, 0x04, 0x02, 0xC5, 0xAC))


class _EnTeteWnode(ctypes.Structure):
    _fields_ = [("BufferSize", wt.ULONG), ("ProviderId", wt.ULONG), ("HistoricalContext", ctypes.c_uint64),
                ("TimeStamp", ctypes.c_int64), ("Guid", GUID), ("ClientContext", wt.ULONG), ("Flags", wt.ULONG)]


class _ProprietesTrace(ctypes.Structure):
    _fields_ = [("Wnode", _EnTeteWnode), ("BufferSize", wt.ULONG), ("MinimumBuffers", wt.ULONG),
                ("MaximumBuffers", wt.ULONG), ("MaximumFileSize", wt.ULONG), ("LogFileMode", wt.ULONG),
                ("FlushTimer", wt.ULONG), ("EnableFlags", wt.ULONG), ("AgeLimit", wt.LONG),
                ("NumberOfBuffers", wt.ULONG), ("FreeBuffers", wt.ULONG), ("EventsLost", wt.ULONG),
                ("BuffersWritten", wt.ULONG), ("LogBuffersLost", wt.ULONG), ("RealTimeBuffersLost", wt.ULONG),
                ("LoggerThreadId", wt.HANDLE), ("LogFileNameOffset", wt.ULONG), ("LoggerNameOffset", wt.ULONG)]


class _Proprietes(ctypes.Structure):
    _fields_ = [("p", _ProprietesTrace), ("nom", ctypes.c_wchar * 256)]


_RAPPEL = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(None, ctypes.c_void_p)   # Windows : convention stdcall


class _FichierTrace(ctypes.Structure):
    _fields_ = [("LogFileName", ctypes.c_wchar_p), ("LoggerName", ctypes.c_wchar_p), ("CurrentTime", ctypes.c_int64),
                ("BuffersRead", wt.ULONG), ("ProcessTraceMode", wt.ULONG), ("CurrentEvent", ctypes.c_byte * 88),
                ("LogfileHeader", ctypes.c_byte * 280), ("BufferCallback", ctypes.c_void_p), ("BufferSize", wt.ULONG),
                ("Filled", wt.ULONG), ("EventsLost", wt.ULONG), ("_bourrage", wt.ULONG), ("EventRecordCallback", _RAPPEL),
                ("IsKernelTrace", wt.ULONG), ("_bourrage2", wt.ULONG), ("Context", ctypes.c_void_p)]


_advapi = None


def _api():
    global _advapi
    if _advapi is None:
        a = ctypes.WinDLL("advapi32")
        a.StartTraceW.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_wchar_p, ctypes.c_void_p]
        a.ControlTraceW.argtypes = [ctypes.c_uint64, ctypes.c_wchar_p, ctypes.c_void_p, wt.ULONG]
        a.EnableTraceEx2.argtypes = [ctypes.c_uint64, ctypes.POINTER(GUID), wt.ULONG, ctypes.c_ubyte,
                                     ctypes.c_uint64, ctypes.c_uint64, wt.ULONG, ctypes.c_void_p]
        a.OpenTraceW.argtypes = [ctypes.POINTER(_FichierTrace)]
        a.OpenTraceW.restype = ctypes.c_uint64
        a.ProcessTrace.argtypes = [ctypes.POINTER(ctypes.c_uint64), wt.ULONG, ctypes.c_void_p, ctypes.c_void_p]
        a.CloseTrace.argtypes = [ctypes.c_uint64]
        _advapi = a
    return _advapi


def _proprietes(rapide: bool = False) -> _Proprietes:
    pr = _Proprietes()
    pr.p.Wnode.BufferSize = ctypes.sizeof(_Proprietes)
    pr.p.Wnode.Flags = 0x20000          # WNODE_FLAG_TRACED_GUID
    pr.p.Wnode.ClientContext = 1        # horloge QPC
    pr.p.LogFileMode = 0x100            # temps réel
    pr.p.BufferSize = 64
    pr.p.FlushTimer = 1                 # en secondes…
    if rapide:
        pr.p.LogFileMode |= 0x10        # … ou en millisecondes (Windows 8 et plus)
        pr.p.FlushTimer = LIVRAISON_MS
    pr.p.LoggerNameOffset = ctypes.sizeof(_ProprietesTrace)
    return pr


def _pktmon(args) -> int:
    r = subprocess.run(["pktmon", *args], capture_output=True, creationflags=SANS_FENETRE)
    return r.returncode


def _arreter_session(nom: str) -> int:
    return _api().ControlTraceW(0, nom, ctypes.byref(_proprietes()), 1)   # EVENT_TRACE_CONTROL_STOP


def nettoyer(executer: Callable = _pktmon, arreter_session: Callable = _arreter_session) -> None:
    """Arrête une écoute restée ouverte (fermeture brutale, plantage)."""
    arreter_session(SESSION)
    executer(["stop"])
    executer(["filter", "remove"])


class Ecoute:
    """Lit les paquets du jeu en direct et appelle `sur_paquet` (depuis un thread à part)."""

    def __init__(self, sur_paquet: Callable[[Paquet], None]) -> None:
        self._sur_paquet = sur_paquet
        self._actif = False
        self._verrou = threading.Lock()
        self._dedoublon = Dedoublonneur()
        self._trace = None
        self._rappel = _RAPPEL(self._sur_evenement)   # gardé vivant tant que l'écoute tourne
        self.erreur: str | None = None

    def demarrer(self) -> None:
        nettoyer()
        if _pktmon(["filter", "add", "Haretool", "-t", "TCP", "-p", str(PORT)]) != 0:
            raise OSError("pktmon refuse le filtre (lancer en administrateur)")
        journal = os.path.join(tempfile.gettempdir(), "haretool-pktmon.etl")   # pktmon l'écrit à l'arrêt
        if _pktmon(["start", "--capture", "--comp", "nics", "--pkt-size", "0", "-m", "memory", "-s", "16",
                    "--file-name", journal]) != 0:
            raise OSError("pktmon ne démarre pas (lancer en administrateur)")
        self._actif = True
        atexit.register(self.arreter)
        a = _api()
        poignee = ctypes.c_uint64(0)
        err = a.StartTraceW(ctypes.byref(poignee), SESSION, ctypes.byref(_proprietes(rapide=True)))
        if err:   # livraison rapide refusée : lots d'une seconde
            err = a.StartTraceW(ctypes.byref(poignee), SESSION, ctypes.byref(_proprietes()))
        if err:
            self.arreter()
            raise OSError(f"session d'écoute impossible (code {err})")
        err = a.EnableTraceEx2(poignee.value, ctypes.byref(FOURNISSEUR), 1, 4, 0xFFFF, 0, 0, None)
        if err:
            self.arreter()
            raise OSError(f"abonnement impossible (code {err})")
        fichier = _FichierTrace()
        fichier.LoggerName = SESSION
        fichier.ProcessTraceMode = 0x100 | 0x10000000      # temps réel, un rappel par événement
        fichier.EventRecordCallback = self._rappel
        self._trace = a.OpenTraceW(ctypes.byref(fichier))
        if self._trace == 0xFFFFFFFFFFFFFFFF:
            self.arreter()
            raise OSError("lecture de la session impossible")
        trace = ctypes.c_uint64(self._trace)
        threading.Thread(target=lambda: a.ProcessTrace(ctypes.byref(trace), 1, None, None),
                         name="ecoute", daemon=True).start()

    def _sur_evenement(self, rec) -> None:
        try:
            if ctypes.c_ushort.from_address(rec + 40).value != EVENEMENT_CONTENU:
                return
            n = ctypes.c_ushort.from_address(rec + 86).value
            ptr = ctypes.c_void_p.from_address(rec + 96).value
            if not ptr or n < 40:
                return
            p = extraire_paquet(ctypes.string_at(ptr, n))
            if p is None or not p.charge or not self._dedoublon.nouveau(p):
                return
            self._sur_paquet(p)
        except Exception as e:   # jamais d'exception dans un rappel Windows
            self.erreur = repr(e)

    def arreter(self) -> None:
        with self._verrou:
            if not self._actif:
                return
            self._actif = False
        if self._trace is not None:
            try:
                _api().CloseTrace(self._trace)
            except OSError:
                pass
            self._trace = None
        nettoyer()


# ---------------------------------------------------------------- macOS et Linux (libpcap)

if sys.platform != "win32":
    from .ecoute_pcap import Ecoute, nettoyer          # noqa: E402,F811
