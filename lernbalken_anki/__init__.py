"""Lernbalken fuer Anki.

- Legt Decks aus der Lernbalken-Datei an: Fach > Lehrbrief (LB1, LB2 ...) > Block.
- Bringt den Kartentyp "Lernbalken MC" fuer Single- und Multiple-Choice mit.
- Zeigt beim Lernen oben einen Fortschrittsbalken, der bei jeder richtigen Antwort
  weiterlaedt, glitzert, +1 zeigt und kurz klingelt. Bei falschen Antworten passiert nichts.
- Deckliste: Decks per Ziehen sortieren und mit dem Auge ausblenden.
- Eigene Zeiten: Schalter Anki/Eigene neben More, eigene Knoepfe 5 Min bis Fertig.
- Zurueck-Knopf neben Edit, Woerter abdecken, Vokabelliste (Buch), Total-Spalte in der Deckliste.
- Bilder im Editor frei verschieben und groesser/kleiner ziehen.
"""

from __future__ import annotations

import html
import json
import os
import time
import traceback
from functools import partial

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.editor import Editor
from aqt.operations.collection import undo
from aqt.operations import CollectionOp
from aqt.overview import Overview
from aqt.qt import QTimer, QWebEngineSettings
from aqt.reviewer import Reviewer, ReviewerBottomBar, V3CardInfo
from aqt.utils import tooltip

from . import auswahl, colops, core, deckliste, extras, modus, wichtig

_ADDON = mw.addonManager.addonFromModule(__name__)
_WEB = f"/_addons/{_ADDON}/web"
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")

_zustand = {"mtime": None, "frisch": True, "wahl": None, "zurueck": False, "antwort_name": None, "gezeigt": (None, None), "total": {}, "zuerst": None, "gefiltert": False}
_timer: QTimer | None = None


def _config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


def _eigen() -> bool:
    return _config().get("modus", "eigen") != "anki"


def _filter() -> dict:
    cfg = _config()
    return {"neu": bool(cfg.get("nur_neu")), "mc": bool(cfg.get("nur_mc"))}


def _datei() -> str:
    return _config().get("lernbalken_datei") or core.STANDARD_DATEI


def _log(text: str) -> None:
    print(f"[Lernbalken] {text}")


# Decks aus der Lernbalken-Datei
##########################################################################


def _decks_pruefen(erzwingen: bool = False) -> None:
    if not mw.col:
        return
    pfad = _datei()
    try:
        mtime = os.path.getmtime(pfad)
    except OSError:
        return
    if not erzwingen and mtime == _zustand["mtime"]:
        return
    daten = core.lies_datei(pfad)
    if daten is None:
        return  # gerade kaputt oder halb geschrieben, beim naechsten Mal wieder
    _zustand["mtime"] = mtime
    try:
        neu = colops.sync_decks(mw.col, daten)
    except Exception:
        traceback.print_exc()
        return
    if neu:
        _log("Decks angelegt/umbenannt: " + ", ".join(neu))
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()


def _profil_offen() -> None:
    global _timer
    try:
        colops.kartentypen_auffrischen(mw.col)
    except Exception:
        traceback.print_exc()
    _decks_pruefen(erzwingen=True)
    try:
        if wichtig.umbenennen(mw.col):
            _log("Wichtig-Decks heissen jetzt " + wichtig.NAME)
        for fach in wichtig.faecher_mit_markierten(mw.col):
            wichtig.deck_id(mw.col, fach, erzeugen=True)
        wichtig.leeren_alle(mw.col)
    except Exception:
        traceback.print_exc()
    cfg = _config()
    if not cfg.get("tageswechsel_erledigt"):
        try:
            if modus.tageswechsel_mitternacht(mw.col):
                _log("Neuer Tag beginnt jetzt um 0 Uhr")
            cfg["tageswechsel_erledigt"] = True
            mw.addonManager.writeConfig(__name__, cfg)
        except Exception:
            traceback.print_exc()
    # Ton im Lernfenster ohne vorherigen Mausklick erlauben
    mw.web.settings().setAttribute(
        QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
    )
    if _timer is None:
        _timer = QTimer(mw)
        _timer.timeout.connect(_decks_pruefen)
    _timer.start(2000)


