/* Lernfenster: Woerter abdecken, Woerter als Vokabel merken, frei gesetzte Bilder.
   Python ruft nach jeder gezeichneten Karte lernen.karte({nid, gruppen, an}).

   Abdecken: Werkzeug (Knopf im Balken) an, Text markieren -> abgedeckt. Mit Strg markiert gehoert es zur
   letzten Gruppe, ohne Strg ist es eine neue. Klick auf eine Abdeckung deckt die ganze Gruppe auf (und wieder zu),
   Rechtsklick bei aktivem Werkzeug loescht die Gruppe. Der Schalter daneben blendet alle Abdeckungen aus.
   Gemerkt wird pro Notiz als Text + wievieltes Vorkommen, das uebersteht auch gemischte Antworten. */
(function () {
  'use strict';
  if (window.lernen) return;

  var nid = null, gruppen = [], an = true, werkzeug = false;
  var offen = {};          // aufgedeckte Gruppen dieser Ansicht
  var klickWeg = false;    // Klick nach einer Markierung nicht an die Karte weitergeben
  var knopfWerkzeug, knopfSchalter, pop;

  function qa() { return document.getElementById('qa'); }

  // Text der Karte
  //////////////////////////////////////////////////////////////////////////

  function textKnoten() {
    var wurzel = qa(), aus = [];
    if (!wurzel) return aus;
    var w = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentElement;
        return p && p.closest('script, style, .lb-vok-pop') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    while (w.nextNode()) aus.push(w.currentNode);
    return aus;
  }

  function volltext(knoten) {
    var starts = [], s = 0, text = '';
    knoten.forEach(function (k) { starts.push(s); s += k.data.length; text += k.data; });
    return { knoten: knoten, starts: starts, text: text };
  }

  // Position einer Auswahlgrenze im Volltext
  function stelle(vt, node, off) {
    if (node.nodeType === 3) {
      var i = vt.knoten.indexOf(node);
      if (i >= 0) return vt.starts[i] + off;
    }
    var p = document.createRange();
    p.setStart(node, off); p.collapse(true);
    for (var j = 0; j < vt.knoten.length; j++) {
      if (p.comparePoint(vt.knoten[j], 0) >= 0) return vt.starts[j];
    }
    return vt.text.length;
  }

  function vorkommen(text, t, bis) {
    var n = 0, i = text.indexOf(t);
    while (i >= 0 && i < bis) { n++; i = text.indexOf(t, i + 1); }
    return n;
  }

  function finde(text, t, n) {
    var i = text.indexOf(t);
    while (i >= 0 && n > 0) { i = text.indexOf(t, i + 1); n--; }
    return i;
  }

  // Abdeckungen zeichnen
  //////////////////////////////////////////////////////////////////////////

  function entfernen() {
    var wurzel = qa();
    if (!wurzel) return;
    wurzel.querySelectorAll('span.lb-deck').forEach(function (s) {
      var p = s.parentNode;
      while (s.firstChild) p.insertBefore(s.firstChild, s);
      p.removeChild(s);
      p.normalize();
    });
  }

  function umhuellen(s, e, gi) {
    var vt = volltext(textKnoten());
    vt.knoten.forEach(function (k, i) {
      var ks = vt.starts[i], ke = ks + k.data.length;
      if (ke <= s || ks >= e) return;
      var a = Math.max(s, ks) - ks, b = Math.min(e, ke) - ks;
      if (!k.data.slice(a, b).trim()) return;
      if (b < k.data.length) k.splitText(b);
      if (a > 0) k = k.splitText(a);
      var span = document.createElement('span');
      span.className = 'lb-deck' + (offen[gi] ? ' offen' : '');
      span.dataset.g = gi;
      k.parentNode.insertBefore(span, k);
      span.appendChild(k);
    });
  }

  function zeichnen() {
    entfernen();
    document.documentElement.classList.toggle('lb-werkzeug', werkzeug && an);
    if (!an) return;
    var text = volltext(textKnoten()).text, belegt = [];
    gruppen.forEach(function (g, gi) {
      g.forEach(function (st) {
        var s = finde(text, st.t, st.n);
        if (s < 0) return;
        var e = s + st.t.length;
        if (belegt.some(function (b) { return s < b[1] && e > b[0]; })) return;
        belegt.push([s, e]);
        umhuellen(s, e, gi);
      });
    });
  }

  function speichern() {
    if (nid != null && window.pycmd) pycmd('lb_abdeck:' + JSON.stringify({ nid: nid, gruppen: gruppen }));
  }

  // Markieren
  //////////////////////////////////////////////////////////////////////////

  function auswahlImQa() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    var r = sel.getRangeAt(0), wurzel = qa();
    if (!wurzel || !wurzel.contains(r.commonAncestorContainer)) return null;
    return r;
  }

  function abdecken(r, strg) {
    var vt = volltext(textKnoten());
    var s = stelle(vt, r.startContainer, r.startOffset), e = stelle(vt, r.endContainer, r.endOffset);
    while (s < e && /\s/.test(vt.text[s])) s++;
    while (e > s && /\s/.test(vt.text[e - 1])) e--;
    if (e <= s) return;
    var t = vt.text.slice(s, e);
    var stueck = { t: t, n: vorkommen(vt.text, t, s) };
    if (strg && gruppen.length) gruppen[gruppen.length - 1].push(stueck);
    else gruppen.push([stueck]);
    window.getSelection().removeAllRanges();
    speichern();
    zeichnen();
  }

  var unten = null;
  document.addEventListener('mousedown', function (e) {
    unten = { x: e.clientX, y: e.clientY };
    klickWeg = false;
    if (pop && !pop.contains(e.target)) pop.hidden = true;
  }, true);

  document.addEventListener('mouseup', function (e) {
    if (e.button !== 0) return;
    var bewegt = unten && (Math.abs(e.clientX - unten.x) + Math.abs(e.clientY - unten.y) > 3);
    var r = auswahlImQa();
    if (!r) return;
    if (bewegt) klickWeg = true;
    if (werkzeug && an) {
      abdecken(r, e.ctrlKey || e.metaKey);
      klickWeg = true;
    } else {
      zeigePop(r);
    }
  }, true);

  document.addEventListener('click', function (e) {
    if (klickWeg) {
      klickWeg = false;
      e.preventDefault(); e.stopPropagation();
      return;
    }
    var d = e.target.closest && e.target.closest('span.lb-deck');
    if (!d) return;
    e.preventDefault(); e.stopPropagation();
    var gi = d.dataset.g;
    offen[gi] = !offen[gi];
    document.querySelectorAll('#qa span.lb-deck[data-g="' + gi + '"]').forEach(function (s) {
      s.classList.toggle('offen', !!offen[gi]);
    });
  }, true);

  document.addEventListener('contextmenu', function (e) {
    var d = e.target.closest && e.target.closest('span.lb-deck');
    if (!d || !werkzeug) return;
    e.preventDefault(); e.stopPropagation();
    gruppen.splice(+d.dataset.g, 1);
    offen = {};
    speichern();
    zeichnen();
  }, true);

  // Kleiner Knopf an der Markierung: als Vokabel merken
  function zeigePop(r) {
    var text = r.toString().replace(/\s+/g, ' ').trim();
    if (!text || text.length > 120) return;
    if (!pop) {
      pop = document.createElement('button');
      pop.type = 'button';
      pop.className = 'lb-vok-pop';
      pop.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>Vocab';
      pop.title = 'Add to your vocabulary list';
      pop.addEventListener('mousedown', function (e) { e.preventDefault(); e.stopPropagation(); });
      pop.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        pop.hidden = true;
        var wort = pop.dataset.wort;
        window.getSelection().removeAllRanges();
        if (window.vokabeln) vokabeln.neu(wort);
      });
      document.body.appendChild(pop);
    }
    var b = r.getBoundingClientRect();
    pop.dataset.wort = text;
    pop.hidden = false;
    var x = Math.min(Math.max(b.left + b.width / 2, 50), window.innerWidth - 50);
    pop.style.left = x + 'px';
    pop.style.top = (b.bottom + 8 + window.scrollY) + 'px';
  }

  // Knoepfe im Balken
  //////////////////////////////////////////////////////////////////////////

  var SVG_DECK = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><rect x="3" y="8" width="18" height="8" rx="2.5"/>' +
    '<path d="M7 12h10" class="lb-strich"/></svg>';

  function knoepfe() {
    var rechts = document.querySelector('#lb-balken .lb-rechts');
    if (!rechts || rechts.querySelector('.lb-werkzeug-knopf')) return;
    var stern = rechts.querySelector('.lb-stern');

    var gruppe = document.createElement('span');
    gruppe.className = 'lb-abdeck-gruppe';
    knopfWerkzeug = document.createElement('button');
    knopfWerkzeug.type = 'button';
    knopfWerkzeug.className = 'lb-knopf lb-werkzeug-knopf';
    knopfWerkzeug.innerHTML = SVG_DECK + '<span>Cover</span>';
    knopfWerkzeug.title = 'Cover: select text to hide it. Hold Ctrl to add it to the last group. ' +
      'Click a cover to reveal its group, right-click to delete it.';
    knopfWerkzeug.addEventListener('click', function (e) {
      e.preventDefault(); knopfWerkzeug.blur();
      werkzeug = !werkzeug;
      if (werkzeug && !an) schalten(true);
      knoepfeZeigen(); zeichnen();
    });
    knopfSchalter = document.createElement('button');
    knopfSchalter.type = 'button';
    knopfSchalter.className = 'lb-schalter';
    knopfSchalter.setAttribute('role', 'switch');
    knopfSchalter.title = 'Show or hide all covers';
    knopfSchalter.innerHTML = '<span class="lb-knauf"></span>';
    knopfSchalter.addEventListener('click', function (e) {
      e.preventDefault(); knopfSchalter.blur();
      schalten(!an);
    });
    gruppe.appendChild(knopfWerkzeug);
    gruppe.appendChild(knopfSchalter);

    var buch = document.createElement('button');
    buch.type = 'button';
    buch.className = 'lb-knopf lb-buch';
    buch.innerHTML = '<i class="lb-buch-icon"></i><span>Vocab</span>';   // Bild steht in vokabeln.css
    buch.title = 'View and quiz your vocabulary';
    buch.addEventListener('click', function (e) {
      e.preventDefault(); buch.blur();
      if (window.vokabeln) vokabeln.oeffnen();
    });
    var trenner = document.createElement('span');
    trenner.className = 'lb-trenner';

    // Reihenfolge rechts: Cover + Schalter | Vocab | Important
    rechts.insertBefore(gruppe, stern);
    rechts.insertBefore(buch, stern);
    rechts.insertBefore(trenner, stern);
    knoepfeZeigen();
  }

  function knoepfeZeigen() {
    if (!knopfWerkzeug) return;
    knopfWerkzeug.classList.toggle('an', werkzeug && an);
    knopfWerkzeug.setAttribute('aria-pressed', werkzeug && an ? 'true' : 'false');
    knopfSchalter.classList.toggle('an', an);
    knopfSchalter.setAttribute('aria-checked', an ? 'true' : 'false');
  }

  function schalten(neu) {
    an = neu;
    if (!an) werkzeug = false;
    offen = {};
    if (window.pycmd) pycmd('lb_abdecken_an:' + (an ? 1 : 0));
    knoepfeZeigen(); zeichnen();
  }

  // Frei gesetzte Bilder (aus dem Editor): Eltern werden Bezugsrahmen und so hoch, dass die Bilder hineinpassen
  //////////////////////////////////////////////////////////////////////////

  function bilder() {
    var wurzel = qa();
    if (!wurzel) return;
    var imgs = wurzel.querySelectorAll('img[data-lb-frei]');
    function hoehe() {
      var max = new Map();
      imgs.forEach(function (img) {
        var p = img.parentElement;
        var unterkante = img.offsetTop + img.offsetHeight;
        max.set(p, Math.max(max.get(p) || 0, unterkante));
      });
      max.forEach(function (h, p) { p.style.minHeight = h + 'px'; });
    }
    imgs.forEach(function (img) {
      var p = img.parentElement;
      if (getComputedStyle(p).position === 'static') p.style.position = 'relative';
      if (!img.complete) img.addEventListener('load', hoehe, { once: true });
    });
    hoehe();
  }

  // Doppelklick auf ein Bild: verschieben und an den Ecken groesser/kleiner ziehen, gespeichert in der Notiz
  //////////////////////////////////////////////////////////////////////////

  var bild = null;   // das Bild unter dem Rahmen (im Lernfenster baut niemand die Karte unter uns neu auf)
  var FELDER = '.lbk-frage, .lbk-antwort, .lbmc-frage, .lbmc-erklaerung, .lbmc-opt, .lb-quelle';

  // Bezugsrahmen wie im Editor: das Element, in dem das Feld steht. Bei Lernbalken-Karten das Feld-Element,
  // sonst #qa (Basic & Co. setzen das Feld direkt hinein). Bei schon freien Bildern ihr Elternteil.
  function bezug(img) {
    return img.hasAttribute('data-lb-frei') ? img.parentElement : (img.closest(FELDER) || qa());
  }

  function bildFertig(r, art) {
    var img = bild;
    if (!img || !img.isConnected) return;
    var d = { src: img.getAttribute('src') };
    if (art === 'groesse' && !img.hasAttribute('data-lb-frei')) {
      img.removeAttribute('width'); img.removeAttribute('height');
      img.style.width = Math.round(r.width) + 'px';
      img.style.height = 'auto';
      d.width = img.style.width;
    } else {
      var b = bezug(img);
      if (getComputedStyle(b).position === 'static') b.style.position = 'relative';
      var alt = img.parentElement;
      if (alt !== b) {
        // wie in der Notiz (extras.bild_setzen): ans Ende des Feldes, leer gewordene Zeile weg
        b.appendChild(img);
        if (!alt.textContent.trim() && !alt.querySelector('img')) alt.remove();
      }
      var lage = lbRahmen.freieLage(r, b);
      lbRahmen.setzeFrei(img, lage);
      d.left = lage.left; d.top = lage.top; d.width = lage.width;
    }
    bilder();
    if (window.pycmd) pycmd('lb_bild:' + JSON.stringify(d));
  }

  function bildZuruecksetzen() {
    var img = bild;
    if (!img) return;
    var b = img.parentElement;
    lbRahmen.loese(img);
    b.style.minHeight = '';
    bilder();
    if (window.pycmd) pycmd('lb_bild:' + JSON.stringify({ src: img.getAttribute('src'), zurueck: true }));
  }

  var bildRahmen = window.lbRahmen ? lbRahmen({
    finde: function () { return bild && bild.isConnected ? bild : null; },
    fertig: bildFertig,
    zuruecksetzen: bildZuruecksetzen
  }) : null;

  document.addEventListener('dblclick', function (e) {
    var img = e.target.closest && e.target.closest('#qa img');
    if (!img || !bildRahmen || img.dataset.anki) return;
    e.preventDefault(); e.stopPropagation();
    window.getSelection().removeAllRanges();
    bild = img;
    bildRahmen.zeigen();
  }, true);

  // Undo-Knopf: MC-Reihenfolge und Auswahl der Karte, zu der es zurueckgeht. Die Vorderseite (karte/vorne.html)
  // schaut in window.__lbmcGemerkt nach ihrer Frage, wenn window.__lbmcUndo gesetzt ist, und mischt dann nicht neu.
  //////////////////////////////////////////////////////////////////////////

  var gemerkt = window.__lbmcGemerkt = {}, reihe = [];
  function mcSpeichern(z) {
    if (!z || !z.id) return;
    if (!(z.id in gemerkt)) reihe.push(z.id);
    gemerkt[z.id] = z;
    while (reihe.length > 30) delete gemerkt[reihe.shift()];   // die letzten 30 reichen fuer mehrmals Undo
  }
  // Sobald die Rueckseite einer MC-Karte steht, ist die Auswahl fertig und noch nicht von der naechsten Karte
  // ueberschrieben
  function mcMerken() {
    if (document.querySelector('#qa .lbmc[data-seite="hinten"]')) mcSpeichern(window.__lbmc);
  }
  // Python ruft das direkt vor dem Zurueckgehen. Die aktuelle Auswahl gilt auch (Undo auf der Frageseite).
  function undoVorbereiten() {
    mcSpeichern(window.__lbmc);
    window.__lbmcUndo = true;
  }

  function karte(d) {
    nid = d.nid;
    gruppen = d.gruppen || [];
    an = d.an !== false;
    if (!an) werkzeug = false;
    offen = {};
    if (pop) pop.hidden = true;
    if (bildRahmen) bildRahmen.weg();
    knoepfe();
    knoepfeZeigen();
    zeichnen();
    bilder();
    mcMerken();
    window.__lbmcUndo = false;   // gilt nur fuer die eine Karte, die nach dem Undo gezeichnet wurde
  }

  window.lernen = { karte: karte, undoVorbereiten: undoVorbereiten };
})();
