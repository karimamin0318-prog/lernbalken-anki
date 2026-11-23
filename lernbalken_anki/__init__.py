"""Lernbalken fuer Anki.

- Legt Decks aus der Lernbalken-Datei an: Fach > Lehrbrief (LB1, LB2 ...) > Block.
- Holt Fragen aus dem Anki-Eingang (vom Lernbalken aus der Zwischenablage abgelegt) und sortiert sie ein.
- Bringt den Kartentyp "Lernbalken MC" fuer Single- und Multiple-Choice mit.
- Zeigt beim Lernen oben einen Fortschrittsbalken, der bei jeder richtigen Antwort
  weiterlaedt, glitzert, +1 zeigt und kurz klingelt. Bei falschen Antworten passiert nichts.
- Deckliste: Decks per Ziehen sortieren und mit dem Auge ausblenden.
"""

from __future__ import annotations

import html
import json
import os
import traceback

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.qt import QTimer, QWebEngineSettings
from aqt.reviewer import Reviewer
from aqt.utils import tooltip

from . import colops, core, deckliste, wichtig

_ADDON = mw.addonManager.addonFromModule(__name__)
_WEB = f"/_addons/{_ADDON}/web"
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")

_zustand = {"mtime": None, "frisch": True}
_timer: QTimer | None = None


def _config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


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


# Fragen aus dem Anki-Eingang
##########################################################################


def _eingang_pruefen() -> None:
    if not mw.col:
        return
    ordner = os.path.join(os.path.dirname(_datei()), "anki-eingang")
    try:
        dateien = sorted(f for f in os.listdir(ordner) if f.endswith(".txt"))
    except OSError:
        return
    meldungen = []
    for name in dateien:
        pfad = os.path.join(ordner, name)
        ziel = "importiert"
        try:
            with open(pfad, encoding="utf-8") as f:
                abschnitte = core.lies_anki(f.read())
            ergebnis = colops.importiere(mw.col, abschnitte)
            if not any(e["neu"] or e["doppelt"] for e in ergebnis):
                ziel = "fehler"
            for e in ergebnis:
                teile = [f"{e['neu']} neu"]
                if e["doppelt"]:
                    teile.append(f"{e['doppelt']} schon da")
                if e["kaputt"]:
                    teile.append(f"{e['kaputt']} unlesbar")
                meldungen.append(f"<b>{html.escape(e['deck'])}</b>: " + ", ".join(teile))
        except Exception:
            traceback.print_exc()
            ziel = "fehler"
        # Die Datei bleibt als Sicherung liegen, aber nicht mehr im Eingang
        try:
            os.makedirs(os.path.join(ordner, ziel), exist_ok=True)
            os.replace(pfad, os.path.join(ordner, ziel, name))
        except OSError:
            traceback.print_exc()
    if meldungen:
        tooltip("Lernbalken → Anki<br>" + "<br>".join(meldungen), period=6000)
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()


def _pruefen() -> None:
    _decks_pruefen()
    _eingang_pruefen()


def _profil_offen() -> None:
    global _timer
    try:
        colops.kartentypen_auffrischen(mw.col)
    except Exception:
        traceback.print_exc()
    _decks_pruefen(erzwingen=True)
    _eingang_pruefen()
    try:
        for fach in wichtig.faecher_mit_markierten(mw.col):
            wichtig.deck_id(mw.col, fach, erzeugen=True)
        wichtig.leeren_alle(mw.col)
    except Exception:
        traceback.print_exc()
    # Ton im Lernfenster ohne vorherigen Mausklick erlauben
    mw.web.settings().setAttribute(
        QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
    )
    if _timer is None:
        _timer = QTimer(mw)
        _timer.timeout.connect(_pruefen)
    _timer.start(2000)


def _profil_zu() -> None:
    if _timer:
        _timer.stop()
    _zustand["mtime"] = None


# Balken im Lernfenster
##########################################################################