def _profil_zu() -> None:
    if _timer:
        _timer.stop()
    _zustand["mtime"] = None


# Balken im Lernfenster
##########################################################################


def _balken_daten():
    """Zahlen fuer den Balken, passend zu den Schaltern: MC only zaehlt nur MC-Fragen, New only nur den Speedrun
    (Karten, die beim Einschalten noch neu waren)."""
    f, cfg = _filter(), _config()
    seit = (cfg.get("nur_neu_seit") or (mw.col.sched.day_cutoff - 86400) * 1000) if f["neu"] else None
    return colops.balken_daten(mw.col, mw.col.decks.get_current_id(), mc=f["mc"], neu_seit=seit)


def _daten() -> dict:
    d = _balken_daten() or {}
    cfg = _config()
    d["ton"] = {"an": bool(cfg.get("ton", True)), "lautstaerke": float(cfg.get("lautstaerke", 0.35))}
    d["filter"] = _filter()
    return d


def _js(funktion: str, daten: dict | None = None) -> None:
    arg = json.dumps(daten) if daten is not None else ""
    mw.reviewer.web.eval(f"window.lernbalken && lernbalken.{funktion}({arg});")


def _web_inhalt(web_content, context) -> None:
    if isinstance(context, DeckBrowser):
        web_content.css.append(f"{_WEB}/deckliste.css")
        web_content.js.append(f"{_WEB}/deckliste.js")
    if isinstance(context, (Reviewer, Overview)):
        web_content.css.append(f"{_WEB}/balken.css")
    if isinstance(context, Reviewer):
        web_content.js.append(f"{_WEB}/balken.js")
        web_content.css.append(f"{_WEB}/lernen.css")
        web_content.js.append(f"{_WEB}/rahmen.js")
        web_content.js.append(f"{_WEB}/lernen.js")
    if isinstance(context, (Reviewer, DeckBrowser)):
        web_content.css.append(f"{_WEB}/vokabeln.css")
        web_content.js.append(f"{_WEB}/vokabeln.js")
    if isinstance(context, Editor):
        web_content.js.append(f"{_WEB}/rahmen.js")
        web_content.js.append(f"{_WEB}/bilder.js")


def _vor_status(neu: str, alt: str) -> None:
    """Laeuft, bevor Anki den neuen Bildschirm zeichnet, damit die Zahlen gleich stimmen."""
    if neu == "review":
        # Hier, nicht erst nach dem Wechsel: Anki zeigt die erste Frage noch vor state_did_change.
        # Sonst kaemen Balken und Schalter erst nach der ersten Antwort.
        _zustand["frisch"] = True
    if not mw.col:
        return
    try:
        if neu == "overview":
            # Wichtig-Deck: beim Oeffnen (egal auf welchem Weg) die markierten Karten einsammeln
            aktuell = mw.col.decks.get_current_id()
            if any(aktuell == w for w, _ in wichtig.alle(mw.col)):
                wichtig.fuellen(mw.col, aktuell)
        elif neu == "deckBrowser":
            # Markierte Karten zurueck in ihre Blocks
            wichtig.leeren_alle(mw.col)
    except Exception:
        traceback.print_exc()


# Stern im Balken: zeigt und schaltet Ankis Markierung (auch die Taste * aktualisiert ihn)
_anki_marke = Reviewer._update_mark_icon


def _marke(self) -> None:
    _anki_marke(self)
    try:
        markiert = self.card.note().has_tag(wichtig.TAG)
        self.web.eval(f"window.lernbalken && lernbalken.stern({json.dumps(markiert)});")
        if markiert:
            wichtig.deck_id(self.mw.col, wichtig.fach_von(self.mw.col, self.card), erzeugen=True)
    except Exception:
        traceback.print_exc()


