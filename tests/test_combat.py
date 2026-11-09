from haretool.combat import EtatCompte
from haretool.protocole import Protocole, EMBARQUE
from haretool.grille import vers_case

from pb import msg, Empaquete

COMTE = 9999


def proto(notre_tour=True, monstre=True):
    import json
    d = json.loads(EMBARQUE.read_text("utf-8"))
    if notre_tour:
        d["messages"]["notre_tour"] = {"nom": "zzt", "champs": {}}
    if monstre:
        d["messages"]["combattants"]["champs"]["monstre"] = [7]
    d["messages"]["carte_courante"] = {"nom": "zzc", "champs": {"carte": [1]}}
    d["messages"]["fiche"] = {"nom": "zzf", "champs": {"id": [1, 1], "monstre": [1, 3, 9], "nom": [1, 3, 4]}}
    return Protocole(d)


MOI = 42
A = vers_case(16, 4)          # ma case
CONTACT = vers_case(17, 4)    # au contact
LOIN = vers_case(20, 4)


def etat(**k):
    return EtatCompte(proto(**k), est_harebourg=lambda m: m == COMTE)


def placement(e, t=0.0, pv=(3000, 4000)):
    e.appliquer("kqo", msg({3: pv[0], 1: pv[1]}), t)
    e.appliquer("kjl", msg({2: [{2: MOI, 3: A}, {2: -1, 3: CONTACT, 7: COMTE}, {2: -2, 3: LOIN, 7: 31}]}), t)


def mon_debut(e, t):
    e.appliquer("jvj", msg({3: MOI}), t)
    e.appliquer("zzt", b"", t + 0.01)


def coup(source, cible, montant):
    return msg({36: source, 37: {6: montant, 5: cible}})


def test_placement():
    e = etat()
    placement(e)
    assert e.en_combat and e.pv == 3000 and e.pv_max == 4000
    assert e.positions == {MOI: A, -1: CONTACT, -2: LOIN}
    assert e.monstres == {-1: COMTE, -2: 31} and e.harebourg_present


def test_moi_par_debut_de_tour_puis_notre_tour():
    e = etat()
    placement(e)
    e.appliquer("jvj", msg({3: -1}), 1.0)          # tour d'un monstre : pas de notre_tour
    assert e.moi is None
    mon_debut(e, 2.0)
    assert e.moi == MOI and e.pv_debut_tour == 3000 and e.mon_tour


def test_notre_tour_apres_un_autre_debut_ignore():
    e = etat()
    placement(e)
    e.appliquer("jvj", msg({3: MOI}), 1.0)
    e.appliquer("jvj", msg({3: -1}), 1.0)
    e.appliquer("zzt", b"", 1.0)          # suit le début de -1 : ne désigne PERSONNE
    assert e.moi is None


def test_messages_groupes_meme_heure():
    # Les messages arrivent par paquets (même heure) : seul l'ORDRE compte.
    e = etat()
    placement(e)
    e.appliquer("jvj", msg({3: MOI}), 5.0)
    e.appliquer("zzt", b"", 5.0)
    e.appliquer("jvj", msg({3: -1}), 5.0)
    assert e.moi == MOI and not e.mon_tour


def test_un_seul_notre_tour_par_debut():
    e = etat()
    placement(e)
    mon_debut(e, 1)
    e.appliquer("jsq", coup(MOI, -1, 100), 1.1)
    e.appliquer("zzt", b"", 1.2)          # doublon : ne remet pas la mêlée à zéro
    assert e.lignes_melee == 1


def test_degats_et_soins():
    e = etat()
    placement(e)
    mon_debut(e, 1)
    e.appliquer("jsq", coup(-1, MOI, 500), 2)
    assert e.pv == 2500
    e.appliquer("jsq", msg({36: MOI, 39: {2: MOI, 4: 9000}}), 3)
    assert e.pv == 4000                              # plafonné au max
    assert e.pv_debut_tour == 3000                   # la tranche ne bouge pas en cours de tour


def test_poison_hors_de_mon_tour_ne_change_pas_pv_debut_tour():
    e = etat()
    placement(e)
    mon_debut(e, 1)
    e.appliquer("jvj", msg({3: -1}), 5)
    e.appliquer("jsq", coup(-1, MOI, 1000), 6)
    assert e.pv_debut_tour == 3000 and e.pv == 2000
    mon_debut(e, 9)
    assert e.pv_debut_tour == 2000


def test_melee_comptee_pendant_mon_tour_seulement():
    e = etat()
    placement(e)
    mon_debut(e, 1)
    e.appliquer("jsq", coup(MOI, -1, 100), 2)        # au contact
    e.appliquer("jsq", coup(MOI, -2, 100), 2.1)      # à distance
    assert e.lignes_melee == 1
    e.appliquer("jug", msg({2: MOI}), 3)
    e.appliquer("jsq", coup(MOI, -1, 100), 3.5)      # hors de mon tour
    assert e.lignes_melee == 1
    mon_debut(e, 9)
    assert e.lignes_melee == 0


