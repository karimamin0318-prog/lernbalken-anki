"""Tests fuer das Add-on, ohne Anki-Fenster, auf einer frischen Testsammlung.

Ausfuehren mit Ankis eigenem Python (dort ist das Paket `anki` installiert):

    "%LOCALAPPDATA%\\AnkiProgramFiles\\.venv\\Scripts\\python.exe" tests\\test_addon.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import types

import anki.collection  # zuerst laden, sonst stolpert anki.decks ueber einen Import-Kreis
from anki.collection import Collection

HIER = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(HIER, "..", "lernbalken_anki")

# Die Module ohne __init__.py laden (das braucht das Anki-Fenster)
_paket = types.ModuleType("lb")
_paket.__path__ = [ADDON]
sys.modules["lb"] = _paket


def _lade(name: str):
    spec = importlib.util.spec_from_file_location(f"lb.{name}", os.path.join(ADDON, f"{name}.py"))
    modul = importlib.util.module_from_spec(spec)
    sys.modules[f"lb.{name}"] = modul
    spec.loader.exec_module(modul)
    return modul


core = _lade("core")
colops = _lade("colops")
deckliste = _lade("deckliste")
wichtig = _lade("wichtig")
modus = _lade("modus")


def neue_sammlung(ordner: str, name: str) -> Collection:
    return Collection(os.path.join(ordner, name))


def karten(col, deck: str, anzahl: int, tag: str = "") -> list[int]:
    did = col.decks.id(deck)
    m = col.models.by_name("Basic")
    nids = []
    for i in range(anzahl):
        n = col.new_note(m)
        n["Front"], n["Back"] = f"{deck} {i}", "a"
        if tag:
            n.add_tag(tag)
        col.add_note(n, did)
        nids.append(n.id)
    return nids


def test_blocknamen():
    assert core.block_pfad("B-Lizenz", "LB1 B2 Gelenke & Knie") == (["B-Lizenz", "LB1", "B2 Gelenke & Knie"], "B2")
    assert core.block_pfad("Bio", "VO3+4 B1 Zelle") == (["Bio", "VO3+4", "B1 Zelle"], "B1")
    assert core.block_pfad("X", "B4 Nur Block") == (["X", "B4 Nur Block"], "B4")
    assert core.block_pfad("X", "Freier Name::mit") == (["X", "Freier Name:mit"], None)
    assert [colops._nummer(t) for t in ["B2", "B02 Titel", "Block 2: X", "B10 Y", "Beweglichkeit"]] == [2, 2, 2, 10, None]


def test_reihenfolge():
    assert core.ordne([(1, "B10"), (2, "B2"), (3, "B1")], []) == [3, 2, 1]
    assert core.ordne([(1, "B10"), (2, "B2"), (3, "⭐ Wichtig")], [1]) == [1, 3, 2]
    assert core.verschiebe([1, 2, 3, 4], 4, 2, "vor") == [1, 4, 2, 3]
    assert core.verschiebe([1, 2, 3, 4], 1, 3, "nach") == [2, 3, 1, 4]
    assert core.verschiebe([1, 2], 1, 9, "vor") == [1, 2]


def test_decks_aus_lernbalken(ordner):
    col = neue_sammlung(ordner, "decks.anki2")
    # Wie nach einem apkg-Import mit anderen Namen: B01 und B1 sind derselbe Block und werden umbenannt
    col.decks.id("B-Lizenz::LB1::B01 Alter Titel")
    daten = {"faecher": [{"name": "B-Lizenz", "bloecke": [{"name": "LB1 B1 Zelle"}, {"name": "LB1 B10 Nerven"}]}]}
    colops.sync_decks(col, daten)
    namen = {d.name for d in col.decks.all_names_and_ids()}
    assert "B-Lizenz::LB1::B1 Zelle" in namen and "B-Lizenz::LB1::B10 Nerven" in namen
    assert not any("Alter Titel" in n for n in namen)
    assert colops.sync_decks(col, daten) == []  # zweiter Lauf aendert nichts
    col.close()


def test_deckliste_sortieren_und_ausblenden(ordner):
    col = neue_sammlung(ordner, "liste.anki2")
    a, b, c = (col.decks.id(n) for n in ("Anatomie", "B-Lizenz", "Z) Archiv"))
    assert deckliste.befehl(col, f"lb_ordnen:0:{b}:{a}:vor")
    assert deckliste.befehl(col, f"lb_aus:{c}")
    baum, eltern, versteckt = deckliste.baum_anpassen(col.sched.deck_due_tree(), deckliste.lies(col))
    sichtbar = [k.name for k in baum.children]
    assert sichtbar.index("B-Lizenz") < sichtbar.index("Anatomie") and "Z) Archiv" not in sichtbar
    assert versteckt == [(c, "Z) Archiv")]
    assert deckliste.befehl(col, f"lb_ein:{c}")
    assert not deckliste.befehl(col, "lb_quatsch")
    col.close()


def test_eigene_zeiten(ordner):
    col = neue_sammlung(ordner, "zeiten.anki2")
    karten(col, "T", 6)
    col.decks.select(col.decks.id("T"))
    heute, jetzt = col.sched.today, int(time.time())
    for wahl, _, ease in modus.ZEITEN:
        c = col.sched.getCard()
        col.sched.answerCard(c, ease)
        modus.plane(col, c, wahl)
        c.load()
        if wahl in modus.SEKUNDEN:
            assert c.queue == 1 and abs(c.due - jetzt - modus.SEKUNDEN[wahl]) < 60, wahl
        else:
            assert c.queue == 2 and c.due - heute == int(modus.TAGE[wahl].rstrip("!")), wahl
    col.close()


def test_rueckgaengig_nimmt_antwort_und_zeit_zurueck(ordner):
    col = neue_sammlung(ordner, "undo.anki2")
    karten(col, "T", 1)
    col.decks.select(col.decks.id("T"))
    c = col.sched.getCard()
    col.sched.answerCard(c, 4)
    modus.plane(col, c, "3d")
    col.undo()
    c.load()
    assert (c.type, c.queue) == (0, 0), "nach einem Mal Rueckgaengig muss die Karte wieder neu sein"
    col.close()


def test_wichtig_deck_behaelt_eigene_zeit(ordner):
    col = neue_sammlung(ordner, "wichtig.anki2")
    nids = karten(col, "F::LB1::B1 X", 2, tag=wichtig.TAG)
    aktuell = col.decks.get_current_id()
    w = wichtig.deck_id(col, "F", erzeugen=True)
    assert col.decks.get_current_id() == aktuell, "Anlegen darf das aktuelle Deck nicht wechseln"
    assert wichtig.anzahl(col, "F") == 2 and wichtig.fuellen(col, w) == 2
    col.decks.select(w)
    c = col.sched.getCard()
    col.sched.answerCard(c, 3)
    modus.plane(col, c, "3h")
    soll = int(time.time()) + modus.SEKUNDEN["3h"]
    wichtig.leeren_alle(col)  # passiert beim Zurueck zur Deckliste
    c.load()
    # Ohne den Fix setzt Anki beim Leeren seine eigene Lernstufe ein (z. B. 12 Minuten statt 3 Stunden)
    assert c.queue == 1 and c.odid == 0 and abs(c.due - soll) < 60, "die gewaehlte Zeit muss das Leeren ueberstehen"
    home = col.decks.id_for_name("F::LB1::B1 X")
    assert col.db.scalar("select count() from cards where did = ?", home) == 2
    col.close()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    with tempfile.TemporaryDirectory() as ordner:
        for name, f in tests:
            f(ordner) if f.__code__.co_argcount else f()
            print(f"ok  {name}")
    print(f"{len(tests)} Tests in Ordnung")
