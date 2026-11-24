/* Lernbalken in Anki: Fortschrittsbalken oben im Lernfenster.
   Python ruft lernbalken.setze(daten) (ohne Effekt) und lernbalken.richtig(daten) (mit Glitzer). */
(function () {
  'use strict';
  if (window.lernbalken) return;

  var el, fuell, offenEl, glanz, spitze, pctEl, nameEl, pfadEl, fachEl, heuteEl, innen, sternEl;
  var angezeigt = null;   // aktuell gezeigter Prozentwert
  var deckName = null;
  var serie = 0;
  var ton = { an: true, lautstaerke: 0.35 };
  var ruhig = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function bauen() {
    if (el) return;
    el = document.createElement('div');
    el.id = 'lb-balken';
    el.innerHTML =
      '<div class="lb-innen">' +
        '<div class="lb-kopf"><span class="lb-name"><span class="lb-pfad"></span><span class="lb-titel"></span></span>' +
        '<span class="lb-rechts">' +
        '<button type="button" class="lb-knopf lb-filter" data-art="neu" aria-pressed="false" ' +
        'title="Speedrun: only cards you have never seen, no daily limit">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/></svg>' +
        '<span>New only</span></button>' +
        '<button type="button" class="lb-knopf lb-filter" data-art="mc" aria-pressed="false" ' +
        'title="Only single and multiple choice questions, no flashcards">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><rect x="3.5" y="4" width="6" height="6" rx="1.5"/>' +
        '<rect x="3.5" y="14" width="6" height="6" rx="1.5"/><path d="M13 7h8M13 17h8"/></svg>' +
        '<span>MC only</span></button><span class="lb-trenner"></span>' +
        '<button type="button" class="lb-stern" title="Mark as important (key *)" aria-pressed="false">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 3.2l2.7 5.5 6 .9-4.35 4.25 1 6L12 17l-5.4 2.85 1-6L3.3 9.6l6-.9z"/></svg>' +
        '<span>Important</span></button></span></div>' +
        '<div class="lb-zeile"><div class="lb-spur"><div class="lb-offen"></div><div class="lb-fuell"><div class="lb-glanz"></div></div><div class="lb-spitze"></div></div>' +
        '<span class="lb-pct"></span></div>' +
        '<div class="lb-fuss"><span class="lb-fach"></span><span class="lb-heute"></span></div>' +
      '</div>';
    document.body.appendChild(el);
    document.documentElement.classList.add('lb-an');
    innen = el.querySelector('.lb-innen');
    fuell = el.querySelector('.lb-fuell');
    offenEl = el.querySelector('.lb-offen');
    glanz = el.querySelector('.lb-glanz');
    spitze = el.querySelector('.lb-spitze');
    pctEl = el.querySelector('.lb-pct');
    nameEl = el.querySelector('.lb-titel');
    pfadEl = el.querySelector('.lb-pfad');
    fachEl = el.querySelector('.lb-fach');
    heuteEl = el.querySelector('.lb-heute');
    sternEl = el.querySelector('.lb-stern');
    el.querySelectorAll('.lb-filter').forEach(function (k) {
      k.addEventListener('click', function (e) {
        e.preventDefault();
        k.blur();
        if (window.pycmd) pycmd('lb_filter:' + k.dataset.art);
      });
    });
    sternEl.addEventListener('click', function (e) {
      e.preventDefault();
      sternEl.blur();
      if (window.pycmd) pycmd('lb_wichtig');
    });
  }

  function stern(an) {
    bauen();
    var vorher = sternEl.classList.contains('an');
    sternEl.classList.toggle('an', !!an);
    sternEl.setAttribute('aria-pressed', an ? 'true' : 'false');
    sternEl.title = an ? 'Remove mark (key *)' : 'Mark as important (key *)';
    if (an && !vorher && !ruhig) {
      sternEl.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.35)' }, { transform: 'scale(1)' }], { duration: 320, easing: 'ease-out' });
    }
  }

  // Schalter "New only" und "MC only": der Zustand kommt aus Python (Config)
  function filter(f) {
    bauen();
    el.querySelectorAll('.lb-filter').forEach(function (k) {
      var an = !!(f && f[k.dataset.art]);
      k.classList.toggle('an', an);
      k.setAttribute('aria-pressed', an ? 'true' : 'false');
    });
  }

  function zahl(p) { return p.toFixed(1).replace('.', ',') + ' %'; }

  function texte(d) {
    pfadEl.textContent = d.pfad ? d.pfad + ' › ' : '';
    nameEl.textContent = d.name;
    fachEl.textContent = d.fach != null ? d.fach + ' ' + zahl(d.fachPct) : d.karten + ' cards';
    heuteEl.textContent = 'today ' + d.heute + ' ✓';
  }

  // p = kraeftiges Gruen (fest), offen = helles Gruen dahinter (Karten auf 5 min / 30 min / 3 h)
  function breite(p, sanft, offen) {
    offen = offen || 0;
    fuell.classList.toggle('ohne', !sanft);
    offenEl.classList.toggle('ohne', !sanft);
    offenEl.style.width = Math.min(100, p + offen) + '%';
    spitze.classList.toggle('ohne', !sanft);
    fuell.style.width = p + '%';
    spitze.style.left = p + '%';
    if (!sanft) { void fuell.offsetWidth; }
  }

  // Ohne Effekt: beim Start, beim Deckwechsel und nach falschen Antworten
  function setze(d) {
    bauen();
    if (d.ton) ton = d.ton;
    if (d.filter) filter(d.filter);
    if (!d.name) { el.hidden = true; return; }
    el.hidden = false;
    if (d.name !== deckName) serie = 0;
    deckName = d.name;
    texte(d);
    angezeigt = d.pct;
    breite(d.pct, false, d.offen);
    pctEl.textContent = zahl(d.pct);
  }

  function zaehlen(von, bis) {
    var start = performance.now(), dauer = 900;
    function schritt(t) {
      var x = Math.min(1, (t - start) / dauer);
      var e = 1 - Math.pow(1 - x, 3);
      pctEl.textContent = zahl(von + (bis - von) * e);
      if (x < 1) requestAnimationFrame(schritt);
    }
    requestAnimationFrame(schritt);
  }

  function spitzePos() {
    var spur = el.querySelector('.lb-spur');
    return { x: spur.offsetLeft + spur.offsetWidth * angezeigt / 100, y: spur.offsetTop + spur.offsetHeight / 2 };
  }

  var FARBEN = ['#4ade80', '#ffffff', '#bbf7d0', '#ffd36e', '#86efac', '#a7f3d0'];

  function funken(anzahl) {
    if (ruhig) return;
    var p = spitzePos();
    for (var i = 0; i < anzahl; i++) {
      var f = document.createElement('div');
      f.className = 'lb-funke';
      var g = 5 + Math.random() * 9;
      f.style.width = f.style.height = g + 'px';
      f.style.marginLeft = f.style.marginTop = (-g / 2) + 'px';
      f.style.left = p.x + 'px';
      f.style.top = p.y + 'px';
      f.style.background = FARBEN[i % FARBEN.length];
      innen.appendChild(f);
      // Hauptsaechlich nach oben und vorne spruehen, ein paar nach unten
      var winkel = (-160 + Math.random() * 200) * Math.PI / 180;
      var weite = 18 + Math.random() * 46;
      var dx = Math.cos(winkel) * weite, dy = Math.sin(winkel) * weite;
      var dreh = (Math.random() * 2 - 1) * 260;
      var anim = f.animate([
        { transform: 'translate(0,0) scale(.3) rotate(0deg)', opacity: 1 },
        { transform: 'translate(' + dx * .7 + 'px,' + dy * .7 + 'px) scale(1.15) rotate(' + dreh * .6 + 'deg)', opacity: 1, offset: .45 },
        { transform: 'translate(' + dx + 'px,' + (dy + 14) + 'px) scale(.2) rotate(' + dreh + 'deg)', opacity: 0 }
      ], { duration: 650 + Math.random() * 500, easing: 'cubic-bezier(.2,.7,.3,1)', delay: Math.random() * 120 });
      anim.onfinish = (function (n) { return function () { n.remove(); }; })(f);
    }
  }

  function plusEins() {
    var p = spitzePos();
    var s = document.createElement('div');
    var meilenstein = serie > 0 && serie % 5 === 0;
    s.className = 'lb-plus' + (meilenstein ? ' serie' : '');
    s.textContent = meilenstein ? '+1  ·  ' + serie + ' streak' : '+1';
    s.style.left = Math.min(Math.max(p.x, 20), innen.offsetWidth - 20) + 'px';
    s.style.top = (p.y + 4) + 'px';
    innen.appendChild(s);
    var a = s.animate([
      { transform: 'translate(-50%, 0) scale(.4)', opacity: 0 },
      { transform: 'translate(-50%, 10px) scale(1.25)', opacity: 1, offset: .22 },
      { transform: 'translate(-50%, 16px) scale(1)', opacity: 1, offset: .55 },
      { transform: 'translate(-50%, 30px) scale(.95)', opacity: 0 }
    ], { duration: meilenstein ? 1500 : 1100, easing: 'ease-out' });
    a.onfinish = function () { s.remove(); };
  }

  function huepfen(n) {
    n.animate([
      { transform: 'scale(1)' }, { transform: 'scale(1.25)' }, { transform: 'scale(1)' }
    ], { duration: 360, easing: 'ease-out' });
  }

  // Ton: kurzes, aufsteigendes Glitzern, mit der Serie etwas hoeher
  var ctx = null;
  function klingeln() {
    if (!ton.an) return;
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') ctx.resume();
      var jetzt = ctx.currentTime + 0.01;
      var hoch = Math.pow(2, Math.min(serie, 10) / 24);
      var laut = Math.max(0, Math.min(1, ton.lautstaerke));
      var master = ctx.createGain();
      master.gain.value = laut;
      master.connect(ctx.destination);
      [1318.5, 1760, 2637].forEach(function (f, i) {
        var t = jetzt + i * 0.055;
        [['sine', 1, 0.5], ['triangle', 2.003, 0.12]].forEach(function (art) {
          var o = ctx.createOscillator(), g = ctx.createGain();
          o.type = art[0];
          o.frequency.value = f * hoch * art[1];
          g.gain.setValueAtTime(0.0001, t);
          g.gain.exponentialRampToValueAtTime(art[2], t + 0.006);
          g.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);
          o.connect(g); g.connect(master);
          o.start(t); o.stop(t + 0.45);
        });
      });
    } catch (e) { /* ohne Ton weiter */ }
  }

  // Richtige Antwort: Balken laedt weiter, Glitzer, +1, Ton
  function richtig(d) {
    bauen();
    if (d.ton) ton = d.ton;
    if (d.filter) filter(d.filter);
    if (!d.name) return;
    if (d.name !== deckName || angezeigt == null) { setze(d); }
    serie += 1;
    var von = angezeigt;
    texte(d);
    angezeigt = d.pct;
    breite(d.pct, d.pct >= von, d.offen);
    if (d.pct >= von) zaehlen(von, d.pct); else pctEl.textContent = zahl(d.pct);

    glanz.classList.remove('los'); void glanz.offsetWidth; glanz.classList.add('los');
    spitze.classList.remove('leuchtet'); void spitze.offsetWidth; spitze.classList.add('leuchtet');
    // Funken starten, wenn der Balken ungefaehr angekommen ist
    setTimeout(function () { funken(14 + 3 * Math.min(serie, 10)); }, ruhig ? 0 : 260);
    plusEins();
    huepfen(heuteEl);
    klingeln();
  }

  // Falsche Antwort (oder 5 min): kein Glitzer, die Serie endet. Die helle Leiste waechst trotzdem leise mit.
  function falsch(d) {
    serie = 0;
    if (!d || !d.name || d.name !== deckName) return;
    texte(d);
    angezeigt = d.pct;
    breite(d.pct, true, d.offen);
    pctEl.textContent = zahl(d.pct);
  }

  window.lernbalken = { setze: setze, richtig: richtig, falsch: falsch, stern: stern, filter: filter };
})();
