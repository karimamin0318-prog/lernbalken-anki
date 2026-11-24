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
extras = _lade("extras")
auswahl = _lade("auswahl")


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
    assert core.ordne([(1, "B10"), (2, "B2"), (3, "⭐ Important")], [1]) == [1, 3, 2]
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


def test_wichtig_deck_umbenennen(ordner):
    col = neue_sammlung(ordner, "umbenennen.anki2")
    karten(col, "F::B1", 2, tag=wichtig.TAG)
    karten(col, "G::B1", 1, tag=wichtig.TAG)
    alt_f = wichtig.deck_id(col, "F", erzeugen=True)
    col.decks.rename(alt_f, "F::" + wichtig.ALTER_NAME)      # Stand bis 1.7.1
    alt_g = wichtig.deck_id(col, "G", erzeugen=True)
    col.decks.rename(alt_g, "G::" + wichtig.ALTER_NAME)
    neu_g = wichtig.deck_id(col, "G", erzeugen=True)           # bei G gibt es das neue schon
    wichtig.fuellen(col, alt_g)
    assert wichtig.umbenennen(col) == 2
    namen = {d.name for d in col.decks.all_names_and_ids()}
    assert "F::⭐ Important" in namen and "G::⭐ Important" in namen and not any("Wichtig" in n for n in namen)
    assert wichtig.deck_id(col, "F") == alt_f, "umbenannt, nicht neu angelegt (Id und Sortierung bleiben)"
    assert wichtig.deck_id(col, "G") == neu_g
    assert col.db.scalar("select count() from cards where did = ?", col.decks.id_for_name("G::B1")) == 1
    assert wichtig.umbenennen(col) == 0
    col.close()


def test_bild_in_notiz():
    feld = 'Text<div><img src="herz%20bild.png" width="300" style="border: 1px solid red"></div>danach<img src="x.png">'
    frei = extras.bild_setzen(feld, "herz bild.png", {"left": "12.5%", "top": "40px", "width": "30%"})
    assert frei == ('Textdanach<img src="x.png"><img src="herz%20bild.png" data-lb-frei="1" '
                    'style="border: 1px solid red; position: absolute; left: 12.5%; top: 40px; width: 30%; height: auto;">')
    groesse = extras.bild_setzen(frei, "herz%20bild.png", {"width": "90px"})
    assert 'width: 90px' in groesse and "data-lb-frei" not in groesse and "position" not in groesse
    zurueck = extras.bild_setzen(frei, "herz bild.png", None)
    assert zurueck == 'Textdanach<img src="x.png"><img src="herz%20bild.png" style="border: 1px solid red;">'
    assert extras.bild_setzen(feld, "anderes.png", None) == feld
    daneben = extras.bild_setzen(feld, "herz bild.png", {"left": "-35.5%", "top": "0px", "width": "30%"})
    assert "left: -35.5%" in daneben, "links neben dem Feld (negativ) muss erlaubt sein"
    for boese in ({"width": "1px; background:url(x)"}, {"width": 90}, {"left": "1%", "top": "2em", "width": "3%"}):
        try:
            extras.bild_setzen(feld, "herz bild.png", boese)
            raise AssertionError(f"haette abgelehnt werden muessen: {boese}")
        except ValueError:
            pass


def test_bildaenderung_eigener_undo_schritt(ordner):
    col = neue_sammlung(ordner, "bildundo.anki2")
    nid = karten(col, "T", 1)[0]
    n = col.get_note(nid)
    n["Front"] = 'A<img src="b.png">'
    col.update_note(n)                       # wie das Speichern aus dem Editor
    for links in ("10%", "20%"):            # zwei Bildaenderungen im Lernfenster
        n = col.get_note(nid)
        n["Front"] = extras.bild_setzen(n["Front"], "b.png", {"left": links, "top": "0px", "width": "30%"})
        extras.notiz_speichern(col, n, "Move image")
    col.undo()
    assert "left: 10%" in col.get_note(nid)["Front"], "Undo darf nur die letzte Bildaenderung zuruecknehmen"
    col.undo()
    assert col.get_note(nid)["Front"] == 'A<img src="b.png">', "zweites Undo: Bild wieder wie aus dem Editor"
    col.close()


