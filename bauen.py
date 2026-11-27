"""Baut lernbalken.ankiaddon (die Download-Datei fuer Anki, Windows und Mac).

Aufruf: python bauen.py   -> legt dist/lernbalken.ankiaddon an.
Packt den Inhalt von lernbalken_anki/ ohne meta.json (persoenliche Einstellungen)
und ohne __pycache__. Pfade mit "/", damit die Datei auch auf dem Mac stimmt.
"""
import os
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
QUELLE = os.path.join(HIER, "lernbalken_anki")
ZIEL = os.path.join(HIER, "dist", "lernbalken.ankiaddon")

os.makedirs(os.path.dirname(ZIEL), exist_ok=True)
with zipfile.ZipFile(ZIEL, "w", zipfile.ZIP_DEFLATED) as z:
    for ordner, unter, dateien in os.walk(QUELLE):
        unter[:] = [u for u in unter if u != "__pycache__"]
        for d in sorted(dateien):
            if d == "meta.json" or d.endswith(".pyc"):
                continue
            pfad = os.path.join(ordner, d)
            z.write(pfad, os.path.relpath(pfad, QUELLE).replace(os.sep, "/"))
print(ZIEL)
