"""Alles, was die Anki-Sammlung anfasst. Bekommt die Sammlung (col) uebergeben, braucht kein Fenster."""

from __future__ import annotations

import os
import re

from anki.utils import ids2str

from .core import anteile, karten_stand, speedrun_stand

MC_NAME = "Lernbalken MC"
KARTE_NAME = "Lernbalken Karte"
_HIER = os.path.dirname(__file__)


# Fortschritt
##########################################################################


def _deck_ids(col, did) -> str:
    return ids2str(col.decks.deck_and_child_ids(did))


def deck_fortschritt(col, did, mc: bool = False, neu_seit: int | None = None) -> tuple[float, float, int]:
    """(Prozent fest, Prozent offen, Anzahl) fuer das Deck mit Unterdecks.
    mc: nur MC-Fragen. neu_seit (ms): Speedrun, nur Karten, die seit dann zum ersten Mal drankamen oder noch neu sind."""
    ids = _deck_ids(col, did)
    wo = f"(c.did in {ids} or c.odid in {ids})"
    if mc:
        mid = col.models.id_for_name(MC_NAME)
        if not mid:
            return 0.0, 0.0, 0
        wo += f" and n.mid = {int(mid)}"
    erste = "(select min(r.id) from revlog r where r.cid = c.id)" if neu_seit is not None else "null"
    # In Filterdecks (Important) steht der echte Faelligkeitstag in odue
    karten = col.db.all(
        f"select c.type, c.queue, case when c.odid and c.odue then c.odue else c.due end, {erste} "
        f"from cards c join notes n on n.id = c.nid where {wo}"
    )
    heute = col.sched.today
    if neu_seit is None:
        return anteile(karten_stand(int(t), int(q), int(d), heute) for t, q, d, _ in karten)
    return anteile(speedrun_stand(int(t), int(q), int(d), heute, e, neu_seit) for t, q, d, e in karten)


def richtig_heute(col, did) -> int:
    ids = _deck_ids(col, did)
    start = (col.sched.day_cutoff - 86400) * 1000
    return col.db.scalar(
        f"""select count() from revlog r join cards c on c.id = r.cid
        where r.id > ? and r.ease > 1 and r.type < 4
        and (c.did in {ids} or c.odid in {ids})""",
        start,
    ) or 0


def balken_daten(col, did, mc: bool = False, neu_seit: int | None = None) -> dict | None:
    """Zahlen fuer den Balken. mc und neu_seit wie bei deck_fortschritt (Schalter MC only / New only)."""
    deck = col.decks.get(did, default=False)
    if not deck:
        return None
    name = deck["name"]
    teile = name.split("::")
    pct, offen, n = deck_fortschritt(col, did, mc, neu_seit)
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
            fpct, _, _ = deck_fortschritt(col, fach_id, mc, neu_seit)
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


def kartentypen_auffrischen(col) -> None:
    """Bringt die vorhandenen Kartentypen auf den Stand."""
    for n in KARTENTYPEN:
        kartentyp(col, n)


# Image Occlusion: ein Bild = eine Karte
##########################################################################
# Anki macht aus jeder Box (Gruppe) eines Bildes eine eigene Karte. Gelernt wird hier pro Bild: die Karte mit der
# kleinsten Nummer bleibt, alle anderen Karten derselben Notiz werden ausgesetzt. Das Lernfenster zeigt auf der
# verbliebenen Karte alle Boxen zum Anklicken (web/bildmasken.js). Bestehende Notizen bleiben, wie sie sind.

IO_ART = 6   # StockNotetype.OriginalStockKind.ORIGINAL_STOCK_KIND_IMAGE_OCCLUSION


def ist_bildtyp(m) -> bool:
    if not m:
        return False
    if m.get("originalStockKind") == IO_ART:
        return True
    return bool(m.get("tmpls")) and "image-occlusion" in m["tmpls"][0].get("qfmt", "")


def bildtyp_ids(col) -> list[int]:
    return [m["id"] for m in col.models.all() if ist_bildtyp(m)]


def bildkarten_zusammenfassen(col) -> int:
    """Setzt pro Image-Occlusion-Notiz alle nicht ausgesetzten Karten aus bis auf die mit der kleinsten Nummer.
    Notizen, deren Karten schon alle ausgesetzt sind, bleiben in Ruhe. Kein eigener Rueckgaengig-Schritt: das Aussetzen
    gehoert zum letzten Schritt (meist "Notiz hinzufuegen"). skip_undo_entry ginge nicht, das leert Ankis ganze Undo-Liste.
    Gibt zurueck, wie viele Karten ausgesetzt wurden."""
    mids = bildtyp_ids(col)
    if not mids:
        return 0
    ids = col.db.list(
        "select c.id from cards c join notes n on n.id = c.nid "
        f"where n.mid in {ids2str(mids)} and c.queue != -1 "
        "and c.ord > (select min(c2.ord) from cards c2 where c2.nid = c.nid and c2.queue != -1)"
    )
    if not ids:
        return 0
    karten = [col.get_card(i) for i in ids]
    for k in karten:
        k.queue = -1
    letzter = col.undo_status().last_step
    if letzter:
        col.update_cards(karten)
        try:
            col.merge_undo_entries(letzter)
        except Exception:
            pass   # letzter Schritt war selbst ein Undo/Redo: dann bleibt es ein eigener Schritt "Update Card"
    else:
        col.update_cards(karten, skip_undo_entry=True)
    return len(karten)