def test_undo_mehrere_schritte(ordner):
    """Wie der Undo-Knopf: A und B beantwortet, C steht als Frage da, dann viermal Undo."""
    col = neue_sammlung(ordner, "undoknopf.anki2")
    karten(col, "T", 3)
    col.decks.select(col.decks.id("T"))
    antwort_name = None
    for _ in range(2):                                   # A und B: aufdecken, dann "Tomorrow"
        c = col.sched.getCard()
        col.sched.answerCard(c, 3)
        modus.plane(col, c, "1d")
        antwort_name = col.undo_status().undo           # merkt sich das Add-on nach jeder Antwort

    def art(ansicht, gezeigt, karte):
        st = col.undo_status()
        return extras.undo_art(ansicht, st.last_step, gezeigt, karte, st.undo, antwort_name)

    c_id = col.sched.getCard().id
    # 1. Undo auf der Frage von C: Antwort von B zuruecknehmen
    assert art("question", (None, None), c_id) == "antwort"
    col.undo()
    b = col.sched.getCard().id                           # Anki zeigt die zurueckgeholte Karte als Naechstes
    gezeigt = (col.undo_status().last_step, b)            # ... das Add-on deckt sie gleich auf
    # 2. Undo auf der Rueckseite von B: zurueck zur Frage von B
    assert art("answer", gezeigt, b) == "frage"
    # 3. Undo auf der Frage von B: Antwort von A zuruecknehmen. Frueher kam hier ein normales Undo und A als Frage,
    #    weil Anki nach jedem Undo neue Schrittnummern vergibt.
    assert art("question", (None, None), b) == "antwort"
    col.undo()
    a = col.sched.getCard().id
    assert a != b
    # 4. Nichts mehr beantwortet: normales Undo (hier gibt es nichts mehr)
    assert art("question", (None, None), a) == "anki"
    # Stern nach dem Aufdecken gesetzt: Undo nimmt zuerst den Stern zurueck, nicht die Rueckseite
    gezeigt = (col.undo_status().last_step, a)
    n = col.get_card(a).note()
    n.add_tag("marked")
    col.update_note(n)
    assert art("answer", gezeigt, a) == "anki"
    col.undo()
    assert art("answer", gezeigt, a) != "antwort"
    col.close()


def test_redo_knopf():
    B, A, C = 2, 1, 3
    assert extras.redo_art([], "question", C, False) is None, "ohne Undo grau"
    assert extras.redo_art([], "question", C, True) == "anki", "nach Strg+Z geht Redo auch"
    # Auf der Frage von C: Undo (Antwort B zurueck), Undo (B zur Frage), Undo (Antwort A zurueck)
    stapel = [("anki", None), ("frage", B), ("anki", None)]
    assert extras.redo_art(stapel, "answer", A, True) == "anki", "1. Redo: Antwort von A wieder"
    stapel.pop()
    assert extras.redo_art(stapel, "question", B, True) == "frage", "2. Redo: Rueckseite von B wieder"
    assert extras.redo_art(stapel, "answer", A, True) == "anki", "andere Karte: Rueckseite passt nicht, Ankis Redo"
    stapel.pop()
    assert extras.redo_art(stapel, "answer", B, True) == "anki", "3. Redo: Antwort von B wieder"
    assert extras.redo_art([("frage", B)], "question", B, False) == "frage", "Rueckseite braucht kein Anki-Redo"
    assert extras.redo_art([("anki", None)], "question", B, False) is None, "Neues gemacht: Anki-Redo weg, grau"


def test_stern_undo_nimmt_neues_wichtig_deck_mit(ordner):
    """Erster Stern im Fach legt das Important-Deck an. Ein Undo nimmt Stern und Deck zurueck, nicht nur das Deck."""
    col = neue_sammlung(ordner, "sternundo.anki2")
    nid = karten(col, "F::B1", 1)[0]
    lernen = col.decks.id("F::B1")
    col.decks.select(lernen)
    n = col.get_note(nid)
    n.add_tag(wichtig.TAG)
    col.update_note(n)                                   # wie der Stern (Ankis Markieren)
    wichtig.deck_id(col, "F", erzeugen=True)              # macht das Add-on gleich danach
    assert col.undo_status().undo == "Update Note"
    col.undo()
    assert not col.get_note(nid).has_tag(wichtig.TAG) and not wichtig.deck_id(col, "F")
    assert col.decks.get_current_id() == lernen, "Undo darf nicht ins Important-Deck wechseln"
    col.close()


