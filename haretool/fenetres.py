"""Fenêtres du jeu ouvertes, trouvées sans jamais ouvrir le processus du jeu.

La liste des processus (instantané système) donne les numéros des Dofus.exe ;
chaque fenêtre visible est rattachée à son processus par ce numéro.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
from typing import NamedTuple

EXECUTABLE = "dofus.exe"


class FenetreJeu(NamedTuple):
    hwnd: int
    titre: str
    rect: tuple[int, int, int, int]     # zone de jeu à l'écran : gauche, haut, largeur, hauteur
    reduite: bool
    devant: bool


class _EntreeProcessus(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def _pids_du_jeu() -> set[int]:
    k32 = ctypes.WinDLL("kernel32")
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    instantane = k32.CreateToolhelp32Snapshot(0x2, 0)    # liste des processus
    if not instantane or instantane == wt.HANDLE(-1).value:
        return set()
    pids = set()
    try:
        e = _EntreeProcessus()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(instantane, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == EXECUTABLE:
                pids.add(e.th32ProcessID)
            ok = k32.Process32NextW(instantane, ctypes.byref(e))
    finally:
        k32.CloseHandle(instantane)
    return pids


_RAPPEL = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(wt.BOOL, wt.HWND, wt.LPARAM)


def lister() -> list[FenetreJeu]:
    if sys.platform == "darwin":
        from .fenetres_mac import lister as lister_mac
        return lister_mac()
    if sys.platform.startswith("linux"):
        from .fenetres_linux import lister as lister_linux
        return lister_linux()
    try:
        u32 = ctypes.WinDLL("user32")
    except OSError:
        return []
    pids = _pids_du_jeu()
    if not pids:
        return []
    devant = u32.GetForegroundWindow()
    trouvees: list[FenetreJeu] = []

    def chaque(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        tampon = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, tampon, n + 1)
        r = wt.RECT()
        u32.GetClientRect(hwnd, ctypes.byref(r))
        coin = wt.POINT(0, 0)
        u32.ClientToScreen(hwnd, ctypes.byref(coin))
        trouvees.append(FenetreJeu(int(hwnd), tampon.value, (coin.x, coin.y, r.right, r.bottom),
                                   bool(u32.IsIconic(hwnd)), hwnd == devant))
        return True

    u32.EnumWindows(_RAPPEL(chaque), 0)
    return trouvees


def associer(nom_perso: str | None, fenetres: list[FenetreJeu]) -> FenetreJeu | None:
    if not nom_perso:
        return None
    nom = nom_perso.lower()
    for f in fenetres:
        if nom in f.titre.lower():
            return f
    return None
