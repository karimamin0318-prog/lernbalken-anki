/* Lernfenster: Image-Occlusion-Karten (Ankis "Image Occlusion") als ein Bild mit allen Boxen lernen.

   Alle Boxen des Bildes sind zugedeckt, egal welche Karte der Notiz gerade dran ist. Klick auf eine Box deckt sie
   (und alle Boxen ihrer Gruppe) auf, sie behaelt einen gestrichelten Rand. Nochmal Klick: wieder zu.
   Gezeichnet wird mit Ankis eigenem Code (anki.imageOcclusion), darum passen Form, Lage und Farbe genau zu Anki.
   Ankis setup() nimmt Filter an: onWillDrawShapes bekommt alle Formen der Karte (aktiv, inaktiv, Rueckseite)
   und gibt zurueck, was zugedeckt gezeichnet wird. Texte (Beschriftungen) bleiben immer sichtbar.
   Die Kartenvorlage ruft anki.imageOcclusion.setup() ohne Filter auf. Darum wird setup hier ersetzt: so zeichnet
   Anki schon beim ersten Mal (und bei jeder Groessenaenderung) mit Filter, die Loesung blitzt nie kurz auf.
   Schalter: window.lbBilderGanz (setzt das Add-on beim Laden des Lernfensters aus der Config bilder_ganz). */
(function () {
  'use strict';
  if (window.lbMasken) return;

  var offen = {};     // Gruppe (ordinal) -> true = aufgedeckt
  var formen = [];    // alle Formen vom letzten Zeichnen
  var rand = { farbe: '#212121' };

  function io() { return window.anki && anki.imageOcclusion; }
  function leinwand() { return document.getElementById('image-occlusion-canvas'); }
  function an() { return window.lbBilderGanz !== false; }   // erst beim Zeichnen fragen, steht evtl. spaeter im Kopf
  function istText(s) { return io() && io().Text && s instanceof io().Text; }

  function vorZeichnen(d) {
    formen = d.activeShapes.concat(d.inactiveShapes, d.highlightShapes);
    if (d.properties && d.properties.activeBorder) rand.farbe = d.properties.activeBorder.color || rand.farbe;
    return {
      activeShapes: formen.filter(function (s) { return istText(s) || !offen[s.ordinal]; }),
      inactiveShapes: [],
      highlightShapes: [],
      properties: d.properties
    };
  }

  function nachZeichnen(d, ctx) {
    var c = leinwand();
    if (!c) return;
    ctx.save();
    ctx.setLineDash([6, 4]);
    formen.forEach(function (s) {
      if (istText(s) || !offen[s.ordinal]) return;
      io().drawShape({ context: ctx, size: c, shape: s, fill: 'rgba(0,0,0,0)', stroke: rand.farbe, strokeWidth: 2 });
    });
    ctx.restore();
    var t = document.getElementById('toggle');   // Ankis "Toggle Masks" braucht es nicht mehr
    if (t) t.style.display = 'none';
  }

  var filter = { onWillDrawShapes: vorZeichnen, onDidDrawShapes: nachZeichnen };
  var ankiSetup = null;

  function zeichnen() {
    if (!ankiSetup || !leinwand()) return;
    try { ankiSetup.call(io(), filter); } catch (e) { /* dann bleibt Ankis eigene Anzeige */ }
  }

  // Aufruf aus der Kartenvorlage = neue Karte oder neue Seite: alles wieder zu
  function einbauen() {
    var o = io();
    if (!o || !o.setup || o.lbGefiltert) return;
    ankiSetup = o.setup;
    o.setup = function (optionen) {
      if (!an()) return ankiSetup.call(o, optionen);
      offen = {};
      formen = [];
      return ankiSetup.call(o, filter);
    };
    if (window.anki.setupImageCloze === ankiSetup) window.anki.setupImageCloze = o.setup;
    o.lbGefiltert = true;
  }
  einbauen();

  // Welche Box liegt unter dem Klick? Jede Form einzeln auf eine unsichtbare Leinwand malen und den Punkt pruefen.
  // So stimmt es auch fuer Ellipsen, Vielecke und gedrehte Boxen. Oberste (zuletzt gezeichnete) zuerst.
  function treffer(e) {
    var c = leinwand();
    if (!c || !c.width || !c.height) return null;
    var r = c.getBoundingClientRect();
    var x = Math.floor((e.clientX - r.left) * c.width / r.width);
    var y = Math.floor((e.clientY - r.top) * c.height / r.height);
    if (x < 0 || y < 0 || x >= c.width || y >= c.height) return null;
    var probe = document.createElement('canvas');
    probe.width = c.width;
    probe.height = c.height;
    var ctx = probe.getContext('2d');
    for (var i = formen.length - 1; i >= 0; i--) {
      var s = formen[i];
      if (istText(s)) continue;
      ctx.clearRect(0, 0, probe.width, probe.height);
      io().drawShape({ context: ctx, size: probe, shape: s, fill: '#000', stroke: '#000', strokeWidth: 6 });
      if (ctx.getImageData(x, y, 1, 1).data[3] > 0) return s;
    }
    return null;
  }

  document.addEventListener('click', function (e) {
    var c = leinwand();
    if (!c || e.target !== c || !an() || !ankiSetup) return;
    var s = treffer(e);
    if (!s) return;
    offen[s.ordinal] = !offen[s.ordinal];
    zeichnen();
  });

  window.lbMasken = { zeichnen: zeichnen, offen: function () { return offen; } };
})();