def test_deplacement_poussee_mort():
    e = etat()
    placement(e)
    chemin = Empaquete([A, vers_case(16, 5), vers_case(16, 6)])
    e.appliquer("jnz", msg({1: chemin, 4: MOI}), 1)
    assert e.positions[MOI] == vers_case(16, 6)
    e.appliquer("jsq", msg({36: MOI, 5: {1: -2, 3: vers_case(21, 4)}}), 2)
    assert e.positions[-2] == vers_case(21, 4)
    e.appliquer("jsq", msg({36: MOI, 3: {2: -2}}), 3)
    assert -2 not in e.positions and -2 in e.morts


def test_deplacement_hors_combat_ignore():
    e = etat()
    e.appliquer("jnz", msg({1: Empaquete([1, 15]), 4: MOI}), 0)
    assert e.positions == {}


def test_fin_combat_remet_a_zero():
    e = etat()
    e.appliquer("zzc", msg({1: 123456}), 0)
    placement(e)
    e.appliquer("zzf", fiche(MOI, nom=b"Perso"), 0)
    mon_debut(e, 1)
    e.appliquer("jwp", b"", 5)
    assert not e.en_combat and e.positions == {} and e.pv_debut_tour is None and e.pv is None
    assert e.moi == MOI and e.carte == 123456 and e.nom_perso == "Perso"
    assert not e.harebourg_present


def fiche(ident, monstre=None, nom=None):
    detail = {}
    if monstre is not None:
        detail[9] = monstre
    if nom is not None:
        detail[4] = nom
    return msg({1: {1: ident, 3: detail}})


def test_fiche_donne_le_monstre_et_le_comte():
    e = etat(monstre=False)
    e.appliquer("kjl", msg({2: [{2: MOI, 3: A}, {2: -1, 3: CONTACT}]}), 0)
    assert not e.harebourg_present
    e.appliquer("zzf", fiche(-1, monstre=COMTE), 0)
    assert e.monstres == {-1: COMTE} and e.harebourg_present


def test_nom_du_perso_connu_des_que_moi_l_est():
    e = etat()
    placement(e)
    e.appliquer("zzf", fiche(MOI, nom=b"Perso1"), 0)
    assert e.nom_perso is None
    mon_debut(e, 1)
    assert e.nom_perso == "Perso1"


def test_fiche_d_un_joueur_n_est_pas_un_monstre():
    e = etat()
    e.appliquer("zzf", fiche(MOI, monstre=COMTE), 0)
    assert e.monstres == {} and not e.harebourg_present


def test_harebourg_reste_present_apres_sa_mort():
    e = etat()
    placement(e)
    e.appliquer("jsq", msg({36: MOI, 3: {2: -1}}), 3)
    assert e.harebourg_present


def test_etat_sans_pv_absolus_ne_dessine_rien():
    e = etat()
    e.appliquer("kjl", msg({2: [{2: MOI, 3: A}, {2: -1, 3: CONTACT, 7: COMTE}]}), 0)
    mon_debut(e, 1)
    assert e.pv_debut_tour is None


def test_protocole_inconnu_signale():
    e = etat()
    for i in range(199):
        e.appliquer("inconnu", b"", i)
    assert e.protocole_ok
    e.appliquer("inconnu", b"", 200)
    assert not e.protocole_ok
    e.appliquer("jnz", msg({1: Empaquete([1]), 4: MOI}), 201)
    assert e.protocole_ok


def test_message_abime_ne_plante_pas():
    e = etat()
    placement(e)
    e.appliquer("jsq", b"\x12\x05ab", 1)
    e.appliquer("kqo", b"\xff", 1)
    assert e.pv == 3000


def test_pv_actuels_absents_gardent_les_derniers():
    """Songe : le maximum érodé fait foi, et un message sans PV actuels (le jeu en
    envoie) ne veut pas dire 0 PV."""
    e = etat()
    placement(e)
    def iib(courants, maxi):
        corps = {3: maxi} if courants is None else {1: courants, 3: maxi}
        e.appliquer("iib", msg({1: 171125, 3: corps, 4: MOI}), 0)
    iib(3000, 3300)
    iib(2500, 3200)          # érosion
    iib(None, 3100)          # PV actuels absents
    assert e.pv_par_id[MOI] == (2500, 3100)


def test_coup_a_zero_degat_au_contact_compte():
    """Le jeu envoie la ligne sans montant quand le coup fait 0 : elle fait quand même tourner."""
    e = etat()
    placement(e)
    mon_debut(e, 1.0)
    e.appliquer("jsq", msg({36: MOI, 37: {5: -1, 4: 3}}), 1.1)      # au contact, 0 dégât
    assert e.lignes_melee == 1
