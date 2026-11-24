"""Vokabelliste, Abdeckungen pro Frage und die Total-Spalte der Deckliste.

Gespeichert in der Sammlung (also auch nach Neustart und Sync):
  lernbalken_vokabeln:   [{"id", "wort", "erklaerung", "quelle", "zeit"}]
  lernbalken_abdeckung:  {"<Notiz-Id>": [[{"t": Text, "n": wievieltes Vorkommen}, ...], ...]}
                         Jede innere Liste ist eine Gruppe (mit Strg zusammen abgedeckt).
"""

from __future__ import annotations

import html
import re
import time
from urllib.parse import unquote

VOKABELN = "lernbalken_vokabeln"
ABDECKUNG = "lernbalken_abdeckung"


# Vokabeln
##########################################################################


def vokabeln(col) -> list[dict]:
    liste = col.get_config(VOKABELN, default=None) or []
    return sorted((v for v in liste if isinstance(v, dict)), key=lambda v: str(v.get("wort", "")).lower())


def vokabel_speichern(col, wort: str, erklaerung: str, quelle: str = "", vid: int | None = None) -> dict | None:
    """Neu anlegen (vid None) oder aendern. Leeres Wort speichert nichts."""
    wort, erklaerung = (wort or "").strip(), (erklaerung or "").strip()
    if not wort:
        return None
    liste = col.get_config(VOKABELN, default=None) or []
    for v in liste:
        if vid is not None and v.get("id") == vid:
            v["wort"], v["erklaerung"] = wort, erklaerung
            col.set_config(VOKABELN, liste)
            return v
    neu = {"id": int(time.time() * 1000), "wort": wort, "erklaerung": erklaerung, "quelle": quelle, "zeit": int(time.time())}
    while any(v.get("id") == neu["id"] for v in liste):
        neu["id"] += 1
    liste.append(neu)
    col.set_config(VOKABELN, liste)
    return neu


def vokabel_loeschen(col, vid: int) -> None:
    liste = col.get_config(VOKABELN, default=None) or []
    col.set_config(VOKABELN, [v for v in liste if v.get("id") != vid])


# Abdeckungen
##########################################################################


def _sauber(gruppen) -> list[list[dict]]:
    aus = []
    for g in gruppen or []:
        teile = [{"t": str(s["t"]), "n": int(s.get("n", 0))} for s in g or [] if isinstance(s, dict) and str(s.get("t", "")).strip()]
        if teile:
            aus.append(teile)
    return aus


def abdeckung(col, nid: int) -> list[list[dict]]:
    return _sauber((col.get_config(ABDECKUNG, default=None) or {}).get(str(nid)))


def abdeckung_setzen(col, nid: int, gruppen) -> None:
    alle = col.get_config(ABDECKUNG, default=None) or {}
    gruppen = _sauber(gruppen)
    if gruppen:
        alle[str(nid)] = gruppen
    else:
        alle.pop(str(nid), None)
    col.set_config(ABDECKUNG, alle)


# Bilder: Lage und Groesse aus dem Lernfenster in die Notiz schreiben
##########################################################################

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_LAGE = ("position", "left", "top", "width", "height", "z-index")
_LEER = re.compile(r"<div>(?:\s|<br\s*/?>)*\x00(?:\s|<br\s*/?>)*</div>", re.I)


def _attr_re(name: str):
    return re.compile(r"\s%s\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)" % re.escape(name), re.I)


def _attr(tag: str, name: str) -> str | None:
    m = _attr_re(name).search(tag)
    if not m:
        return None
    v = m.group(1)
    return html.unescape(v[1:-1] if v[:1] in "\"'" else v)


def _quelle(src: str) -> str:
    return unquote(html.unescape(src or ""))


_MASS = re.compile(r"^-?\d{1,5}(?:\.\d{1,3})?(?:px|%)$")  # links darf negativ sein (Bild neben dem Feld)


def bild_setzen(feld: str, src: str, stil: dict | None) -> str:
    """Setzt Lage/Groesse aller Bilder mit dieser Quelle in einem Feld.
    stil {"left", "top", "width"} = frei an diese Stelle, {"width"} = nur Groesse im Text,
    None = zurueck in den Text in Originalgroesse. Werte als "12.5%" oder "40px" (anderes wird abgelehnt).
    Freie Bilder wandern ans Feldende (wie im Editor), damit ihr Bezugsrahmen das Feld selbst ist."""
    if stil and not all(_MASS.match(str(v)) for v in stil.values()):
        raise ValueError(f"ungueltige Bildmasse: {stil}")
    frei_tags: list[str] = []

    def neu(m):
        tag = m.group(0)
        if _quelle(_attr(tag, "src")) != _quelle(src):
            return tag
        alt = _attr(tag, "style") or ""
        props = [p.split(":", 1) for p in alt.split(";") if ":" in p]
        props = [(k.strip(), v.strip()) for k, v in props if k.strip().lower() not in _LAGE]
        t = tag
        for a in ("style", "width", "height", "data-lb-frei"):
            t = _attr_re(a).sub("", t)
        t = re.sub(r"\s*/?>$", "", t)
        frei = bool(stil and "left" in stil)
        if frei:
            props += [("position", "absolute"), ("left", stil["left"]), ("top", stil["top"])]
        if stil:
            props += [("width", stil["width"]), ("height", "auto")]
        if frei:
            t += ' data-lb-frei="1"'
        if props:
            t += ' style="%s"' % html.escape("; ".join(f"{k}: {v}" for k, v in props) + ";")
        t += ">"
        if frei:
            frei_tags.append(t)
            return "\x00"
        return t

    aus = _IMG.sub(neu, feld)
    if frei_tags:
        aus = _LEER.sub("", aus).replace("\x00", "") + "".join(frei_tags)
    return aus