def test_vokabeln(ordner):
    col = neue_sammlung(ordner, "vok.anki2")
    assert extras.vokabel_speichern(col, "  ", "x") is None
    a = extras.vokabel_speichern(col, "Meniskus", "Knorpelscheibe im Knie", "B-Lizenz › LB1")
    b = extras.vokabel_speichern(col, "adduktion", "Heranfuehren")
    assert a["id"] != b["id"]
    assert [v["wort"] for v in extras.vokabeln(col)] == ["adduktion", "Meniskus"]
    extras.vokabel_speichern(col, "Adduktion", "Heranführen zur Körpermitte", vid=b["id"])
    assert len(extras.vokabeln(col)) == 2 and extras.vokabeln(col)[0]["erklaerung"].startswith("Heranführen zur")
    extras.vokabel_loeschen(col, a["id"])
    assert [v["wort"] for v in extras.vokabeln(col)] == ["Adduktion"]
    col.close()


def test_abdeckung(ordner):
    col = neue_sammlung(ordner, "abdeck.anki2")
    extras.abdeckung_setzen(col, 5, [[{"t": "Knie", "n": 0}, {"t": "Huefte", "n": 1}], [{"t": " ", "n": 0}], []])
    assert extras.abdeckung(col, 5) == [[{"t": "Knie", "n": 0}, {"t": "Huefte", "n": 1}]]
    assert extras.abdeckung(col, 6) == []
    extras.abdeckung_setzen(col, 5, [])
    assert col.get_config(extras.ABDECKUNG) == {}
    col.close()


def test_total(ordner):
    col = neue_sammlung(ordner, "total.anki2")
    karten(col, "F::LB1::B1", 3, tag=wichtig.TAG)
    karten(col, "F::LB1::B2", 2)
    karten(col, "G", 1)
    w = wichtig.deck_id(col, "F", erzeugen=True)
    wichtig.fuellen(col, w)  # auch wenn die markierten gerade im Wichtig-Deck liegen, zaehlen sie zu B1
    t = extras.totale(col.decks.deck_tree(), extras.karten_pro_deck(col), lambda k: 99)
    i = col.decks.id_for_name
    assert (t[i("F")], t[i("F::LB1")], t[i("F::LB1::B1")], t[i("F::LB1::B2")], t[i("G")], t[w]) == (5, 5, 3, 2, 1, 99)
    col.close()


def test_balken_hell_und_kraeftig(ordner):
    # Rechnung: neu und heute faellig = noch zu tun, am Lernen = hell, spaeter faellig = fuer heute erledigt
    assert core.karten_stand(0, 0, 1, 100) == "leer"
    assert core.karten_stand(1, 1, 0, 100) == "offen"
    assert core.karten_stand(1, 3, 101, 100) == "fest", "Lernschritt erst morgen: fuer heute erledigt"
    assert core.karten_stand(3, 3, 100, 100) == "offen", "Lernschritt heute faellig: noch in Arbeit"
    assert core.karten_stand(2, 2, 100, 100) == "leer"
    assert core.karten_stand(2, 2, 101, 100) == "fest"
    assert core.karten_stand(2, -1, 101, 100) is None
    assert core.anteile([]) == (0.0, 0.0, 0)
    # In der Sammlung, 4 Karten: 5 min -> hell, Tomorrow -> kraeftig (eine ganze Karte), heute faellig -> leer
    col = neue_sammlung(ordner, "hell.anki2")
    karten(col, "T", 4)
    did = col.decks.id("T")
    col.decks.select(did)
    c = col.sched.getCard()
    col.sched.answerCard(c, 1)
    modus.plane(col, c, "5m")
    assert colops.deck_fortschritt(col, did) == (0.0, 25.0, 4)
    modus.plane(col, c, "1d")
    assert colops.deck_fortschritt(col, did) == (25.0, 0.0, 4), "Tomorrow: aus hell wird gleich viel kraeftig"
    d = col.sched.getCard()
    col.sched.set_due_date([d.id], "0")   # Wiederholung, heute faellig: noch zu tun
    assert colops.deck_fortschritt(col, did) == (25.0, 0.0, 4)
    modus.plane(col, d, "fertig")
    assert colops.balken_daten(col, did)["pct"] == 50.0
    col.close()


