/* Editor: Bilder frei verschieben und an allen vier Ecken groesser/kleiner ziehen (Rahmen aus rahmen.js).

   Bild anklicken -> lila Rahmen. Bild/Rahmen ziehen -> es loest sich vom Text und liegt genau dort,
   wo man es loslaesst (position:absolute, left/top in px, relativ zum Feld, markiert mit data-lb-frei).
   Ecke ziehen -> groesser/kleiner. ↺ -> zurueck in den Text. Entf -> Bild loeschen.
   Anki speichert von selbst (es beobachtet das Feld) und baut das Feld danach neu auf. Darum merkt sich
   das Skript nicht das Bild-Element, sondern Feld-Nummer, Bildquelle und das wievielte Bild mit dieser Quelle. */
(function () {
  'use strict';
  if (window.lbBilder || !window.lbRahmen) return;
  window.lbBilder = true;

  var wahl = null;   // {feld (Nummer), el (das Feld-Element), src, nr}

  function felder() {
    var aus = [];
    document.querySelectorAll('*').forEach(function (n) {
      if (n.shadowRoot) n.shadowRoot.querySelectorAll('anki-editable').forEach(function (f) { aus.push(f); });
    });
    return aus;
  }

  function gleiche(f, src) {
    return Array.prototype.filter.call(f.querySelectorAll('img'), function (i) { return i.getAttribute('src') === src; });
  }

  function merke(img, f) {
    var src = img.getAttribute('src');
    wahl = { feld: felder().indexOf(f), el: f, src: src, nr: gleiche(f, src).indexOf(img) };
  }

  // Das Feld-Element bleibt beim Neuaufbau erhalten (nur sein Inhalt wird ersetzt). Darum nur neu suchen, wenn es
  // weg ist: der Rahmen fragt bei jedem Bild-Frame, die ganze Seite zu durchsuchen waere zu teuer.
  function feld() {
    if (!wahl) return null;
    if (!wahl.el || !wahl.el.isConnected) wahl.el = felder()[wahl.feld] || null;
    return wahl.el;
  }
  function finde() { var f = feld(); return f ? gleiche(f, wahl.src)[wahl.nr] || null : null; }

  function bildAus(e) {
    var pfad = e.composedPath ? e.composedPath() : [];
    var img = pfad[0];
    if (!img || img.tagName !== 'IMG' || img.dataset.anki) return null;   // MathJax-Bilder nicht
    for (var i = 0; i < pfad.length; i++) if (pfad[i].tagName === 'ANKI-EDITABLE') return { img: img, feld: pfad[i] };
    return null;
  }

  // nur schreiben, wenn sich etwas aendert (jede Aenderung laesst Anki speichern und neu aufbauen)
  function setze(el, eigenschaft, wert) { if (el.style[eigenschaft] !== wert) el.style[eigenschaft] = wert; }

  // Ankis "Bilder verkleinern" kappt im Editor jedes Bild (z. B. auf 250 px). Bilder, die man selbst gesetzt
  // oder in der Groesse gezogen hat, sollen so gross erscheinen wie auf der Karte. Steht im Shadow-DOM des
  // Feldes, nicht im Feldinhalt, wird also nicht gespeichert.
  function stilEinbauen(f) {
    var root = f.getRootNode();
    if (!root || root.querySelector('style[data-lb-bilder]')) return;
    var s = document.createElement('style');
    s.setAttribute('data-lb-bilder', '');
    s.textContent = 'img[data-lb-frei], img[style*="width"] { max-width: none !important; max-height: none !important; }';
    root.appendChild(s);
    // Neu aufgebautes Feld (Ankis setFields) oder fertig geladenes Bild: Hoehe neu messen.
    // Beobachtet nur Kinder, nicht Attribute; hoeheAnpassen aendert nur Attribute, also keine Schleife.
    var geplant = false;
    function spaeter() {
      if (geplant) return;
      geplant = true;
      requestAnimationFrame(function () {
        geplant = false;
        if (f.isConnected && (f.querySelector('img[data-lb-frei]') || f.style.minHeight)) hoeheAnpassen(f);
      });
    }
    root.addEventListener('load', function (e) { if (e.target.tagName === 'IMG') spaeter(); }, true);
    new MutationObserver(spaeter).observe(f, { childList: true, subtree: true });
    spaeter();
  }

  // Feld als Bezugsrahmen und hoch genug fuer die freien Bilder
  function hoeheAnpassen(f) {
    stilEinbauen(f);
    setze(f, 'position', 'relative');
    var max = 0;
    f.querySelectorAll('img[data-lb-frei]').forEach(function (img) { max = Math.max(max, img.offsetTop + img.offsetHeight); });
    setze(f, 'minHeight', max ? max + 'px' : '');
  }

  function fertig(r, art) {
    var img = finde(), f = feld();
    if (!img || !f) return;
    if (art === 'groesse' && !img.hasAttribute('data-lb-frei')) {
      // Bild im Text: nur die Groesse
      img.removeAttribute('width'); img.removeAttribute('height');
      img.style.width = Math.round(r.width) + 'px';
      img.style.height = 'auto';
    } else {
      f.style.position = 'relative';
      var lage = lbRahmen.freieLage(r, f);
      var alt = img.parentNode;
      if (alt !== f) {
        f.appendChild(img);   // direkt ins Feld, dann hat es im Lernfenster denselben Bezugsrahmen
        if (alt.isConnected && !alt.textContent.trim() && !alt.querySelector('img')) alt.remove();
      }
      lbRahmen.setzeFrei(img, lage);
    }
    merke(img, f);   // Reihenfolge im Feld kann sich geaendert haben
    hoeheAnpassen(f);
  }

  function zuruecksetzen() {
    var img = finde(), f = feld();
    if (!img) return;
    lbRahmen.loese(img);
    merke(img, f);
    hoeheAnpassen(f);
  }

  var rahmen = lbRahmen({
    finde: finde, fertig: fertig, zuruecksetzen: zuruecksetzen,
    gehoertDazu: function (e) { return !!bildAus(e); }
  });

  // Klick auf ein Bild: Rahmen zeigen und gleich ziehen koennen. Ankis eigenen Bild-Griff dabei abfangen.
  window.addEventListener('pointerdown', function (e) {
    if (e.button !== 0) return;
    var t = bildAus(e);
    if (!t) return;
    e.preventDefault(); e.stopImmediatePropagation();
    merke(t.img, t.feld);
    rahmen.ziehen(e);
  }, true);
  ['mousedown', 'click', 'dblclick'].forEach(function (art) {
    window.addEventListener(art, function (e) {
      if (bildAus(e)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
  });

  window.addEventListener('keydown', function (e) {
    if (!rahmen.offen()) return;
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault(); e.stopImmediatePropagation();
      var img = finde(), f = feld();
      if (img) img.remove();
      rahmen.weg();
      if (f) hoeheAnpassen(f);
    } else if (e.key !== 'Escape') {
      rahmen.weg();   // jede andere Taste (Tab, Tippen) gibt das Bild frei, damit Entf spaeter nichts loescht
    }
  }, true);

  // Python ruft das nach jedem Laden einer Notiz. Die Felder erscheinen etwas spaeter, Bilder laden noch
  // spaeter: darum ein paar Mal nachziehen und beim Laden jedes freien Bildes.
  function alleAnpassen() {
    felder().forEach(function (f) {
      stilEinbauen(f);
      if (f.querySelector('img[data-lb-frei]') || f.style.minHeight) hoeheAnpassen(f);
    });
  }
  window.lbBilderAnpassen = function () {
    rahmen.weg();
    [0, 300, 1200].forEach(function (ms) { setTimeout(alleAnpassen, ms); });
  };
  window.lbBilderAnpassen();
})();
