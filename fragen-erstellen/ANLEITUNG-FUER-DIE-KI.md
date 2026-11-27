# Anleitung für die KI: Anki-Fragen für das Lernbalken-Add-on erstellen

Du bekommst diese Datei, `baue_deck.py` und Lernunterlagen (Skript, Folien, PDF). Deine Aufgabe: aus den Unterlagen Fragen erstellen und daraus eine Anki-Datei (`.apkg`) bauen, die ich herunterlade und in Anki importiere. In meinem Anki läuft das Add-on „Lernbalken“, es zeigt Single und Multiple Choice zum Anklicken und Flashcards mit grün hervorgehobenen Stichwörtern.

**Wichtig:** Die `.apkg` nur mit `baue_deck.py` bauen (Python, nur Standardbibliothek). Keine eigene apkg mit genanki, keine CSV, keine anderen Kartentypen, sonst erkennt das Add-on die Karten nicht. Kannst du keinen Code ausführen, sag es mir sofort.

## Vor dem Erstellen kurz fragen (wenn ich es nicht schon gesagt habe)
- Fragetyp: nur Single Choice, nur Multiple Choice, nur Flashcards, Single + Multiple, oder Mix.
- Menge: wenig (nur das Wichtigste), mittel oder viel (alles bis ins Detail). Nenn mir grob die Kartenzahl.
- Wie das Fach heißen soll (wird der oberste Deckname).

## Regeln für gute Fragen
- **Nur aus den Unterlagen.** Nichts erfinden. Bist du unsicher, sag es. Jede Karte bekommt die Fundstelle in `quelle` ("S. 12" oder "Folie 5"), aber keine Fragen nach Seitenzahlen.
- **Jede Vorderseite ist eine vollständige Frage**, nie nur ein Begriff. Falsch: "Zytoplasma". Richtig: "Was ist das Zytoplasma und wovon ist es umgeben?"
- **Aufzählungen** (alle Phasen von X, die 5 Prinzipien von Y) sind immer Flashcards, weil man sie nur durch Auswendiglernen behält.
- **Flashcards:** kurze Antwort, mehrere Teile als Zeilen mit "- ". Die 1 bis 4 Schlüsselwörter **fett** (erscheinen grün), keine ganzen Sätze fett.
- **Choice:** 3 bis 5 Optionen, falsche Antworten plausibel, keine Fangfragen, kein "alle genannten", die Frage verrät die Lösung nicht. Multiple Choice hat mindestens 2 richtige Antworten. Nicht in die Frage schreiben, wie viele richtig sind.
- Jede Choice-Frage bekommt eine kurze `erklaerung`, warum die Lösung stimmt.

## Die richtige Antwort darf man nicht an der Form erkennen
Ich soll die Antwort aus Wissen ableiten, nicht an Länge oder Aufbau der Optionen erraten. Prüf jede Frage auf diese Muster:
- **Länge:** Optionen etwa gleich lang, oder die richtige ist mal die kürzeste, mal mittel, mal die längste. "Die längste, genaueste Option ist richtig" ist verboten. Lieber die falschen Optionen genauso detailliert formulieren.
- **Klammern:** Erklärende Klammern sind gut, aber bei allen passenden Optionen, richtigen wie falschen. Nie hat nur die richtige eine Klammer (oder nur die richtige keine).
- **Weitere Muster:** Nicht nur die richtige Option enthält Fachbegriffe, Zahlen oder Beispiele. Nicht nur die richtige ist vorsichtig formuliert ("meist") und die falschen absolut ("immer", "nie"). Die richtige wiederholt nicht Wörter aus der Frage. Die Position der richtigen Buchstaben wechselt (bei Multiple Choice auch Anzahl und Position).
- **Selbsttest:** Könnte jemand ohne jedes Fachwissen allein an Form, Länge oder Formulierung die richtige Antwort erraten? Wenn ja, umschreiben.

## Bauen
1. Alle Karten in eine Datei `karten.json` schreiben (Zeilenumbrüche in `antwort` als `\n`):

```json
{
  "fach": "Biologie",
  "karten": [
    {"block": "B1 Zelle", "typ": "single", "frage": "...", "optionen": ["...", "...", "...", "..."], "richtig": "B", "erklaerung": "...", "quelle": "S. 8"},
    {"block": "B1 Zelle", "typ": "multi", "frage": "...", "optionen": ["...", "...", "...", "..."], "richtig": "A, C", "erklaerung": "...", "quelle": "S. 9"},
    {"block": "B2 Gewebe", "typ": "karte", "frage": "Welche vier Gewebearten gibt es?", "antwort": "- **Epithelgewebe**\n- **Bindegewebe**\n- ...", "quelle": "S. 14"}
  ]
}
```

   - `typ`: `single`, `multi` oder `karte` (Flashcard).
   - `richtig`: Buchstaben der Optionen in der angegebenen Reihenfolge (A = erste). Das Add-on mischt die Optionen beim Lernen selbst.
   - `block`: Thema bzw. Kapitel. Daraus werden Unterdecks (Fach::B1 Zelle). Gleiche Schreibweise für alle Karten eines Blocks.
   - optional `"kern": true` für die wichtigsten Karten: Sie landen im Unterdeck "0 Kernwissen".
2. Ausführen: `python baue_deck.py karten.json <Fach>.apkg`
3. Mir die `.apkg` zum Herunterladen geben und sagen, wie viele Karten pro Block. Meldet das Skript übersprungene Karten, die Fehler beheben und neu bauen.

Ich importiere die Datei in Anki mit Doppelklick oder *Datei → Importieren*. Dieselbe Frage im selben Block nochmal importiert gibt keine doppelte Karte.
