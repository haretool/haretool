"""Réassemblage d'un sens d'une connexion TCP et découpage en messages du jeu.

Chaque trame = sa longueur en varint, puis une enveloppe protobuf qui contient,
quelque part, un sous-message { 1: "type.ankama.com/<nom>", 2: valeur }.
"""

from .protobuf import champs, lire_varint

PREFIXE = b"type.ankama.com/"
DEMARRAGE = 3          # paquets attendus avant de choisir le début du flux
TROU_MAX = 6           # paquets en attente avant d'abandonner un trou (paquet perdu par la capture)
TAILLE_MAX = 1 << 20   # une trame plus grande = désynchronisé
MOD = 1 << 32


def trouver_message(octets: bytes, profondeur: int = 0) -> tuple[str, bytes] | None:
    """Cherche récursivement le sous-message nommé dans une enveloppe."""
    if profondeur > 4:
        return None
    try:
        m = champs(octets)
    except ValueError:
        return None
    nom = m.get(1, [None])[0]
    if isinstance(nom, bytes) and nom.startswith(PREFIXE):
        valeur = m.get(2, [b""])[0]
        return nom[len(PREFIXE):].decode("ascii", "replace"), valeur if isinstance(valeur, bytes) else b""
    for valeurs in m.values():
        for v in valeurs:
            if isinstance(v, bytes) and PREFIXE in v:
                trouve = trouver_message(v, profondeur + 1)
                if trouve:
                    return trouve
    return None


class Flux:
    def __init__(self) -> None:
        self._attente: dict[int, bytes] = {}
        self._attendu: int | None = None
        self._tampon = b""
        self._resync = True     # le début du flux n'est pas forcément un début de trame

    def ajouter(self, seq: int, charge: bytes) -> list[tuple[str, bytes]]:
        if not charge:
            return []
        if self._attendu is not None:
            avance = (seq - self._attendu) % MOD
            fin = (avance + len(charge)) % MOD
            if avance >= MOD // 2:                 # commence avant l'attendu
                if fin == 0 or fin >= MOD // 2:    # entièrement déjà reçu
                    return []
                charge = charge[len(charge) - fin:]
                seq = self._attendu
        ancien = self._attente.get(seq)
        if ancien is None or len(charge) > len(ancien):
            self._attente[seq] = charge
        if self._attendu is None:
            if len(self._attente) < DEMARRAGE:
                return []
            self._attendu = min(self._attente)
        self._avancer()
        return self._decouper()

    def _avancer(self) -> None:
        while True:
            morceau = self._attente.pop(self._attendu, None)
            if morceau is not None:
                self._tampon += morceau
                self._attendu = (self._attendu + len(morceau)) % MOD
                continue
            # retransmissions qui chevauchent l'attendu
            for s in list(self._attente):
                avance = (s - self._attendu) % MOD
                if avance >= MOD // 2:
                    m = self._attente.pop(s)
                    fin = (avance + len(m)) % MOD
                    if 0 < fin < MOD // 2:
                        self._attente[self._attendu] = m[len(m) - fin:]
                        break
            else:
                if len(self._attente) > TROU_MAX:   # trou jamais comblé : on saute
                    self._attendu = min(self._attente, key=lambda s: (s - self._attendu) % MOD)
                    self._tampon = b""
                    self._resync = True
                    continue
                return

    def _decouper(self) -> list[tuple[str, bytes]]:
        sortie = []
        pos = 0
        t = self._tampon
        while pos < len(t):
            try:
                n, debut = lire_varint(t, pos)
            except ValueError:
                if len(t) - pos > 10:   # varint impossible : désynchronisé
                    self._resync, pos = True, pos + 1
                    continue
                break
            if n == 0 or n > TAILLE_MAX:
                self._resync, pos = True, pos + 1
                continue
            if debut + n > len(t):
                if self._resync and n > TAILLE_MAX // 16:
                    pos += 1
                    continue
                break
            trouve = trouver_message(t[debut:debut + n])
            if trouve is None:
                self._resync, pos = True, pos + 1
                continue
            sortie.append(trouve)
            self._resync = False
            pos = debut + n
        self._tampon = t[pos:]
        return sortie
