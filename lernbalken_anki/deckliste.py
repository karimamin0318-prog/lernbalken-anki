"""Deckliste: Decks per Ziehen sortieren und mit dem Auge ausblenden.

Gespeichert in der Sammlung (col config "lernbalken_decks"), also auch nach Neustart und Sync:
  {"reihe": {"<Eltern-Id>": [Deck-Ids ...]}, "aus": [Deck-Ids ...]}   Eltern-Id 0 = oberste Ebene
"""

from __future__ import annotations

import html
import json

from anki.decks import DeckTreeNode

from . import core

SCHLUESSEL = "lernbalken_decks"


def lies(col) -> dict:
    d = col.get_config(SCHLUESSEL, default=None) or {}
    reihe = {str(k): [int(i) for i in v] for k, v in (d.get("reihe") or {}).items()}
    return {"reihe": reihe, "aus": [int(i) for i in d.get("aus") or []]}


def schreibe(col, d: dict) -> None:
    col.set_config(SCHLUESSEL, d)


def baum_anpassen(top: DeckTreeNode, d: dict, anzeige=None) -> tuple[DeckTreeNode, dict, list]:
    """Kopie des Baums in eigener Reihenfolge und ohne ausgeblendete Decks.
    Gibt ausserdem die Eltern jedes sichtbaren Decks und die ausgeblendeten Decks (Id, voller Name) zurueck."""
    neu = DeckTreeNode()
    neu.CopyFrom(top)
    aus = set(d["aus"])
    eltern: dict[int, int] = {}
    versteckt: list[tuple[int, str]] = []

    def gehe(knoten: DeckTreeNode, pfad: str) -> None:
        kinder = {}
        for k in knoten.children:
            kopie = DeckTreeNode()
            kopie.CopyFrom(k)
            kinder[k.deck_id] = kopie
        reihe = core.ordne([(i, k.name) for i, k in kinder.items()], d["reihe"].get(str(knoten.deck_id), []))
        del knoten.children[:]
        for i in reihe:
            k = kinder[i]
            name = f"{pfad}::{k.name}" if pfad else k.name
            if i in aus:
                versteckt.append((i, name))
                continue
            eltern[i] = knoten.deck_id
            if anzeige:
                neu_name = anzeige(name, k)
                if neu_name:
                    k.name = neu_name
            gehe(k, name)
            knoten.children.append(k)

    gehe(neu, "")
    return neu, eltern, versteckt


def befehl(col, nachricht: str) -> bool:
    """Verarbeitet lb_ordnen / lb_aus / lb_ein aus der Deckliste. True, wenn neu gezeichnet werden soll."""
    teile = nachricht.split(":")
    d = lies(col)
    if teile[0] == "lb_aus" and len(teile) == 2:
        did = int(teile[1])
        if did not in d["aus"]:
            d["aus"].append(did)
    elif teile[0] == "lb_ein" and len(teile) == 2:
        d["aus"] = [i for i in d["aus"] if i != int(teile[1])]
    elif teile[0] == "lb_ordnen" and len(teile) == 5:
        # lb_ordnen:<eltern>:<deck>:<ziel>:<vor|nach>, dazu die aktuell sichtbare Reihenfolge aus dem Baum
        eltern, did, ziel, wo = int(teile[1]), int(teile[2]), int(teile[3]), teile[4]
        geschwister = _geschwister(col, eltern, d)
        d["reihe"][str(eltern)] = core.verschiebe(geschwister, did, ziel, wo)
    else:
        return False
    schreibe(col, d)
    return True


def _geschwister(col, eltern: int, d: dict) -> list[int]:
    """Alle Kinder (auch ausgeblendete) in der aktuellen Reihenfolge."""
    top = col.decks.deck_tree()
    knoten = top if eltern == 0 else col.decks.find_deck_in_tree(top, eltern)
    if knoten is None:
        return []
    return core.ordne([(k.deck_id, k.name) for k in knoten.children], d["reihe"].get(str(eltern), []))


AUGE = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/>'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>')
AUGE_ZU = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="none" stroke="currentColor" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M3 3l18 18M10.6 5.1A10.4 10.4 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>')


def html_dazu(eltern: dict, versteckt: list) -> tuple[str, str]:
    """(Skript fuer die Tabelle, Bereich "Ausgeblendete Decks" unter der Tabelle)."""
    skript = "<script>window.LB_DECKS = %s;</script>" % json.dumps(
        {"eltern": {str(k): v for k, v in eltern.items()}, "auge": AUGE}
    )
    if not versteckt:
        return skript, ""
    knoepfe = "".join(
        f'<button type="button" class="lb-aus-deck" title="Wieder einblenden" '
        f'onclick="return pycmd(\'lb_ein:{did}\')">{AUGE_ZU}<span>{html.escape(name.replace("::", " › "))}</span></button>'
        for did, name in sorted(versteckt, key=lambda v: core._natuerlich(v[1]))
    )
    bereich = (
        f'<details class="lb-aus"><summary>Ausgeblendete Decks ({len(versteckt)})</summary>'
        f'<div class="lb-aus-liste">{knoepfe}</div></details>'
    )
    return skript, bereich
