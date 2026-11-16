"""Un compte par connexion au jeu : son flux dans chaque sens et son état de combat."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .combat import EtatCompte
from .ecoute import PORT, Paquet, cle_connexion
from .flux import Flux
from .protocole import Protocole

INACTIF_S = 60.0


@dataclass
class Compte:
    cle: tuple[str, int]
    etat: EtatCompte
    flux: dict[str, Flux] = field(default_factory=lambda: {"recu": Flux(), "envoye": Flux()})
    dernier: float = 0.0
    fenetre: Any = None
    overlay: Any = None
    cal: Any = None              # calibrage de la fenêtre suivie (dernier rafraîchissement)
    devant_reel: bool = False    # le jeu est vraiment devant (pas seulement la fenêtre de réglages)


class Comptes:
    def __init__(self, protocole: Protocole, est_harebourg: Callable[[int], bool] | None = None) -> None:
        self.protocole = protocole
        self._est_harebourg = est_harebourg
        self._comptes: dict[tuple[str, int], Compte] = {}
        self.enregistreur: Callable | None = None   # (cle, sens, nom, valeur, t), pour le mode apprendre

    def sur_paquet(self, p: Paquet, t: float) -> None:
        cle = cle_connexion(p)
        compte = self._comptes.get(cle)
        if compte is None:
            compte = Compte(cle, EtatCompte(self.protocole, self._est_harebourg))
            self._comptes[cle] = compte
        compte.dernier = t
        sens = "recu" if p.sport == PORT else "envoye"
        for nom, valeur in compte.flux[sens].ajouter(p.seq, p.charge):
            if self.enregistreur is not None:
                self.enregistreur(cle, sens, nom, valeur, t)
            compte.etat.appliquer(nom, valeur, t)

    def oublier_inactifs(self, t: float) -> list[Compte]:
        partis = [c for c in self._comptes.values() if t - c.dernier > INACTIF_S]
        for c in partis:
            del self._comptes[c.cle]
        return partis

    def comptes(self) -> list[Compte]:
        return list(self._comptes.values())
