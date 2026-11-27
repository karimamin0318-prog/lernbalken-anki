#!/usr/bin/env python3
"""Baut aus einer JSON-Datei mit Karten eine Anki-Datei (.apkg). Nur Python-Standardbibliothek.

    python baue_deck.py karten.json [ausgabe.apkg]

karten.json:
{
  "fach": "B-Lizenz",
  "karten": [
    {"block": "LB1 B1 Zelle & Knochen", "typ": "single", "frage": "...",
     "optionen": ["...", "...", "...", "..."], "richtig": "B",
     "erklaerung": "...", "quelle": "S. 8", "kern": false},
    {"block": "LB1 B1 Zelle & Knochen", "typ": "multi", "frage": "...",
     "optionen": ["...", "...", "...", "..."], "richtig": "A, C", "erklaerung": "...", "quelle": "S. 9"},
    {"block": "LB1 B2 Gelenke & Knie", "typ": "karte", "frage": "Welche sechs Gelenktypen gibt es?",
     "antwort": "- **Kugelgelenk** (Schulter, Hüfte)\\n- **Scharniergelenk** (Ellenbogen)\\n...", "quelle": "S. 14", "kern": true}
  ]
}

- block: genau der Blockname aus der BLOECKE-Zeile. Daraus wird das Deck Fach::LB1::B1 Zelle & Knochen.
- kern: true legt die Karte stattdessen in Fach::LB1::0 Kernwissen.
- **so** wird fett (bei Flashcards gruen hervorgehoben), Zeilen mit "- " werden zur Liste.
- Gleiche Frage im gleichen Block = gleiche Karte: erneutes Importieren aktualisiert statt zu verdoppeln.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))

# Feste Ids: so erkennt Anki die Kartentypen bei jedem Import wieder (muessen zum Lernbalken-Add-on passen).
MC = {"id": 1732300000101, "name": "Lernbalken MC",
      "felder": ["Frage", "A", "B", "C", "D", "E", "F", "Richtig", "Erklärung", "Quelle", "ID"],
      "vorne": "vorne.html", "hinten": "hinten.html"}
KARTE = {"id": 1732300000102, "name": "Lernbalken Karte",
         "felder": ["Frage", "Antwort", "Quelle", "ID"],
         "vorne": "karte_vorne.html", "hinten": "karte_hinten.html"}

_MIT_TEIL = re.compile(r"^\s*(\S+)\s+([Bb]\d+)\b\s*(.*)$")  # wie im Add-on (core.py) und Lernbalken
KERN = "0 Kernwissen"


def _sauber(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("::", ":")).strip()


def deck_pfad(fach: str, block: str, kern: bool) -> tuple[str, str]:
    """(Deckname, Block-Tag)."""
    m = _MIT_TEIL.match(block)
    if m:
        teil, nr, titel = m.group(1).upper(), m.group(2).upper(), _sauber(m.group(3))
        unten = KERN if kern else f"{nr} {titel}".strip()
        return f"{_sauber(fach)}::{teil}::{unten}", f"{teil}::{nr}"
    unten = KERN if kern else _sauber(block)
    return f"{_sauber(fach)}::{unten}", re.sub(r"\s+", "_", _sauber(block))


def karten_id(fach: str, block: str, frage: str) -> str:
    m = _MIT_TEIL.match(block)
    kenn = f"{m.group(1)} {m.group(2)}".lower() if m else re.sub(r"\s+", " ", block).strip().lower()
    roh = "|".join([re.sub(r"\s+", " ", fach).strip().lower(), kenn, re.sub(r"\s+", " ", frage).strip().lower()])
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def text(t: str | None) -> str:
    """Klartext mit **fett** und "- " Listen zu HTML."""
    if not t:
        return ""
    t = html.escape(str(t).strip(), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    aus, liste = [], []
    for zeile in t.split("\n"):
        m = re.match(r"^\s*(?:[-•*]|\d+[.)])\s+(.*)$", zeile)
        if m:
            liste.append(f"<li>{m.group(1)}</li>")
            continue
        if liste:
            aus.append("<ul>" + "".join(liste) + "</ul>")
            liste = []
        aus.append(zeile)
    if liste:
        aus.append("<ul>" + "".join(liste) + "</ul>")
    return "<br>".join(x for x in aus if x != "") if aus else ""


def _int_id(s: str) -> int:
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:13], 16)


# --- VORLAGEN: von `npm run skill` aus dem Anki-Add-on erzeugt, nicht von Hand aendern ---
VORLAGEN: dict[str, str] = {
 "hinten.html": "<div class=\"lbmc\" data-seite=\"hinten\" data-richtig=\"{{text:Richtig}}\" data-id=\"{{text:ID}}\">\n  <div class=\"lbmc-frage\">{{Frage}}</div>\n  <div class=\"lbmc-ergebnis\"></div>\n  <div class=\"lbmc-optionen\">\n    {{#A}}<div class=\"lbmc-opt\" data-k=\"A\">{{A}}</div>{{/A}}\n    {{#B}}<div class=\"lbmc-opt\" data-k=\"B\">{{B}}</div>{{/B}}\n    {{#C}}<div class=\"lbmc-opt\" data-k=\"C\">{{C}}</div>{{/C}}\n    {{#D}}<div class=\"lbmc-opt\" data-k=\"D\">{{D}}</div>{{/D}}\n    {{#E}}<div class=\"lbmc-opt\" data-k=\"E\">{{E}}</div>{{/E}}\n    {{#F}}<div class=\"lbmc-opt\" data-k=\"F\">{{F}}</div>{{/F}}\n  </div>\n  {{#Erklärung}}<div class=\"lbmc-erklaerung\">{{Erklärung}}</div>{{/Erklärung}}\n  {{#Quelle}}<div class=\"lb-quelle\">{{Quelle}}</div>{{/Quelle}}\n</div>\n<script>\n(function () {\n  var box = document.querySelector('.lbmc[data-seite=\"hinten\"]');\n  if (!box) return;\n  var richtig = (box.dataset.richtig || '').toUpperCase().match(/[A-F]/g) || [];\n  var id = box.dataset.id + '|' + box.querySelector('.lbmc-frage').textContent;\n  var zustand = window.__lbmc;\n  if (!zustand) { try { zustand = JSON.parse(sessionStorage.getItem('lbmc')); } catch (e) {} }\n  if (!zustand || zustand.id !== id) zustand = null;\n  var liste = box.querySelector('.lbmc-optionen');\n  var opts = Array.prototype.slice.call(liste.children);\n  if (zustand) {\n    zustand.reihe.forEach(function (k) {\n      var o = liste.querySelector('[data-k=\"' + k + '\"]');\n      if (o) liste.appendChild(o);\n    });\n  }\n  var wahl = zustand ? zustand.wahl : [];\n  opts.forEach(function (o) {\n    var k = o.dataset.k, istRichtig = richtig.indexOf(k) >= 0, gewaehlt = wahl.indexOf(k) >= 0;\n    if (istRichtig) o.classList.add(gewaehlt || !zustand ? 'richtig' : 'verpasst');\n    else if (gewaehlt) o.classList.add('falsch');\n  });\n  var erg = box.querySelector('.lbmc-ergebnis');\n  if (!zustand) { erg.textContent = ''; return; }\n  var treffer = wahl.length === richtig.length && wahl.every(function (k) { return richtig.indexOf(k) >= 0; });\n  if (!wahl.length) { erg.textContent = 'Nichts angeklickt'; erg.className += ' leer'; }\n  else if (treffer) { erg.textContent = 'Richtig'; erg.className += ' gut'; }\n  else { erg.textContent = 'Nicht ganz'; erg.className += ' daneben'; }\n})();\n</script>\n",
 "karte_hinten.html": "<div class=\"lbk\">\n  <div class=\"lbk-frage\">{{Frage}}</div>\n  <hr class=\"lbk-linie\">\n  <div class=\"lbk-antwort\">{{Antwort}}</div>\n  {{#Quelle}}<div class=\"lb-quelle\">{{Quelle}}</div>{{/Quelle}}\n</div>\n",
 "karte_vorne.html": "<div class=\"lbk\">\n  <div class=\"lbk-frage\">{{Frage}}</div>\n</div>\n",
 "stil.css": ".card {\n  font-family: \"Segoe UI\", system-ui, sans-serif;\n  font-size: 19px;\n  line-height: 1.45;\n  color: #1d1b26;\n  background: #f7f6fb;\n  text-align: left;\n}\n.card.nightMode { color: #ecebf3; background: #1b1a22; }\n\n.lbmc { max-width: 760px; margin: 0 auto; padding: 8px 4px 24px; }\n.lbmc-frage { font-size: 1.25em; font-weight: 600; margin-bottom: 4px; }\n.lbmc-hinweis { font-size: .85em; opacity: .6; margin-bottom: 12px; }\n\n.lbmc-optionen { display: flex; flex-direction: column; gap: 8px; }\n/* Antwortkaestchen. Anki hat fuer alle Knoepfe eigene Regeln (12px Schrift, 1px Rand und Schatten beim\n   Drueberfahren, Abstand aussen). Mit \".lbmc .lbmc-opt\" sind diese Regeln hier staerker, Vorder- und\n   Rueckseite sehen dadurch gleich aus und beim Drueberfahren aendert sich nur die Randfarbe. */\n.lbmc .lbmc-opt,\n.lbmc .lbmc-opt:hover,\n.lbmc .lbmc-opt:active,\n.lbmc .lbmc-opt:focus {\n  display: block; width: 100%; box-sizing: border-box; margin: 0;\n  text-align: left; font: inherit; font-size: 1.1em; font-weight: 400; line-height: 1.35; color: inherit;\n  padding: 15px 20px; border-radius: 12px;\n  border-width: 2px; border-style: solid;\n  background-image: none; background-clip: padding-box;\n  box-shadow: none; transform: none; outline: none;\n  -webkit-appearance: none; appearance: none;\n}\n.lbmc .lbmc-opt { border-color: #d4d0e2; background-color: #ffffff; }\n.nightMode .lbmc .lbmc-opt { border-color: #464354; background-color: #26252e; }\n.lbmc button.lbmc-opt { cursor: pointer; transition: border-color .12s ease; }\n.lbmc button.lbmc-opt:hover, .nightMode .lbmc button.lbmc-opt:hover { border-color: #8b6cff; }\n\n.lbmc .lbmc-opt.gewaehlt, .nightMode .lbmc .lbmc-opt.gewaehlt { border-color: #7c5cff; background-color: #ece7ff; }\n.nightMode .lbmc .lbmc-opt.gewaehlt { background-color: #2f2a4a; }\n.lbmc .lbmc-opt.richtig, .nightMode .lbmc .lbmc-opt.richtig { border-color: #2fb36d; background-color: #e3f6ec; }\n.nightMode .lbmc .lbmc-opt.richtig { background-color: #1f3a2d; }\n.lbmc .lbmc-opt.verpasst, .nightMode .lbmc .lbmc-opt.verpasst { border-color: #2fb36d; border-style: dashed; }\n.lbmc .lbmc-opt.falsch, .nightMode .lbmc .lbmc-opt.falsch { border-color: #e0525e; background-color: #fbe6e8; }\n.nightMode .lbmc .lbmc-opt.falsch { background-color: #3d2328; }\n\n.lbmc-ergebnis { font-weight: 700; margin: 4px 0 14px; }\n.lbmc-ergebnis.gut { color: #2fb36d; }\n.lbmc-ergebnis.daneben { color: #e0525e; }\n.lbmc-ergebnis.leer { opacity: .6; font-weight: 500; }\n\n.lbmc-erklaerung {\n  margin-top: 18px; padding: 12px 16px; border-radius: 12px;\n  background: rgba(124, 92, 255, .08); font-size: .9em;\n}\n\n.lb-quelle { margin-top: 16px; font-size: .75em; opacity: .55; }\n\n/* Flashcards: fett geschriebene Stichwoerter leuchten gruen, damit sie mit einem Blick ins Auge fallen */\n.lbk { max-width: 760px; margin: 0 auto; padding: 8px 4px 24px; }\n.lbk-frage { font-size: 1.25em; font-weight: 600; }\n.lbk-antwort { font-size: 1.1em; }\n.lbk-linie { border: 0; border-top: 1px solid rgba(120, 110, 160, .3); margin: 18px 0; }\n.lbk-antwort ul, .lbk-antwort ol { margin: 6px 0; padding-left: 1.3em; }\n.lbk-antwort li { margin: 4px 0; }\n.lbk-antwort b, .lbk-antwort strong {\n  color: #1f9d55; font-weight: 700;\n  background: rgba(47, 179, 109, .12); padding: 0 .2em; border-radius: 4px;\n}\n.nightMode .lbk-antwort b, .nightMode .lbk-antwort strong { color: #4ade80; background: rgba(74, 222, 128, .12); }\n",
 "vorne.html": "<div class=\"lbmc\" data-seite=\"vorne\" data-richtig=\"{{text:Richtig}}\" data-id=\"{{text:ID}}\">\n  <div class=\"lbmc-frage\">{{Frage}}</div>\n  <div class=\"lbmc-hinweis\"></div>\n  <div class=\"lbmc-optionen\">\n    {{#A}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"A\">{{A}}</button>{{/A}}\n    {{#B}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"B\">{{B}}</button>{{/B}}\n    {{#C}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"C\">{{C}}</button>{{/C}}\n    {{#D}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"D\">{{D}}</button>{{/D}}\n    {{#E}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"E\">{{E}}</button>{{/E}}\n    {{#F}}<button type=\"button\" class=\"lbmc-opt\" data-k=\"F\">{{F}}</button>{{/F}}\n  </div>\n</div>\n<script>\n(function () {\n  var box = document.querySelector('.lbmc[data-seite=\"vorne\"]');\n  if (!box) return;\n  var richtig = (box.dataset.richtig || '').toUpperCase().match(/[A-F]/g) || [];\n  var mehrere = richtig.length > 1;\n  var liste = box.querySelector('.lbmc-optionen');\n  var opts = Array.prototype.slice.call(liste.children);\n  var id = box.dataset.id + '|' + box.querySelector('.lbmc-frage').textContent;\n  // Undo im Lernbalken-Add-on: dieselbe Karte kommt mit ihrer alten Reihenfolge und Auswahl zurueck\n  var alt = window.__lbmcUndo && window.__lbmcGemerkt ? window.__lbmcGemerkt[id] : null;\n  if (alt) {\n    opts.sort(function (a, b) { return alt.reihe.indexOf(a.dataset.k) - alt.reihe.indexOf(b.dataset.k); });\n  } else {\n    alt = null;\n    // Reihenfolge mischen, damit man sich nicht die Position merkt\n    for (var i = opts.length - 1; i > 0; i--) {\n      var j = Math.floor(Math.random() * (i + 1));\n      var t = opts[i]; opts[i] = opts[j]; opts[j] = t;\n    }\n  }\n  opts.forEach(function (o) { liste.appendChild(o); });\n  box.querySelector('.lbmc-hinweis').textContent = mehrere\n    ? richtig.length + ' Antworten sind richtig'\n    : 'Eine Antwort ist richtig';\n  var zustand = { id: id, reihe: opts.map(function (o) { return o.dataset.k; }), wahl: alt ? alt.wahl.slice() : [] };\n  opts.forEach(function (x) { x.classList.toggle('gewaehlt', zustand.wahl.indexOf(x.dataset.k) >= 0); });\n  function merken() {\n    window.__lbmc = zustand;\n    try { sessionStorage.setItem('lbmc', JSON.stringify(zustand)); } catch (e) {}\n  }\n  opts.forEach(function (o) {\n    o.addEventListener('click', function () {\n      var k = o.dataset.k;\n      if (mehrere) {\n        var p = zustand.wahl.indexOf(k);\n        if (p >= 0) zustand.wahl.splice(p, 1); else zustand.wahl.push(k);\n      } else {\n        zustand.wahl = zustand.wahl[0] === k ? [] : [k];\n      }\n      opts.forEach(function (x) { x.classList.toggle('gewaehlt', zustand.wahl.indexOf(x.dataset.k) >= 0); });\n      merken();\n    });\n  });\n  merken();\n})();\n</script>\n"
}
# --- /VORLAGEN ---


def _lies(datei: str) -> str:
    """Vorlage aus anki/karte/, sonst die eingebaute Kopie (falls der Skill ohne Zusatzdateien gespeichert ist)."""
    pfad = os.path.join(HIER, "karte", datei)
    if os.path.exists(pfad):
        with open(pfad, encoding="utf-8") as f:
            return f.read()
    return VORLAGEN[datei]


def _modell(art: dict, css: str, jetzt: int) -> dict:
    return {
        "id": art["id"], "name": art["name"], "type": 0, "mod": jetzt, "usn": -1, "sortf": 0, "did": 1,
        "tmpls": [{"name": "Karte", "ord": 0, "qfmt": _lies(art["vorne"]), "afmt": _lies(art["hinten"]),
                   "did": None, "bqfmt": "", "bafmt": ""}],
        "flds": [{"name": n, "ord": i, "sticky": False, "rtl": False, "font": "Arial", "size": 20, "media": []}
                 for i, n in enumerate(art["felder"])],
        "css": css, "latexPre": "", "latexPost": "", "latexsvg": False,
        "req": [[0, "any", [0]]], "tags": [], "vers": [],
    }


def _deck(did: int, name: str, jetzt: int) -> dict:
    return {"id": did, "name": name, "mod": jetzt, "usn": -1, "lrnToday": [0, 0], "revToday": [0, 0],
            "newToday": [0, 0], "timeToday": [0, 0], "collapsed": False, "browserCollapsed": False,
            "desc": "", "dyn": 0, "conf": 1, "extendNew": 0, "extendRev": 0}


_DCONF = {"1": {"id": 1, "name": "Default", "mod": 0, "usn": 0, "maxTaken": 60, "autoplay": True, "timer": 0,
                "replayq": True, "dyn": False,
                "new": {"bury": False, "delays": [1, 10], "initialFactor": 2500, "ints": [1, 4, 0], "order": 1, "perDay": 20},
                "lapse": {"delays": [10], "leechAction": 1, "leechFails": 8, "minInt": 1, "mult": 0},
                "rev": {"bury": False, "ease4": 1.3, "ivlFct": 1, "maxIvl": 36500, "perDay": 200, "hardFactor": 1.2}}}

_SCHEMA = """
CREATE TABLE col (id integer primary key, crt integer not null, mod integer not null, scm integer not null,
  ver integer not null, dty integer not null, usn integer not null, ls integer not null, conf text not null,
  models text not null, decks text not null, dconf text not null, tags text not null);
CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null, mod integer not null,
  usn integer not null, tags text not null, flds text not null, sfld integer not null, csum integer not null,
  flags integer not null, data text not null);
CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null, ord integer not null,
  mod integer not null, usn integer not null, type integer not null, queue integer not null, due integer not null,
  ivl integer not null, factor integer not null, reps integer not null, lapses integer not null, left integer not null,
  odue integer not null, odid integer not null, flags integer not null, data text not null);
CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null, ease integer not null,
  ivl integer not null, lastIvl integer not null, factor integer not null, time integer not null, type integer not null);
CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
CREATE INDEX ix_notes_usn on notes (usn); CREATE INDEX ix_cards_usn on cards (usn);
CREATE INDEX ix_revlog_usn on revlog (usn); CREATE INDEX ix_cards_nid on cards (nid);
CREATE INDEX ix_cards_sched on cards (did, queue, due); CREATE INDEX ix_revlog_cid on revlog (cid);
CREATE INDEX ix_notes_csum on notes (csum);
"""


def pruefe(daten: dict) -> tuple[list[dict], list[str]]:
    """Gueltige Karten (vorbereitet) und Fehlermeldungen."""
    fach = (daten.get("fach") or "").strip()
    fehler, gut, gesehen = [], [], set()
    if not fach:
        return [], ["'fach' fehlt"]
    for i, k in enumerate(daten.get("karten") or [], 1):
        wo = f"Karte {i}"
        typ = (k.get("typ") or "").lower()
        block, frage = (k.get("block") or "").strip(), (k.get("frage") or "").strip()
        if not block or not frage:
            fehler.append(f"{wo}: block oder frage fehlt"); continue
        if re.search(r"<[^>]*>", block + fach):
            fehler.append(f"{wo}: Platzhalter statt echtem Namen"); continue
        kid = karten_id(fach, block, frage)
        if kid in gesehen:
            fehler.append(f"{wo}: dieselbe Frage gibt es im Block schon"); continue
        deck, tag_block = deck_pfad(fach, block, bool(k.get("kern")))
        tags = ["Lernbalken", tag_block] + (["Kern"] if k.get("kern") else [])
        if typ in ("single", "multi"):
            opts = [str(o).strip() for o in (k.get("optionen") or []) if str(o).strip()]
            richtig = sorted(set(re.findall(r"[A-F]", str(k.get("richtig") or "").upper())))
            if not 2 <= len(opts) <= 6:
                fehler.append(f"{wo}: 2 bis 6 Optionen noetig"); continue
            if not richtig or any(ord(r) - 65 >= len(opts) for r in richtig):
                fehler.append(f"{wo}: 'richtig' passt nicht zu den Optionen"); continue
            if typ == "single" and len(richtig) != 1:
                fehler.append(f"{wo}: Single Choice braucht genau eine richtige Antwort"); continue
            felder = {"Frage": text(frage), "Richtig": ", ".join(richtig), "Erklärung": text(k.get("erklaerung")),
                      "Quelle": text(k.get("quelle")), "ID": kid}
            for j, o in enumerate(opts):
                felder["ABCDEF"[j]] = text(o)
            gut.append({"art": MC, "felder": felder, "deck": deck, "tags": tags + [typ.capitalize()]})
        elif typ == "karte":
            antwort = (k.get("antwort") or "").strip()
            if not antwort:
                fehler.append(f"{wo}: Flashcard ohne antwort"); continue
            felder = {"Frage": text(frage), "Antwort": text(antwort), "Quelle": text(k.get("quelle")), "ID": kid}
            gut.append({"art": KARTE, "felder": felder, "deck": deck, "tags": tags + ["Karte"]})
        else:
            fehler.append(f"{wo}: typ muss single, multi oder karte sein"); continue
        gesehen.add(kid)
    return gut, fehler


def baue(daten: dict, ziel: str) -> dict:
    karten, fehler = pruefe(daten)
    if not karten:
        raise SystemExit("Keine gueltigen Karten.\n" + "\n".join(fehler))
    jetzt = int(time.time())
    css = _lies("stil.css")
    decks = {"1": _deck(1, "Default", jetzt)}
    for k in karten:
        teile = k["deck"].split("::")
        for n in range(1, len(teile) + 1):
            name = "::".join(teile[:n])
            did = _int_id("deck:" + name)
            decks.setdefault(str(did), _deck(did, name, jetzt))
    ids = {d["name"]: d["id"] for d in decks.values()}
    modelle = {str(a["id"]): _modell(a, css, jetzt) for a in (MC, KARTE)}

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "collection.anki2")
        con = sqlite3.connect(db)
        con.executescript(_SCHEMA)
        con.execute("insert into col values (1,?,?,?,11,0,0,0,?,?,?,?,?)",
                    (jetzt, jetzt * 1000, jetzt * 1000, json.dumps({"nextPos": len(karten) + 1}),
                     json.dumps(modelle), json.dumps(decks), json.dumps(_DCONF), "{}"))
        for pos, k in enumerate(karten, 1):
            art, f = k["art"], k["felder"]
            flds = [f.get(n, "") for n in art["felder"]]
            nid = _int_id("note:" + f["ID"])
            sfld = re.sub(r"<[^>]+>", "", flds[0])
            csum = int(hashlib.sha1(sfld.encode("utf-8")).hexdigest()[:8], 16)
            con.execute("insert into notes values (?,?,?,?,-1,?,?,?,?,0,'')",
                        (nid, "lb" + f["ID"], art["id"], jetzt, " " + " ".join(k["tags"]) + " ",
                         "\x1f".join(flds), sfld, csum))
            con.execute("insert into cards values (?,?,?,0,?,-1,0,0,?,0,0,0,0,0,0,0,0,'')",
                        (_int_id("card:" + f["ID"]), nid, ids[k["deck"]], jetzt, pos))
        con.commit()
        con.close()
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db, "collection.anki2")
            z.writestr("media", "{}")

    uebersicht: dict[str, dict] = {}
    for k in karten:
        u = uebersicht.setdefault(k["deck"], {"MC": 0, "Karte": 0})
        u["MC" if k["art"] is MC else "Karte"] += 1
    return {"datei": ziel, "karten": len(karten), "decks": uebersicht, "fehler": fehler}


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        daten = json.load(f)
    ziel = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(sys.argv[1])[0] + ".apkg"
    erg = baue(daten, ziel)
    print(f"{erg['karten']} Karten -> {erg['datei']}")
    for deck, u in sorted(erg["decks"].items()):
        print(f"  {deck}: {u['MC']} Choice, {u['Karte']} Flashcards")
    if erg["fehler"]:
        print(f"\n{len(erg['fehler'])} Karten uebersprungen:")
        for f in erg["fehler"]:
            print("  " + f)


if __name__ == "__main__":
    main()
