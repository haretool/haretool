"""Réglages de l'utilisateur, sauvés dans %APPDATA%\\Haretool\\reglages.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .marques import PALETTE_DEFAUT, OptionsDessin
from .protocole import dossier_reglages


def chemin_par_defaut() -> Path:
    return dossier_reglages() / "reglages.json"


@dataclass
class Reglages:
    actif_par_compte: dict = field(default_factory=dict)      # nom du perso → affiché ou non
    association: dict = field(default_factory=dict)           # nom du perso → titre de fenêtre choisi
    palette: list = field(default_factory=lambda: list(PALETTE_DEFAUT))
    opacite: float = 0.85
    taille_icones: float = 1.0
    montrer_losange_mob: bool = True
    montrer_ldv: bool = True
    montrer_avertissements: bool = True
    montrer_allies: bool = True
    raccourci: str = "Ctrl+Alt+H"
    reglage_fin: dict = field(default_factory=dict)            # calibrages corrigés aux flèches, par taille de fenêtre
    url_protocole: str | None = None

    @classmethod
    def charger(cls, chemin: Path | None = None) -> "Reglages":
        chemin = Path(chemin or chemin_par_defaut())
        defauts = cls()
        try:
            brut = chemin.read_text("utf-8")
        except OSError:
            return defauts
        try:
            donnees = json.loads(brut)
            if not isinstance(donnees, dict):
                raise ValueError
        except ValueError:
            try:
                chemin.with_name(chemin.name + ".bak").write_text(brut, "utf-8")
            except OSError:
                pass
            return defauts
        valeurs = {}
        for f in fields(cls):
            if f.name not in donnees:
                continue
            v, attendu = donnees[f.name], getattr(defauts, f.name)
            if f.name == "url_protocole":
                if v is None or isinstance(v, str):
                    valeurs[f.name] = v
            elif isinstance(attendu, bool):
                if isinstance(v, bool):
                    valeurs[f.name] = v
            elif isinstance(attendu, float):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    valeurs[f.name] = float(v)
            elif isinstance(attendu, list):
                if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                    valeurs[f.name] = v
            elif isinstance(v, type(attendu)):
                valeurs[f.name] = v
        return cls(**valeurs)

    def sauver(self, chemin: Path | None = None) -> None:
        chemin = Path(chemin or chemin_par_defaut())
        chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = chemin.with_name(chemin.name + ".tmp")
        provisoire.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), "utf-8")
        provisoire.replace(chemin)

    def options_dessin(self) -> OptionsDessin:
        return OptionsDessin(palette=list(self.palette), montrer_losange_mob=self.montrer_losange_mob,
                             montrer_ldv=self.montrer_ldv, montrer_avertissements=self.montrer_avertissements,
                             montrer_allies=self.montrer_allies)
