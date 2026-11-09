"""Fabrique l'icône de l'exe (.ico, plusieurs tailles) à partir de la coiffe du Comte Harebourg."""
from pathlib import Path

from PIL import Image

ICONES = Path(__file__).resolve().parent.parent / "haretool" / "icones"
TAILLES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    coiffe = Image.open(ICONES / "coiffe.png").convert("RGBA")
    boite = coiffe.getbbox()
    if boite:
        coiffe = coiffe.crop(boite)
    cote = max(coiffe.size)
    carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    carre.paste(coiffe, ((cote - coiffe.width) // 2, (cote - coiffe.height) // 2))
    grande = carre.resize((256, 256), Image.LANCZOS)
    sortie = ICONES / "haretool.ico"
    grande.save(sortie, format="ICO", sizes=TAILLES)
    print(sortie)


if __name__ == "__main__":
    main()
