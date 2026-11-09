"""État du combat d'UN compte, tenu à jour message par message.

PV : valeur absolue reçue avant le combat, puis dégâts et soins. Le tour du perso
commence à son « début de tour » (suivi juste après du signal « c'est à toi »)
et se ferme au début de tour de quelqu'un d'autre. Pendant ce tour, chaque ligne
de dégâts infligée à une cible au contact décale la confusion d'un quart.
"""

from __future__ import annotations

from typing import Callable

from .grille import adjacentes
from .protobuf import champs, varint_signe, varints_empaquetes
from .confusion import quarts_depuis_effet
from .protocole import Protocole

SEUIL_PROTOCOLE = 200
STAT_VITALITE = 11
EFFET_PERTE_PV = 1047      # « −# PV » à plat (ex. sort qui coûte des PV au lanceur)


def _sous_messages(m: dict, numero: int) -> list[dict]:
    sortie = []
    for v in m.get(numero, []):
        if isinstance(v, bytes):
            try:
                sortie.append(champs(v))
            except ValueError:
                pass
    return sortie


def lire(m: dict, chemin: list[int] | None):
    """Première valeur au bout d'un chemin de champs imbriqués, ou None."""
    if not chemin:
        return None
    for numero in chemin[:-1]:
        subs = _sous_messages(m, numero)
        if not subs:
            return None
        m = subs[0]
    valeurs = m.get(chemin[-1])
    return valeurs[0] if valeurs else None


def lignes(m: dict, chemins: dict[str, list[int] | None]) -> list[dict]:
    """Toutes les occurrences d'un groupe de champs voisins (même parent).

    Ex. {"montant": [37, 1], "cible": [37, 5]} → [{"montant": .., "cible": ..}, ...]
    """
    if any(c is None for c in chemins.values()):
        return []
    parents = {tuple(c[:-1]) for c in chemins.values()}
    if len(parents) != 1:
        return []
    parent = list(parents.pop())
    noeuds = [m]
    for numero in parent:
        noeuds = [s for n in noeuds for s in _sous_messages(n, numero)]
    sortie = []
    for n in noeuds:
        ligne = {nom: (n.get(c[-1]) or [None])[0] for nom, c in chemins.items()}
        if all(v is not None for v in ligne.values()):
            sortie.append(ligne)
    return sortie


def _id(v) -> int | None:
    return varint_signe(v) if isinstance(v, int) else None


