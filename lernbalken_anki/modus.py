"""Eigene Zeiten statt Ankis Planung.

Im eigenen Modus zeigt das Lernfenster sechs Knoepfe: 5 Min, 30 Min, 3 Std, Morgen, 3 Tage, Fertig.
Anki beantwortet die Karte trotzdem ganz normal (damit Statistik, "heute" und der Balken stimmen),
danach legt plane() die Karte genau auf die gewaehlte Zeit.
"""

from __future__ import annotations

import time

# (Schluessel, Beschriftung, Ease fuer Ankis Antwort)
ZEITEN = [
    ("5m", "5 Min", 1),
    ("30m", "30 Min", 2),
    ("3h", "3 Std", 3),
    ("1d", "Morgen", 3),
    ("3d", "3 Tage", 4),
    ("fertig", "Fertig", 4),
]
EASE = {k: e for k, _, e in ZEITEN}
# Antwort ohne Klick auf einen der Knoepfe (z. B. Leertaste): Ankis Ease -> eigene Zeit
AUS_EASE = {1: "5m", 2: "30m", 3: "1d", 4: "3d"}

SEKUNDEN = {"5m": 5 * 60, "30m": 30 * 60, "3h": 3 * 3600}
# Ganze Tage, "!" setzt auch den Abstand. "Fertig" = in zehn Jahren, zaehlt im Balken als voll gelernt.
TAGE = {"1d": "1!", "3d": "3!", "fertig": "3650!"}


def plane(col, card, wahl: str) -> None:
    """Legt die gerade beantwortete Karte auf die gewaehlte Zeit."""
    if wahl in SEKUNDEN:
        card.load()
        # Lernkarte mit genauer Uhrzeit. War sie schon gelernt, wird sie zur Wieder-Lernkarte.
        card.type = 3 if card.type in (2, 3) else 1
        card.queue = 1
        card.due = int(time.time()) + SEKUNDEN[wahl]
        card.left = 1
        col.update_card(card)
    elif wahl in TAGE:
        col.sched.set_due_date([card.id], TAGE[wahl])


def tageswechsel_mitternacht(col) -> bool:
    """Der neue Tag beginnt um 0 Uhr (Anki: 4 Uhr). Gibt True zurueck, wenn geaendert."""
    prefs = col.get_preferences()
    if prefs.scheduling.rollover == 0:
        return False
    prefs.scheduling.rollover = 0
    col.set_preferences(prefs)
    return True


KNOEPFE_CSS = """
<style>
#lb-zeiten td { padding: 0 3px; }
#lb-zeiten button { min-width: 74px; }
#lb-zeiten button.lb-fertig { color: #22c55e; }
</style>"""


def knoepfe_html() -> str:
    teile = []
    for i, (k, text, _) in enumerate(ZEITEN, 1):
        klasse = ' class="lb-fertig"' if k == "fertig" else ""
        teile.append(
            f'<td align=center><button{klasse} title="Taste {i}" '
            f"onclick='pycmd(\"lb_zeit:{k}\");'>{text}<span class=\"nobold\">{i}</span></button></td>"
        )
    return KNOEPFE_CSS + '<center><table id="lb-zeiten" cellpadding=0 cellspacing=0><tr>' + "".join(teile) + "</tr></table></center>"


def schalter_html(eigen: bool) -> str:
    an_e, an_a = ("an", "") if eigen else ("", "an")
    return f"""<style>
#lb-modus {{ display: inline-flex; vertical-align: top; margin: 0 6px 0 0; padding: 2px; gap: 2px;
  border: 1px solid var(--border); border-radius: 999px; background: var(--canvas-inset); }}
#lb-modus button, #lb-modus button:hover, #lb-modus button:active {{ margin: 0; border: 0; box-shadow: none;
  background: transparent; padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 600;
  color: var(--fg-subtle); cursor: pointer; }}
#lb-modus button:hover {{ color: var(--fg); }}
#lb-modus button.an, #lb-modus button.an:hover {{ background: var(--button-primary-bg); color: #fff; }}
</style><script>
// Rechts (Schalter + More) ist breiter als links (Edit). Beide Spalten gleich breit, dann sitzen die
// Antwortknoepfe in der Mitte des Fensters.
(function () {{
  function mitte() {{
    var t = document.querySelectorAll('#innertable > tbody > tr > td.stat');
    if (t.length < 2) return;
    // erst auf den Inhalt schrumpfen, dann beide auf die breitere Seite setzen
    t[0].style.whiteSpace = t[1].style.whiteSpace = 'nowrap';
    t[0].style.width = t[1].style.width = '1px';
    var w = Math.max(t[0].offsetWidth, t[1].offsetWidth);
    t[0].style.width = t[1].style.width = w + 'px';
  }}
  window.addEventListener('resize', mitte);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mitte); else setTimeout(mitte, 0);
}})();
</script><span id="lb-modus" title="Eigene feste Zeiten oder Ankis Planung">
<button class="{an_a}" onclick="pycmd('lb_modus:anki');">Anki</button>
<button class="{an_e}" onclick="pycmd('lb_modus:eigen');">Eigene</button></span>"""
