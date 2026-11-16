"""Copie d'une zone de l'écran (Windows) pour lire la zone rouge du jeu.

Lecture seule de pixels déjà affichés : aucune interaction avec le jeu. La fenêtre de
dessin d'Haretool est exclue des copies d'écran, sinon on relirait nos propres losanges.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from .zone import ImageEcran

SRCCOPY = 0x00CC0020
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class _EnteteBitmap(ctypes.Structure):
    _fields_ = [("taille", wintypes.DWORD), ("largeur", wintypes.LONG), ("hauteur", wintypes.LONG),
                ("plans", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("octets", wintypes.DWORD), ("ppm_x", wintypes.LONG), ("ppm_y", wintypes.LONG),
                ("couleurs", wintypes.DWORD), ("importantes", wintypes.DWORD)]


def disponible() -> bool:
    return sys.platform == "win32"


_dll = None


def _dll_typees():
    """Copies privées de user32/gdi32 avec types déclarés (poignées 64 bits), sans toucher
    aux déclarations partagées du reste de l'outil."""
    global _dll
    if _dll is not None:
        return _dll
    u32, g32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    P = ctypes.c_void_p
    u32.GetDC.restype, u32.GetDC.argtypes = P, [P]
    u32.ReleaseDC.argtypes = [P, P]
    u32.SetWindowDisplayAffinity.argtypes = [P, wintypes.DWORD]
    g32.CreateCompatibleDC.restype, g32.CreateCompatibleDC.argtypes = P, [P]
    g32.CreateCompatibleBitmap.restype, g32.CreateCompatibleBitmap.argtypes = P, [P, ctypes.c_int, ctypes.c_int]
    g32.SelectObject.restype, g32.SelectObject.argtypes = P, [P, P]
    g32.BitBlt.argtypes = [P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, P,
                           ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    g32.GetDIBits.argtypes = [P, P, wintypes.UINT, wintypes.UINT, P, P, wintypes.UINT]
    g32.DeleteObject.argtypes = [P]
    g32.DeleteDC.argtypes = [P]
    _dll = (u32, g32)
    return _dll


def exclure_des_copies(hwnd: int) -> bool:
    """Rend la fenêtre invisible aux copies d'écran (Windows 10 2004 et plus). Faux si refusé."""
    if not disponible():
        return False
    return bool(_dll_typees()[0].SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


def copier(rect: tuple[int, int, int, int]) -> ImageEcran | None:
    """Pixels de l'écran dans `rect` (gauche, haut, largeur, hauteur), ou None."""
    if not disponible():
        return None
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    u32, g32 = _dll_typees()
    ecran = u32.GetDC(None)
    if not ecran:
        return None
    memoire = g32.CreateCompatibleDC(ecran)
    image = g32.CreateCompatibleBitmap(ecran, w, h)
    try:
        ancien = g32.SelectObject(memoire, image)
        if not g32.BitBlt(memoire, 0, 0, w, h, ecran, x, y, SRCCOPY):
            return None
        entete = _EnteteBitmap(ctypes.sizeof(_EnteteBitmap), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        tampon = ctypes.create_string_buffer(w * h * 4)
        g32.SelectObject(memoire, ancien)
        if g32.GetDIBits(memoire, image, 0, h, tampon, ctypes.byref(entete), 0) != h:
            return None
        return ImageEcran(tampon.raw, w, h)
    finally:
        g32.DeleteObject(image)
        g32.DeleteDC(memoire)
        u32.ReleaseDC(None, ecran)