class EtatCompte:
    def __init__(self, protocole: Protocole, est_harebourg: Callable[[int], bool] | None = None) -> None:
        self.protocole = protocole
        if est_harebourg is None:
            from .terrain import est_harebourg as defaut
            est_harebourg = defaut
        self._est_harebourg = est_harebourg
        self.moi: int | None = None
        self.carte: int | None = None
        self.nom_perso: str | None = None
        self.noms: dict[int, str] = {}       # combattant → nom (fiches)
        self.protocole_ok = True
        self._sans_reconnu = 0
        self._dernier_debut: int | None = None
        self._remettre_a_zero()

    def _remettre_a_zero(self) -> None:
        self.en_combat = False
        self.pv: int | None = None
        self.pv_max: int | None = None
        self.pv_debut_tour: int | None = None
        self.mon_tour = False
        self.lignes_melee = 0
        self.positions: dict[int, int] = {}
        self.monstres: dict[int, int] = {}
        self.morts: set[int] = set()
        self.ordre: dict[int, int] = {}      # monstre → rang d'apparition (couleur stable)
        self.pv_par_id: dict[int, tuple[int, int]] = {}   # PV absolus reçus (Songes) : id → (PV, max)
        # PV comptés de chaque joueur dès le début du combat (avant de savoir qui est « moi ») :
        # id → [PV, maximum sans érosion, bonus de vitalité reçu, érosion subie]
        self.vie: dict[int, list[int]] = {}
        self.confusion: dict[int, int] = {}   # joueur → quarts horaires envoyés par le jeu pour ce tour
        self.harebourg_present = False
        self.quarts_force: int | None = None  # correction manuelle, jusqu'au prochain tour

    # ------------------------------------------------------------ entrée

    def appliquer(self, nom: str, valeur: bytes, t: float) -> None:
        cle = self.protocole.reconnu(nom)
        if cle is None:
            self._sans_reconnu += 1
            if self._sans_reconnu >= SEUIL_PROTOCOLE:
                self.protocole_ok = False
            return
        self._sans_reconnu = 0
        self.protocole_ok = True
        try:
            m = champs(valeur)
        except ValueError:
            return
        getattr(self, "_sur_" + cle)(m, t)

    def _c(self, cle: str, champ: str):
        return self.protocole.champ(cle, champ)

    # ------------------------------------------------------------ messages

    def _sur_pv_absolus(self, m, t) -> None:
        courants, maxi = lire(m, self._c("pv_absolus", "courants")), lire(m, self._c("pv_absolus", "max"))
        if isinstance(courants, int) and isinstance(maxi, int) and maxi > 0:
            self.pv, self.pv_max = courants, maxi
            self._kqo = (courants, maxi)

    def _vie(self, ident: int | None) -> list[int] | None:
        """Les PV comptés d'un joueur, partis des PV de base du perso (kqo)."""
        if ident is None or ident <= 0:
            return None
        v = self.vie.get(ident)
        if v is None:
            base = getattr(self, "_kqo", None)
            if base is None:
                return None
            v = self.vie[ident] = [base[0], base[1], 0, 0]
        return v

    def _suivre(self, ident: int | None) -> None:
        if ident is not None and ident == self.moi and ident not in self.pv_par_id and ident in self.vie:
            self.pv, self.pv_max = self._pv_et_max(self.vie[ident])

    @staticmethod
    def _pv_et_max(v: list[int]) -> tuple[int, int]:
        """PV et maximum ÉRODÉ : c'est sur eux que le jeu compte la confusion
        (vérifié en jeu : 1416 PV, max 3329 − 190 d'érosion = 45 % → 2 quarts)."""
        maxi = max(1, v[1] - v[3])
        return min(v[0], maxi), maxi

    def _sur_effet(self, m, t) -> None:
        """Effet posé sur un combattant : la confusion du tour (codes 770 à 775), ou une perte de PV à plat."""
        action = lire(m, self._c("effet", "action"))
        cible = _id(lire(m, self._c("effet", "cible")))
        valeur = lire(m, self._c("effet", "valeur"))
        if cible is None or not isinstance(valeur, int):
            return
        q = quarts_depuis_effet(action, valeur)
        if q is not None:
            self.confusion[cible] = q
        elif action == EFFET_PERTE_PV:
            v = self._vie(cible)
            if v is not None:
                v[0] = max(0, v[0] - valeur)
                self._suivre(cible)

    def _sur_caracteristique(self, m, t) -> None:
        """Vitalité ajoutée en combat (Songes : +80 % au début) : elle monte le maximum ET les PV."""
        if lire(m, self._c("caracteristique", "stat")) != STAT_VITALITE:
            return
        ident = _id(lire(m, self._c("caracteristique", "id")))
        bonus = lire(m, self._c("caracteristique", "bonus_moi"))
        if not isinstance(bonus, int):
            bonus = lire(m, self._c("caracteristique", "bonus"))
        v = self._vie(ident)
        if v is None or not isinstance(bonus, int):
            return
        bonus = varint_signe(bonus)
        ecart, v[2] = bonus - v[2], bonus
        v[1] = max(1, v[1] + ecart)
        v[0] = max(0, v[0] + ecart)
        self._suivre(ident)

    def _sur_combattants(self, m, t) -> None:
        liste = self._c("combattants", "liste")
        if not liste:
            return
        noeuds = [m]
        for numero in liste:
            noeuds = [s for n in noeuds for s in _sous_messages(n, numero)]
        self.en_combat = True
        for n in noeuds:
            ident = _id(lire(n, self._c("combattants", "id")))
            case = lire(n, self._c("combattants", "case"))
            if ident is None or not isinstance(case, int):
                continue
            if ident in self.morts:
                continue
            self._noter(ident, case)
            monstre = lire(n, self._c("combattants", "monstre"))
            if isinstance(monstre, int) and ident < 0:
                self.monstres[ident] = monstre
                if self._est_harebourg(monstre):
                    self.harebourg_present = True

    def _sur_deplacement(self, m, t) -> None:
        if not self.en_combat:
            return
        acteur = _id(lire(m, self._c("deplacement", "acteur")))
        chemin = lire(m, self._c("deplacement", "chemin"))
        if acteur is None:
            return
        if isinstance(chemin, bytes):
            try:
                cases = varints_empaquetes(chemin)
            except ValueError:
                return
        elif isinstance(chemin, int):
            cases = [chemin]
        else:
            return
        if cases and acteur not in self.morts:
            self._noter(acteur, cases[-1])

    def _sur_action(self, m, t) -> None:
        if not self.en_combat:
            return
        c = lambda nom: self._c("action", nom)   # noqa: E731
        source = _id(lire(m, c("source")))
        for l in lignes(m, {"montant": c("degats_montant"), "cible": c("degats_cible")}):
            cible = _id(l["cible"])
            v = self._vie(cible)
            if v is not None:
                v[0] = max(0, v[0] - l["montant"])
                self._suivre(cible)
        # Une ligne de dégâts au contact fait tourner la confusion MÊME À 0 DÉGÂT (le jeu envoie
        # alors la ligne sans montant) : vérifié en jeu, coup à 0 au contact puis sort arrivé
        # à 2 + 1 quarts.
        for l in lignes(m, {"cible": c("degats_cible")}):
            cible = _id(l["cible"])
            if (self.mon_tour and source == self.moi and cible != self.moi
                    and cible in self.positions and self.moi in self.positions
                    and adjacentes(self.positions[self.moi], self.positions[cible])):
                self.lignes_melee += 1
        # l'érosion baisse le maximum (et borne les soins)
        for l in lignes(m, {"erosion": c("degats_erosion"), "cible": c("degats_cible")}):
            v = self._vie(_id(l["cible"]))
            if v is not None:
                v[3] += l["erosion"]
        for l in lignes(m, {"montant": c("soin_montant"), "cible": c("soin_cible")}):
            cible = _id(l["cible"])
            v = self._vie(cible)
            if v is not None:
                v[0] = min(max(v[0], v[1] - v[3]), v[0] + l["montant"])
                self._suivre(cible)
        for l in lignes(m, {"acteur": c("poussee_acteur"), "case": c("poussee_arrivee")}):
            self._poser(_id(l["acteur"]), l["case"])
        for l in lignes(m, {"acteur": c("teleport_acteur"), "case": c("teleport_case")}):
            self._poser(_id(l["acteur"]), l["case"])
        for l in lignes(m, {"case_lanceur": c("echange_case_lanceur"), "autre": c("echange_autre"),
                            "case_autre": c("echange_case_autre")}):
            self._poser(source, l["case_lanceur"])
            self._poser(_id(l["autre"]), l["case_autre"])
        for l in lignes(m, {"id": c("mort_id")}):
            mort = _id(l["id"])
            if mort is not None:
                self.positions.pop(mort, None)
                self.morts.add(mort)

    def _poser(self, acteur: int | None, case) -> None:
        if acteur is not None and isinstance(case, int) and acteur not in self.morts:
            self._noter(acteur, case)

    def _noter(self, ident: int, case: int) -> None:
        self.positions[ident] = case
        if ident < 0 and ident not in self.ordre:
            self.ordre[ident] = len(self.ordre)

    def _sur_pv_combattant(self, m, t) -> None:
        """PV absolus d'un combattant (Songes, à plusieurs) : PV actuels et maximum ÉRODÉ,
        qui font foi. PV actuels absents : le jeu ne les renvoie pas toujours (bonus posés,
        fin de combat) ; on garde les derniers."""
        ident = _id(lire(m, self._c("pv_combattant", "id")))
        maxi = lire(m, self._c("pv_combattant", "max"))
        if ident is None or not isinstance(maxi, int) or maxi <= 0:
            return
        avant = self.pv_par_id.get(ident)
        courants = lire(m, self._c("pv_combattant", "courants"))
        if not isinstance(courants, int):
            if avant is None:
                return
            courants = avant[0]
        self.pv_par_id[ident] = (courants, maxi)
        if ident == self.moi:
            self.pv, self.pv_max = courants, maxi

    def _sur_debut_tour(self, m, t) -> None:
        acteur = _id(lire(m, self._c("debut_tour", "acteur")))
        if acteur is None:
            return
        self._dernier_debut = acteur
        if acteur == self.moi:
            self._commencer_mon_tour()
        else:
            self.mon_tour = False

    def _sur_notre_tour(self, m, t) -> None:
        """« C'est à toi » désigne l'acteur du début de tour qui le précède (par l'ordre :
        les messages arrivent groupés, leurs heures ne disent rien)."""
        acteur, self._dernier_debut = self._dernier_debut, None
        if acteur is None or acteur < 0:
            return
        if not (self.mon_tour and self.moi == acteur):
            self.moi = acteur
            self._commencer_mon_tour()

    def _commencer_mon_tour(self) -> None:
        if self.moi in self.pv_par_id:
            self.pv, self.pv_max = self.pv_par_id[self.moi]
        elif self.moi in self.vie:
            self.pv, self.pv_max = self._pv_et_max(self.vie[self.moi])
        if self.moi in self.noms:
            self.nom_perso = self.noms[self.moi]
        self.mon_tour = True
        self.pv_debut_tour = self.pv
        self.lignes_melee = 0
        self.quarts_force = None

    def _sur_fin_tour(self, m, t) -> None:
        if _id(lire(m, self._c("fin_tour", "acteur"))) == self.moi:
            self.mon_tour = False
            self.confusion.pop(self.moi, None)     # le jeu renvoie celle du tour suivant

    def _sur_fin_combat(self, m, t) -> None:
        self._remettre_a_zero()

    def _sur_carte_courante(self, m, t) -> None:
        carte = lire(m, self._c("carte_courante", "carte"))
        if isinstance(carte, int):
            self.carte = carte

    def _sur_fiche(self, m, t) -> None:
        """Fiche d'un combattant : identifiant de monstre (monstres) ou nom (joueurs)."""
        ident = _id(lire(m, self._c("fiche", "id")))
        if ident is None:
            return
        if ident < 0:
            monstre = lire(m, self._c("fiche", "monstre"))
            if isinstance(monstre, int):
                self.monstres[ident] = monstre
                if self._est_harebourg(monstre):
                    self.harebourg_present = True
            return
        nom = lire(m, self._c("fiche", "nom"))
        if isinstance(nom, bytes) and nom:
            self.noms[ident] = nom.decode("utf-8", "replace")
            if ident == self.moi:
                self.nom_perso = self.noms[ident]
