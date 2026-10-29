/* Interfeys: sessiyalar paneli, sessiya sahifasi, mashq ekrani. Har bir mashq ekrani aniq bitta sessiyaga bog'langan. */
(function (V) {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var app = $('#app'), modalEl = $('#modal');
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fdate(t) { return t ? new Date(t).toLocaleString('uz', { dateStyle: 'short', timeStyle: 'short' }) : '—'; }
  function hue(id) { var h = 0; for (var i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 360; return h; }
  function color(id) { return 'hsl(' + hue(id) + ' 62% 38%)'; }
  function toast(m) { var d = document.createElement('div'); d.className = 'toast'; d.textContent = m; $('#toasts').appendChild(d); setTimeout(function () { d.remove(); }, 3200); }
  function settings() { return V.db().settings; }
  function applyTheme() { var t = settings().theme, dark = t === 'dark' || (t === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches); document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }
  function speak(t) { if (!settings().speech || !window.speechSynthesis || !window.SpeechSynthesisUtterance) return; try { speechSynthesis.cancel(); var u = new SpeechSynthesisUtterance(t); u.lang = 'en-US'; u.rate = .9; speechSynthesis.speak(u); } catch (e) {} }
  var canSpeak = function () { return !!(window.speechSynthesis && window.SpeechSynthesisUtterance); };
  var actx; function beep(ok) { if (!settings().sound) return; try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); var o = actx.createOscillator(), g = actx.createGain(); o.frequency.value = ok ? 740 : 190; g.gain.value = .05; o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + .12); } catch (e) {} }

  function modal(html) { modalEl.hidden = false; modalEl.innerHTML = '<div class="box" role="dialog" aria-modal="true">' + html + '</div>'; var f = $('input,textarea,select,button', modalEl); if (f) f.focus(); }
  function closeModal() { modalEl.hidden = true; modalEl.innerHTML = ''; }
  modalEl.addEventListener('click', function (e) { if (e.target === modalEl) closeModal(); });
  function confirmBox(text, label) { return new Promise(function (res) { modal('<h2>Tasdiqlang</h2><p>' + esc(text) + '</p><div class="row"><button class="btn d" id="cy">' + esc(label || 'Ha') + '</button><button class="btn" id="cn">Bekor qilish</button></div>'); $('#cy').onclick = function () { closeModal(); res(true); }; $('#cn').onclick = function () { closeModal(); res(false); }; }); }

  // ---- Marshrutlash ----
  var run = null, cur = null;   // run: joriy ekran sessiyasi {sid}
  function route() {
    closeModal(); var h = (location.hash || '#/').slice(2).split('/'), name = h[0] || 'home', sid = h[1];
    if ((name === 's' || name === 'run') && !V.db().sessions[sid]) { location.hash = '#/'; return; }
    if (name === 'run') return openRun(sid);
    run = null;
    if (name === 's') { V.setActive(sid); return page(vSession(sid), sid); }
    if (name === 'settings') return page(vSettings());
    page(vHome());
  }
  window.addEventListener('hashchange', route);
  function topbar() {
    var aid = V.activeId(), a = aid && V.session(aid);
    return '<header class="top"><a class="brand" href="#/"><span class="logo">T</span><span>Til Yo\'li <span class="mute hide-sm">· Lug\'at</span></span></a><span class="sp"></span>' +
      (a ? '<a class="chip" style="--sc:' + color(aid) + ';background:var(--sc);color:#fff" href="#/s/' + aid + '" title="Faol sessiya"><span class="dot" style="background:#fff"></span><span>Faol: ' + esc(a.name) + '</span></a>' : '<span class="mute">Faol sessiya yo\'q</span>') +
      '<button class="btn s" data-act="theme" aria-label="Mavzu">🌓</button><a class="btn s" href="#/settings">⚙️<span class="hide-sm"> Sozlamalar</span></a></header>';
  }
  function page(html, sid) {
    app.innerHTML = '<div style="--sc:' + (sid ? color(sid) : 'var(--g)') + '">' + topbar() + '<main class="page" id="main">' + html + '</main></div>'; window.scrollTo(0, 0);
  }

  // ---- Bosh sahifa: sessiyalar paneli ----
  var q = { text: '', sort: 'recent' };
  function sessionsHTML() {
    var list = V.list().filter(function (s) { return s.name.toLowerCase().indexOf(q.text.toLowerCase()) >= 0; });
    var st = {}; list.forEach(function (s) { st[s.id] = V.stats(s.id); });
    var cmp = { recent: function (a, b) { return (b.lastActivity || b.createdAt) - (a.lastActivity || a.createdAt); }, name: function (a, b) { return a.name.localeCompare(b.name); }, words: function (a, b) { return st[b.id].total - st[a.id].total; }, progress: function (a, b) { return st[b.id].percent - st[a.id].percent; }, created: function (a, b) { return b.createdAt - a.createdAt; } }[q.sort];
    list.sort(cmp);
    if (!V.list().length) return '<div class="card empty"><h2>Hali sessiya yo\'q</h2><p>Birinchi lug\'at sessiyangizni yarating: masalan «English Unit 1» yoki «IELTS Words».</p><button class="btn p" data-act="new">＋ Yangi sessiya</button></div>';
    if (!list.length) return '<div class="card empty">«' + esc(q.text) + '» bo\'yicha sessiya topilmadi.</div>';
    return '<div class="grid cards">' + list.map(function (s) {
      var x = st[s.id], isA = V.activeId() === s.id;
      return '<a class="card scard' + (isA ? ' active' : '') + '" style="--sc:' + color(s.id) + '" href="#/s/' + s.id + '" data-sid="' + s.id + '"><div class="row sb"><h3>' + esc(s.name) + '</h3>' + (isA ? '<span class="chip g">Faol</span>' : '') + '</div>' +
        '<p class="mute" style="margin:0 0 .6rem">' + x.total + ' ta so\'z · ' + esc(s.lang) + '</p><div class="bar" role="progressbar" aria-label="Progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + x.percent + '"><i style="width:' + x.percent + '%"></i></div>' +
        '<p class="mute" style="margin:.5rem 0 0;font-size:.88rem">' + x.mastered + ' o\'zlashtirilgan · ' + x.learning + ' o\'rganilmoqda · ' + x.fresh + ' yangi</p>' +
        '<div class="row" style="margin-top:.5rem">' + (s.status === 'paused' ? '<span class="chip y">To\'xtatilgan</span>' : '') + (s.run ? '<span class="chip">Davom etayotgan raund</span>' : '') + (x.dueNow ? '<span class="chip r">' + x.dueNow + ' takrorlash</span>' : '') + '</div></a>';
    }).join('') + '</div>';
  }
  function vHome() {
    var mig = V.db().migrations.filter(function (m) { return m.id.indexOf('legacy-') === 0 && !m.dismissed; });
    return '<div class="row sb"><div><h1>Lug\'at sessiyalari</h1><p class="mute">Har bir sessiya faqat o\'z so\'zlari bilan ishlaydi.</p></div><button class="btn p" data-act="new">＋ Yangi sessiya</button></div>' +
      mig.map(function (m) { return '<div class="card" style="background:var(--yl)"><div class="row sb"><span>🔁 <b>Migratsiya:</b> eski Til Yo\'li kursidan <b>' + m.words + '</b> ta so\'z va ularning progressi «' + esc(V.session(m.sessionId) ? V.session(m.sessionId).name : '') + '» sessiyasiga ko\'chirildi. Eski ma\'lumot o\'zgarmadi.</span><button class="btn s" data-act="dismiss" data-id="' + esc(m.id) + '">Yopish</button></div></div>'; }).join('') +
      '<div class="row" style="margin-bottom:1rem"><label class="sr" for="sq">Sessiya qidirish</label><input id="sq" type="search" placeholder="Sessiya qidirish…" value="' + esc(q.text) + '" style="flex:1;min-width:180px"><label class="sr" for="ss">Saralash</label><select id="ss">' + [['recent', 'Oxirgi faollik'], ['name', 'Nom'], ['words', "So'zlar soni"], ['progress', 'Progress'], ['created', 'Yaratilgan sana']].map(function (o) { return '<option value="' + o[0] + '"' + (q.sort === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select></div><div id="slist">' + sessionsHTML() + '</div>';
  }

  // ---- Sessiya sahifasi ----
  var wf = '';
  function wordRows(sid) {
    var s = V.session(sid), f = wf.toLowerCase(), ws = V.words(sid).filter(function (w) { return !f || w.en.toLowerCase().indexOf(f) >= 0 || w.tr.join(' ').toLowerCase().indexOf(f) >= 0; });
    if (!s.order.length) return '<div class="empty"><b>Bu sessiyada hali so\'z yo\'q.</b><br>Yuqoridagi shakl orqali so\'z qo\'shing yoki «Ko\'p so\'z import» tugmasini bosing.</div>';
    if (!ws.length) return '<div class="empty">Hech narsa topilmadi.</div>';
    return '<div class="tw"><table><thead><tr><th>Inglizcha</th><th>Tarjima</th><th>Holat</th><th></th></tr></thead><tbody>' + ws.map(function (w) {
      var p = V.prog(s, w.id), stt = !p.seen ? ['Yangi', 'new'] : p.box >= V.MASTER_BOX ? ["O'zlashtirilgan", 'mastered'] : ["O'rganilmoqda", 'learning'];
      return '<tr><td><b>' + esc(w.en) + '</b>' + (w.pron ? ' <span class="mute">' + esc(w.pron) + '</span>' : '') + (w.example ? '<br><span class="mute" style="font-size:.85rem">' + esc(w.example) + '</span>' : '') + '</td><td>' + esc(w.tr.join('; ')) + '</td><td><span class="status-' + stt[1] + '">' + stt[0] + '</span>' + (p.mistake ? ' <span class="chip r">xato</span>' : '') + '</td><td style="white-space:nowrap"><button class="btn s" data-act="ew" data-id="' + w.id + '">Tahrir</button> <button class="btn s" data-act="dw" data-id="' + w.id + '">O\'chirish</button></td></tr>';
    }).join('') + '</tbody></table></div>';
  }
  function vSession(sid) {
    var s = V.session(sid), x = V.stats(sid), paused = s.status === 'paused', empty = !s.order.length, sum = s.lastSummary;
    var modeName = { learn: "O'rganish", review: 'Takrorlash', mistakes: 'Xatolar', test: 'Yakuniy test' };
    var start = s.run ? '<button class="btn p" data-act="resume">▶ Davom etish (' + modeName[s.run.mode] + ', ' + s.run.i + '/' + s.run.queue.length + ')</button>' : '<button class="btn p" data-act="start" data-m="learn"' + (empty || paused ? ' disabled' : '') + '>▶ O\'rganishni boshlash</button>';
    var s4 = function (v, l) { return '<div class="card stat"><b>' + v + '</b><span>' + l + '</span></div>'; };
    return '<p><a href="#/">← Barcha sessiyalar</a></p><div class="card shead"><div class="row sb"><div><h1>' + esc(s.name) + '</h1><div class="row"><span class="chip g">Faol sessiya</span>' + (paused ? '<span class="chip y">To\'xtatilgan</span>' : '') + '<span class="chip">' + esc(s.lang) + '</span><span class="mute">' + x.total + ' ta so\'z</span></div></div><div class="row"><button class="btn s" data-act="rename">Nomini o\'zgartirish</button><button class="btn s" data-act="pause">' + (paused ? 'Davom ettirish' : "To'xtatish") + '</button><button class="btn s" data-act="restart">Qayta boshlash</button><button class="btn s" data-act="delete">O\'chirish</button></div></div>' +
      '<div class="bar" style="margin:.9rem 0 .3rem"><i style="width:' + x.percent + '%"></i></div><p class="mute" style="margin:0">Progress: ' + x.percent + '% o\'zlashtirilgan</p></div>' +
      (paused ? '<div class="card" style="background:var(--yl)">Sessiya to\'xtatilgan. Mashq qilish uchun «Davom ettirish» ni bosing.</div>' : '') +
      '<div class="grid g4">' + s4(x.total, 'Jami so\'zlar') + s4(x.fresh, 'Yangi') + s4(x.learning, "O'rganilmoqda") + s4(x.mastered, "O'zlashtirilgan") + s4(x.wrong, "Xato javoblar") + s4(x.accuracy == null ? '—' : x.accuracy + '%', 'Aniqlik') + s4(x.rounds, 'Tugallangan raundlar') + s4(x.dueNow, 'Takrorlash kerak') + '</div>' +
      '<div class="card"><div class="row sb"><span class="mute">Oxirgi faollik: <b>' + fdate(x.lastActivity) + '</b> · Keyingi takrorlash: <b>' + (x.dueNow ? 'hozir (' + x.dueNow + ' ta)' : x.nextDue ? fdate(x.nextDue) : '—') + '</b></span></div></div>' +
      (empty ? '<div class="card empty"><b>Bu sessiyada hali so\'z yo\'q.</b><br>Mashq boshlash uchun avval so\'z qo\'shing yoki import qiling.</div>' : '') +
      '<div class="card"><h2>Mashq</h2><div class="row">' + start + '<button class="btn" data-act="start" data-m="review"' + (empty || paused ? ' disabled' : '') + '>🔁 Takrorlash (' + x.dueNow + ')</button><button class="btn" data-act="start" data-m="mistakes"' + (empty || paused || !x.mistakes ? ' disabled' : '') + '>🧩 Xato so\'zlar (' + x.mistakes + ')</button><button class="btn" data-act="start" data-m="test"' + (empty || paused ? ' disabled' : '') + '>🏁 Yakuniy test</button></div></div>' +
      (sum ? '<div class="card"><h3>Oxirgi raund (' + modeName[sum.mode] + ', ' + fdate(sum.ts) + ')</h3><p class="mute" style="margin:0">Aniqlik ' + sum.accuracy + '% · ' + sum.correct + '/' + sum.total + ' birinchi urinishda to\'g\'ri' + (sum.passed === true ? ' · ✅ test topshirildi' : sum.passed === false ? ' · ❌ test topshirilmadi' : '') + '</p></div>' : '') +
      '<div class="card"><div class="row sb"><h2 style="margin:0">So\'zlar</h2><button class="btn s" data-act="import">⬆ Ko\'p so\'z import</button></div>' +
      '<form id="wform" class="row" style="align-items:end;margin-top:.6rem"><div style="flex:1;min-width:140px"><label for="w_en">Inglizcha</label><input id="w_en" name="en" required maxlength="80" style="width:100%" autocomplete="off"></div><div style="flex:1;min-width:140px"><label for="w_tr">Tarjima (; bilan bir nechta)</label><input id="w_tr" name="tr" required style="width:100%" autocomplete="off"></div><div style="flex:1;min-width:140px"><label for="w_ex">Misol gap (ixtiyoriy)</label><input id="w_ex" name="example" style="width:100%" autocomplete="off"></div><button class="btn p" type="submit">＋ Qo\'shish</button></form><p class="err" id="werr" role="alert"></p>' +
      '<label class="sr" for="wq">So\'z qidirish</label><input id="wq" type="search" placeholder="So\'z qidirish…" value="' + esc(wf) + '" style="width:100%;margin:.4rem 0"><div id="wlist">' + wordRows(sid) + '</div></div>';
  }

  // ---- Sozlamalar ----
  function vSettings() {
    var d = V.db(), seg = function (k, o) { return '<div class="row">' + o.map(function (x) { return '<button class="btn s' + (String(d.settings[k]) === String(x[0]) ? ' p' : '') + '" data-act="set" data-k="' + k + '" data-v="' + x[0] + '">' + x[1] + '</button>'; }).join('') + '</div>'; };
    return '<p><a href="#/">← Orqaga</a></p><h1>Sozlamalar</h1><div class="card"><h3>Mavzu</h3>' + seg('theme', [['auto', 'Avto'], ['light', '☀️ Yorug\''], ['dark', '🌙 Qorong\'i']]) + '</div>' +
      '<div class="card"><h3>Ovoz</h3><div class="row"><button class="btn s' + (d.settings.sound ? ' p' : '') + '" data-act="tog" data-k="sound">Effektlar: ' + (d.settings.sound ? 'yoqiq' : 'o\'chiq') + '</button><button class="btn s' + (d.settings.speech ? ' p' : '') + '" data-act="tog" data-k="speech">Talaffuz: ' + (d.settings.speech ? 'yoqiq' : 'o\'chiq') + '</button></div>' + (canSpeak() ? '' : '<p class="mute">Bu brauzerda talaffuz (TTS) yo\'q.</p>') + '</div>' +
      '<div class="card"><h3>Zaxira nusxa</h3><p class="mute">Barcha sessiyalar shu brauzerda (localStorage) saqlanadi. Boshqa qurilmaga ko\'chirish uchun eksport qiling.</p><div class="row"><button class="btn s" data-act="export">⬇ Eksport (JSON)</button><label class="btn s" style="cursor:pointer;margin:0">⬆ Import<input type="file" id="imp" accept="application/json" hidden></label></div></div>' +
      '<div class="card"><h3>Eski Til Yo\'li ma\'lumoti</h3><p class="mute">Eski kursdagi o\'rganilgan so\'zlar va progress alohida sessiyaga ko\'chiriladi. Eski ma\'lumot o\'chirilmaydi va o\'zgarmaydi.</p><button class="btn s" data-act="migrate">🔁 Eski ma\'lumotni qidirish va ko\'chirish</button>' +
      (d.migrations.filter(function (m) { return m.id.indexOf('legacy-') === 0; }).map(function (m) { return '<p class="mute" style="margin:.5rem 0 0">✔ ' + fdate(m.time) + ': ' + m.words + ' ta so\'z (' + esc(m.from) + ')</p>'; }).join('')) + '</div>';
  }

  // ---- Mashq ekrani (aniq bitta sessiyaga bog'langan) ----
  function openRun(sid) {
    var s = V.session(sid); V.setActive(sid);
    if (!s.run || V.runDone(sid)) { if (s.run && V.runDone(sid)) return finish(sid); location.hash = '#/s/' + sid; return; }
    run = { sid: sid }; nextQuestion();
  }
  function rhead(sid) {
    var s = V.session(sid), r = s.run, pct = r.queue.length ? 100 * r.i / r.queue.length : 0, names = { learn: "O'rganish", review: 'Takrorlash', mistakes: 'Xato so\'zlar', test: 'Yakuniy test' };
    return '<div id="run" style="--sc:' + color(sid) + '"><div class="r-top"><button class="x" data-act="quit" aria-label="Mashqni to\'xtatish">✕</button><div class="bar" role="progressbar" aria-label="Progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(pct) + '"><i style="width:' + pct + '%"></i></div></div>' +
      '<div class="sess-chip" data-testid="session-chip"><span class="dot"></span><span>' + esc(s.name) + '</span><span class="mute">· ' + names[r.mode] + '</span></div>';
  }
  function nextQuestion() {
    var sid = run.sid, s = V.session(sid);
    if (V.runDone(sid)) return finish(sid);
    var qn = s.run.queue[s.run.i];
    try { V.assertQuestion(sid, qn); } catch (e) { app.innerHTML = '<main class="page"><div class="card"><h2>Xavfsizlik tekshiruvi</h2><p>' + esc(e.message) + '</p><a class="btn" href="#/s/' + sid + '">Sessiyaga qaytish</a></div></main>'; return; }
    cur = { q: qn, sel: null, checked: false, picked: [], matched: {}, wrongM: {}, revealed: false };
    var w = qn.w ? s.words[qn.w] : null, body = '', foot = '', t = qn.type;
    var spk = function (txt) { return canSpeak() && settings().speech ? '<button class="spk" data-act="say" data-t="' + esc(txt) + '" aria-label="Talaffuz">🔊</button>' : ''; };
    if (t === 'study') {
      body = '<p class="q-hint">Yangi so\'z</p><div class="card" style="text-align:center"><div class="q-word" style="justify-content:center">' + esc(w.en) + spk(w.en) + '</div>' + (w.pron ? '<p class="mute">' + esc(w.pron) + '</p>' : '') + '<div id="trv"><p style="font-size:1.5rem;font-weight:800;margin:.3rem 0">' + esc(w.tr.join('; ')) + '</p></div>' + (w.example ? '<p class="mute">«' + esc(w.example) + '»' + (w.exampleTr ? '<br>' + esc(w.exampleTr) : '') + '</p>' : '') + '<button class="btn s" data-act="toggle-tr">Tarjimani yashirish</button></div>';
      foot = '<button class="btn p" id="primary" data-act="study-next">Tushundim →</button>';
    } else if (t === 'flash') {
      var front = qn.dir === 'en-tr' ? w.en : w.tr[0];
      body = '<p class="q-hint">' + (qn.dir === 'en-tr' ? 'Tarjimasini eslang' : 'Inglizchasini eslang') + '</p><div class="fcard"><div class="q-word">' + esc(front) + (qn.dir === 'en-tr' ? spk(w.en) : '') + '</div><div id="ans" hidden><p style="font-size:1.4rem;font-weight:800;margin:.3rem 0">' + esc(qn.dir === 'en-tr' ? w.tr.join('; ') : w.en) + '</p>' + (w.example ? '<p class="mute">«' + esc(w.example) + '»</p>' : '') + '</div><button class="btn s" data-act="reveal" id="rv">Javobni ko\'rsatish</button></div>';
      foot = '<div class="row" id="selfgrade" hidden><button class="btn p" data-act="know">✅ Bilardim</button><button class="btn d" data-act="dunno">❌ Bilmadim</button></div>';
    } else if (t === 'mc') {
      body = '<p class="q-hint">' + (qn.dir === 'en-tr' ? 'Tarjimasini tanlang' : 'Inglizcha so\'zni tanlang') + '</p><div class="q-word">' + esc(qn.dir === 'en-tr' ? w.en : w.tr.join('; ')) + (qn.dir === 'en-tr' ? spk(w.en) : '') + '</div><div class="opts" role="radiogroup" aria-label="Javob variantlari">' + qn.options.map(function (o, i) { return '<button class="opt" role="radio" aria-checked="false" data-act="opt" data-i="' + i + '"><kbd>' + (i + 1) + '</kbd>' + esc(o) + '</button>'; }).join('') + '</div>';
      foot = '<button class="btn p" id="primary" data-act="check" disabled>Tekshirish</button>';
    } else if (t === 'type' || t === 'spell') {
      var prompt = t === 'spell' ? '<p class="q-hint">Inglizcha yozing (imlo)</p><div class="q-word">' + esc(w.tr.join('; ')) + spk(w.en) + '</div><div class="pattern" aria-label="' + w.en.replace(/[^ ]/g, '_').length + ' harf">' + esc(qn.pattern) + '</div>' : qn.dir === 'en-tr' ? '<p class="q-hint">Tarjimasini yozing</p><div class="q-word">' + esc(w.en) + spk(w.en) + '</div>' : '<p class="q-hint">Inglizcha so\'zni yozing</p><div class="q-word">' + esc(w.tr.join('; ')) + '</div>';
      body = prompt + '<label class="sr" for="ti">Javobingiz</label><input class="inp" id="ti" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Javobingiz">';
      foot = '<button class="btn p" id="primary" data-act="check" disabled>Tekshirish</button>';
    } else if (t === 'scramble') {
      body = '<p class="q-hint">Harflardan so\'z tuzing</p><div class="q-word">' + esc(w.tr.join('; ')) + '</div><div class="tray" id="tray" aria-live="polite" aria-label="Sizning javobingiz"></div><div class="tray" style="border:0" id="bank">' + qn.letters.map(function (l, i) { return '<button class="tile" data-act="tile" data-i="' + i + '">' + esc(l) + '</button>'; }).join('') + '</div>';
      foot = '<button class="btn p" id="primary" data-act="check" disabled>Tekshirish</button>';
    } else if (t === 'match') {
      body = '<p class="q-hint">Juftlarini toping</p><div class="mcols"><div class="grid" id="ml">' + qn.left.map(function (o) { return '<button class="opt" data-act="m" data-side="l" data-id="' + o.id + '">' + esc(o.t) + '</button>'; }).join('') + '</div><div class="grid" id="mr">' + qn.right.map(function (o) { return '<button class="opt" data-act="m" data-side="r" data-id="' + o.id + '">' + esc(o.t) + '</button>'; }).join('') + '</div></div>';
    }
    var tag = qn.retry ? '<p class="mute">↩️ Qayta urinib ko\'ring</p>' : '';
    app.innerHTML = rhead(sid) + '<div class="r-body" id="rbody">' + tag + body + '</div><div class="fb" id="fb"><div class="fb-in"><span class="msg" id="msg" role="status" aria-live="polite"></span><span id="fbtn">' + foot + '</span></div></div></div>';
    if (t === 'type' || t === 'spell') { var ti = $('#ti'); ti.focus(); ti.oninput = function () { $('#primary').disabled = !ti.value.trim(); }; }
    if (t === 'mc' && qn.dir === 'en-tr') speak(w.en);
  }
  function feedback(ok, res) {
    var fb = $('#fb'); fb.className = 'fb pop ' + (ok ? 'good' : 'bad');
    $('#msg').innerHTML = ok ? '<b>' + esc(['To\'g\'ri!', 'Ajoyib!', 'Zo\'r!', 'Barakalla!'][Math.floor(Math.random() * 4)]) + '</b>' : '<b>Noto\'g\'ri</b><small>To\'g\'ri javob: <b>' + esc(res.correct) + '</b></small><small>' + esc(res.explain) + '</small>';
    if (!ok && res.close) $('#msg').insertAdjacentHTML('afterbegin', '');
    beep(ok); if (!ok) { var b = $('#rbody'); b.classList.add('shake'); }
  }
  function cont(ok) {
    $('#fbtn').innerHTML = '<button class="btn ' + (ok ? 'p' : 'd') + '" id="primary" data-act="next">Davom etish</button>'; $('#primary').focus();
    var r = V.session(run.sid).run, bar = $('.r-top .bar i'); if (bar) bar.style.width = Math.min(100, 100 * (r.i + 1) / r.queue.length) + '%';
  }
  function check() {
    var qn = cur.q, sid = run.sid, input; if (cur.checked) return;
    if (qn.type === 'mc') { if (cur.sel == null) return; input = qn.options[cur.sel]; }
    else if (qn.type === 'type' || qn.type === 'spell') input = $('#ti').value;
    else input = cur.picked.map(function (i) { return qn.letters[i]; }).join('');
    var res = V.grade(sid, qn, input); if (res.empty) return; cur.checked = true;
    V.answer(sid, qn, res.ok, [qn.w], input);
    if (qn.type === 'mc') document.querySelectorAll('.opt').forEach(function (b) { var o = qn.options[+b.dataset.i]; b.disabled = true; if (V.grade(sid, qn, o).ok) b.classList.add('good'); else if (+b.dataset.i === cur.sel) b.classList.add('bad'); });
    if ($('#ti')) $('#ti').disabled = true;
    feedback(res.ok, res); cont(res.ok);
  }
  function matchClick(btn) {
    var side = btn.dataset.side; if (btn.classList.contains('gone') || cur.checked) return;
    document.querySelectorAll('.opt.sel[data-side="' + side + '"]').forEach(function (b) { b.classList.remove('sel'); }); btn.classList.add('sel'); cur[side === 'l' ? 'mL' : 'mR'] = btn;
    if (cur.mL && cur.mR) {
      var a = cur.mL, b = cur.mR;
      if (a.dataset.id === b.dataset.id) { a.classList.remove('sel'); b.classList.remove('sel'); a.classList.add('good'); b.classList.add('good'); beep(true); setTimeout(function () { a.classList.add('gone'); b.classList.add('gone'); }, 300); cur.matched[a.dataset.id] = 1; }
      else { [a, b].forEach(function (x) { x.classList.add('bad', 'shake'); setTimeout(function () { x.classList.remove('bad', 'shake', 'sel'); }, 420); }); beep(false); cur.wrongM[a.dataset.id] = 1; cur.wrongM[b.dataset.id] = 1; }
      cur.mL = cur.mR = null;
      if (Object.keys(cur.matched).length === cur.q.ws.length) {
        cur.checked = true; var wrong = Object.keys(cur.wrongM).length ? cur.wrongM : true; V.answer(run.sid, cur.q, wrong, cur.q.ws); var ok = wrong === true;
        setTimeout(function () { var fb = $('#fb'); fb.className = 'fb pop ' + (ok ? 'good' : 'bad'); $('#msg').innerHTML = ok ? '<b>Hammasi to\'g\'ri!</b>' : '<b>Tugadi</b><small>Xato juftliklar shu sessiyaning xatolar ro\'yxatiga qo\'shildi.</small>'; cont(ok); }, 380);
      }
    }
  }
  function tileClick(btn) {
    var qn = cur.q, i = +btn.dataset.i; if (cur.checked) return;
    if (btn.dataset.in) cur.picked = cur.picked.filter(function (x) { return x !== i; }); else cur.picked.push(i);
    $('#tray').innerHTML = cur.picked.map(function (j) { return '<button class="tile" data-act="tile" data-in="1" data-i="' + j + '" aria-label="' + esc(qn.letters[j]) + ' ni olib tashlash">' + esc(qn.letters[j]) + '</button>'; }).join('');
    document.querySelectorAll('#bank .tile').forEach(function (b) { b.disabled = cur.picked.indexOf(+b.dataset.i) >= 0; }); $('#primary').disabled = !cur.picked.length;
  }
  function finish(sid) {
    var s = V.session(sid), sum = V.finishRun(sid), names = { learn: "O'rganish", review: 'Takrorlash', mistakes: 'Xato so\'zlar', test: 'Yakuniy test' };
    var words = sum.wordIds.map(function (id) { var w = s.words[id]; return '<span class="pill' + (sum.wrongIds.indexOf(id) >= 0 ? ' bad' : '') + '">' + esc(w.en) + ' — ' + esc(w.tr[0]) + '</span>'; }).join('');
    var x = V.stats(sid); beep(true);
    app.innerHTML = '<div id="run" style="--sc:' + color(sid) + '"><div class="sess-chip" style="padding-top:1rem"><span class="dot"></span><span>' + esc(s.name) + '</span></div><div class="r-body center"><div style="font-size:4rem">' + (sum.passed === false ? '😕' : sum.accuracy >= 80 ? '🏆' : '🎉') + '</div><h1>' + names[sum.mode] + ' tugadi</h1>' +
      (sum.passed === true ? '<p><span class="chip g">Test topshirildi</span></p>' : sum.passed === false ? '<p><span class="chip r">Test topshirilmadi (kamida 70% kerak)</span></p>' : '') +
      '<div class="grid g4" style="margin:1rem 0"><div class="card stat"><b>' + sum.accuracy + '%</b><span>Aniqlik</span></div><div class="card stat"><b>' + sum.correct + '/' + sum.total + '</b><span>Birinchi urinishda</span></div><div class="card stat"><b>' + x.mastered + '</b><span>O\'zlashtirilgan</span></div><div class="card stat"><b>' + sum.wrongIds.length + '</b><span>Xato so\'zlar</span></div></div>' +
      '<div class="card" style="text-align:left"><h3>«' + esc(s.name) + '» so\'zlari</h3>' + words + (sum.wrongIds.length ? '<p class="mute">Qizil — xato qilingan so\'zlar. Ular faqat shu sessiyada takrorlanadi.</p>' : '') + '</div>' +
      '<div class="grid">' + (sum.wrongIds.length ? '<button class="btn p block" data-act="start2" data-m="mistakes">🧩 Xatolarni takrorlash</button>' : '') + '<a class="btn block" id="primary" href="#/s/' + sid + '">Sessiyaga qaytish</a></div></div></div>';
    run = { sid: sid }; var p = $('#primary'); if (p) p.focus();
    try { history.replaceState(null, '', '#/s/' + sid); } catch (e) {}
  }

  // ---- Boshqaruv amallari ----
  function curSid() { var m = /^#\/s\/(.+)$/.exec(location.hash); return m ? m[1] : (run && run.sid); }
  function startMode(sid, mode, fresh) {
    var r = V.startRun(sid, mode, { fresh: fresh }); if (r.error) { toast(r.message); route(); return; }
    if (location.hash === '#/run/' + sid) route(); else location.hash = '#/run/' + sid;
  }
  function newSessionForm() {
    modal('<h2>Yangi sessiya</h2><form id="nf"><label for="nn">Sessiya nomi</label><input id="nn" maxlength="60" required placeholder="Masalan: English Unit 1" style="width:100%"><label for="nl">Tarjima tili</label><input id="nl" value="O\'zbekcha" maxlength="30" style="width:100%"><p class="err" id="ne" role="alert"></p><div class="row"><button class="btn p">Yaratish</button><button type="button" class="btn" data-act="close">Bekor qilish</button></div></form>');
    $('#nf').onsubmit = function (e) { e.preventDefault(); try { var id = V.createSession($('#nn').value, { lang: $('#nl').value.trim() || "O'zbekcha" }); closeModal(); location.hash = '#/s/' + id; } catch (er) { $('#ne').textContent = er.message; } };
  }
  function wordForm(sid, wid) {
    var w = wid ? V.session(sid).words[wid] : null;
    modal('<h2>So\'zni tahrirlash</h2><form id="ef"><label for="e1">Inglizcha</label><input id="e1" value="' + esc(w.en) + '" maxlength="80" required style="width:100%"><label for="e2">Tarjima (; bilan bir nechta — barchasi to\'g\'ri javob)</label><input id="e2" value="' + esc(w.tr.join('; ')) + '" required style="width:100%"><label for="e3">Misol gap</label><input id="e3" value="' + esc(w.example) + '" style="width:100%"><label for="e4">Misol tarjimasi</label><input id="e4" value="' + esc(w.exampleTr) + '" style="width:100%"><label for="e5">Talaffuz (ixtiyoriy)</label><input id="e5" value="' + esc(w.pron) + '" style="width:100%"><label for="e6">Qo\'shimcha qabul qilinadigan inglizcha imlo (; bilan)</label><input id="e6" value="' + esc((w.variants || []).join('; ')) + '" style="width:100%"><p class="err" id="ee" role="alert"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-act="close">Bekor</button></div></form>');
    $('#ef').onsubmit = function (e) { e.preventDefault(); try { V.updateWord(sid, wid, { en: $('#e1').value, tr: $('#e2').value, example: $('#e3').value, exampleTr: $('#e4').value, pron: $('#e5').value, variants: $('#e6').value }); closeModal(); route(); } catch (er) { $('#ee').textContent = er.message; } };
  }
  function importForm(sid) {
    modal('<h2>Ko\'p so\'z import</h2><p class="mute">Har qatorga bitta so\'z: <code>inglizcha - tarjima</code>. Ajratuvchi: <b>-</b>, <b>=</b>, <b>|</b>, <b>;</b>, <b>,</b> yoki Excel/Sheets\'dan nusxalangan <b>TAB</b>. Qo\'shimcha ustunlar (TAB yoki |): misol gap, talaffuz. Bir nechta tarjima: <code>;</code> yoki <code>,</code>. Barcha so\'zlar <b>faqat shu sessiyaga</b> qo\'shiladi.</p><label class="sr" for="it">Ro\'yxat</label><textarea id="it" placeholder="apple - olma&#10;book = kitob&#10;window\tderaza"></textarea><label for="im">Takrorlangan so\'zlar bo\'lsa (shu sessiya ichida)</label><select id="im"><option value="report">Faqat ko\'rsat — hech narsa qo\'shma</option><option value="skip">Takrorlarni o\'tkazib yubor</option><option value="update">Takrorlarni yangila (tarjimani almashtir)</option><option value="allow">Takrorlarni ham qo\'sh</option></select><div id="ir" style="margin-top:.6rem" aria-live="polite"></div><div class="row" style="margin-top:.6rem"><button class="btn" id="ipv">Oldindan ko\'rish</button><button class="btn p" id="iap">Import qilish</button><button class="btn" data-act="close">Yopish</button></div>');
    var show = function (r, applied) {
      $('#ir').innerHTML = '<p>✅ Qo\'shiladi: <b>' + (applied ? r.added.length : r.toAdd) + '</b> · 🔁 Takror: <b>' + r.duplicates.length + '</b> · ✏️ Yangilanadi: <b>' + (applied ? r.updated.length : r.toUpdate) + '</b> · ❌ Xato: <b>' + r.invalid.length + '</b></p>' + (r.duplicates.length ? '<p class="mute">Takror: ' + r.duplicates.map(function (d) { return esc(d.en); }).join(', ') + '</p>' : '') + (r.invalid.length ? '<p class="err">' + r.invalid.map(function (d) { return d.line + '-qator: ' + esc(d.error); }).join('<br>') + '</p>' : '') + (!applied && !r.applied && r.duplicates.length && $('#im').value === 'report' ? '<p class="err">Takrorlar bor — «Faqat ko\'rsat» rejimida hech narsa qo\'shilmaydi. Variantni tanlang.</p>' : '');
    };
    $('#ipv').onclick = function () { show(V.previewImport(sid, $('#it').value), false); };
    $('#iap').onclick = function () { var r = V.importInto(sid, $('#it').value, $('#im').value); show(r, r.applied); if (r.applied) { toast(r.added.length + " ta so'z qo'shildi"); closeModal(); route(); } };
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-act]'); if (!b) return; var act = b.dataset.act, sid = curSid();
    if (act === 'new') newSessionForm();
    else if (act === 'close') closeModal();
    else if (act === 'theme') { var d = settings(); d.theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; V.save(); applyTheme(); }
    else if (act === 'dismiss') { V.db().migrations.forEach(function (m) { if (m.id === b.dataset.id) m.dismissed = true; }); V.save(); route(); }
    else if (act === 'start') { var s = V.session(sid); if (s.run && s.run.mode !== b.dataset.m) confirmBox('Davom etayotgan «' + s.run.mode + '» raundi bekor qilinadi (saqlangan progress qoladi). Davom etasizmi?', 'Ha, yangi raund').then(function (y) { if (y) startMode(sid, b.dataset.m, true); }); else startMode(sid, b.dataset.m, false); }
    else if (act === 'start2') startMode(sid, b.dataset.m, true);
    else if (act === 'resume') { location.hash = '#/run/' + sid; }
    else if (act === 'rename') { modal('<h2>Nomini o\'zgartirish</h2><form id="rf"><input id="rn" value="' + esc(V.session(sid).name) + '" maxlength="60" style="width:100%"><p class="err" id="re" role="alert"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-act="close">Bekor</button></div></form>'); $('#rf').onsubmit = function (ev) { ev.preventDefault(); try { V.renameSession(sid, $('#rn').value); closeModal(); route(); } catch (er) { $('#re').textContent = er.message; } }; }
    else if (act === 'pause') { var ss = V.session(sid); V.setStatus(sid, ss.status === 'paused' ? 'active' : 'paused'); route(); }
    else if (act === 'restart') confirmBox('Barcha progress (holat, xatolar, statistika) tozalanadi, so\'zlar qoladi.', 'Qayta boshlash').then(function (y) { if (y) { V.restartSession(sid); toast('Sessiya qayta boshlandi'); route(); } });
    else if (act === 'delete') confirmBox('«' + V.session(sid).name + '» sessiyasi va uning barcha so\'zlari o\'chiriladi. Bu amalni qaytarib bo\'lmaydi.', "O'chirish").then(function (y) { if (y) { V.deleteSession(sid); location.hash = '#/'; } });
    else if (act === 'import') importForm(sid);
    else if (act === 'ew') wordForm(sid, b.dataset.id);
    else if (act === 'dw') { var w = V.session(sid).words[b.dataset.id]; confirmBox('«' + w.en + '» so\'zi shu sessiyadan o\'chiriladi.', "O'chirish").then(function (y) { if (y) { V.deleteWord(sid, w.id); route(); } }); }
    else if (act === 'say') speak(b.dataset.t);
    else if (act === 'toggle-tr') { var t = $('#trv'); t.hidden = !t.hidden; b.textContent = t.hidden ? 'Tarjimani ko\'rsatish' : 'Tarjimani yashirish'; }
    else if (act === 'study-next') { V.studyDone(run.sid, cur.q); V.next(run.sid); nextQuestion(); }
    else if (act === 'reveal') { $('#ans').hidden = false; b.hidden = true; $('#selfgrade').hidden = false; var f = $('#selfgrade button'); if (f) f.focus(); }
    else if (act === 'know' || act === 'dunno') { if (cur.checked) return; cur.checked = true; var ok = act === 'know', res = V.grade(run.sid, cur.q, ok); V.answer(run.sid, cur.q, ok, [cur.q.w], ok ? 'bilardim' : 'bilmadim'); feedback(ok, res); cont(ok); }
    else if (act === 'opt') { if (cur.checked) return; cur.sel = +b.dataset.i; document.querySelectorAll('.opt').forEach(function (o) { var on = o === b; o.classList.toggle('sel', on); o.setAttribute('aria-checked', on); }); $('#primary').disabled = false; }
    else if (act === 'check') check();
    else if (act === 'next') { V.next(run.sid); nextQuestion(); }
    else if (act === 'm') matchClick(b);
    else if (act === 'tile') tileClick(b);
    else if (act === 'quit') modal('<h2>To\'xtatasizmi?</h2><p>Progress saqlanadi. Keyin shu joydan davom etishingiz mumkin.</p><div class="row"><button class="btn" data-act="close">Davom etish</button><button class="btn p" data-act="leave">To\'xtatish</button></div>');
    else if (act === 'leave') { var rs = run.sid; closeModal(); V.stopRun(rs); location.hash = '#/s/' + rs; }
    else if (act === 'set') { settings()[b.dataset.k] = b.dataset.v; V.save(); applyTheme(); route(); }
    else if (act === 'tog') { settings()[b.dataset.k] = !settings()[b.dataset.k]; V.save(); route(); }
    else if (act === 'export') { var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([V.exportJSON()], { type: 'application/json' })); a.download = 'lugat-' + new Date().toISOString().slice(0, 10) + '.json'; a.click(); }
    else if (act === 'migrate') { var r = V.migrateLegacy(); toast(r.sessions.length ? r.words + " ta so'z ko'chirildi" : r.found ? "Yangi ko'chiriladigan narsa yo'q" : "Eski Til Yo'li ma'lumoti topilmadi"); route(); }
  });
  document.addEventListener('submit', function (e) {
    if (e.target.id !== 'wform') return; e.preventDefault(); var sid = curSid(), f = e.target, en = f.en.value, err = $('#werr');
    var dup = V.words(sid).some(function (w) { return V.norm(w.en) === V.norm(en); });
    var add = function () { try { V.addWord(sid, { en: en, tr: f.tr.value, example: f.example.value }); route(); setTimeout(function () { var i = $('#w_en'); if (i) i.focus(); }, 0); } catch (er) { err.textContent = er.message; } };
    if (dup) confirmBox('«' + en.trim() + '» bu sessiyada allaqachon bor. Baribir qo\'shasizmi?', "Ha, qo'shish").then(function (y) { if (y) add(); }); else add();
  });
  document.addEventListener('input', function (e) {
    if (e.target.id === 'sq') { q.text = e.target.value; $('#slist').innerHTML = sessionsHTML(); }
    else if (e.target.id === 'wq') { wf = e.target.value; $('#wlist').innerHTML = wordRows(curSid()); }
  });
  document.addEventListener('change', function (e) {
    if (e.target.id === 'ss') { q.sort = e.target.value; $('#slist').innerHTML = sessionsHTML(); }
    else if (e.target.id === 'imp' && e.target.files[0]) { var r = new FileReader(); r.onload = function () { try { V.importJSON(r.result); applyTheme(); toast('Import qilindi (oldingi ma\'lumot zaxiraga olindi)'); route(); } catch (er) { toast('Xato: ' + er.message); } }; r.readAsText(e.target.files[0]); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !modalEl.hidden) { closeModal(); return; }
    if (!$('#run') || !modalEl.hidden || !cur) return;
    if (e.key === 'Enter') { var p = $('#primary'); if (p && !p.disabled && p.tagName === 'BUTTON') { e.preventDefault(); p.click(); } }
    else if (cur.q && cur.q.type === 'mc' && !cur.checked && /^[1-5]$/.test(e.key)) { var o = document.querySelectorAll('.opt')[+e.key - 1]; if (o) o.click(); }
  });

  V._debug = { get run() { return run; }, route: route, startMode: startMode };
  V.restore().then(function () {
    V.load(); applyTheme(); V.runInitialMigration(); route();
  });
})(window.V = window.V || {});
