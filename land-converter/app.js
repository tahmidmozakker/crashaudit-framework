/* জমির পরিমাপ — অ্যাপ লজিক */
(function () {
  'use strict';

  var APP_VERSION = '1.0.0';
  var BN_DIGITS = '০১২৩৪৫৬৭৮৯';
  var $ = function (sel) { return document.querySelector(sel); };

  var state = {
    amount: 1,
    unit: 'katha',
    bengaliDigits: true
  };

  /* ---------------- সংখ্যা ---------------- */

  function toBengaliDigits(str) {
    return String(str).replace(/[0-9]/g, function (d) { return BN_DIGITS[+d]; });
  }

  function toLatinDigits(str) {
    return String(str).replace(/[০-৯]/g, function (d) {
      return String(d.charCodeAt(0) - 0x09E6);
    });
  }

  function parseAmount(raw) {
    var s = toLatinDigits(raw || '')
      .replace(/[,,\s৳]/g, '')   // কমা, ফাঁকা, টাকার চিহ্ন
      .replace(/[৴-৹]/g, '');    // পুরোনো বাংলা ভগ্নাংশ চিহ্ন
    var m = s.match(/-?\d*\.?\d+/);
    if (!m) { return NaN; }
    return parseFloat(m[0]);
  }

  function decimalsFor(abs) {
    if (abs === 0) { return 0; }
    if (abs >= 10000) { return 0; }
    if (abs >= 100) { return 2; }
    if (abs >= 1) { return 3; }
    if (abs >= 0.01) { return 4; }
    return 6;
  }

  function formatNumber(n) {
    if (!isFinite(n)) { return '—'; }
    var d = decimalsFor(Math.abs(n));
    var out;
    try {
      out = new Intl.NumberFormat(
        state.bengaliDigits ? 'bn-BD-u-nu-beng' : 'en-US-u-nu-latn',
        { maximumFractionDigits: d, minimumFractionDigits: 0 }
      ).format(n);
    } catch (e) {
      out = trimZeros(n.toFixed(d));
      if (state.bengaliDigits) { out = toBengaliDigits(out); }
    }
    return out;
  }

  function plainNumber(n) {
    var d = decimalsFor(Math.abs(n));
    return trimZeros(n.toFixed(d));
  }

  function trimZeros(s) {
    return s.indexOf('.') < 0 ? s : s.replace(/\.?0+$/, '');
  }

  /* ---------------- রূপান্তর ---------------- */

  function unitById(id) {
    for (var i = 0; i < UNITS.length; i++) {
      if (UNITS[i].id === id) { return UNITS[i]; }
    }
    return UNITS[0];
  }

  function buildUnitSelect() {
    var sel = $('#unit');
    var groups = {};
    var order = [];
    UNITS.forEach(function (u) {
      if (!groups[u.group]) { groups[u.group] = []; order.push(u.group); }
      groups[u.group].push(u);
    });
    order.forEach(function (g) {
      var og = document.createElement('optgroup');
      og.label = g;
      groups[g].forEach(function (u) {
        var o = document.createElement('option');
        o.value = u.id;
        o.textContent = u.name;
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    sel.value = state.unit;
  }

  function buildChips() {
    var wrap = $('#chips');
    wrap.innerHTML = '';
    UNITS.filter(function (u) { return u.common; }).forEach(function (u) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.dataset.unit = u.id;
      b.textContent = u.name;
      b.addEventListener('click', function () {
        state.unit = u.id;
        $('#unit').value = u.id;
        save();
        render();
      });
      wrap.appendChild(b);
    });
  }

  function render() {
    var src = unitById(state.unit);
    var amount = isNaN(state.amount) ? 0 : state.amount;
    var base = amount * src.sqft;   // বর্গফুটে

    $('#basisText').textContent = ' — ' +
      formatNumber(amount) + ' ' + src.name;

    var note = $('#unitNote');
    if (src.note) { note.textContent = src.note; note.hidden = false; }
    else { note.hidden = true; }

    Array.prototype.forEach.call(document.querySelectorAll('.chip'), function (c) {
      c.classList.toggle('is-on', c.dataset.unit === state.unit);
    });

    var box = $('#results');
    box.innerHTML = '';
    var groups = {};
    var order = [];
    UNITS.forEach(function (u) {
      if (!groups[u.group]) { groups[u.group] = []; order.push(u.group); }
      groups[u.group].push(u);
    });

    order.forEach(function (g) {
      var sec = document.createElement('div');
      sec.className = 'res-group';
      var h = document.createElement('h2');
      h.textContent = g;
      var list = document.createElement('div');
      list.className = 'res-list';

      groups[g].forEach(function (u) {
        var val = base / u.sqft;
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'res' + (u.id === src.id ? ' is-source' : '');
        row.innerHTML = '<span class="res-val"></span><span class="res-unit"></span>';
        row.firstChild.textContent = formatNumber(val);
        row.lastChild.textContent = u.name;
        row.addEventListener('click', function () {
          copyText(plainNumber(val) + ' ' + u.name);
        });
        list.appendChild(row);
      });

      sec.appendChild(h);
      sec.appendChild(list);
      box.appendChild(sec);
    });
  }

  /* ---------------- তালিকা ---------------- */

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function buildTables() {
    var box = $('#tables');
    TABLES.forEach(function (t, i) {
      var d = document.createElement('details');
      d.className = 'acc';
      d.dataset.table = t.id;
      if (i === 0) { d.open = true; }
      var s = document.createElement('summary');
      s.textContent = t.title;
      var ul = document.createElement('ul');
      t.rows.forEach(function (r) {
        var li = document.createElement('li');
        li.textContent = r;
        li.dataset.text = r;
        ul.appendChild(li);
      });
      d.appendChild(s);
      d.appendChild(ul);
      box.appendChild(d);
    });

    var cv = $('#caveats');
    CAVEATS.forEach(function (c) {
      var li = document.createElement('li');
      li.textContent = c;
      cv.appendChild(li);
    });
  }

  function filterTables(q) {
    var needles = [q, toBengaliDigits(q), toLatinDigits(q)].filter(function (n, i, a) {
      return n && a.indexOf(n) === i;
    });
    var any = false;

    Array.prototype.forEach.call(document.querySelectorAll('#tables details'), function (d) {
      var shown = 0;
      Array.prototype.forEach.call(d.querySelectorAll('li'), function (li) {
        var text = li.dataset.text;
        var hit = !q || needles.some(function (n) { return text.indexOf(n) >= 0; });
        li.hidden = !hit;
        if (hit) { shown++; }
        li.innerHTML = (q && hit) ? highlight(text, needles) : esc(text);
      });
      var titleHit = !q || needles.some(function (n) {
        return d.querySelector('summary').textContent.indexOf(n) >= 0;
      });
      if (titleHit && q) {
        Array.prototype.forEach.call(d.querySelectorAll('li'), function (li) { li.hidden = false; });
        shown = d.querySelectorAll('li').length;
      }
      d.hidden = shown === 0;
      if (shown) { any = true; }
      if (q) { d.open = true; }
    });

    $('#noMatch').hidden = any;
  }

  function highlight(text, needles) {
    var out = esc(text);
    needles.forEach(function (n) {
      var safe = esc(n).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (!safe) { return; }
      out = out.replace(new RegExp('(' + safe + ')(?![^<]*>)', 'g'), '<mark>$1</mark>');
    });
    return out;
  }

  /* ---------------- পরিভাষা ---------------- */

  function buildGlossary() {
    var box = $('#glossary');
    GLOSSARY.forEach(function (g) {
      var d = document.createElement('details');
      d.className = 'acc term';
      var s = document.createElement('summary');
      s.textContent = g.term;
      var p = document.createElement('p');
      p.textContent = g.def;
      d.appendChild(s);
      d.appendChild(p);
      box.appendChild(d);
    });
  }

  /* ---------------- টুকিটাকি ---------------- */

  var toastTimer;
  function toast(msg) {
    var el = $('#toast');
    el.textContent = msg;
    el.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('is-on'); }, 1600);
  }

  function copyText(text) {
    var done = function () { toast('কপি হয়েছে: ' + text); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { legacyCopy(text, done); });
    } else {
      legacyCopy(text, done);
    }
  }

  function legacyCopy(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { toast(text); }
    document.body.removeChild(ta);
  }

  function save() {
    try {
      localStorage.setItem('jomi.unit', state.unit);
      localStorage.setItem('jomi.bn', state.bengaliDigits ? '1' : '0');
    } catch (e) { /* বেসরকারি মোডে উপেক্ষা */ }
  }

  function load() {
    try {
      var u = localStorage.getItem('jomi.unit');
      if (u && unitById(u).id === u) { state.unit = u; }
      var b = localStorage.getItem('jomi.bn');
      if (b !== null) { state.bengaliDigits = b === '1'; }
    } catch (e) { /* উপেক্ষা */ }
  }

  function refreshVersion() {
    $('#verLine').textContent = 'সংস্করণ ' +
      (state.bengaliDigits ? toBengaliDigits(APP_VERSION) : APP_VERSION) +
      ' • পুরোটাই অফলাইনে চলে, কোনো তথ্য বাইরে পাঠানো হয় না।';
  }

  function showTab(id) {
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (t) {
      t.classList.toggle('is-active', t.id === id);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.tabbtn'), function (b) {
      b.classList.toggle('is-active', b.dataset.tab === id);
    });
    window.scrollTo(0, 0);
  }

  /* ---------------- চালু ---------------- */

  function init() {
    load();
    buildUnitSelect();
    buildChips();
    buildTables();
    buildGlossary();

    $('#amount').value = state.bengaliDigits ? toBengaliDigits('1') : '1';
    $('#digitToggle').textContent = state.bengaliDigits ? '123' : '১২৩';
    refreshVersion();

    $('#amount').addEventListener('input', function () {
      state.amount = parseAmount(this.value);
      render();
    });
    $('#amount').addEventListener('focus', function () { this.select(); });

    $('#unit').addEventListener('change', function () {
      state.unit = this.value;
      save();
      render();
    });

    $('#digitToggle').addEventListener('click', function () {
      state.bengaliDigits = !state.bengaliDigits;
      this.textContent = state.bengaliDigits ? '123' : '১২৩';
      var inp = $('#amount');
      inp.value = state.bengaliDigits ? toBengaliDigits(toLatinDigits(inp.value))
                                      : toLatinDigits(inp.value);
      save();
      refreshVersion();
      render();
    });

    Array.prototype.forEach.call(document.querySelectorAll('.tabbtn'), function (b) {
      b.addEventListener('click', function () { showTab(b.dataset.tab); });
    });

    var searchTimer;
    $('#tableSearch').addEventListener('input', function () {
      var q = this.value.trim();
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { filterTables(q); }, 120);
    });

    state.amount = 1;
    render();

    /* ইনস্টল প্রম্পট */
    var deferred = null;
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferred = e;
      $('#installBtn').hidden = false;
    });
    $('#installBtn').addEventListener('click', function () {
      if (!deferred) { return; }
      deferred.prompt();
      deferred.userChoice.then(function () {
        deferred = null;
        $('#installBtn').hidden = true;
      });
    });
    window.addEventListener('appinstalled', function () {
      $('#installBtn').hidden = true;
      $('#installedMsg').hidden = false;
      toast('অ্যাপ ইনস্টল হয়েছে');
    });
    if (window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone) {
      $('#installedMsg').hidden = false;
    }

    /* অফলাইন ক্যাশ */
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function () {
        navigator.serviceWorker.register('sw.js').catch(function () { /* উপেক্ষা */ });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
