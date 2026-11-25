**ton**: `true` = kurzes Glitzer-Klingeln bei jeder richtigen Antwort, `false` = still.

**lautstaerke**: 0 bis 1.

**modus**: `"eigen"` = eigene Zeiten (5 Min, 30 Min, 3 Std, Morgen, 3 Tage, Fertig), `"anki"` = Ankis Planung. Lässt sich auch beim Lernen mit dem Schalter neben „More“ umstellen.

**tageswechsel_erledigt**: wird vom Add-on gesetzt, nachdem es den Tageswechsel einmal auf 0 Uhr gestellt hat. Danach kannst du ihn in Ankis Einstellungen wieder frei ändern.

**abdecken**: `true` = Abdeckungen beim Lernen zeigen, `false` = alle ausgeblendet. Lässt sich auch mit dem Schalter neben „Abdecken“ im Balken umstellen.

**nur_neu**: `true` = Speedrun: beim Lernen kommen nur Karten, die du noch nie gesehen hast, ohne Tageslimit. Lässt sich auch mit „New only“ im Balken umschalten.

**nur_mc**: `true` = nur Single- und Multiple-Choice-Fragen, keine Flashcards. Lässt sich auch mit „MC only“ im Balken umschalten. Geht zusammen mit `nur_neu`.

**nur_neu_seit**: wird vom Add-on gesetzt, wenn du „New only“ einschaltest (Zeit in ms). Ab da zählt der Balken den Speedrun: Karten, die damals noch neu waren. `0` = ab heute 0 Uhr.

**bilder_ganz**: `true` = Ankis Image Occlusion wird pro Bild gelernt: nur eine Karte pro Bild (die übrigen Box-Karten setzt das Add-on aus), alle Boxen sind zu und lassen sich einzeln anklicken (Klick = auf, nochmal Klick = wieder zu), die Zeit-Knöpfe sind sofort da. `false` = Ankis normales Verhalten (ausgesetzte Karten bleiben ausgesetzt, die kannst du im Browser wieder aktivieren).
