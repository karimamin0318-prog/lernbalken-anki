# Lernbalken für Anki

Add-on für Anki 25.09.

- **Decks von selbst:** Es liest `C:\Users\<Name>\Lernbalken\lernbalken.json` und legt für jedes Fach die Decks an: `B-Lizenz › LB1 › B2 Gelenke & Knie`. Neue Blöcke tauchen innerhalb von zwei Sekunden auf, solange Anki läuft. Hat ein Block-Deck dieselbe Nummer, aber einen anderen Titel (`B02 …`, `B2 Alt`), wird es umbenannt statt doppelt angelegt. Gelöscht wird nie etwas.
- **Kartentypen** (kommen mit der apkg aus dem lernprojekt-Skill, mit festen Ids; das Add-on hält ihr Aussehen auf dem Stand von `lernbalken_anki/karte/`):
  - **Lernbalken MC:** Single und Multiple Choice zum Anklicken. Felder `Frage`, `A` bis `F`, `Richtig` (`B` oder `A, C`), `Erklärung`, `Quelle`, `ID`. Die Antworten werden gemischt, die Rückseite zeigt richtig, falsch und verpasst.
  - **Lernbalken Karte:** Flashcard. Felder `Frage`, `Antwort`, `Quelle`, `ID`. Fett geschriebene Wörter in der Antwort erscheinen grün.
- **Fortschrittsbalken beim Lernen:** oben im Lernfenster und in der Deck-Übersicht. Bei jeder richtigen Antwort lädt er weiter, glitzert, zeigt +1 und klingelt kurz. Alle 5 richtigen in Folge gibt es „5er Serie“. Bei „Nochmal“ passiert nichts. Was er misst: wie gut die Karten im gewählten Deck sitzen (neu 0, gerade gelernt 20 %, danach bis 100 % bei 21 Tagen Abstand).
- **Wichtig:** Der Stern „Wichtig“ im Balken (oder die Taste `*`) markiert die Frage mit Ankis eigener Markierung. Pro Fach gibt es dann ein Deck `⭐ Wichtig (n)` ganz oben. Es sammelt die markierten Karten erst beim Öffnen ein und gibt sie zurück, sobald du wieder in der Deckliste bist. In ihren Blöcken fehlen sie also nie.
- **Eigene Zeiten:** Links neben „More“ schaltet „Anki | Eigene“ zwischen Ankis Planung und festen Zeiten um (gespeichert, ab Werk „Eigene“). Im eigenen Modus gibt es nach dem Aufdecken sechs Knöpfe, auch über die Tasten 1–6: **5 Min, 30 Min, 3 Std** (Lernkarte auf die Minute genau), **Morgen, 3 Tage** (nächster Kalendertag bzw. in drei Tagen) und **Fertig** (kommt in zehn Jahren wieder, zählt im Balken als gelernt). Anki beantwortet die Karte trotzdem normal (Statistik, „heute“, Glitzer), danach legt das Add-on sie auf die gewählte Zeit. 5 Min zählt als „nicht gewusst“ (kein Glitzer). Leertaste = Morgen. Beim ersten Start stellt das Add-on Ankis Tageswechsel einmal auf 0 Uhr.
- **Deckliste sortieren:** Ein Deck auf ein anderes derselben Ebene ziehen, die blaue Linie zeigt, wo es landet. Auf ein Deck einer anderen Ebene gezogen wird es wie in Anki üblich zum Unterdeck. Nie sortierte Decks stehen in natürlicher Reihenfolge (B2 vor B10).
- **Decks ausblenden:** Auge neben dem Zahnrad. Ganz unten öffnet „Ausgeblendete Decks (n)“ die Liste zum Wiedereinblenden.
- **Fragen aus der Zwischenablage** (älterer Weg): Ein kopierter `ANKI | Fach | Block`-Block landet über den Lernbalken in `%USERPROFILE%\Lernbalken\anki-eingang\` und wird von hier ins passende Deck importiert.

Gespeichert wird alles in der Sammlung selbst (Reihenfolge und ausgeblendete Decks unter `lernbalken_decks`), also auch nach Neustart und Sync.

**Einstellungen:** Anki → Tools → Add-ons → Lernbalken → Config (`ton`, `lautstaerke`, `lernbalken_datei`).

**Installiert** ist es als Verknüpfung: `%APPDATA%\Anki2\addons21\lernbalken_anki` zeigt auf den Ordner hier. Änderungen am Code wirken nach einem Neustart von Anki. Ändert sich etwas an den Kartenvorlagen, danach `npm run skill` im Lernbalken-Ordner, damit der Skill dieselben Vorlagen in seine apkg packt.
