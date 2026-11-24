"""Filter beim Lernen: nur neue Karten (Speedrun) und/oder nur Single-/Multiple-Choice-Karten.

Anki laesst nur die Karte oben in seiner Warteschlange beantworten. Die Filter holen oft eine andere
(z. B. eine neue Karte ueber dem Tageslimit). Darum laeuft vor jeder Antwort auf eine gefilterte Karte frei(): das setzt
Ankis Warteschlange zurueck, ohne etwas an der Sammlung oder der Rueckgaengig-Kette zu aendern.
"""

from __future__ import annotations

import time

from anki.collection import SearchNode
from anki.scheduler_pb2 import QueuedCards

from .colops import MC_NAME

# Ganze Warteschlange von heute holen (Anki kappt selbst bei seinen Tageslimits)
GRENZE = 1000


def _mc_notizen(col) -> set[int]:
    mid = col.models.id_for_name(MC_NAME)
    return set(col.db.list("select id from notes where mid = ?", mid)) if mid else set()


def _eintrag(col, cid: int) -> QueuedCards.QueuedCard:
    """Eine Karte, die nicht aus Ankis Warteschlange kommt, mit ihren moeglichen naechsten Zustaenden."""
    e = QueuedCards.QueuedCard()
    e.card.CopyFrom(col._backend.get_card(cid))
    e.queue = {0: QueuedCards.NEW, 2: QueuedCards.REVIEW}.get(e.card.queue, QueuedCards.LEARNING)
    e.states.CopyFrom(col._backend.get_scheduling_states(cid))
    e.context.deck_name = col.decks.name(e.card.deck_id)
    e.context.seed = cid
    return e


def _passt_mc(col, cid: int) -> bool:
    suche = col.build_search_string(f"cid:{cid}", "-is:suspended", "-is:buried", SearchNode(note=MC_NAME))
    return bool(col.find_cards(suche))


def _neue(col, did: int, mc: bool) -> list[int]:
    """Noch nie gesehene Karten des Decks (mit Unterdecks), in Reihenfolge der Erstellung."""
    teile = [SearchNode(deck=col.decks.name(did)), "is:new", "-is:suspended", "-is:buried"]
    if mc:
        teile.append(SearchNode(note=MC_NAME))
    return list(col.find_cards(col.build_search_string(*teile), order="c.due, c.ord"))


def naechste(col, did: int, neu: bool, mc: bool, zuerst: int | None = None) -> QueuedCards | None:
    """Naechste Karte fuer die Filter, als Warteschlange mit genau dieser Karte oben.
    zuerst: diese Karte vorziehen, falls sie passt (eben zurueckgenommene Antwort)."""
    if neu:
        # Speedrun: alle neuen Karten, ohne Tageslimit
        cids = _neue(col, did, mc)
        if zuerst in cids:
            cids.remove(zuerst)
            cids.insert(0, zuerst)
        if not cids:
            return None
        q = QueuedCards(new_count=len(cids))
        q.cards.append(_eintrag(col, cids[0]))
        return q
    # Nur MC mit Ankis Planung: Ankis Warteschlange in ihrer Reihenfolge, Flashcards raus. Die Plaetze fuer neue
    # Karten (so viele, wie Ankis Tageslimit heute noch erlaubt) bekommen die naechsten neuen MC-Fragen, sonst
    # wuerden vorne liegende neue Flashcards das ganze Limit belegen.
    anki_q = col.sched.get_queued_cards(fetch_limit=GRENZE)
    mc_n = _mc_notizen(col)
    neue = iter(_neue(col, did, mc=True))
    treffer: list = []   # QueuedCard aus Ankis Warteschlange oder Id einer neuen MC-Frage
    for c in anki_q.cards:
        if c.queue == QueuedCards.NEW:
            cid = next(neue, None)
            if cid is not None:
                treffer.append(cid)
        elif c.card.note_id in mc_n:
            treffer.append(c)
    if zuerst and _passt_mc(col, zuerst):
        treffer = [t for t in treffer if (t if isinstance(t, int) else t.card.id) != zuerst]
        treffer.insert(0, zuerst)
    if not treffer:
        return None
    q = QueuedCards(
        new_count=sum(isinstance(t, int) for t in treffer),
        learning_count=sum(not isinstance(t, int) and t.queue == QueuedCards.LEARNING for t in treffer),
        review_count=sum(not isinstance(t, int) and t.queue == QueuedCards.REVIEW for t in treffer),
    )
    q.cards.append(_eintrag(col, treffer[0]) if isinstance(treffer[0], int) else treffer[0])
    return q


FREI = "lernbalkenFrei"


def frei(col, card, alt: int | None = None) -> int:
    """Ankis Warteschlange zuruecksetzen, damit jede Karte beantwortet werden darf.
    Dazu wird das Deck der Karte gespeichert (ein unsichtbarer Zeitstempel): jede Deck-Aenderung baut Ankis
    Warteschlange neu. Nicht extend_limits, das loescht Ankis ganze Undo-Liste (Undo ging dann nur einen Schritt).
    Gibt den Undo-Schritt zurueck; die Antwort wird danach mit merge_undo_entries angehaengt, so bleibt es
    ein Schritt mit Ankis Namen fuer Antworten.
    alt: Schritt einer frueheren Freigabe, deren Antwort fehlschlug. Liegt er noch oben, wird er weiterverwendet,
    statt einen zweiten (leeren) "Answer Card"-Schritt anzulegen, den Undo sonst fuer eine Antwort hielte."""
    if alt and col.undo_status().last_step == alt:
        schritt = alt
    else:
        schritt = col.add_custom_undo_entry(col.tr.actions_answer_card())
    deck = col.decks.get(card.did)
    deck[FREI] = int(time.time() * 1000)
    col.decks.save(deck)
    col.merge_undo_entries(schritt)
    return schritt
