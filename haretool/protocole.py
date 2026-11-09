"""Correspondance entre les informations utiles et les messages du jeu.

Les noms de messages et les numéros de champs changent à chaque mise à jour du
jeu : ils vivent dans un fichier JSON, embarqué dans l'outil ET vérifié en
ligne au lancement, pour réparer tout le monde sans republier l'exe.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

EMBARQUE = Path(__file__).parent / "donnees" / "protocole.json"
URL_OFFICIELLE = "https://haretool.vercel.app/protocole.json"   # réparé ici après une MAJ du jeu
CLES = ("pv_absolus", "combattants", "deplacement", "action", "debut_tour", "notre_tour",
        "fin_tour", "fin_combat", "carte_courante", "fiche", "pv_combattant", "caracteristique", "effet")
OPTIONNELLES = {"caracteristique", "effet"}    # absentes d'un ancien fichier en ligne : simplement ignorées


def dossier_reglages() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "Haretool"


def _telecharger(url: str, delai: float) -> bytes:
    with urllib.request.urlopen(url, timeout=delai) as r:
        return r.read(1 << 20)


class Protocole:
    def __init__(self, donnees: dict) -> None:
        if not isinstance(donnees, dict) or not isinstance(donnees.get("version"), str):
            raise ValueError("version absente")
        messages = donnees.get("messages")
        if not isinstance(messages, dict) or any(c not in messages for c in CLES if c not in OPTIONNELLES):
            raise ValueError("messages incomplets")
        self.version: str = donnees["version"]
        self.messages: dict[str, dict | None] = {}
        self._par_nom: dict[str, str] = {}
        for cle in CLES:
            m = messages.get(cle)
            if m is None:
                self.messages[cle] = None
                continue
            if not isinstance(m.get("nom"), str) or not isinstance(m.get("champs"), dict):
                raise ValueError(f"{cle} mal formé")
            for chemin in m["champs"].values():
                if chemin is not None and not (isinstance(chemin, list) and all(isinstance(n, int) for n in chemin)):
                    raise ValueError(f"{cle} : chemin mal formé")
            self.messages[cle] = m
            self._par_nom[m["nom"]] = cle

    @classmethod
    def depuis_fichier(cls, chemin: Path) -> "Protocole":
        return cls(json.loads(Path(chemin).read_text("utf-8")))

    def reconnu(self, nom: str) -> str | None:
        return self._par_nom.get(nom)

    def nom(self, cle: str) -> str | None:
        m = self.messages.get(cle)
        return m["nom"] if m else None

    def champ(self, cle: str, nom_champ: str) -> list[int] | None:
        m = self.messages.get(cle)
        return m["champs"].get(nom_champ) if m else None

    @classmethod
    def charger(cls, chemin_local: Path, url: str | None, delai_s: float = 3,
                dossier_cache: Path | None = None) -> tuple["Protocole", str]:
        """Rend (protocole, origine) avec origine « en ligne », « cache » ou « embarqué »."""
        cache = Path(dossier_cache or dossier_reglages()) / "protocole.json"
        embarque = cls.depuis_fichier(chemin_local)
        if url:
            try:
                brut = _telecharger(url, delai_s)
                p = cls(json.loads(brut.decode("utf-8")))
                try:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_bytes(brut)
                except OSError:
                    pass
                return p, "en ligne"
            except (OSError, ValueError):
                pass
        try:
            p = cls.depuis_fichier(cache)
            if p.version > embarque.version:
                return p, "cache"
        except (OSError, ValueError):
            pass
        return embarque, "embarqué"
