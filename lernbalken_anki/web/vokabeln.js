/* Vokabelliste: im Lernfenster (Buch im Balken, Knopf an markiertem Text) und in der Deckliste.
   vokabeln.oeffnen() zeigt die Liste, vokabeln.neu(wort) oeffnet gleich das Formular. */
(function () {
  'use strict';
  if (window.vokabeln) return;

  var el, liste = [], ansicht = 'liste', suche = '';
  var abfrage = null;   // {reihe, pos, gezeigt, gewusst, runde}

  function cmd(text, cb) { if (window.pycmd) pycmd(text, cb || function () {}); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function laden(weiter) {
    cmd('lb_vok_liste', function (d) { liste = d || []; if (weiter) weiter(); });
  }

  function bauen() {
    if (el) return;
    el = document.createElement('div');
    el.className = 'lb-vok';
    el.innerHTML =
      '<div class="lb-vok-karte" role="dialog" aria-modal="true" aria-label="Vocabulary">' +
        '<div class="lb-vok-kopf">' +
          '<div class="lb-vok-tabs" role="tablist">' +
            '<button type="button" data-a="liste">List</button>' +
            '<button type="button" data-a="abfrage">Quiz</button>' +
          '</div>' +
          '<button type="button" class="lb-vok-zu" title="Close (Esc)" aria-label="Close">×</button>' +
        '</div>' +
        '<div class="lb-vok-inhalt"></div>' +
      '</div>';
    document.body.appendChild(el);
    el.addEventListener('mousedown', function (e) { if (e.target === el) schliessen(); });
    el.querySelector('.lb-vok-zu').addEventListener('click', schliessen);
    el.querySelectorAll('.lb-vok-tabs button').forEach(function (b) {
      b.addEventListener('click', function () { zeige(b.dataset.a); });
    });
    el.addEventListener('keydown', tasten);
  }

  function inhalt() { return el.querySelector('.lb-vok-inhalt'); }

  function zeige(a) {
    ansicht = a;
    el.querySelectorAll('.lb-vok-tabs button').forEach(function (b) {
      b.classList.toggle('an', b.dataset.a === a || (a === 'form' && b.dataset.a === 'liste'));
    });
    if (a === 'liste') zeigeListe();
    else if (a === 'abfrage') starteAbfrage();
  }

  function offenMachen() {
    bauen();
    if (!el.classList.contains('offen')) {
      el.classList.add('offen');
      cmd('lb_vok_panel:1');
    }
  }

  function oeffnen() {
    offenMachen();
    laden(function () { zeige('liste'); });
  }

  function schliessen() {
    if (!el || !el.classList.contains('offen')) return;
    el.classList.remove('offen');
    cmd('lb_vok_panel:0');
    var zahl = document.querySelector('.lb-vok-zahl');   // Knopf in der Deckliste
    if (zahl) zahl.textContent = liste.length;
  }

  // Liste
  //////////////////////////////////////////////////////////////////////////

  function zeigeListe() {
    var c = inhalt();
    c.innerHTML =
      '<div class="lb-vok-leiste">' +
        '<input type="search" class="lb-vok-suche" placeholder="Search …" value="' + esc(suche) + '">' +
        '<button type="button" class="lb-vok-haupt lb-vok-neu">+ New</button>' +
      '</div>' +
      '<div class="lb-vok-liste"></div>';
    var s = c.querySelector('.lb-vok-suche');
    s.addEventListener('input', function () { suche = s.value; fuellen(); });
    c.querySelector('.lb-vok-neu').addEventListener('click', function () { formular({ wort: '', erklaerung: '' }); });
    fuellen();
  }

  function fuellen() {
    var box = el.querySelector('.lb-vok-liste');
    if (!box) return;
    var q = suche.trim().toLowerCase();
    var treffer = liste.filter(function (v) {
      return !q || (v.wort + ' ' + v.erklaerung).toLowerCase().indexOf(q) >= 0;
    });
    if (!liste.length) {
      box.innerHTML = '<p class="lb-vok-leer">No vocabulary yet. Select a word while studying and click ' +
        '<b>+ Vocab</b>, or click <b>+ New</b> here.</p>';
      return;
    }
    if (!treffer.length) { box.innerHTML = '<p class="lb-vok-leer">Nothing found.</p>'; return; }
    box.innerHTML = treffer.map(function (v) {
      return '<div class="lb-vok-eintrag" data-id="' + v.id + '">' +
        '<div class="lb-vok-text"><div class="lb-vok-wort">' + esc(v.wort) + '</div>' +
        '<div class="lb-vok-erkl">' + (v.erklaerung ? esc(v.erklaerung) : '<i>no explanation</i>') + '</div>' +
        (v.quelle ? '<div class="lb-vok-quelle">' + esc(v.quelle) + '</div>' : '') + '</div>' +
        '<div class="lb-vok-aktionen">' +
          '<button type="button" data-tun="bearbeiten" title="Edit">✎</button>' +
          '<button type="button" data-tun="weg" title="Delete">🗑</button>' +
        '</div></div>';
    }).join('');
    box.querySelectorAll('.lb-vok-eintrag').forEach(function (z) {
      var id = +z.dataset.id;
      var v = liste.filter(function (x) { return x.id === id; })[0];
      z.querySelector('[data-tun="bearbeiten"]').addEventListener('click', function () { formular(v); });
      var weg = z.querySelector('[data-tun="weg"]');
      weg.addEventListener('click', function () {
        if (!weg.classList.contains('sicher')) {
          weg.classList.add('sicher'); weg.textContent = 'Delete?';
          setTimeout(function () { if (weg.isConnected) { weg.classList.remove('sicher'); weg.textContent = '🗑'; } }, 2500);
          return;
        }
        cmd('lb_vok_weg:' + id, function () { laden(fuellen); });
      });
    });
  }

  // Neu / bearbeiten
  //////////////////////////////////////////////////////////////////////////

  function formular(v) {
    zeige('form');
    var c = inhalt();
    c.innerHTML =
      '<form class="lb-vok-form">' +
        '<label>Word<input name="wort" autocomplete="off" value="' + esc(v.wort) + '"></label>' +
        '<label>Explanation<textarea name="erklaerung" rows="4">' + esc(v.erklaerung) + '</textarea></label>' +
        '<div class="lb-vok-knoepfe">' +
          '<button type="button" class="lb-vok-zurueck">Cancel</button>' +
          '<button type="submit" class="lb-vok-haupt">Save</button>' +
        '</div>' +
        '<p class="lb-vok-hinweis">Ctrl + Enter saves</p>' +
      '</form>';
    var f = c.querySelector('form');
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var d = { wort: f.wort.value, erklaerung: f.erklaerung.value };
      if (v.id) d.id = v.id;
      if (!d.wort.trim()) { f.wort.focus(); return; }
      cmd('lb_vok_speichern:' + JSON.stringify(d), function () { laden(function () { zeige('liste'); }); });
    });
    f.querySelector('.lb-vok-zurueck').addEventListener('click', function () { zeige('liste'); });
    f.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); f.requestSubmit(); }
      else if (e.key === 'Enter' && e.target === f.wort) { e.preventDefault(); f.erklaerung.focus(); }
    });
    (v.wort ? f.erklaerung : f.wort).focus();
  }

  // Abfragen
  //////////////////////////////////////////////////////////////////////////

  function mischen(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }

  function starteAbfrage() {
    abfrage = { reihe: mischen(liste), pos: 0, gezeigt: false, gewusst: 0, gesamt: liste.length, fehler: {} };
    zeigeAbfrage();
  }

  function zeigeAbfrage() {
    var c = inhalt();
    if (!abfrage.gesamt) {
      c.innerHTML = '<p class="lb-vok-leer">No vocabulary to quiz yet.</p>';
      return;
    }
    if (abfrage.pos >= abfrage.reihe.length) {
      c.innerHTML = '<div class="lb-vok-ende"><div class="lb-vok-gross">Done!</div>' +
        '<p>' + abfrage.gewusst + ' of ' + abfrage.gesamt + ' known on the first try.</p>' +
        '<button type="button" class="lb-vok-haupt">Again</button></div>';
      c.querySelector('button').addEventListener('click', starteAbfrage);
      c.querySelector('button').focus();
      return;
    }
    var v = abfrage.reihe[abfrage.pos];
    c.innerHTML =
      '<div class="lb-vok-stand">' + Math.min(abfrage.gewusst + Object.keys(abfrage.fehler).length, abfrage.gesamt) +
        ' / ' + abfrage.gesamt + '<div class="lb-vok-spur"><div style="width:' +
        (100 * abfrage.gewusst / abfrage.gesamt) + '%"></div></div></div>' +
      '<div class="lb-vok-frage" tabindex="0">' +
        '<div class="lb-vok-gross">' + esc(v.wort) + '</div>' +
        (abfrage.gezeigt
          ? '<div class="lb-vok-antwort">' + (v.erklaerung ? esc(v.erklaerung) : '<i>no explanation</i>') + '</div>'
          : '<div class="lb-vok-tipp">Click or press Space to show the explanation</div>') +
      '</div>' +
      (abfrage.gezeigt
        ? '<div class="lb-vok-knoepfe mitte"><button type="button" class="lb-vok-nochmal">Again <kbd>1</kbd></button>' +
          '<button type="button" class="lb-vok-haupt lb-vok-gewusst">Got it <kbd>2</kbd></button></div>'
        : '');
    var frage = c.querySelector('.lb-vok-frage');
    frage.addEventListener('click', aufdecken);
    if (abfrage.gezeigt) {
      c.querySelector('.lb-vok-nochmal').addEventListener('click', function () { weiter(false); });
      c.querySelector('.lb-vok-gewusst').addEventListener('click', function () { weiter(true); });
    }
    frage.focus();
  }

  function aufdecken() { if (abfrage && !abfrage.gezeigt) { abfrage.gezeigt = true; zeigeAbfrage(); } }

  function weiter(gewusst) {
    var v = abfrage.reihe[abfrage.pos];
    if (gewusst) { if (!abfrage.fehler[v.id]) abfrage.gewusst++; }
    else { abfrage.fehler[v.id] = true; abfrage.reihe.push(v); }   // kommt am Ende der Runde nochmal
    abfrage.pos++;
    abfrage.gezeigt = false;
    zeigeAbfrage();
  }

  function tasten(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      if (ansicht === 'form') zeige('liste'); else schliessen();
      return;
    }
    if (ansicht !== 'abfrage' || !abfrage || /INPUT|TEXTAREA/.test(e.target.tagName)) return;
    if (!abfrage.gezeigt && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); aufdecken(); }
    else if (abfrage.gezeigt && e.key === '1') { e.preventDefault(); weiter(false); }
    else if (abfrage.gezeigt && (e.key === '2' || e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); weiter(true); }
  }

  function neu(wort) {
    offenMachen();
    laden(function () {
      var gleich = liste.filter(function (v) { return v.wort.toLowerCase() === String(wort).toLowerCase(); })[0];
      formular(gleich || { wort: wort, erklaerung: '' });
    });
  }

  window.vokabeln = { oeffnen: oeffnen, neu: neu, schliessen: schliessen };
})();
