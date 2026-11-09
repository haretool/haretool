# Haretool

Aide visuelle pour le combat contre le **Comte Harebourg** (Dofus 3), en donjon comme en Songes.

Quand le Comte est dans le combat, ses confusions font dévier tes sorts d'un quart, d'un demi
ou de trois quarts de tour. Haretool dessine directement sur la carte, pour chaque monstre,
**la case où cliquer** pour le toucher.

- Chaque monstre a sa couleur : un losange sous lui, le même losange et une **épée** sur la case
  à cliquer.
- La confusion est celle que le jeu applique à ton perso au début de chaque tour (repli : tes PV
  de début de tour, maximum érodé compris, d'après le tableau des tranches).
- Chaque ligne de dégâts portée au contact décale la case à viser d'un quart dans le sens
  inverse des aiguilles d'une montre : le dessin suit tout de suite.
- Case à cliquer hors de la carte ou injouable : icône **interdit** rouge sur le monstre.
- Case à cliquer hors de ta ligne de vue : petit **œil barré**.
- Monstre mort : plus aucun dessin.
- Plusieurs comptes : chaque fenêtre du jeu a son propre dessin, avec ses propres PV.

## Installation

1. Télécharge `Haretool.exe` (un seul fichier, rien à installer).
2. Lance-le. Windows demande les droits **administrateur** : accepte (voir plus bas pourquoi).
3. Une icône orange apparaît près de l'horloge. Clic dessus = réglages.

Rien à calibrer : la grille se cale toute seule sur la fenêtre du jeu, quelle que soit sa taille.
Si le dessin est un peu décalé, les flèches **Réglage fin** des réglages le corrigent (retenu pour
cette taille de fenêtre).

## Comment ça marche, et pourquoi l'administrateur

Haretool **ne touche pas au jeu** : aucune lecture de sa mémoire, aucun fichier ajouté au jeu,
aucun clic ni aucun envoi à ta place. Il lit seulement, avec l'outil de capture réseau intégré à
Windows (`pktmon`), les messages que le serveur envoie déjà au jeu (PV, positions, tours). Cet
outil Windows demande les droits administrateur. À la fermeture, la capture est arrêtée ; si
Haretool a été fermé de force, elle est nettoyée au lancement suivant.

Le dessin est une fenêtre transparente posée par-dessus le jeu : la souris passe à travers.

## Après une mise à jour du jeu

Les noms des messages du jeu changent à chaque mise à jour. Haretool vérifie au lancement un
fichier de correspondance en ligne : il est réparé pour tout le monde dès qu'il est mis à jour,
sans retélécharger l'exe. Si les réglages affichent **« protocole à mettre à jour »**, le dessin
reste caché en attendant (le **mode apprendre** des réglages aide le mainteneur à le refaire).

## Antivirus

Les petits outils non signés sont parfois signalés à tort. Vérifie l'empreinte du fichier
téléchargé avec celle publiée :

```
certutil -hashfile Haretool.exe SHA256
```


## Règles du jeu

Haretool est un outil tiers. Même sans toucher au jeu, lire son trafic reste contraire aux
conditions d'utilisation d'Ankama. **Tu l'utilises à tes risques.**

## Crédits

- Police Outfit, The Outfit Project Authors, licence SIL Open Font License 1.1.
- Icône : la Coiffe du Comte Harebourg, image tirée du jeu Dofus, propriété d'Ankama.

## Construire soi-même

Python 3.12, puis :

```
pip install PySide6 nuitka zstandard pytest
powershell -ExecutionPolicy Bypass -File compiler.ps1
```

`compiler.ps1` fabrique le livrable : le code est compilé en code machine (Nuitka), sans bytecode
Python à décompiler. `construire.ps1` (PyInstaller) reste pour un exe d'essai rapide.

`outils/extraire_donnees.py` (UnityPy) régénère les données embarquées depuis un jeu installé.
