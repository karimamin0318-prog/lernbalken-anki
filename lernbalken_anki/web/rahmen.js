/* Rahmen zum Verschieben und Groesser/Kleiner-Ziehen eines Bildes, fuer Editor (bilder.js) und Lernfenster (lernen.js).

   Der Rahmen liegt ueber dem Bild, ausserhalb des Kartentextes. Beim Ziehen bewegt sich nur der Rahmen mit
   einer Vorschau des Bildes; das Bild selbst wird erst beim Loslassen einmal geaendert (opt.fertig).
   Das ist wichtig fuer den Editor: Anki baut das Feld nach jeder Aenderung neu auf, ein festgehaltenes
   Bild-Element ist danach veraltet. Darum fragt der Rahmen jedes Mal opt.finde() nach dem aktuellen Bild.

   lbRahmen({ finde: () => img|null, fertig: (r, art) => {}, zuruecksetzen: () => {} })
     r = neue Lage {left, top, width, height} in Fensterkoordinaten, art = 'ziehen' | 'groesse'
   -> { zeigen(), weg(), offen(), ziehen(pointerEvent) } */
(function () {
  'use strict';
  if (window.lbRahmen) return;

  var LILA = '#7c5cff';
  var ECKEN = { nw: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize', se: 'nwse-resize' };

  window.lbRahmen = function (opt) {
    var box, vorschau, zug = null, an = false;

    function bauen() {
      box = document.createElement('div');
      box.className = 'lb-rahmen';
      box.style.cssText = 'position:fixed;z-index:10002;display:none;box-sizing:border-box;cursor:move;' +
        'border:2px solid ' + LILA + ';border-radius:3px;touch-action:none;';
      vorschau = document.createElement('img');
      vorschau.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;opacity:.85;pointer-events:none;display:none';
      box.appendChild(vorschau);
      Object.keys(ECKEN).forEach(function (e) {
        var g = document.createElement('div');
        g.dataset.ecke = e;
        g.title = 'Drag to resize';
        g.style.cssText = 'position:absolute;width:12px;height:12px;background:' + LILA + ';border:2px solid #fff;' +
          'border-radius:3px;box-shadow:0 1px 3px rgba(0,0,0,.3);cursor:' + ECKEN[e] + ';' +
          (e[0] === 'n' ? 'top:-8px;' : 'bottom:-8px;') + (e[1] === 'w' ? 'left:-8px;' : 'right:-8px;');
        box.appendChild(g);
      });
      var reset = document.createElement('button');
      reset.type = 'button';
      reset.textContent = '↺';
      reset.title = 'Back into the text, original size';
      reset.style.cssText = 'position:absolute;right:-2px;top:-32px;cursor:pointer;font:600 13px "Segoe UI",sans-serif;' +
        'color:#fff;background:' + LILA + ';border:0;border-radius:6px;padding:3px 8px;margin:0;box-shadow:0 1px 4px rgba(0,0,0,.25)';
      reset.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
      reset.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        if (opt.zuruecksetzen) opt.zuruecksetzen();
      });
      box.appendChild(reset);
      document.body.appendChild(box);

      box.addEventListener('pointerdown', function (e) {
        if (e.button !== 0) return;
        e.preventDefault(); e.stopPropagation();
        starten(e, e.target.dataset && e.target.dataset.ecke);
      });
      window.addEventListener('pointermove', bewegen, true);
      window.addEventListener('pointerup', loslassen, true);
      window.addEventListener('pointercancel', function () { zug = null; vorschau.style.display = 'none'; }, true);
    }

    function lage() {
      var img = opt.finde();
      if (!img || !img.isConnected) return null;
      var r = img.getBoundingClientRect();
      return { left: r.left, top: r.top, width: r.width, height: r.height };
    }

    function malen(r) {
      box.style.left = (r.left - 2) + 'px';
      box.style.top = (r.top - 2) + 'px';
      box.style.width = (r.width + 4) + 'px';
      box.style.height = (r.height + 4) + 'px';
    }

    function schleife() {
      if (!an) return;
      if (!zug) {
        var r = lage();
        if (!r) { weg(); return; }
        malen(r);
      }
      requestAnimationFrame(schleife);
    }

    function starten(e, ecke) {
      var r = lage(), img = opt.finde();
      if (!r || !r.width) return;
      zug = { ecke: ecke || null, x: e.clientX, y: e.clientY, r: r, neu: null, verhaeltnis: r.width / r.height };
      vorschau.src = img.currentSrc || img.src;
      try { box.setPointerCapture(e.pointerId); } catch (x) { /* kein Zeiger zum Einfangen */ }
    }

    function bewegen(e) {
      if (!zug) return;
      var dx = e.clientX - zug.x, dy = e.clientY - zug.y, r = zug.r, n;
      if (!zug.neu && Math.abs(dx) + Math.abs(dy) < 3) return;
      if (zug.ecke) {
        var ost = zug.ecke[1] === 'e', sued = zug.ecke[0] === 's';
        // Breite folgt der Maus, die Hoehe dem Seitenverhaeltnis; die gegenueberliegende Ecke bleibt stehen
        var w = Math.max(24, Math.round(r.width + (ost ? dx : -dx)));
        var h = w / zug.verhaeltnis;
        n = { width: w, height: h, left: ost ? r.left : r.left + r.width - w, top: sued ? r.top : r.top + r.height - h };
      } else {
        n = { width: r.width, height: r.height, left: r.left + dx, top: r.top + dy };
      }
      zug.neu = n;
      vorschau.style.display = 'block';
      malen(n);
      e.preventDefault();
    }

    function loslassen() {
      if (!zug) return;
      var z = zug;
      zug = null;
      vorschau.style.display = 'none';
      if (z.neu) opt.fertig(z.neu, z.ecke ? 'groesse' : 'ziehen');
    }

    function zeigen() {
      if (!box) bauen();
      box.style.display = 'block';
      if (!an) { an = true; requestAnimationFrame(schleife); }
      var r = lage();
      if (r) malen(r);
    }

    function weg() {
      an = false;
      zug = null;
      if (box) box.style.display = 'none';
    }

    // Klick daneben oder Esc schliesst den Rahmen
    window.addEventListener('pointerdown', function (e) {
      if (an && box && !box.contains(e.target) && !(opt.gehoertDazu && opt.gehoertDazu(e))) weg();
    }, true);
    window.addEventListener('keydown', function (e) {
      if (an && e.key === 'Escape') weg();
    }, true);

    return {
      zeigen: zeigen,
      weg: weg,
      offen: function () { return an; },
      ziehen: function (e) { zeigen(); starten(e, null); }
    };
  };

  /* Lage eines frei gesetzten Bildes relativ zu seinem Bezugsrahmen b (dem Feld). Links und Breite in Prozent
     der Feldbreite, oben in px: Editor und Karte sind verschieden breit, so sieht es in beiden gleich aus.
     Seitlich darf das Bild ueber das Feld hinaus (auch in den leeren Rand der Karte), nur nicht aus dem Fenster:
     links kann also negativ oder ueber 100 % sein. */
  window.lbRahmen.freieLage = function (r, b) {
    var br = b.getBoundingClientRect(), w = b.clientWidth || 1;
    var fenster = document.documentElement.clientWidth;
    var breite = Math.min(r.width, fenster);
    var x = Math.min(Math.max(0, r.left), fenster - breite);   // im Fenster halten
    var links = x - br.left - b.clientLeft + b.scrollLeft;
    var oben = Math.max(0, r.top - br.top - b.clientTop + b.scrollTop);
    function pz(x) { return Math.round(x / w * 1000) / 10 + '%'; }
    return { left: pz(links), top: Math.round(oben) + 'px', width: pz(breite) };
  };

  // Setzt die Lage aufs Bild (Element-Stil) und markiert es als frei
  window.lbRahmen.setzeFrei = function (img, lage) {
    img.removeAttribute('width'); img.removeAttribute('height');
    img.style.position = 'absolute';
    img.style.left = lage.left;
    img.style.top = lage.top;
    img.style.width = lage.width;
    img.style.height = 'auto';
    img.setAttribute('data-lb-frei', '1');
  };

  // ↺: Lage und Groesse weg, das Bild steht wieder im Text in Originalgroesse
  window.lbRahmen.loese = function (img) {
    ['position', 'left', 'top', 'width', 'height', 'z-index'].forEach(function (p) { img.style.removeProperty(p); });
    if (!img.getAttribute('style')) img.removeAttribute('style');
    img.removeAttribute('data-lb-frei');
  };
})();