Reviewer._update_mark_icon = _marke
Reviewer._drawMark = _marke


def _karte_js(card, extra: str = "") -> None:
    """Abdeckungen dieser Frage ins Lernfenster geben, sobald Anki die Karte fertig gezeichnet hat."""
    daten = {"nid": card.nid, "gruppen": extras.abdeckung(mw.col, card.nid), "an": bool(_config().get("abdecken", True))}
    mw.reviewer.web.eval(
        f"_queueAction(function(){{ window.lernen && lernen.karte({json.dumps(daten)}); {extra} }});"
    )


def _frage_gezeigt(card) -> None:
    if _zustand["frisch"]:
        _zustand["frisch"] = False
        try:
            _js("setze", _daten())
        except Exception:
            traceback.print_exc()
    try:
        extra = ""
        if _zustand["zurueck"]:
            # Antwort zurueckgenommen: Anki zeigt genau diese Karte als Naechstes. Wieder auf die Rueckseite,
            # wo man vor der Antwort war.
            extra = "pycmd('lb_aufdecken');"
        _zustand["zurueck"] = False
        _karte_js(card, extra)
    except Exception:
        traceback.print_exc()


def _antwort_gezeigt(card) -> None:
    # Fuer Undo: solange danach nichts an der Sammlung passiert, ist "Rueckseite aufgedeckt" der letzte Schritt
    _zustand["gezeigt"] = (mw.col.undo_status().last_step, card.id)
    try:
        _karte_js(card)
    except Exception:
        traceback.print_exc()


def _beantwortet(reviewer, card, ease: int) -> None:
    try:
        richtig = ease > 1
        if _eigen():
            wahl = _zustand["wahl"] or modus.AUS_EASE.get(ease, "1d")
            _zustand["wahl"] = None
            modus.plane(mw.col, card, wahl)
            richtig = wahl != "5m"
        # Fuer den Zurueck-Knopf: welcher Rueckgaengig-Schritt diese Antwort ist
        _zustand["antwort_name"] = mw.col.undo_status().undo   # z. B. "Answer Card", in Ankis Sprache
        if richtig:
            _js("richtig", _daten())
        else:
            _js("falsch", _daten())
    except Exception:
        traceback.print_exc()


# Filter: nur neue Karten (Speedrun), nur MC-Karten
##########################################################################

_anki_naechste = Reviewer._get_next_v3_card


def _naechste(self) -> None:
    f = _filter()
    zuerst, _zustand["zuerst"] = _zustand["zuerst"], None
    _zustand["gefiltert"] = False
    if not (f["neu"] or f["mc"]):
        return _anki_naechste(self)
    try:
        q = auswahl.naechste(self.mw.col, self.mw.col.decks.get_current_id(), f["neu"], f["mc"], zuerst)
    except Exception:
        traceback.print_exc()
        return _anki_naechste(self)
    if q is None:
        tooltip("No new MC cards left" if f["neu"] and f["mc"] else "No new cards left" if f["neu"] else "No MC cards due")
        return
    _zustand["gefiltert"] = True
    self._v3 = V3CardInfo.from_queue(q)
    self.card = Card(self.mw.col, backend_card=self._v3.top_card().card)
    self.card.start_timer()


Reviewer._get_next_v3_card = _naechste


def _vor_antwort(ease_tuple, reviewer, card):
    # Gefilterte Karten liegen oft nicht oben in Ankis Warteschlange: die erst zuruecksetzen
    if _zustand["gefiltert"]:
        try:
            auswahl.frei(mw.col, card)
        except Exception:
            traceback.print_exc()
    return ease_tuple


