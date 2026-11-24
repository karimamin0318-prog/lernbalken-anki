"""Reine Logik ohne Anki-Abhaengigkeit: Lernbalken-Datei lesen, Decknamen ableiten, Fortschritt rechnen."""

from __future__ import annotations

import json
import os
import re

STANDARD_DATEI = os.path.join(os.path.expanduser("~"), "Lernbalken", "lernbalken.json")

# "LB1 B2 Gelenke & Knie" -> Teil "LB1", Block "B2 Gelenke & Knie". Kuerzel wie "VO3+4" gehen auch,
# genau wie im Lernbalken (KUERZEL in src/eingang.ts) und in baue_deck.py des Skills.
_MIT_TEIL = re.compile(r"^\s*(\S+)\s+([Bb]\d+)\b\s*(.*)$")
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


def karten_stand(typ: int, queue: int, due: int, heute: int) -> str | None:
    """Wo eine Karte heute steht. None = zaehlt nicht (ausgesetzt).
    "fest"  fuer heute erledigt (Tomorrow, 3 days, Done): kraeftiges Gruen
    "offen" gerade in Arbeit (5 min, 30 min, 3 h): helles Gruen
    "leer"  heute noch zu tun (neu oder heute faellig)"""
    if queue == -1:
        return None
    if typ in (1, 3):
        # queue 3 = Lernschritt von einem Tag oder mehr, due ist dann ein Tag (bei queue 1 eine Uhrzeit)
        return "fest" if queue == 3 and due > heute else "offen"
    if typ == 2 and due > heute:
        return "fest"
    return "leer"


def fortschritt(karten: list[tuple[int, int, int]], heute: int) -> tuple[float, float, int]:
    """Prozent fest, Prozent offen (je 0 bis 100) und Anzahl zaehlender Karten. karten: (type, queue, due)."""
    staende = [s for s in (karten_stand(*k, heute) for k in karten) if s]
    if not staende:
        return 0.0, 0.0, 0
    n = len(staende)
    return 100 * staende.count("fest") / n, 100 * staende.count("offen") / n, n


# Deckliste: eigene Reihenfolge und ausgeblendete Decks
##########################################################################


def _natuerlich(name: str):
    """"B2" vor "B10", Gross/Klein egal. Decks mit Stern (⭐ Important) zuerst."""
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
