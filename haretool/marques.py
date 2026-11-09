"""Ce qu'il faut dessiner sur le sol, déduit de l'état du combat d'un compte."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from .confusion import case_a_cliquer, tranche_de
from .ldv import en_vue
from .terrain import jouables, bloque_vue

ROUGE = "#E53935"
BLEU_VUE = "#1565C0"      # œil barré : seulement avec un sort sans ligne de vue
GRIS_ALLIE = "#B0BEC5"    # alliés : même règle que les monstres, seule la couleur change
PALETTE_DEFAUT = ["#FFD600", "#00E5FF", "#FF4081", "#76FF03", "#FF9100", "#D500F9", "#FFFFFF", "#2979FF"]


class Marque(NamedTuple):
    forme: Literal["losange", "epee", "bouclier", "indisponible", "hors_vue"]
    case: int
    couleur: str


@dataclass
class OptionsDessin:
    palette: list[str] = field(default_factory=lambda: list(PALETTE_DEFAUT))
    montrer_losange_mob: bool = True
    montrer_ldv: bool = True
    montrer_avertissements: bool = True
    montrer_allies: bool = True


def marques(etat, options: OptionsDessin) -> list[Marque]:
    """Marques dans l'ordre de peinture : tous les losanges, puis toutes les icônes."""
    if not etat.en_combat or not etat.harebourg_present or etat.moi is None or etat.moi not in etat.positions:
        return []
    q = tranche_de(etat)
    if q is None:
        return []
    moi = etat.positions[etat.moi]
    jouable = jouables(etat.carte)
    obstacles = bloque_vue(etat.carte)
    occupees = {c for i, c in etat.positions.items() if i != etat.moi}
    fonds: list[Marque] = []
    icones: list[Marque] = []
    palette = options.palette or PALETTE_DEFAUT
    monstres = sorted((i for i in etat.positions if i < 0 and i not in etat.morts),
                      key=lambda i: etat.ordre.get(i, len(etat.ordre)))
    cibles = [(i, palette[etat.ordre.get(i, 0) % len(palette)], "epee") for i in monstres]
    if options.montrer_allies:
        cibles += [(i, GRIS_ALLIE, "bouclier") for i in sorted(etat.positions)
                   if i > 0 and i != etat.moi and i not in etat.morts]
    for ident, couleur, action in cibles:
        case_cible = etat.positions[ident]
        if options.montrer_losange_mob:
            fonds.append(Marque("losange", case_cible, couleur))
        cible = case_a_cliquer(moi, case_cible, q, etat.lignes_melee)
        if cible is None or (jouable is not None and cible not in jouable):
            if options.montrer_avertissements:
                icones.append(Marque("indisponible", case_cible, ROUGE))
            continue
        fonds.append(Marque("losange", cible, couleur))
        # La vue se juge de ma case jusqu'à la CIBLE : derrière un obstacle ou un autre
        # combattant, l'œil barré remplace l'épée (ou le bouclier).
        cache = (options.montrer_ldv and obstacles is not None
                 and not en_vue(moi, case_cible, set(obstacles) | occupees))
        icones.append(Marque("hors_vue", cible, BLEU_VUE) if cache else Marque(action, cible, couleur))
    return fonds + icones
