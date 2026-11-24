"""Alles, was die Anki-Sammlung anfasst. Bekommt die Sammlung (col) uebergeben, braucht kein Fenster."""

from __future__ import annotations

import os
import re

from anki.utils import ids2str

from .core import deck_plan, fortschritt

MC_NAME = "Lernbalken MC"
KARTE_NAME = "Lernbalken Karte"
_HIER = os.path.dirname(__file__)


# Decks
##########################################################################


def sync_decks(col, daten: dict) -> list[str]:
    """Legt fehlende Decks an. Umbenannte Bloecke (gleiches Kuerzel, neuer Titel) werden umbenannt.
    Loescht nie etwas. Gibt die geaenderten Decknamen zurueck."""
    geaendert: list[str] = []
    for pfad, nr in deck_plan(daten):
        _, neu = deck_fuer(col, pfad, nr)
        if neu:
            geaendert.append("::".join(pfad))
    return geaendert


def deck_fuer(col, pfad: list[str], nr: str | None):
    """Id des Decks fuer diesen Pfad und ob es neu angelegt oder umbenannt wurde.
    Ein Deck mit gleichem Kuerzel (z. B. B2) unter demselben Teil gilt als dasselbe und wird umbenannt."""
    name = "::".join(pfad)
    did = col.decks.id_for_name(name)
    if did:
        return did, False
    alt = _deck_mit_kuerzel(col, "::".join(pfad[:-1]), nr) if nr and len(pfad) > 1 else None
    if alt:
        col.decks.rename(alt, name)
        return alt, True
    return col.decks.id(name, create=True), True


_NUMMER = re.compile(r"^\s*B(?:lock)?\s*0*(\d+)(?!\d)", re.I)


def _nummer(text: str) -> int | None:
    """"B2", "B02", "B02 Titel", "Block 2: Titel" -> 2"""
    m = _NUMMER.match(text)
    return int(m.group(1)) if m else None


def _deck_mit_kuerzel(col, eltern: str, nr: str):
    praefix = eltern.lower() + "::"
    gesucht = _nummer(nr)
    if gesucht is None:
        return None
    for d in col.decks.all_names_and_ids():
        if not d.name.lower().startswith(praefix):
            continue
        rest = d.name[len(praefix):]
        if "::" in rest:
            continue
        if _nummer(rest) == gesucht:
            return d.id
    return None


# Fortschritt
##########################################################################


def _deck_ids(col, did) -> str:
    return ids2str(col.decks.deck_and_child_ids(did))


def deck_fortschritt(col, did) -> tuple[float, float, int]:
    ids = _deck_ids(col, did)
    # In Filterdecks (Important) steht der echte Faelligkeitstag in odue
    karten = col.db.all(
        f"select type, queue, case when odid and odue then odue else due end from cards where did in {ids} or odid in {ids}"
    )
    return fortschritt([(int(t), int(q), int(d)) for t, q, d in karten], col.sched.today)


def richtig_heute(col, did) -> int:
    ids = _deck_ids(col, did)
    start = (col.sched.day_cutoff - 86400) * 1000
    return col.db.scalar(
        f"""select count() from revlog r join cards c on c.id = r.cid
        where r.id > ? and r.ease > 1 and r.type < 4
        and (c.did in {ids} or c.odid in {ids})""",
        start,
    ) or 0


def balken_daten(col, did) -> dict | None:
    deck = col.decks.get(did, default=False)
    if not deck:
        return None
    name = deck["name"]
    teile = name.split("::")
    pct, offen, n = deck_fortschritt(col, did)
    daten = {
        "name": teile[-1],
        "pfad": " › ".join(teile[:-1]),
        "pct": round(pct, 2),
        "offen": round(offen, 2),
        "karten": n,
        "fach": None,
        "fachPct": None,
        "heute": richtig_heute(col, did),
    }
    if len(teile) > 1:
        fach_id = col.decks.id_for_name(teile[0])
        if fach_id:
            fpct, _, _ = deck_fortschritt(col, fach_id)
            daten["fach"] = teile[0]
            daten["fachPct"] = round(fpct, 2)
    return daten


# Kartentypen
##########################################################################
# Die apkg aus dem lernprojekt-Skill bringt beide Kartentypen mit festen Ids mit. Das Add-on legt keine an
# (es kann keine festen Ids vergeben), sondern haelt Vorlagen und Design der vorhandenen auf dem Stand dieses Ordners.

KARTENTYPEN = {
    MC_NAME: {"vorne": "vorne.html", "hinten": "hinten.html"},
    KARTE_NAME: {"vorne": "karte_vorne.html", "hinten": "karte_hinten.html"},
}


def _lies(datei: str) -> str:
    with open(os.path.join(_HIER, "karte", datei), encoding="utf-8") as f:
        return f.read()


def kartentyp(col, name: str):
    """Den Kartentyp (aktuell gehalten) oder None, wenn es ihn (noch) nicht gibt."""
    mm = col.models
    art = KARTENTYPEN[name]
    vorne, hinten, css = _lies(art["vorne"]), _lies(art["hinten"]), _lies("stil.css")
    m = mm.by_name(name)
    if not m:
        return None
    t = m["tmpls"][0]
    if t["qfmt"] != vorne or t["afmt"] != hinten or m["css"] != css:
        t["qfmt"], t["afmt"], m["css"] = vorne, hinten, css
        mm.update_dict(m)
    return m


def kartentypen_auffrischen(col) -> list[str]:
    """Bringt die vorhandenen Kartentypen auf den Stand. Gibt die Namen der vorhandenen zurueck."""
    return [n for n in KARTENTYPEN if kartentyp(col, n) is not None]
