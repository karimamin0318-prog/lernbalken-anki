"""Reine Logik ohne Anki-Abhaengigkeit: Fortschritt rechnen, Decks sortieren."""

from __future__ import annotations

import re


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


def speedrun_stand(typ: int, queue: int, due: int, heute: int, erste: int | None, seit: int) -> str | None:
    """Stand im Speedrun (New only), nur Karten, die beim Einschalten noch neu waren:
    "leer" = noch neu, "offen" = gesehen und auf 5 min / 30 min / 3 h, "fest" = gesehen und Tomorrow oder spaeter
    (auch wenn sie inzwischen wieder faellig ist: fuer den Speedrun ist sie durch).
    None = gehoert nicht dazu (schon vorher gesehen oder ausgesetzt). erste = Zeit der ersten Antwort (ms)."""
    if queue == -1:
        return None
    if typ == 0:
        return "leer"
    if erste is None or erste < seit:
        return None
    return "offen" if karten_stand(typ, queue, due, heute) == "offen" else "fest"


def anteile(staende) -> tuple[float, float, int]:
    """Prozent fest, Prozent offen (je 0 bis 100) und Anzahl zaehlender Karten. None in staende zaehlt nicht."""
    staende = [s for s in staende if s]
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
