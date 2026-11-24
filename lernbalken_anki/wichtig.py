"""Wichtige Fragen: Ankis eigenes Markieren (Tag "marked", Taste *) plus ein Filterdeck "<Fach>::⭐ Important".

Das Filterdeck sammelt die markierten Karten des Fachs erst, wenn man es oeffnet, und gibt sie zurueck,
sobald man wieder in der Deckliste ist. So fehlen markierte Karten nie in ihren Block-Decks.
"""

from __future__ import annotations

from anki.collection import SearchNode

NAME = "⭐ Important"
# shortcut: einmalige Umbenennung von "⭐ Wichtig" (bis Version 1.7.1). Nach der Pruefung (26.11.2026)
# ALTER_NAME, umbenennen(), den Aufruf in __init__._profil_offen und test_wichtig_deck_umbenennen loeschen.
ALTER_NAME = "⭐ Wichtig"
TAG = "marked"


def umbenennen(col) -> int:
    """Benennt alte "<Fach>::⭐ Wichtig"-Filterdecks in "⭐ Important" um. Gibt es das neue schon,
    wird das alte geleert (Karten gehen nach Hause) und entfernt. Gibt die Zahl der alten Decks zurueck."""
    n = 0
    for d in col.decks.all_names_and_ids():
        teile = d.name.split("::")
        if len(teile) != 2 or teile[1] != ALTER_NAME or not col.decks.is_filtered(d.id):
            continue
        neu = f"{teile[0]}::{NAME}"
        if col.decks.id_for_name(neu):
            col.sched.empty_filtered_deck(d.id)
            col.decks.remove([d.id])
        else:
            col.decks.rename(d.id, neu)
        n += 1
    return n


def fach_von(col, card) -> str:
    return col.decks.name(card.odid or card.did).split("::")[0]


def suche(col, fach: str) -> str:
    return col.build_search_string(SearchNode(deck=fach), SearchNode(tag=TAG))


def deck_id(col, fach: str, erzeugen: bool = False):
    name = f"{fach}::{NAME}"
    did = col.decks.id_for_name(name)
    if did or not erzeugen:
        return did
    aktuell = col.decks.get_current_id()  # Anlegen waehlt das neue Deck aus, das soll beim Lernen nicht passieren
    # Das Anlegen passiert meist direkt nach dem Stern. Es haengt sich an dessen Undo-Schritt an: sonst naehme
    # Undo erst das Anlegen zurueck (und Anki spraenge in die Uebersicht des neuen Decks) statt den Stern.
    vorher = col.undo_status().last_step
    d = col.sched.get_or_create_filtered_deck(deck_id=0)
    d.name = name
    d.config.reschedule = True
    del d.config.search_terms[:]
    term = d.config.search_terms.add()
    term.search = suche(col, fach)
    term.limit = 9999
    term.order = 1  # zufaellig
    did = col.sched.add_or_update_filtered_deck(d).id
    col.sched.empty_filtered_deck(did)  # erst beim Oeffnen fuellen
    col.decks.select(aktuell)
    if vorher:
        col.merge_undo_entries(vorher)
    return did


def alle(col) -> list[tuple[int, str]]:
    """(Id, Fach) aller Wichtig-Decks."""
    aus = []
    for d in col.decks.all_names_and_ids():
        teile = d.name.split("::")
        if len(teile) == 2 and teile[1] == NAME and col.decks.is_filtered(d.id):
            aus.append((d.id, teile[0]))
    return aus


def fuellen(col, did) -> int:
    return col.sched.rebuild_filtered_deck(did).count


def leeren_alle(col) -> None:
    for did, _ in alle(col):
        if col.db.scalar("select 1 from cards where did = ? limit 1", did):
            col.sched.empty_filtered_deck(did)


def anzahl(col, fach: str) -> int:
    return len(col.find_cards(suche(col, fach)))


def faecher_mit_markierten(col) -> set[str]:
    dids = col.db.list(
        "select distinct case when c.odid then c.odid else c.did end from cards c join notes n on n.id = c.nid "
        "where n.tags like '% marked %'"
    )
    return {col.decks.name(d).split("::")[0] for d in dids}