def _mc_karten(col, deck: str, anzahl: int) -> None:
    # Den MC-Kartentyp bringt sonst der Import mit; hier reicht eine Kopie von Basic mit dem Namen
    if not col.models.by_name(colops.MC_NAME):
        m = col.models.copy(col.models.by_name("Basic"), add=False)
        m["name"] = colops.MC_NAME
        col.models.add_dict(m)
    m, did = col.models.by_name(colops.MC_NAME), col.decks.id(deck)
    for i in range(anzahl):
        n = col.new_note(m)
        n[n.keys()[0]] = f"MC {deck} {i}"
        col.add_note(n, did)


def _antworten(col, q) -> int:
    """Wie das Lernfenster: Karte oben aus q, vorher Ankis Warteschlange freigeben."""
    from anki.scheduler.v3 import CardAnswer
    e = q.cards[0]
    c = col.get_card(e.card.id)
    c.start_timer()
    schritt = auswahl.frei(col, c)
    col.sched.answer_card(col.sched.build_answer(card=c, states=e.states, rating=CardAnswer.GOOD))
    col.merge_undo_entries(schritt)
    return c.id


def test_nur_neu_speedrun_ohne_tageslimit(ordner):
    col = neue_sammlung(ordner, "neu.anki2")
    karten(col, "F::B1", 6)
    _mc_karten(col, "F::B2", 3)
    did = col.decks.id("F")
    col.decks.select(did)
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 2
    col.decks.save(conf)
    gesehen = []
    while (q := auswahl.naechste(col, did, neu=True, mc=False)) is not None:
        assert q.cards[0].queue == q.NEW
        gesehen.append(_antworten(col, q))
        assert len(gesehen) <= 9, "jede Karte nur einmal"
    assert len(set(gesehen)) == 9, "alle neuen Karten, ueber das Tageslimit von 2 hinaus"
    col.close()


def test_nur_mc(ordner):
    col = neue_sammlung(ordner, "mc.anki2")
    karten(col, "F::B1", 4)
    _mc_karten(col, "F::B1", 3)
    did = col.decks.id("F")
    col.decks.select(did)
    mc_n = auswahl._mc_notizen(col)
    # Nur MC und nur neu
    q = auswahl.naechste(col, did, neu=True, mc=True)
    assert q.new_count == 3 and q.cards[0].card.note_id in mc_n
    # Nur MC mit Ankis Planung: Flashcards kommen nicht, auch wenn sie oben in Ankis Warteschlange liegen
    gesehen = []
    while (q := auswahl.naechste(col, did, neu=False, mc=True)) is not None and len(gesehen) < 20:
        assert q.cards[0].card.note_id in mc_n
        gesehen.append(_antworten(col, q))
    assert len(gesehen) >= 3
    col.close()


def test_filter_zurueckgenommene_karte_kommt_zuerst(ordner):
    col = neue_sammlung(ordner, "filter_undo.anki2")
    _mc_karten(col, "F", 4)
    did = col.decks.id("F")
    col.decks.select(did)
    for neu in (True, False):
        _antworten(col, auswahl.naechste(col, did, neu=neu, mc=True))
        zweite = _antworten(col, auswahl.naechste(col, did, neu=neu, mc=True))
        col.undo()
        assert auswahl.naechste(col, did, neu=neu, mc=True, zuerst=zweite).cards[0].card.id == zweite
    col.close()


def test_nur_mc_neue_trotz_flashcards_im_limit(ordner):
    # Vorne 25 neue Flashcards, Tageslimit 20: die neuen Plaetze muessen trotzdem an MC-Fragen gehen
    col = neue_sammlung(ordner, "mc_limit.anki2")
    karten(col, "F", 25)
    _mc_karten(col, "F", 5)
    did = col.decks.id("F")
    col.decks.select(did)
    mc_n = auswahl._mc_notizen(col)
    gesehen = []
    while (q := auswahl.naechste(col, did, neu=False, mc=True)) is not None and len(gesehen) < 20:
        assert q.cards[0].card.note_id in mc_n
        if q.cards[0].queue == q.NEW:
            gesehen.append(_antworten(col, q))
        else:
            break   # Lernkarte auf "spaeter heute": genug gesehen
    assert len(set(gesehen)) == 5, gesehen
    col.close()


