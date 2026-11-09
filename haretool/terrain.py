"""Données du jeu embarquées : cases jouables par carte, identifiants du Comte."""

from __future__ import annotations

import json
import struct
import zlib
from functools import lru_cache
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees"
CASES = 560
OCTETS = CASES // 8
ENTREE = 4 + 2 * OCTETS


def _entete(n: int) -> bytes:
    return b"HTCB" + struct.pack("<I", n)


def _cases(octets: bytes) -> frozenset[int]:
    return frozenset(n for n in range(CASES) if octets[n // 8] >> (n % 8) & 1)


class Terrain:
    def __init__(self, brut: bytes) -> None:
        if brut[:4] != b"HTCB":
            raise ValueError("cartes.bin invalide")
        n = struct.unpack_from("<I", brut, 4)[0]
        self._index: dict[int, int] = {}
        self._brut = brut
        for i in range(n):
            pos = 8 + i * ENTREE
            self._index[struct.unpack_from("<I", brut, pos)[0]] = pos + 4

    def __len__(self) -> int:
        return len(self._index)

    def jouables(self, carte: int) -> frozenset[int] | None:
        pos = self._index.get(carte)
        return None if pos is None else _cases(self._brut[pos:pos + OCTETS])

    def bloque_vue(self, carte: int) -> frozenset[int] | None:
        pos = self._index.get(carte)
        return None if pos is None else _cases(self._brut[pos + OCTETS:pos + 2 * OCTETS])


@lru_cache(maxsize=1)
def _terrain() -> Terrain:
    try:
        return Terrain(zlib.decompress((DONNEES / "cartes.bin").read_bytes()))
    except (OSError, ValueError, zlib.error):
        return Terrain(_entete(0))


@lru_cache(maxsize=1)
def _comtes() -> frozenset[int]:
    try:
        return frozenset(m["id"] for m in json.loads((DONNEES / "monstres_harebourg.json").read_text("utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()


def nombre_de_cartes() -> int:
    return len(_terrain())


def jouables(carte: int | None) -> frozenset[int] | None:
    return None if carte is None else _terrain().jouables(carte)


def bloque_vue(carte: int | None) -> frozenset[int] | None:
    return None if carte is None else _terrain().bloque_vue(carte)


def est_harebourg(id_monstre: int) -> bool:
    return id_monstre in _comtes()
