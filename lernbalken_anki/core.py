"""Reine Logik ohne Anki-Abhaengigkeit: Lernbalken-Datei lesen, Decknamen ableiten, Fortschritt rechnen."""

from __future__ import annotations

import json
import os
import re

STANDARD_DATEI = os.path.join(os.path.expanduser("~"), "Lernbalken", "lernbalken.json")

# "LB1 B2 Gelenke & Knie" -> Teil "LB1", Block "B2 Gelenke & Knie"
_MIT_TEIL = re.compile(r"^\s*([^\W\d_]+\d+)\s+([Bb]\d+)\b\s*(.*)$")
# "B2 Gelenke & Knie" (ohne Teil-Kuerzel)
_NUR_BLOCK = re.compile(r"^\s*([Bb]\d+)\b\s*(.*)$")


def _sauber(teil: str) -> str:
    # "::" trennt in Anki Unterdecks, darf also nicht im Namen stehen
    return re.sub(r"\s+", " ", teil.replace("::", ":")).strip()


def block_pfad(fach: str, block: str) -> tuple[list[str], str | None]:
    """Deckpfad fuer einen Block und sein Kuerzel (z. B. "B2"), falls vorhanden.

    "LB1 B2 Gelenke & Knie" -> (["B-Lizenz", "LB1", "B2 Gelenke & Knie"], "B2")
    """
    fach = _sauber(fach)
    m = _MIT_TEIL.match(block)
    if m:
        teil, nr, titel = m.group(1).upper(), m.group(2).upper(), _sauber(m.group(3))
        return [fach, teil, f"{nr} {titel}".strip()], nr
    m = _NUR_BLOCK.match(block)
    if m:
        nr, titel = m.group(1).upper(), _sauber(m.group(2))
        return [fach, f"{nr} {titel}".strip()], nr
    return [fach, _sauber(block)], None


def lies_datei(pfad: str) -> dict | None:
    try:
        with open(pfad, encoding="utf-8") as f:
            daten = json.load(f)
    except (OSError, ValueError):
        return None
    return daten if isinstance(daten, dict) else None