def _filter_setzen(art: str) -> None:
    schluessel = {"neu": "nur_neu", "mc": "nur_mc"}.get(art)
    if not schluessel:
        return
    cfg = _config()
    cfg[schluessel] = not cfg.get(schluessel)
    if art == "neu" and cfg[schluessel]:
        cfg["nur_neu_seit"] = int(time.time() * 1000)   # Speedrun beginnt jetzt, der Balken zaehlt ab hier
    mw.addonManager.writeConfig(__name__, cfg)
    _js("setze", _daten())   # Schalter und Balken gleich passend zeigen
    # Frage offen: gleich die passende Karte zeigen. Steht schon die Rueckseite da, gilt es ab der naechsten.
    r = mw.reviewer
    if mw.state == "review" and r.state == "question":
        r.nextCard()


# Balken in der Deck-Uebersicht (vor dem Lernen)
##########################################################################


def _uebersicht(overview, content) -> None:
    try:
        d = _balken_daten()
    except Exception:
        traceback.print_exc()
        return
    if not d:
        return
    zahl = lambda p: f"{p:.1f}".replace(".", ",") + " %"
    links = html.escape(d["fach"] + " " + zahl(d["fachPct"])) if d["fach"] else f'{d["karten"]} cards'
    zweite = f'<span class="lb-pct2">/ {zahl(min(100, d["pct"] + d["offen"]))}</span>' if d["offen"] else ""
    f = _filter()
    an = [t for t, ja in (("New only", f["neu"]), ("MC only", f["mc"])) if ja]
    # Filter an: die Zahlen oben (Anki) zaehlen auch Karten, die gerade nicht kommen
    hinweis = f'<div class="lb-fuss lb-hinweis">Filter on: {" + ".join(an)} (switch in the bar while studying)</div>' if an else ""
    content.table += f"""
<div id="lb-balken" class="statisch"><div class="lb-innen">
  <div class="lb-kopf"><span class="lb-name">{html.escape(d["name"])}</span></div>
  <div class="lb-zeile"><div class="lb-spur"><div class="lb-offen ohne" style="width:{min(100, d["pct"] + d["offen"])}%"></div><div class="lb-fuell ohne" style="width:{d["pct"]}%"></div></div>
  <span class="lb-pct">{zahl(d["pct"])}</span>{zweite}</div>
  <div class="lb-fuss"><span>{links}</span><span>today {d["heute"]} ✓</span></div>
  {hinweis}
</div></div>"""


# Deckliste: eigene Reihenfolge, ausgeblendete Decks
##########################################################################

_deckliste = {"skript": "", "bereich": ""}


def _anzeige(voller_name: str, knoten):
    """Das Wichtig-Deck ist leer, bis man es oeffnet. Damit man trotzdem sieht, wie viele drin sind."""
    teile = voller_name.split("::")
    if knoten.filtered and len(teile) == 2 and teile[1] == wichtig.NAME:
        return f"{wichtig.NAME} ({wichtig.anzahl(mw.col, teile[0])})"
    return None
_anki_baum = DeckBrowser._renderDeckTree


def _filter_zahl(col, knoten) -> int:
    if knoten.name == wichtig.NAME:  # ist in der Deckliste leer, zaehlt die markierten Karten des Fachs
        return wichtig.anzahl(col, col.decks.name(knoten.deck_id).split("::")[0])
    return col.db.scalar("select count() from cards where did = ?", knoten.deck_id) or 0


def _baum_zeichnen(self, top):
    col = self.mw.col
    try:
        _zustand["total"] = extras.totale(col.decks.deck_tree(), extras.karten_pro_deck(col), partial(_filter_zahl, col))
    except Exception:
        traceback.print_exc()
        _zustand["total"] = {}
    try:
        top, eltern, versteckt = deckliste.baum_anpassen(top, deckliste.lies(col), _anzeige)
        _deckliste["skript"], _deckliste["bereich"] = deckliste.html_dazu(eltern, versteckt)
    except Exception:
        traceback.print_exc()
        _deckliste["skript"] = _deckliste["bereich"] = ""
    html_ = _anki_baum(self, top)
    return html_.replace("<th class=optscol>", "<th class=count>Total</th><th class=optscol>", 1)