def test_undo_karte_auch_nach_ankis_rueckgaengig(ordner):
    col = neue_sammlung(ordner, "undo_revlog.anki2")
    _mc_karten(col, "F", 4)
    did = col.decks.id("F")
    col.decks.select(did)
    a = _antworten(col, auswahl.naechste(col, did, neu=True, mc=True))
    _antworten(col, auswahl.naechste(col, did, neu=True, mc=True))   # B
    col.undo()                                                       # Strg+Z: B zurueck
    c = _antworten(col, auswahl.naechste(col, did, neu=True, mc=True))
    assert extras.zuletzt_beantwortet(col) == c
    col.undo()                                                       # Undo-Knopf: C zurueck
    assert extras.zuletzt_beantwortet(col) == a, "naechstes Undo nimmt A zurueck, nicht B"
    col.close()

def test_filter_behaelt_undo_liste_und_redo(ordner):
    """Mit Filter loeschte frei() frueher bei jeder Antwort Ankis ganze Undo-Liste: Undo ging nur einen Schritt."""
    col = neue_sammlung(ordner, "filter_tief.anki2")
    _mc_karten(col, "F", 30)
    did = col.decks.id("F")
    col.decks.select(did)
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 2                       # Speedrun geht ueber das Tageslimit hinaus
    col.decks.save(conf)
    antwort_name = None
    ids = []
    for _ in range(25):
        ids.append(_antworten(col, auswahl.naechste(col, did, neu=True, mc=True)))
        antwort_name = col.undo_status().undo
    assert antwort_name == col.tr.actions_answer_card(), "gleicher Name wie Antworten ohne Filter"
    for i in range(25):
        assert col.undo_status().undo == antwort_name, f"Undo Nr. {i + 1} ist keine Antwort mehr"
        assert extras.zuletzt_beantwortet(col) == ids[-1 - i]
        col.undo()
    assert extras.zuletzt_beantwortet(col) is None
    # Redo: Antworten kommen in derselben Reihenfolge wieder
    for i in range(3):
        assert col.undo_status().redo == antwort_name
        col.redo()
        assert extras.zuletzt_beantwortet(col) == ids[i]
    col.close()


def test_balken_folgt_den_filtern(ordner):
    # 4 Flashcards + 2 MC-Fragen, eine Flashcard schon vor dem Speedrun gesehen
    col = neue_sammlung(ordner, "balken_filter.anki2")
    karten(col, "F", 4)
    _mc_karten(col, "F", 2)
    did = col.decks.id("F")
    col.decks.select(did)
    vorher = _antworten(col, auswahl.naechste(col, did, neu=True, mc=False))
    modus.plane(col, col.get_card(vorher), "1d")
    seit = int(time.time() * 1000) + 1
    time.sleep(0.01)
    # Ohne Filter: 1 von 6 fuer heute erledigt
    assert colops.deck_fortschritt(col, did)[::2] == (100 / 6, 6)
    # MC only: nur die 2 MC-Fragen, beide noch offen
    assert colops.deck_fortschritt(col, did, mc=True) == (0.0, 0.0, 2)
    # New only: die vorher gesehene Karte zaehlt nicht mit, 5 noch neu
    assert colops.deck_fortschritt(col, did, neu_seit=seit) == (0.0, 0.0, 5)
    mc1 = _antworten(col, auswahl.naechste(col, did, neu=True, mc=True))   # erste neue MC-Frage, nur 5 min
    modus.plane(col, col.get_card(mc1), "5m")
    assert colops.deck_fortschritt(col, did, neu_seit=seit) == (0.0, 20.0, 5), "Speedrun, 5 min: hell"
    assert colops.deck_fortschritt(col, did, mc=True, neu_seit=seit) == (0.0, 50.0, 2)
    modus.plane(col, col.get_card(mc1), "1d")
    assert colops.deck_fortschritt(col, did, mc=True, neu_seit=seit) == (50.0, 0.0, 2), "Speedrun, Tomorrow: kraeftig"
    modus.plane(col, col.get_card(mc1), "5m")
    assert colops.balken_daten(col, did, mc=True, neu_seit=seit)["karten"] == 2
    col.undo()   # Antwort zurueck: wieder neu, wieder offen
    assert colops.deck_fortschritt(col, did, mc=True, neu_seit=seit) == (0.0, 0.0, 2)
    col.close()

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    with tempfile.TemporaryDirectory() as ordner:
        for name, f in tests:
            f(ordner) if f.__code__.co_argcount else f()
            print(f"ok  {name}")
    print(f"{len(tests)} Tests in Ordnung")
