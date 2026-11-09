"""Petit encodeur protobuf pour fabriquer des messages de test.

msg({1: 5, 2: b"ab", 3: {1: 7}, 4: [1, 2]}) ; liste = champ répété ;
Empaquete([...]) = varints empaquetés dans un seul champ « longueur ».
"""


class Empaquete(list):
    pass


def varint(n: int) -> bytes:
    n &= (1 << 64) - 1
    sortie = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            sortie.append(b | 0x80)
        else:
            sortie.append(b)
            return bytes(sortie)


def _un(numero, v) -> bytes:
    if isinstance(v, bool) or isinstance(v, int):
        return varint(numero << 3) + varint(int(v))
    if isinstance(v, Empaquete):
        corps = b"".join(varint(x) for x in v)
    elif isinstance(v, dict):
        corps = msg(v)
    else:
        corps = bytes(v)
    return varint((numero << 3) | 2) + varint(len(corps)) + corps


def msg(champs: dict) -> bytes:
    sortie = b""
    for numero, v in champs.items():
        valeurs = v if isinstance(v, list) and not isinstance(v, Empaquete) else [v]
        for x in valeurs:
            sortie += _un(numero, x)
    return sortie