def notiz_speichern(col, note, name: str):
    """Speichert die Notiz als eigenen Undo-Schritt. Ohne das fasst Anki alle Aenderungen an derselben Notiz
    (auch die aus dem Editor) zu einem Schritt zusammen, und Undo naehme alles auf einmal zurueck."""
    schritt = col.add_custom_undo_entry(name)
    col.update_note(note)
    return col.merge_undo_entries(schritt)


# Undo-Knopf
##########################################################################

def sperr_namen(col) -> set[str]:
    """Undo-Namen der Aufraeum-Schritte am Important-Deck (Fuellen beim Oeffnen, Leeren in der Deckliste).
    Die nimmt der Undo-Knopf nicht zurueck: sonst waere das Deck beim Lernen ploetzlich leer oder die
    markierten Karten fehlten im Block."""
    return {col.tr.actions_build_filtered_deck(), col.tr.actions_rebuild(), col.tr.studying_empty()}


def undo_art(ansicht: str, last_step: int, gezeigt: tuple, karte: int, undo_name: str, antwort_name: str | None,
             sperre: set[str] = frozenset()) -> str:
    """Was der Undo-Knopf als Naechstes zuruecknimmt:
    "frage"    Rueckseite aufgedeckt und seitdem nichts geaendert -> zurueck zur Frage dieser Karte
    "antwort"  der oberste Undo-Schritt ist eine Antwort -> zuruecknehmen; Anki zeigt die Karte danach als
               Naechstes, das Add-on deckt dann gleich die Rueckseite auf
    "sperre"   oberster Schritt ist ein Aufraeum-Schritt am Important-Deck (sperr_namen) -> nichts tun
    "anki"     sonst: Ankis normales Rueckgaengig (Stern, Bild, ...)
    Antworten erkennt man an Ankis Undo-Namen ("Answer Card"), nicht an der Schrittnummer: nach jedem
    Rueckgaengig vergibt Anki neue Nummern, eine gemerkte Nummer passt dann nicht mehr."""
    if ansicht == "answer" and tuple(gezeigt) == (last_step, karte):
        return "frage"
    if antwort_name and undo_name == antwort_name:
        return "antwort"
    if undo_name in sperre:
        return "sperre"
    return "anki"


def redo_art(stapel: list, ansicht: str, karte: int | None, anki_redo: bool) -> str | None:
    """Was der Redo-Knopf jetzt macht. stapel merkt sich jeden Undo-Klick, der juengste hinten:
    ("frage", Karte) = Rueckseite wieder zeigen (passt nur, solange genau diese Frage dasteht),
    ("anki", None)   = Ankis Redo.
    Ergebnis "frage", "anki" oder None (Knopf grau)."""
    for art, cid in reversed(stapel):
        if art != "frage":
            break
        if ansicht == "question" and karte == cid:
            return "frage"
    return "anki" if anki_redo else None


# Total-Spalte
##########################################################################


def karten_pro_deck(col) -> dict[int, int]:
    """Karten je Deck. Karten in Filterdecks zaehlen bei ihrem Heimatdeck."""
    return {
        int(d): int(n)
        for d, n in col.db.all("select case when odid then odid else did end, count() from cards group by 1")
    }


def totale(baum, pro_deck: dict[int, int], filter_zahl=None) -> dict[int, int]:
    """Gesamtzahl je Deck inklusive Unterdecks. filter_zahl(knoten) liefert die Zahl fuer Filterdecks."""
    aus: dict[int, int] = {}

    def gehe(k) -> int:
        if k.filtered:
            n = filter_zahl(k) if filter_zahl else 0
        else:
            n = pro_deck.get(k.deck_id, 0) + sum(gehe(c) for c in k.children if not c.filtered)
            for c in k.children:
                if c.filtered:
                    gehe(c)
        aus[k.deck_id] = n
        return n

    for c in baum.children:
        gehe(c)
    return aus


def zuletzt_beantwortet(col) -> int | None:
    """Karte der juengsten Antwort. Undo nimmt genau diese als Naechstes zurueck, auch nach Ankis eigenem
    Rueckgaengig (das loescht die Eintraege der zurueckgenommenen Antworten)."""
    return col.db.scalar("select cid from revlog order by id desc limit 1")
