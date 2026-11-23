"""Lernbalken fuer Anki.

- Legt Decks aus der Lernbalken-Datei an: Fach > Lehrbrief (LB1, LB2 ...) > Block.
- Bringt den Kartentyp "Lernbalken MC" fuer Single- und Multiple-Choice mit.
- Zeigt beim Lernen oben einen Fortschrittsbalken, der bei jeder richtigen Antwort
  weiterlaedt, glitzert, +1 zeigt und kurz klingelt. Bei falschen Antworten passiert nichts.
- Deckliste: Decks per Ziehen sortieren und mit dem Auge ausblenden.
- Eigene Zeiten: Schalter Anki/Eigene neben More, eigene Knoepfe 5 Min bis Fertig.
"""

from __future__ import annotations

import html
import json
import os
import traceback
from functools import partial

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.qt import QTimer, QWebEngineSettings
from aqt.reviewer import Reviewer, ReviewerBottomBar

from . import colops, core, deckliste, modus, wichtig

_ADDON = mw.addonManager.addonFromModule(__name__)
_WEB = f"/_addons/{_ADDON}/web"
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")

_zustand = {"mtime": None, "frisch": True, "wahl": None}
_timer: QTimer | None = None


def _config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


def _eigen() -> bool:
    return _config().get("modus", "eigen") != "anki"


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


def _vor_status(neu: str, alt: str) -> None:
    """Laeuft, bevor Anki den neuen Bildschirm zeichnet, damit die Zahlen gleich stimmen."""
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


def _frage_gezeigt(card) -> None:
    if _zustand["frisch"]:
        _zustand["frisch"] = False
        try:
            _js("setze", _daten())
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
        if richtig:
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


# Eigene Zeiten
##########################################################################

_anki_knoepfe = Reviewer._answerButtons
_anki_leiste = Reviewer._bottomHTML


def _knoepfe(self) -> str:
    return modus.knoepfe_html() if _eigen() else _anki_knoepfe(self)


def _leiste(self) -> str:
    html_ = _anki_leiste(self)
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
    if isinstance(context, ReviewerBottomBar) and message.startswith(("lb_zeit:", "lb_modus:")):
        art, wert = message.split(":", 1)
        try:
            (_zeit_waehlen if art == "lb_zeit" else _modus_setzen)(wert)
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
gui_hooks.state_did_change.append(_status)
gui_hooks.state_will_change.append(_vor_status)
gui_hooks.reviewer_did_show_question.append(_frage_gezeigt)
gui_hooks.reviewer_did_answer_card.append(_beantwortet)
gui_hooks.overview_will_render_content.append(_uebersicht)