DeckBrowser._renderDeckTree = _baum_zeichnen
_anki_zeile = DeckBrowser._render_deck_node


def _zeile(self, node, ctx) -> str:
    html_ = _anki_zeile(self, node, ctx)
    n = _zustand["total"].get(node.deck_id, 0)
    zahl = n if n else '<span class="zero-count">0</span>'
    # Die erste Optionen-Zelle gehoert zu dieser Zeile, die Unterdecks kommen erst danach
    return html_.replace("<td align=center class=opts>", f"<td align=end>{zahl}</td><td align=center class=opts>", 1)


DeckBrowser._render_deck_node = _zeile


def _deckliste_inhalt(deck_browser, content) -> None:
    # Neu gezeichnet, waehrend das Vokabel-Fenster offen war: das Fenster ist weg, die Tasten muessen wieder gehen
    _tasten_an(True)
    content.tree += _deckliste["skript"]
    try:
        n = len(extras.vokabeln(mw.col))
    except Exception:
        n = 0
    buch = (f'<div class="lb-vok-start"><button type="button" onclick="window.vokabeln && vokabeln.oeffnen()" '
            f'title="View and quiz your vocabulary"><i class="lb-buch-icon"></i><span>Vocabulary (<span class="lb-vok-zahl">{n}</span>)</span></button></div>')
    content.stats = buch + _deckliste["bereich"] + content.stats


# Eigene Zeiten
##########################################################################

_anki_knoepfe = Reviewer._answerButtons
_anki_leiste = Reviewer._bottomHTML


def _knoepfe(self) -> str:
    return modus.knoepfe_html() if _eigen() else _anki_knoepfe(self)


ZURUECK_HTML = """<style>
#lb-zurueck { margin-inline-start: 6px; }
#lb-zurueck svg { vertical-align: -2px; margin-inline-end: 4px; }
</style><button id="lb-zurueck" title="Undo your last step"
onclick="pycmd('lb_zurueck');"><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="none"
stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
d="M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>Undo</button>"""


def _leiste(self) -> str:
    html_ = _anki_leiste(self)
    # Zurueck rechts neben Edit
    html_ = html_.replace(
        "</button></td>\n<td align=center valign=top id=middle>",
        "</button>" + ZURUECK_HTML + "</td>\n<td align=center valign=top id=middle>", 1,
    )
    # Schalter links neben den More-Knopf
    marke = "<td align=end valign=top class=stat>\n<button"
    return html_.replace(marke, "<td align=end valign=top class=stat>\n" + modus.schalter_html(_eigen()) + "<button", 1)


Reviewer._answerButtons = _knoepfe
Reviewer._bottomHTML = _leiste


def _zeit_waehlen(wahl: str) -> None:
    r = mw.reviewer
    if r.state != "answer" or wahl not in modus.EASE:
        return
    _zustand["wahl"] = wahl
    r._answerCard(modus.EASE[wahl])


def _zurueck() -> None:
    """Undo: genau der letzte Schritt, so wie man ihn auf dem Bildschirm gemacht hat.
    - Rueckseite aufgedeckt (und seitdem nichts geaendert) -> zurueck zur Frage derselben Karte
    - Karte beantwortet -> Antwort zurueck, die Karte steht wieder mit Rueckseite da
    - sonst (z. B. Stern gesetzt) -> Ankis Rueckgaengig fuer genau diesen Schritt"""
    r, col = mw.reviewer, mw.col
    if not col or not r.card:
        return
    status = col.undo_status()
    art = extras.undo_art(r.state, status.last_step, _zustand["gezeigt"], r.card.id, status.undo, _zustand["antwort_name"])
    if art == "frage":
        _zustand["gezeigt"] = (None, None)
        r.web.eval("window.lernen && lernen.undoVorbereiten();")
        r._showQuestion()
        return
    if not status.undo:
        tooltip("Nothing to undo")
        return
    _zustand["zurueck"] = art == "antwort"
    # Filter-Modus: diese Karte kommt gleich zurueck und soll als Naechstes dran sein
    _zustand["zuerst"] = extras.zuletzt_beantwortet(col) if art == "antwort" else None
    # Gleich erscheint eine Vorderseite neu (die zurueckgeholte Karte oder die neu gezeichnete Frage):
    # MC-Karten sollen dann nicht neu mischen, sondern Reihenfolge und Auswahl behalten
    if art == "antwort" or r.state == "question":
        r.web.eval("window.lernen && lernen.undoVorbereiten();")
    undo(parent=mw)


