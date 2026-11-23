/* Deckliste: Auge zum Ausblenden und Umsortieren per Ziehen innerhalb derselben Ebene.
   Anki zieht Decks schon mit jQuery UI. Auf ein Deck einer anderen Ebene bleibt Ankis Verhalten (Unterdeck machen). */
$(function () {
  'use strict';
  var daten = window.LB_DECKS;
  if (!daten) return;
  var eltern = daten.eltern;

  // Auge in jede Zeile, neben das Zahnrad
  $('tr.deck').each(function () {
    var did = this.id;
    var zelle = $(this).find('td.opts');
    if (!zelle.length || !did) return;
    var knopf = $('<a class="lb-auge" title="Ausblenden"></a>').html(daten.auge);
    knopf.on('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      pycmd('lb_aus:' + did);
      return false;
    });
    zelle.prepend(knopf);
  });

  // Umsortieren: Linie ueber oder unter dem Ziel, solange es ein Geschwister ist
  var ziel = null, wo = null, quelle = null;

  function aufraeumen() {
    $('tr.deck').removeClass('lb-davor lb-danach');
    ziel = wo = null;
  }

  function zielUnter(x, y) {
    var el = document.elementFromPoint(x, y);
    var tr = el && el.closest ? el.closest('tr.deck') : null;
    return tr;
  }

  $('tr.deck').on('dragstart', function () { quelle = this.id; });
  $('tr.deck').on('drag', function (e, ui) {
    var ev = e.originalEvent || e;
    var x = ev.clientX, y = ev.clientY;
    if (x == null && ui) { x = ui.position.left; y = ui.position.top; }
    var tr = zielUnter(x, y);
    $('tr.deck').removeClass('lb-davor lb-danach');
    ziel = wo = null;
    if (!tr || tr.id === quelle || eltern[tr.id] === undefined || eltern[tr.id] !== eltern[quelle]) return;
    var r = tr.getBoundingClientRect();
    wo = y < r.top + r.height / 2 ? 'vor' : 'nach';
    ziel = tr.id;
    $(tr).addClass(wo === 'vor' ? 'lb-davor' : 'lb-danach');
  });
  function ordnen() {
    if (!ziel || !quelle) return false;
    pycmd('lb_ordnen:' + eltern[quelle] + ':' + quelle + ':' + ziel + ':' + wo);
    aufraeumen();
    return true;
  }

  // Liegt die Linie, wird umsortiert, egal welches Deck jQuery UI als Ablage sieht
  var ankiDrop = $('tr.deck').droppable('option', 'drop');
  $('tr.deck').droppable('option', 'drop', function (e, ui) {
    if (ordnen()) return;
    aufraeumen();
    return ankiDrop.call(this, e, ui);
  });
  $('tr.top-level-drag-row').on('drop', function () { aufraeumen(); });
  $('tr.deck').on('dragstop', function () { ordnen(); setTimeout(aufraeumen, 0); });
});
