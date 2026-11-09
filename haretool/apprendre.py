"""Mode « apprendre » : après une mise à jour du jeu, retrouver les messages utiles
par leur FORME dans un petit combat enregistré, sans connaître leurs noms.

- combattants : une liste de sous-messages portant un identifiant (négatif pour
  les monstres) et un numéro de case (< 560) ;
- PV absolus : reçus juste avant cette liste, un entier égal aux PV lus par
  l'utilisateur, un autre ≥ (le maximum) ;
- déplacement : un champ dont les varints empaquetés avancent par pas de 13, 14
  ou 15 ;
- dégâts : le sous-message dont un champ, additionné entre deux lectures de PV
  pour la cible « moi », retombe exactement sur la perte de PV ;
- début de tour : un message simple dont un champ parcourt les combattants.
Le résultat est un brouillon de protocole.json, à vérifier par le mainteneur.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from .protobuf import champs, varint_signe, varints_empaquetes
from .protocole import CLES, dossier_reglages

CASES = 560
PAS = {13, 14, 15}


def _decoder(messages):
    sortie = []
    for t, nom, valeur in messages:
        try:
            sortie.append((t, nom, champs(valeur)))
        except ValueError:
            pass
    return sortie


def _sous(v):
    if not isinstance(v, bytes):
        return None
    try:
        m = champs(v)
    except ValueError:
        return None
    return m or None


def _entiers(m: dict) -> dict[int, int]:
    return {f: vs[0] for f, vs in m.items() if len(vs) == 1 and isinstance(vs[0], int)}


def _combattants(decodes):
    meilleur = None
    for t, nom, m in decodes:
        for f, valeurs in m.items():
            if len(valeurs) < 2:
                continue
            items = [_sous(v) for v in valeurs]
            if any(i is None for i in items):
                continue
            communs = set.intersection(*(set(_entiers(i)) for i in items))
            ident = next((c for c in sorted(communs)
                          if any(varint_signe(i[c][0]) < 0 for i in items)
                          and any(varint_signe(i[c][0]) > 0 for i in items)), None)
            if ident is None:
                continue
            cases = [c for c in sorted(communs) if c != ident and all(0 <= i[c][0] < CASES for i in items)]
            if not cases:
                continue
            case = max(cases, key=lambda c: len({i[c][0] for i in items}))
            score = len(items)
            if meilleur is None or score > meilleur[0]:
                ids = {varint_signe(i[ident][0]) for i in items}
                meilleur = (score, t, nom, f, ident, case, ids)
    return meilleur


def _pv_absolus(decodes, t_combat, pv0):
    for t, nom, m in reversed(decodes):
        if t > t_combat or t_combat - t > 30:
            continue
        entiers = _entiers(m)
        courants = next((f for f, v in sorted(entiers.items()) if v == pv0), None)
        if courants is None:
            continue
        au_dessus = [(v, f) for f, v in entiers.items() if f != courants and v >= pv0]
        if not au_dessus:
            continue
        return nom, courants, min(au_dessus)[1]
    return None


def _est_chemin(v) -> bool:
    if not isinstance(v, bytes) or len(v) < 2:
        return False
    try:
        cases = varints_empaquetes(v)
    except ValueError:
        return False
    return (len(cases) >= 2 and all(0 <= c < CASES for c in cases)
            and all(abs(b - a) in PAS for a, b in zip(cases, cases[1:])))


def _deplacement(decodes, ids):
    compte: Counter = Counter()
    acteurs: dict = defaultdict(Counter)
    for _, nom, m in decodes:
        for f, valeurs in m.items():
            if len(valeurs) == 1 and _est_chemin(valeurs[0]):
                compte[(nom, f)] += 1
                for fa, v in _entiers(m).items():
                    if varint_signe(v) in ids:
                        acteurs[(nom, f)][fa] += 1
    if not compte:
        return None
    (nom, f), _ = compte.most_common(1)[0]
    acteur = acteurs[(nom, f)].most_common(1)
    return nom, f, acteur[0][0] if acteur else None


def _degats(decodes, ids, lectures):
    (t0, pv0), (t1, pv1) = lectures[0], lectures[-1]
    perte = pv0 - pv1
    if perte <= 0:
        return None
    sommes: dict = defaultdict(int)
    for t, nom, m in decodes:
        if not t0 < t <= t1:
            continue
        for p, valeurs in m.items():
            for v in valeurs:
                s = _sous(v)
                if s is None:
                    continue
                e = _entiers(s)
                for fm, montant in e.items():
                    for fc, cible in e.items():
                        if fm != fc and varint_signe(cible) in ids:
                            sommes[(nom, p, fm, fc, varint_signe(cible))] += montant
    trouves = [k for k, s in sommes.items() if s == perte and k[4] > 0]
    if not trouves:
        return None
    nom, p, fm, fc, moi = min(trouves, key=lambda k: (k[1], k[2], k[3]))
    source = Counter()
    for _, n, m in decodes:
        if n == nom:
            for f, v in _entiers(m).items():
                if varint_signe(v) in ids:
                    source[f] += 1
    return nom, p, fm, fc, source.most_common(1)[0][0] if source else None


def _debut_tour(decodes, ids, exclus):
    candidats = []
    par_nom: dict = defaultdict(list)
    for _, nom, m in decodes:
        if nom not in exclus:
            par_nom[nom].append(m)
    for nom, liste in par_nom.items():
        if any(isinstance(v, bytes) for m in liste for vs in m.values() for v in vs):
            continue
        communs = set.intersection(*(set(_entiers(m)) for m in liste))
        for f in communs:
            valeurs = [varint_signe(m[f][0]) for m in liste]
            if len(set(valeurs)) >= 3 and sum(v in ids for v in valeurs) >= 0.9 * len(valeurs):
                changements = sum(a != b for a, b in zip(valeurs, valeurs[1:]))
                candidats.append((changements, len(valeurs), nom, f))
    if not candidats:
        return None
    _, _, nom, f = max(candidats)
    return nom, f


def proposer(paquets_rejoues, pv_lus: list[tuple[float, int]]) -> dict:
    """paquets_rejoues : [(t, nom, valeur)] reçus du serveur ; pv_lus : [(t, PV lus)]."""
    messages: dict = {c: None for c in CLES}
    brouillon = {"version": "propose-" + time.strftime("%Y-%m-%d"), "messages": messages}
    decodes = _decoder(paquets_rejoues)
    cmb = _combattants(decodes)
    if cmb is None:
        return brouillon
    _, t_combat, nom, liste, ident, case, ids = cmb
    messages["combattants"] = {"nom": nom, "champs": {"liste": [liste], "id": [ident], "case": [case],
                                                       "monstre": None}}
    if pv_lus:
        pv = _pv_absolus(decodes, t_combat, pv_lus[0][1])
        if pv:
            messages["pv_absolus"] = {"nom": pv[0], "champs": {"courants": [pv[1]], "max": [pv[2]]}}
    dep = _deplacement(decodes, ids)
    if dep:
        messages["deplacement"] = {"nom": dep[0], "champs": {"chemin": [dep[1]],
                                                             "acteur": [dep[2]] if dep[2] else None}}
    if len(pv_lus) >= 2:
        d = _degats(decodes, ids, pv_lus)
        if d:
            nom_a, p, fm, fc, source = d
            vides = ("soin_cible", "soin_montant", "poussee_acteur", "poussee_arrivee", "mort_id",
                     "teleport_acteur", "teleport_case", "echange_case_lanceur", "echange_autre",
                     "echange_case_autre")
            messages["action"] = {"nom": nom_a, "champs": {"source": [source] if source else None,
                                                           "degats_montant": [p, fm], "degats_cible": [p, fc],
                                                           **{k: None for k in vides}}}
    exclus = {m["nom"] for m in messages.values() if m}
    tour = _debut_tour(decodes, ids, exclus)
    if tour:
        messages["debut_tour"] = {"nom": tour[0], "champs": {"acteur": [tour[1]]}}
    return brouillon


def ecrire(brouillon: dict, dossier: Path | None = None) -> Path:
    chemin = Path(dossier or dossier_reglages()) / "protocole-propose.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(brouillon, ensure_ascii=False, indent=1), "utf-8")
    return chemin


def lancer_depuis_application(application) -> None:
    """Petite fenêtre : enregistre les messages reçus, note les PV tapés, écrit le brouillon."""
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget

    enregistres: list = []
    lectures: list = []
    application.comptes.enregistreur = lambda cle, sens, nom, valeur, t: (
        sens == "recu" and enregistres.append((t, nom, valeur)))

    w = QWidget(None)
    w.setWindowTitle("Haretool — mode apprendre")
    v = QVBoxLayout(w)
    v.addWidget(QLabel("1. Lance un petit combat (un seul compte connecté).\n"
                       "2. Au début du combat, tape tes PV et clique « Noter ».\n"
                       "3. Prends quelques coups, puis note à nouveau tes PV.\n"
                       "4. Clique « Terminer » quand le combat est fini."))
    ligne = QHBoxLayout()
    pv = QSpinBox()
    pv.setRange(1, 100000)
    noter = QPushButton("Noter")
    etat = QLabel("0 lecture")
    ligne.addWidget(QLabel("PV maintenant :"))
    ligne.addWidget(pv)
    ligne.addWidget(noter)
    ligne.addWidget(etat)
    v.addLayout(ligne)
    finir = QPushButton("Terminer")
    v.addWidget(finir)

    def sur_noter():
        lectures.append((time.monotonic(), pv.value()))
        etat.setText(f"{len(lectures)} lecture(s)")

    def sur_finir():
        application.comptes.enregistreur = None
        chemin = ecrire(proposer(enregistres, lectures))
        w.close()
        QMessageBox.information(None, "Haretool", f"Brouillon écrit :\n{chemin}\n\n"
                                "Envoie-le au mainteneur pour mettre à jour le protocole.")

    noter.clicked.connect(sur_noter)
    finir.clicked.connect(sur_finir)
    w.show()
    application._fenetre_apprendre = w
