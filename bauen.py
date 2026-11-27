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

# Gemini-/Claude-Skill: Ordner anki-lernbalken-fragen mit SKILL.md (Anleitung aus baue_deck.py) + baue_deck.py, als ZIP
import ast
import re

SKILL = "anki-lernbalken-fragen"
SKRIPT = os.path.join(HIER, "fragen-erstellen", "baue_deck.py")
with open(SKRIPT, encoding="utf-8") as f:
    code = f.read()
anleitung = ast.get_docstring(ast.parse(code)).strip()
erster_absatz = re.compile(r"^Diese eine Datei ist Anleitung und Werkzeug zugleich:.*?Du bekommst sie zusammen mit Lernunterlagen", re.S | re.M)
assert erster_absatz.search(anleitung), "Einleitung in baue_deck.py geaendert: bauen.py anpassen"
anleitung = erster_absatz.sub("Zu diesem Skill gehoert das Python-Skript `baue_deck.py` (liegt im Skill-Ordner). Du bekommst Lernunterlagen", anleitung)
anleitung = anleitung.replace("nur mit dieser Datei bauen (unverändert als `baue_deck.py` speichern und ausführen,",
                              "nur mit `baue_deck.py` aus diesem Skill bauen (unverändert ausführen,")
kopf = ("---\nname: " + SKILL + "\ndescription: Erstellt aus Lernunterlagen (Skript, Folien, PDF) Anki-Fragen "
        "(Single Choice, Multiple Choice, Flashcards) als .apkg-Datei fuer das Anki-Add-on Lernbalken. Verwenden, wenn "
        "Anki-Fragen, Karteikarten oder Multiple-Choice-Fragen zu Unterlagen gewuenscht sind.\n---\n\n")
ZIP = os.path.join(HIER, "dist", SKILL + ".zip")
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(SKILL + "/SKILL.md", kopf + anleitung + "\n")
    z.writestr(SKILL + "/baue_deck.py", code)
print(ZIP)