def _bild_speichern(d: dict) -> None:
    """Bild im Lernfenster verschoben/vergroessert: in der Notiz speichern. Die Karte zeigt es schon richtig,
    darum zeichnet das Lernfenster nicht neu (initiator). Undo nimmt es als eigenen Schritt zurueck."""
    r = mw.reviewer
    if not r.card:
        return
    if d.get("zurueck"):
        stil = None
    elif "left" in d:
        stil = {"left": d["left"], "top": d["top"], "width": d["width"]}
    else:
        stil = {"width": d["width"]}
    note, cid = r.card.note(), r.card.id
    geaendert = False
    for name in note.keys():
        neu = extras.bild_setzen(note[name], d["src"], stil)
        if neu != note[name]:
            note[name] = neu
            geaendert = True
    if not geaendert:
        return

    def danach(_) -> None:
        # Die Karte hat ihren Text zwischengespeichert; frisch laden, damit die Rueckseite die neue Lage zeigt
        if r.card and r.card.id == cid:
            r.card.load()

    CollectionOp(mw, lambda col: extras.notiz_speichern(col, note, "Move image")).success(danach).run_in_background(initiator=r)


def _nach_undo(_changes) -> None:
    """Jedes Rueckgaengig (auch Strg+Z): Balken neu, sonst zeigt er die zurueckgenommene Antwort bis zur naechsten."""
    if mw.state == "review":
        try:
            _js("setze", _daten())
        except Exception:
            traceback.print_exc()


def _aufdecken() -> None:
    r = mw.reviewer
    if r.state == "question" and r.card:
        r._getTypedAnswer()
    try:
        _js("setze", _daten())
    except Exception:
        traceback.print_exc()


def _tasten_an(an: bool) -> None:
    """Solange das Vokabel-Fenster offen ist, duerfen Leertaste und 1-6 keine Karte beantworten."""
    for s in mw.stateShortcuts:
        s.setEnabled(an)


def _vokabel_befehl(message: str):
    art, _, wert = message.partition(":")
    col = mw.col
    if art == "lb_vok_liste":
        return extras.vokabeln(col)
    if art == "lb_vok_speichern":
        d = json.loads(wert)
        quelle = ""
        if mw.state == "review" and mw.reviewer.card:
            c = mw.reviewer.card
            quelle = col.decks.name(c.odid or c.did).replace("::", " › ")
        return extras.vokabel_speichern(col, d.get("wort", ""), d.get("erklaerung", ""), quelle, d.get("id"))
    if art == "lb_vok_weg":
        extras.vokabel_loeschen(col, int(wert))
        return True
    if art == "lb_vok_panel":
        _tasten_an(wert != "1")
        return True
    return None


def _modus_setzen(neu: str) -> None:
    cfg = _config()
    cfg["modus"] = "anki" if neu == "anki" else "eigen"
    mw.addonManager.writeConfig(__name__, cfg)
    eigen = cfg["modus"] == "eigen"
    r = mw.reviewer
    r.bottom.web.eval(
        "(function(){var k=document.querySelectorAll('#lb-modus button');"
        f"if(k.length==2){{k[0].classList.toggle('an',{json.dumps(not eigen)});k[1].classList.toggle('an',{json.dumps(eigen)});}}}})();"
    )
    if r.state == "answer":
        r._showEaseButtons()


