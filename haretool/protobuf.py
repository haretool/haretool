"""Lecture brute du format protobuf, sans schéma : numéro de champ → valeurs."""


def lire_varint(octets: bytes, pos: int) -> tuple[int, int]:
    resultat = decalage = 0
    while True:
        if pos >= len(octets) or decalage > 63:
            raise ValueError("varint tronqué")
        b = octets[pos]
        pos += 1
        resultat |= (b & 0x7F) << decalage
        if not b & 0x80:
            return resultat, pos
        decalage += 7


def champs(octets: bytes) -> dict[int, list]:
    """Décode un message : varint → int, longueur → bytes, 32 et 64 bits → int.

    Lève ValueError si les octets ne forment pas un message valide.
    """
    sortie: dict[int, list] = {}
    pos = 0
    while pos < len(octets):
        cle, pos = lire_varint(octets, pos)
        numero, genre = cle >> 3, cle & 7
        if numero == 0:
            raise ValueError("champ 0")
        if genre == 0:
            valeur, pos = lire_varint(octets, pos)
        elif genre == 2:
            n, pos = lire_varint(octets, pos)
            if pos + n > len(octets):
                raise ValueError("longueur hors message")
            valeur, pos = octets[pos:pos + n], pos + n
        elif genre in (1, 5):
            taille = 8 if genre == 1 else 4
            if pos + taille > len(octets):
                raise ValueError("fixe tronqué")
            valeur, pos = int.from_bytes(octets[pos:pos + taille], "little"), pos + taille
        else:
            raise ValueError(f"genre {genre} non géré")
        sortie.setdefault(numero, []).append(valeur)
    return sortie


sous = champs


def varint_signe(n: int) -> int:
    """Complément à 2 sur 64 bits (les monstres ont des identifiants négatifs)."""
    n &= 0xFFFFFFFFFFFFFFFF
    return n - (1 << 64) if n >> 63 else n


def varints_empaquetes(octets: bytes) -> list[int]:
    valeurs, pos = [], 0
    while pos < len(octets):
        v, pos = lire_varint(octets, pos)
        valeurs.append(v)
    return valeurs


def premier(message: dict[int, list], numero: int, defaut=None):
    valeurs = message.get(numero)
    return valeurs[0] if valeurs else defaut
