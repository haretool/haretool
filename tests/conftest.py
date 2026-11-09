"""Les tests ne vont jamais chercher le fichier de correspondance en ligne."""
import os

os.environ["HARETOOL_HORS_LIGNE"] = "1"