def _taste(nr: int) -> None:
    r = mw.reviewer
    if _eigen():
        if r.state == "answer":
            _zeit_waehlen(modus.ZEITEN[nr - 1][0])
    elif nr <= 4:
        r._answerCard(nr)
    elif nr == 5:
        r.on_pause_audio()
    elif nr == 6:
        r.on_seek_backward()


def _tasten(state: str, shortcuts: list) -> None:
    if state != "review":
        return
    shortcuts[:] = [s for s in shortcuts if s[0] not in ("1", "2", "3", "4", "5", "6")]
    shortcuts.extend((str(i), partial(_taste, i)) for i in range(1, 7))


def _js_nachricht(handled, message: str, context):
    if isinstance(context, ReviewerBottomBar) and message == "lb_zurueck":
        try:
            _zurueck()
        except Exception:
            traceback.print_exc()
        return (True, None)
    if isinstance(context, (Reviewer, DeckBrowser)) and message.startswith("lb_vok_"):
        try:
            return (True, _vokabel_befehl(message))
        except Exception:
            traceback.print_exc()
            return (True, None)
    if isinstance(context, Reviewer) and message.startswith("lb_bild:"):
        try:
            _bild_speichern(json.loads(message.split(":", 1)[1]))
        except Exception:
            traceback.print_exc()
        return (True, None)
    if isinstance(context, Reviewer) and message.startswith(("lb_abdeck:", "lb_abdecken_an:", "lb_aufdecken")):
        try:
            if message == "lb_aufdecken":
                _aufdecken()
            elif message.startswith("lb_abdeck:"):
                d = json.loads(message.split(":", 1)[1])
                extras.abdeckung_setzen(mw.col, int(d["nid"]), d["gruppen"])
            else:
                cfg = _config()
                cfg["abdecken"] = message.endswith(":1")
                mw.addonManager.writeConfig(__name__, cfg)
        except Exception:
            traceback.print_exc()
        return (True, None)
    if isinstance(context, ReviewerBottomBar) and message.startswith(("lb_zeit:", "lb_modus:")):
        art, wert = message.split(":", 1)
        try:
            (_zeit_waehlen if art == "lb_zeit" else _modus_setzen)(wert)
        except Exception:
            traceback.print_exc()
        return (True, None)
    if isinstance(context, Reviewer) and message.startswith("lb_filter:"):
        try:
            _filter_setzen(message.split(":", 1)[1])
        except Exception:
            traceback.print_exc()
        return (True, None)
    if isinstance(context, Reviewer) and message == "lb_wichtig":
        mw.reviewer.toggle_mark_on_current_note()
        return (True, None)
    if not isinstance(context, DeckBrowser) or not message.startswith("lb_"):
        return handled
    try:
        if deckliste.befehl(mw.col, message):
            context.refresh()
    except Exception:
        traceback.print_exc()
    return (True, None)


gui_hooks.state_shortcuts_will_change.append(_tasten)
gui_hooks.deck_browser_will_render_content.append(_deckliste_inhalt)
gui_hooks.webview_did_receive_js_message.append(_js_nachricht)
gui_hooks.profile_did_open.append(_profil_offen)
gui_hooks.profile_will_close.append(_profil_zu)
gui_hooks.webview_will_set_content.append(_web_inhalt)
gui_hooks.editor_did_load_note.append(lambda ed: ed.web.eval("window.lbBilderAnpassen && lbBilderAnpassen();"))
gui_hooks.state_will_change.append(_vor_status)
gui_hooks.state_did_undo.append(_nach_undo)
gui_hooks.reviewer_did_show_question.append(_frage_gezeigt)
gui_hooks.reviewer_did_show_answer.append(_antwort_gezeigt)
gui_hooks.reviewer_did_answer_card.append(_beantwortet)
gui_hooks.reviewer_will_answer_card.append(_vor_antwort)
gui_hooks.overview_will_render_content.append(_uebersicht)