def deck_plan(daten: dict) -> list[tuple[list[str], str | None]]:
    """Alle Decks, die es laut Lernbalken geben soll, in Lernreihenfolge."""
    plan: list[tuple[list[str], str | None]] = []
    for fach in daten.get("faecher") or []:
        name = fach.get("name") if isinstance(fach, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        plan.append(([_sauber(name)], None))
        for block in fach.get("bloecke") or []:
            bname = block.get("name") if isinstance(block, dict) else None
            if isinstance(bname, str) and bname.strip():
                plan.append(block_pfad(name, bname))
    return plan


def karten_wert(typ: int, queue: int, ivl: int) -> float | None:
    """Wie gut eine Karte sitzt, 0 bis 1. None = zaehlt nicht (ausgesetzt)."""
    if queue == -1:
        return None
    if typ == 0:  # neu
        return 0.0
    if typ in (1, 3):  # gerade am Lernen / neu Lernen
        return 0.2
    # Wiederholung: ab 21 Tagen Abstand gilt sie als voll gelernt
    return 0.3 + 0.7 * min(1.0, max(ivl, 0) / 21)


def fortschritt(karten: list[tuple[int, int, int]]) -> tuple[float, int]:
    """Prozent (0 bis 100) und Anzahl zaehlender Karten."""
    werte = [w for w in (karten_wert(*k) for k in karten) if w is not None]
    if not werte:
        return 0.0, 0
    return 100 * sum(werte) / len(werte), len(werte)


# Anki-Karten aus dem lernprojekt-Skill
##########################################################################
#
# ANKI | B-Lizenz | LB1 B2 Gelenke & Knie
# Frage: Welche Gelenke sind Kugelgelenke?
# A) Schultergelenk
# B) Kniegelenk
# C) Hueftgelenk
# Richtig: A, C
# Erklaerung: ... (S. 12)

_RAND = re.compile(r"^[\s`*>]+|[\s`*]+$")
_KOPF = re.compile(r"^(?:ANKI|BLOECKE|BLÖCKE|LERNSTAND)\s*\|", re.I)
_FELD = re.compile(r"^(?:(Frage)\s*:|([A-F])\s*[).:]|(Richtig)\s*:|(Erkl(?:ä|ae)rung)\s*:)\s*(.*)$", re.I)
_PLATZHALTER = re.compile(r"<[^>]*>")


def _html(text: str) -> str:
    import html

    t = html.escape(text.strip(), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def karten_id(fach: str, block: str, frage: str) -> str:
    import hashlib

    m = _MIT_TEIL.match(block) or None
    kenn = f"{m.group(1)} {m.group(2)}".lower() if m else re.sub(r"\s+", " ", block).strip().lower()
    roh = "|".join([re.sub(r"\s+", " ", fach).strip().lower(), kenn, re.sub(r"\s+", " ", frage).strip().lower()])
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def lies_anki(text: str) -> list[dict]:
    """Zerlegt den kopierten Text in Abschnitte: {fach, block, fragen: [...], kaputt: int}."""
    abschnitte: list[dict] = []
    akt = None
    frage = None
    feld = None

    def abschliessen():
        nonlocal frage
        if akt is None or frage is None:
            frage = None
            return
        richtig = sorted(set(re.findall(r"[A-F]", (frage.get("Richtig") or "").upper())))
        optionen = [k for k in "ABCDEF" if frage.get(k, "").strip()]
        if frage.get("Frage", "").strip() and len(optionen) >= 2 and richtig and set(richtig) <= set(optionen):
            frage["Richtig"] = ", ".join(richtig)
            akt["fragen"].append(frage)
        else:
            akt["kaputt"] += 1
        frage = None

    for roh in text.splitlines():
        zeile = _RAND.sub("", roh)
        if not zeile or zeile.startswith("```") or zeile == "---":
            feld = None if zeile == "---" else feld
            continue
        if _KOPF.match(zeile):
            abschliessen()
            teile = [t.strip() for t in zeile.split("|")]
            if teile[0].upper() == "ANKI" and len(teile) >= 3 and teile[1] and teile[2] and not any(_PLATZHALTER.search(t) for t in teile):
                akt = {"fach": teile[1], "block": "|".join(teile[2:]).strip(), "fragen": [], "kaputt": 0}
                abschnitte.append(akt)
            else:
                akt = None
            feld = None
            continue
        if akt is None:
            continue
        m = _FELD.match(zeile)
        if m:
            wert = m.group(5)
            if m.group(1):
                abschliessen()
                frage, feld = {"Frage": wert}, "Frage"
            elif frage is not None:
                feld = m.group(2).upper() if m.group(2) else ("Richtig" if m.group(3) else "Erklärung")
                frage[feld] = wert
            continue
        if frage is not None and feld:
            frage[feld] = (frage.get(feld, "") + "\n" + zeile).strip()
    abschliessen()

    for a in abschnitte:
        for f in a["fragen"]:
            f["ID"] = karten_id(a["fach"], a["block"], f["Frage"])
            for k in list(f):
                if k not in ("ID", "Richtig"):
                    f[k] = _html(f[k]).replace("\n", "<br>")
    return [a for a in abschnitte if a["fragen"] or a["kaputt"]]


# Deckliste: eigene Reihenfolge und ausgeblendete Decks
##########################################################################


def _natuerlich(name: str):
    """"B2" vor "B10", Gross/Klein egal. Decks mit Stern (⭐ Wichtig) zuerst."""
    if name.startswith("⭐"):
        return ["", -1, name.lower()]
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name.lower())]


def ordne(kinder: list[tuple[int, str]], reihe: list[int]) -> list[int]:
    """Deck-Ids in Anzeige-Reihenfolge: erst die von Hand sortierten, dann der Rest natuerlich nach Namen."""
    da = {i for i, _ in kinder}
    vorne = [i for i in reihe if i in da]
    rest = sorted((k for k in kinder if k[0] not in vorne), key=lambda k: _natuerlich(k[1]))
    return vorne + [i for i, _ in rest]


def verschiebe(reihe: list[int], did: int, ziel: int, wo: str) -> list[int]:
    """Legt did vor ("vor") oder hinter ("nach") ziel. Unbekannte Ids aendern nichts."""
    if did == ziel or did not in reihe or ziel not in reihe:
        return list(reihe)
    neu = [i for i in reihe if i != did]
    pos = neu.index(ziel) + (1 if wo == "nach" else 0)
    neu.insert(pos, did)
    return neu