def _daten() -> dict:
    d = colops.balken_daten(mw.col, mw.col.decks.get_current_id()) or {}
    cfg = _config()
    d["ton"] = {"an": bool(cfg.get("ton", True)), "lautstaerke": float(cfg.get("lautstaerke", 0.35))}
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


def _status(neu: str, alt: str) -> None:
    if neu == "review":
        _zustand["frisch"] = True
    if neu == "deckBrowser" and mw.col:
        # Markierte Karten zurueck in ihre Blocks, Anki zeichnet die Liste gleich danach
        try:
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


def _frage_gezeigt(card) -> None:
    if _zustand["frisch"]:
        _zustand["frisch"] = False
        try:
            _js("setze", _daten())
        except Exception:
            traceback.print_exc()


def _beantwortet(reviewer, card, ease: int) -> None:
    try:
        if ease > 1:
            _js("richtig", _daten())
        else:
            _js("falsch")
    except Exception:
        traceback.print_exc()


# Balken in der Deck-Uebersicht (vor dem Lernen)
##########################################################################


def _uebersicht(overview, content) -> None:
    try:
        d = colops.balken_daten(mw.col, mw.col.decks.get_current_id())
    except Exception:
        traceback.print_exc()
        return
    if not d:
        return
    zahl = lambda p: f"{p:.1f}".replace(".", ",") + " %"
    links = html.escape(d["fach"] + " " + zahl(d["fachPct"])) if d["fach"] else f'{d["karten"]} Karten'
    content.table += f"""
<div id="lb-balken" class="statisch"><div class="lb-innen">
  <div class="lb-kopf"><span class="lb-name">{html.escape(d["name"])}</span><span class="lb-pct">{zahl(d["pct"])}</span></div>
  <div class="lb-spur"><div class="lb-fuell ohne" style="width:{d["pct"]}%"></div></div>
  <div class="lb-fuss"><span>{links}</span><span>heute {d["heute"]} ✓</span></div>
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


def _baum_zeichnen(self, top):
    try:
        top, eltern, versteckt = deckliste.baum_anpassen(top, deckliste.lies(self.mw.col), _anzeige)
        _deckliste["skript"], _deckliste["bereich"] = deckliste.html_dazu(eltern, versteckt)
    except Exception:
        traceback.print_exc()
        _deckliste["skript"] = _deckliste["bereich"] = ""
    return _anki_baum(self, top)


DeckBrowser._renderDeckTree = _baum_zeichnen


def _deckliste_inhalt(deck_browser, content) -> None:
    content.tree += _deckliste["skript"]
    content.stats = _deckliste["bereich"] + content.stats


def _js_nachricht(handled, message: str, context):
    if isinstance(context, Reviewer) and message == "lb_wichtig":
        mw.reviewer.toggle_mark_on_current_note()
        return (True, None)
    if isinstance(context, DeckBrowser) and message.startswith("open:"):
        # Wichtig-Deck: beim Oeffnen die markierten Karten einsammeln, dann oeffnet Anki es wie gewohnt
        try:
            did = int(message.split(":", 1)[1])
            if any(did == w for w, _ in wichtig.alle(mw.col)):
                wichtig.fuellen(mw.col, did)
        except Exception:
            traceback.print_exc()
        return handled
    if not isinstance(context, DeckBrowser) or not message.startswith("lb_"):
        return handled
    try:
        if deckliste.befehl(mw.col, message):
            context.refresh()
    except Exception:
        traceback.print_exc()
    return (True, None)


gui_hooks.deck_browser_will_render_content.append(_deckliste_inhalt)
gui_hooks.webview_did_receive_js_message.append(_js_nachricht)
gui_hooks.profile_did_open.append(_profil_offen)
gui_hooks.profile_will_close.append(_profil_zu)
gui_hooks.webview_will_set_content.append(_web_inhalt)
gui_hooks.state_did_change.append(_status)
gui_hooks.reviewer_did_show_question.append(_frage_gezeigt)
gui_hooks.reviewer_did_answer_card.append(_beantwortet)
gui_hooks.overview_will_render_content.append(_uebersicht)
