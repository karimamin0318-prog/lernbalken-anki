"""Wichtige Fragen: Ankis eigenes Markieren (Tag "marked", Taste *) plus ein Filterdeck "<Fach>::⭐ Wichtig".

Das Filterdeck sammelt die markierten Karten des Fachs erst, wenn man es oeffnet, und gibt sie zurueck,
sobald man wieder in der Deckliste ist. So fehlen markierte Karten nie in ihren Block-Decks.
"""

from __future__ import annotations

from anki.collection import SearchNode

NAME = "⭐ Wichtig"
TAG = "marked"


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
