# Lernbalken für Anki

Add-on für Anki 25.09. Läuft für sich allein, die Lernbalken-App braucht es nicht.

## Download und Installation (Windows und Mac)

1. **Anki installieren** (kostenlos): [apps.ankiweb.net](https://apps.ankiweb.net), Version 25.09 oder neuer. Auf dem Mac die Datei öffnen und Anki in den Ordner „Programme“ ziehen.
2. **Add-on herunterladen:** [lernbalken.ankiaddon](https://github.com/karimamin0318-prog/lernbalken-anki/releases/latest/download/lernbalken.ankiaddon)
3. **Installieren:** Anki öffnen → *Tools → Add-ons → Install from file…* (Mac: *Extras → Add-ons* bzw. *Tools → Add-ons*) → die heruntergeladene Datei wählen. Alternativ die Datei einfach doppelklicken.
4. **Anki neu starten.** Fertig: beim Lernen erscheint oben der Balken.

Die Fragen selbst sind nicht dabei, sie kommen als `.apkg` (Datei → Importieren). Mit eigenen Decks funktioniert alles außer den Ankreuzfragen, denn die brauchen die Kartentypen aus der `.apkg`.

**Eigene Fragen mit einer KI erstellen:** Im Ordner [`fragen-erstellen`](fragen-erstellen) liegen `ANLEITUNG-FUER-DIE-KI.md` und `baue_deck.py`. Beide Dateien zusammen mit den Lernunterlagen in eine KI hochladen, die Code ausführen kann (z. B. ChatGPT oder Claude), und schreiben: „Lies die Anleitung und mach mir Anki-Fragen zu diesen Unterlagen.“ Die KI gibt eine `.apkg` zurück, die man in Anki importiert. Damit kommen auch die Kartentypen für die Ankreuzfragen mit.

**Neue Version bauen:** `python bauen.py` legt `dist/lernbalken.ankiaddon` an, die dann als Release auf GitHub hochgeladen wird.

## Installation von Hand (für Entwickler oder eine AI)

1. Anki 25.09 installieren und einmal starten, dann Anki schließen.
2. Dieses Repo klonen oder als ZIP herunterladen.
3. Den Ordner `lernbalken_anki` (nur diesen, nicht das ganze Repo) in den Add-on-Ordner von Anki kopieren. Der Ordnername bleibt `lernbalken_anki`:
   - Windows: `%APPDATA%\Anki2\addons21\lernbalken_anki`
   - macOS: `~/Library/Application Support/Anki2/addons21/lernbalken_anki`
   - Linux: `~/.local/share/Anki2/addons21/lernbalken_anki`
4. Anki starten. Unter Tools → Add-ons steht jetzt „Lernbalken“.
5. Fragen importieren: Datei → Importieren → die `.apkg` mit den Fragen wählen. Die Kartentypen „Lernbalken MC“ und „Lernbalken Karte“ kommen mit der apkg, das Add-on legt keine eigenen an.
6. Deck anklicken, „Study Now“. Zum schnellen Durchgehen aller Fragen oben im Balken „New only“ (Blitz) einschalten, für nur Ankreuzfragen zusätzlich „MC only“.

Die Fragen selbst sind nicht in diesem Repo, sie kommen als `.apkg`.

## Was es kann

- **Kartentypen** (kommen mit der apkg, mit festen Ids; das Add-on legt selbst keine an, hält aber ihr Aussehen auf dem Stand von `lernbalken_anki/karte/`):
  - **Lernbalken MC:** Single und Multiple Choice zum Anklicken. Felder `Frage`, `A` bis `F`, `Richtig` (`B` oder `A, C`), `Erklärung`, `Quelle`, `ID`. Die Antworten werden gemischt, die Rückseite zeigt richtig, falsch und verpasst.
  - **Lernbalken Karte:** Flashcard. Felder `Frage`, `Antwort`, `Quelle`, `ID`. Fett geschriebene Wörter in der Antwort erscheinen grün.
- **Fortschrittsbalken beim Lernen:** oben im Lernfenster und in der Deck-Übersicht. Bei jeder richtigen Antwort lädt er weiter, glitzert, zeigt +1 und klingelt kurz. Alle 5 richtigen in Folge gibt es „5 streak“. Die Prozentzahl steht rechts direkt an der Spur, die Knöpfe New only, MC only, Cover, Vocab und Important oben rechts. Bei „Nochmal“ passiert nichts. Was er misst: wie viel vom gewählten Deck (mit allen Unterdecks) heute erledigt ist. Kräftiges Grün = für heute fertig (Tomorrow, 3 days, Done oder bei Anki ein Abstand ab morgen), helles, halb durchsichtiges Grün dahinter = gerade in Arbeit (5 min, 30 min, 3 h), leer = heute noch zu tun (neu oder heute fällig). Die Prozentzahl zählt nur das kräftige Grün, unten links steht dasselbe fürs ganze Fach.
- **Important:** Der Stern „Important“ im Balken (oder die Taste `*`) markiert die Frage mit Ankis eigener Markierung. Pro Fach gibt es dann ein Deck `⭐ Important (n)` ganz oben (hieß bis 1.7.1 `⭐ Wichtig`, wird beim Start einmal umbenannt). Es sammelt die markierten Karten erst beim Öffnen ein und gibt sie zurück, sobald du wieder in der Deckliste bist. In ihren Blöcken fehlen sie also nie.
- **Eigene Zeiten:** Links neben „More“ schaltet „Anki | Custom“ zwischen Ankis Planung und festen Zeiten um (gespeichert, ab Werk „Custom“). Im eigenen Modus gibt es nach dem Aufdecken sechs Knöpfe, auch über die Tasten 1–6: **5 min, 30 min, 3 h** (Lernkarte auf die Minute genau), **Tomorrow, 3 days** (nächster Kalendertag bzw. in drei Tagen) und **Done** (kommt in zehn Jahren wieder, zählt im Balken als gelernt). Anki beantwortet die Karte trotzdem normal (Statistik, „today“, Glitzer), danach legt das Add-on sie auf die gewählte Zeit. 5 min zählt als „nicht gewusst“ (kein Glitzer). Leertaste = Tomorrow. Beim ersten Start stellt das Add-on Ankis Tageswechsel einmal auf 0 Uhr.
- **Deckliste sortieren:** Ein Deck auf ein anderes derselben Ebene ziehen, die blaue Linie zeigt, wo es landet. Auf ein Deck einer anderen Ebene gezogen wird es wie in Anki üblich zum Unterdeck. Nie sortierte Decks stehen in natürlicher Reihenfolge (B2 vor B10).
- **Decks ausblenden:** Auge neben dem Zahnrad. Ganz unten öffnet „Hidden decks (n)“ die Liste zum Wiedereinblenden.
- **Total:** In der Deckliste steht nach New / Learn / Due die Spalte „Total“ mit allen Karten des Decks samt Unterdecks.
- **New only (Speedrun):** Schalter mit Blitz oben im Balken. An: es kommen nur Karten, die du noch nie gesehen hast, ohne Tageslimit, in der Reihenfolge, in der sie angelegt wurden. Jede beantwortete Karte ist danach nicht mehr neu und kommt in diesem Modus nicht wieder. So läufst du einmal schnell durch alle Fragen. Achtung: diese Karten zählen trotzdem für Ankis Tageslimit neuer Karten.
- **MC only:** Schalter daneben. An: nur Single- und Multiple-Choice-Fragen (Kartentyp „Lernbalken MC“), keine Flashcards. Allein mit Ankis bzw. deiner eigenen Planung, zusammen mit „New only“ alle neuen MC-Fragen. Beide Schalter werden gespeichert und stehen auch in der Deck-Übersicht (vor „Study Now“) zum Umschalten; ist einer an, steht dort ein Hinweis, denn Ankis Zahlen oben zählen trotzdem alle Karten. Der Balken folgt den Schaltern: Mit „MC only“ zählt er nur MC-Fragen, mit „New only“ zeigt er den Speedrun (von den Karten, die beim Einschalten noch neu waren: kräftig = mit Tomorrow oder später beantwortet, hell = mit 5 min / 30 min / 3 h, leer = noch nicht gesehen; jedes Einschalten startet neu), mit beiden nur die neuen MC-Fragen.
- **Undo:** Unten links neben „Edit“. Geht Schritt für Schritt zurück, bis zu 30 Antworten (mehr hält Anki nicht), auch mit New only / MC only: Auf der Rückseite zurück zur Frage. Auf der Frage nimmt es die Antwort der vorigen Karte zurück, die dann wieder mit Rückseite dasteht, damit du die Zeit neu wählen kannst. MC-Karten behalten dabei Reihenfolge und Auswahl (die letzten 30 werden gemerkt). Anderes (Stern, Bild verschoben) nimmt es mit Ankis Rückgängig zurück. Das Füllen und Leeren des Important-Decks nimmt es nicht zurück (dort ist dann Schluss).
- **Redo:** Rechts neben Undo, grau, solange es nichts wiederherzustellen gibt. Nach einem oder mehreren Undo geht es damit Schritt für Schritt wieder nach vorne (Rückseite wieder zeigen, Antwort wieder setzen). Sobald du etwas Neues machst (z. B. eine Karte beantwortest), ist Redo wieder grau.
- **Cover:** Knopf „Cover“ im Balken, dann Text markieren: er wird lila abgedeckt. Mit gedrückter Strg-Taste markiert gehört er zur letzten Gruppe, ohne Strg ist es eine eigene. Klick auf eine Abdeckung deckt die ganze Gruppe auf (nochmal Klick: wieder zu). Rechtsklick bei aktivem Werkzeug löscht die Gruppe. Der Schalter daneben blendet alle Abdeckungen aus und wieder ein. Gemerkt wird pro Frage (unter `lernbalken_abdeckung`).
- **Vokabeln:** Beim Lernen ein Wort markieren, am Text erscheint „+ Vocab“: Wort und Erklärung eintragen. „Vocab“ im Balken (und „Vocabulary (n)“ in der Deckliste) öffnet „List“ mit Suche, Bearbeiten und Löschen, und „Quiz“: Wort sehen, Leertaste zeigt die Erklärung, 1 = Again, 2 = Got it. Gespeichert unter `lernbalken_vokabeln`.
- **Bilder verschieben und skalieren:** Im Editor Bild anklicken, beim Lernen Bild doppelklicken: Es erscheint ein lila Rahmen. Ziehen legt das Bild frei an genau diese Stelle (auch seitlich über die Karte hinaus bis zum Fensterrand; links und Breite in Prozent der Feldbreite, oben in Pixeln, so sieht es im schmaleren Editor und auf der Karte gleich aus), die Griffe an allen vier Ecken machen es größer oder kleiner (die gegenüberliegende Ecke bleibt stehen), ↺ setzt es zurück in den Text, Esc oder ein Klick daneben schließt den Rahmen. Im Editor löscht Entf das Bild. Beim Lernen wird die Änderung in der Notiz gespeichert, jede als eigener Undo-Schritt („Move image“).
- **Bilder abfragen (Image Occlusion):** Ankis eigene Funktion zum Anlegen: Hinzufügen → Notiztyp „Image Occlusion“ → Bild wählen → Boxen ziehen. Gelernt wird pro Bild statt pro Box: Das Add-on lässt pro Bild nur eine Karte aktiv und setzt die übrigen Box-Karten aus (auch bei schon vorhandenen Bildern, nichts muss neu angelegt werden). Beim Lernen sind alle Boxen zu, die Zeit-Knöpfe sind sofort da. Klick auf eine Box deckt sie auf (gestrichelter Rand bleibt), nochmal Klick deckt sie wieder zu. Boxen, die du in Anki zu einer Gruppe gemacht hast, gehen zusammen auf. Fehlt einem Bild die aktive Karte (z. B. nach „Empty Cards“), wird die nächste vom Add-on ausgesetzte wieder aktiv. Abschalten mit `bilder_ganz: false` in der Config (ausgesetzte Karten dann im Browser wieder aktivieren).

Gespeichert wird alles in der Sammlung selbst (Reihenfolge und ausgeblendete Decks unter `lernbalken_decks`), also auch nach Neustart und Sync.

**Einstellungen:** Anki → Tools → Add-ons → Lernbalken → Config (`ton`, `lautstaerke`, `modus`, `abdecken`, `bilder_ganz`).

**Tests:** `tests/test_addon.py` mit Ankis Python (Sammlung, Zeiten, Vokabeln, Total). `tests/lernen.html` prüft die Skripte im Lernfenster und Editor (Cover, Undo bei MC, Bilder, Image-Occlusion-Boxen): im Ordner `python -m http.server 8799` starten und `http://localhost:8799/tests/lernen.html` öffnen, oben steht OK oder FEHLER.

Die Knöpfe und Texte des Add-ons sind englisch, die Karteninhalte bleiben deutsch.

**Zum Weiterentwickeln** statt Kopieren eine Verknüpfung anlegen: `%APPDATA%\Anki2\addons21\lernbalken_anki` zeigt auf den Ordner hier. Änderungen am Code wirken nach einem Neustart von Anki.
