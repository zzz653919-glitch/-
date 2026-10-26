/* Interfeys: marshrutlash, sahifalar va dars oynasi. */
(function (TY) {
  var A = TY.Auth, G = TY.Game, $ = function (s, r) { return (r || document).querySelector(s); };
  var app = $('#app'), lessonEl = $('#lesson'), modalEl = $('#modal');
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function st() { return A.state; }

  // ---- Tema, tovush, xabarlar ----
  function applyTheme() {
    var t = st() ? st().theme : 'auto', dark = t === 'dark' || (t === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    try { localStorage.setItem('tilyoli:pref', JSON.stringify({ theme: t })); } catch (e) {}
  }
  var actx;
  function beep(kind) {
    if (!st() || !st().sound) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      var seq = kind === 'good' ? [[660, 0], [880, .09]] : kind === 'bad' ? [[200, 0], [150, .12]] : [[523, 0], [659, .1], [784, .2]];
      seq.forEach(function (n) { var o = actx.createOscillator(), g = actx.createGain(); o.type = 'sine'; o.frequency.value = n[0]; g.gain.value = .06; o.connect(g); g.connect(actx.destination); o.start(actx.currentTime + n[1]); o.stop(actx.currentTime + n[1] + .12); });
    } catch (e) {}
  }
  function toast(msg) { var d = document.createElement('div'); d.className = 'toast'; d.textContent = msg; $('#toasts').appendChild(d); setTimeout(function () { d.remove(); }, 3200); }
  function modal(html, onClose) {
    modalEl.hidden = false; modalEl.innerHTML = '<div class="sheet" role="dialog" aria-modal="true">' + html + '</div>';
    modalEl._close = onClose; var f = $('button, a, input', modalEl); if (f) f.focus();
  }
  function closeModal() { modalEl.hidden = true; modalEl.innerHTML = ''; if (modalEl._close) { var c = modalEl._close; modalEl._close = null; c(); } }
  modalEl.addEventListener('click', function (e) { if (e.target === modalEl) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !modalEl.hidden) closeModal(); });

  // ---- Marshrutlash ----
  var NAV = [['#/', '🏠', 'Bosh sahifa'], ['#/learn', '🗺️', 'Xarita'], ['#/review', '🔁', 'Takrorlash'], ['#/quests', '🎯', 'Topshiriqlar'], ['#/ielts', '🎓', 'IELTS'], ['#/stats', '📊', 'Statistika'], ['#/achievements', '🏆', 'Yutuqlar'], ['#/profile', '👤', 'Profil']];
  var TABS = [0, 1, 2, 3, 7];
  var LOGO = '<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M16 20h32M32 20v28" stroke="#fff" stroke-width="9" stroke-linecap="round"/></svg>';
  var session = null, cleanupLesson = null;

  function route() {
    var h = location.hash || '#/', parts = h.slice(2).split('/'), name = parts[0] || 'home';
    closeModal();
    if (!A.state) { if (!A.restore()) { renderAuth(); return; } applyTheme(); }
    G.regen();
    if (name === 'lesson' || name === 'practice') { startRoute(name, parts[1]); return; }
    stopLesson();
    var views = { home: vHome, learn: vLearn, review: vReview, quests: vQuests, ielts: vIelts, stats: vStats, achievements: vAch, profile: vProfile };
    var fn = views[name] || vHome, key = { home: '#/', learn: '#/learn', review: '#/review', quests: '#/quests', ielts: '#/ielts', stats: '#/stats', achievements: '#/achievements', profile: '#/profile' }[views[name] ? name : 'home'];
    shell(key, fn());
    var hd = $('#main h1'); if (hd) { hd.setAttribute('tabindex', '-1'); }
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', route);

  function topbar() {
    var s = st(), b = G.levelBounds(s.xp), nh = G.nextHeartMs();
    return '<a class="chip lvl" href="#/profile" title="Daraja">⭐ Daraja ' + b.lvl + '</a>' +
      '<a class="chip fire" href="#/stats" title="Seriya: ketma-ket kunlar">🔥 ' + G.streakNow() + '</a>' +
      '<a class="chip xp" href="#/stats" title="Jami XP">⚡ ' + s.xp + ' XP</a>' +
      '<a class="chip heart" href="#/review" title="Yurakchalar">❤️ ' + s.hearts + (nh ? ' <small id="hTimer">' + fmtMs(nh) + '</small>' : '') + '</a>';
  }
  function fmtMs(ms) { var m = Math.floor(ms / 60000), s = Math.floor(ms % 60000 / 1000); return m + ':' + (s < 10 ? '0' : '') + s; }
  function shell(active, html) {
    var nav = NAV.map(function (n) { return '<a href="' + n[0] + '"' + (n[0] === active ? ' aria-current="page"' : '') + '><span class="ic" aria-hidden="true">' + n[1] + '</span>' + n[2] + '</a>'; }).join('');
    var tabs = TABS.map(function (i) { var n = NAV[i]; return '<a href="' + n[0] + '"' + (n[0] === active ? ' aria-current="page"' : '') + '><span class="ic" aria-hidden="true">' + n[1] + '</span>' + n[2].split(' ')[0] + '</a>'; }).join('') +
      '<button data-act="more"><span class="ic" aria-hidden="true">⋯</span>Yana</button>';
    app.innerHTML = '<div class="shell"><aside class="side"><a class="brand" href="#/"><span class="logo">' + LOGO + '</span>Til Yo\'li</a><nav class="nav" aria-label="Asosiy menyu">' + nav + '</nav></aside>' +
      '<div class="main"><header class="top" id="top">' + topbar() + '</header><main class="page" id="main">' + html + '</main></div>' +
      '<nav class="tabs" aria-label="Tezkor menyu">' + tabs + '</nav></div>';
    lessonEl.hidden = true; app.hidden = false;
  }
  setInterval(function () {
    if (!A.state || app.hidden) return; var before = A.state.hearts; G.regen();
    var t = $('#top'); if (t && (A.state.hearts !== before || $('#hTimer'))) { t.innerHTML = topbar(); }
  }, 1000);

  // ---- Kirish / ro'yxatdan o'tish ----
  function renderAuth() {
    lessonEl.hidden = true; app.hidden = false;
    var mode = 'login';
    function draw(err) {
      app.innerHTML = '<main class="auth" id="main"><a class="brand" href="#/"><span class="logo">' + LOGO + '</span>Til Yo\'li</a>' +
        '<h1 class="center">' + (mode === 'login' ? 'Qaytganingiz bilan!' : 'Hisob yarating') + '</h1><p class="center mute">Ingliz tilini A1 dan IELTS gacha qadamma-qadam o\'rganing.</p>' +
        '<div class="card"><form class="form" id="af" novalidate><label for="u">Foydalanuvchi nomi</label><input class="inp" id="u" autocomplete="username" required>' +
        '<label for="p">Parol</label><input class="inp" id="p" type="password" autocomplete="' + (mode === 'login' ? 'current-password' : 'new-password') + '" required>' +
        '<p class="err" role="alert" id="err">' + esc(err || '') + '</p><button class="btn block" type="submit">' + (mode === 'login' ? 'Kirish' : 'Ro\'yxatdan o\'tish') + '</button></form></div>' +
        '<div class="row" style="justify-content:center"><button class="btn ghost small" id="sw">' + (mode === 'login' ? 'Hisobim yo\'q' : 'Hisobim bor') + '</button>' + (TY.Server.on ? '' : '<button class="btn ghost small" id="gst">Mehmon sifatida</button>') + '</div>' +
        '<p class="mute center" style="margin-top:1rem;font-size:.85rem">' + (TY.Server.on ? 'Hisobingiz va natijalaringiz serverda saqlanadi.' : 'Ma\'lumotlar faqat shu qurilma brauzerida saqlanadi (server yo\'q).') + '</p></main>';
      $('#sw').onclick = function () { mode = mode === 'login' ? 'reg' : 'login'; draw(); };
      if ($('#gst')) $('#gst').onclick = function () { A.guest(); applyTheme(); location.hash = '#/'; route(); };
      $('#af').onsubmit = function (e) {
        e.preventDefault();
        var p = (mode === 'login' ? A.login : A.register)($('#u').value, $('#p').value);
        p.then(function () { applyTheme(); location.hash = '#/'; route(); }).catch(function (er) { draw(er.message); });
      };
      $('#u').focus();
    }
    draw();
  }

  // ---- Bosh sahifa ----
  function ringSVG(p, label) {
    var r = 40, c = 2 * Math.PI * r;
    return '<svg class="ring" viewBox="0 0 100 100" role="img" aria-label="' + esc(label) + '"><circle cx="50" cy="50" r="' + r + '" fill="none" stroke="var(--line)" stroke-width="12"/><circle cx="50" cy="50" r="' + r + '" fill="none" stroke="#facc15" stroke-width="12" stroke-linecap="round" stroke-dasharray="' + (c * p) + ' ' + c + '" transform="rotate(-90 50 50)"/><text x="50" y="57" text-anchor="middle" font-size="22">' + Math.round(p * 100) + '%</text></svg>';
  }
  function todayInfo() { var s = st(), d = s.days[TY.today()] || { xp: 0, secs: 0, lessons: 0, correct: 0, wrong: 0 }; return d; }
  function vHome() {
    var s = st(), d = todayInfo(), goal = s.goalMin * 60, p = Math.min(1, d.secs / goal), cur = G.currentNode(), b = G.levelBounds(s.xp);
    var hello = 'Salom, ' + esc(A.current.name) + '!';
    var hero = cur ? '<section class="card hero"><div><h2>' + (G.learnedCount(s) ? 'Davom etamiz' : 'Boshlaymiz') + '</h2><p>' + esc(TY.LEVELS[cur.level].sub) + ' · ' + esc(cur.title) + '</p></div><a class="btn" href="#/lesson/' + cur.id + '">' + cur.icon + ' ' + (s.done[cur.id] ? 'Takrorlash' : 'Boshlash') + '</a></section>'
      : '<section class="card hero"><div><h2>Barcha darslar tugadi!</h2><p>Takrorlash markazida bilimingizni mustahkamlang.</p></div><a class="btn" href="#/review">Takrorlash</a></section>';
    var qs = G.quests(), done = qs.filter(function (q) { return q.cur >= q.goal; }).length;
    var ann = (TY.Server.announcements || []).map(function (a) { return '<section class="card" style="background:var(--blue-l)"><b>📣 ' + esc(a.title) + '</b><p style="margin:.3rem 0 0">' + esc(a.body) + '</p></section>'; }).join('');
    return '<h1>' + hello + '</h1>' + ann + hero +
      '<div class="grid g2"><section class="card row" aria-labelledby="gh"><div><h3 id="gh">Kunlik maqsad</h3><p class="mute">' + Math.floor(d.secs / 60) + ' / ' + s.goalMin + ' daqiqa</p><a href="#/profile">Maqsadni o\'zgartirish</a></div>' + ringSVG(p, 'Kunlik maqsad ' + Math.round(p * 100) + ' foiz') + '</section>' +
      '<section class="card"><h3>Daraja ' + b.lvl + '</h3><div class="bar yellow" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(100 * (s.xp - b.from) / (b.to - b.from)) + '"><i style="width:' + (100 * (s.xp - b.from) / (b.to - b.from)) + '%"></i></div><p class="mute" style="margin-top:.5rem">' + (b.to - s.xp) + ' XP keyingi darajagacha</p></section></div>' +
      '<div class="grid g3"><div class="card stat"><b>🔥 ' + G.streakNow() + '</b>kunlik seriya</div><div class="card stat"><b>⚡ ' + d.xp + '</b>bugungi XP</div><div class="card stat"><b>📖 ' + G.learnedCount(s) + '</b>o\'rganilgan so\'z</div></div>' +
      '<section class="card"><div class="row"><h3>Kunlik topshiriqlar</h3><a href="#/quests">' + done + '/' + qs.length + ' →</a></div>' + qs.slice(0, 2).map(questRow).join('') + '</section>' +
      (Object.keys(s.mistakes).length ? '<section class="card row"><div><h3>Xato so\'zlar: ' + Object.keys(s.mistakes).length + '</h3><p class="mute" style="margin:0">Ularni takrorlab yurakcha ham tiklang.</p></div><a class="btn blue small" href="#/practice/mistakes">Takrorlash</a></section>' : '');
  }
  function questRow(q) {
    var p = Math.min(1, q.cur / q.goal), cl = G.questClaimed(q.id);
    return '<div class="quest"><span aria-hidden="true" style="font-size:1.6rem">' + q.icon + '</span><div><b>' + esc(q.t) + '</b><div class="bar yellow" role="progressbar" aria-valuemin="0" aria-valuemax="' + q.goal + '" aria-valuenow="' + Math.min(q.cur, q.goal) + '"><i style="width:' + p * 100 + '%"></i></div></div><span>' + Math.min(q.cur, q.goal) + '/' + q.goal + (cl ? ' ✅' : ' · +' + q.xp) + '</span></div>';
  }

  // ---- Xarita ----
  var OFFS = [0, 38, 58, 38, 0, -38, -58];
  function levelUnlocked(li) { return li === 0 || !!st().done[TY.LEVELS[li - 1].nodes[TY.LEVELS[li - 1].nodes.length - 1].id]; }
  function mapHTML(li) {
    var lv = TY.LEVELS[li], s = st(), cur = G.currentNode(), doneN = lv.nodes.filter(function (n) { return s.done[n.id]; }).length;
    var h = '<section aria-labelledby="lv' + li + '"><div class="lvl-head" style="background:' + lv.color + '"><div><h2 id="lv' + li + '">' + esc(lv.title) + '</h2><small>' + esc(lv.sub) + '</small></div><b>' + doneN + '/' + lv.nodes.length + '</b></div><div class="path">';
    lv.nodes.forEach(function (n, i) {
      var done = !!s.done[n.id], unlocked = G.isUnlocked(n.id), isCur = cur && cur.id === n.id;
      var cls = done ? 'done' : isCur ? 'cur' : unlocked ? 'cur' : 'lock';
      var state = done ? 'tugallangan' : unlocked ? 'ochiq' : 'qulflangan';
      h += '<button class="node ' + cls + '" style="margin-left:' + OFFS[i % OFFS.length] + 'px" data-act="node" data-id="' + n.id + '" aria-label="' + esc(n.title + ', ' + state) + '"><span class="disc">' + (isCur ? '<span class="start">Boshlash</span>' : '') + (unlocked || done ? n.icon : '🔒') + (done ? '<span class="badge" aria-hidden="true">✓</span>' : '') + '</span><span class="lab">' + esc(n.title) + '</span></button>';
    });
    return h + '</div></section>';
  }
  function vLearn() {
    var h = '<h1>O\'rganish xaritasi</h1><p class="mute">Keyingi darsni ochish uchun oldingisini tugating. Har daraja sinov bilan yakunlanadi (kamida 75%).</p>';
    for (var i = 0; i < TY.LEVELS.length; i++) h += mapHTML(i);
    return h;
  }
  function nodeSheet(id) {
    var n = TY.nodeById[id], lv = TY.LEVELS[n.level], s = st(), r = s.done[id];
    if (!G.isUnlocked(id)) { toast('🔒 Avval oldingi darsni tugating'); return; }
    var goals = { lesson: lv.topics[n.topic] ? lv.topics[n.topic].words.length + ' ta yangi so\'zni o\'rganish va mashq qilish' : '', review: 'Shu darajadagi so\'zlarni aralash takrorlash (xatolar birinchi navbatda)', test: '14 ta savol; o\'tish uchun kamida 75% to\'g\'ri javob' };
    var words = n.kind === 'lesson' ? lv.topics[n.topic].words.map(function (w) { return '<span class="pill">' + esc(w.en) + '</span>'; }).join('') : '';
    modal('<h2>' + n.icon + ' ' + esc(n.title) + '</h2><p class="mute">' + esc(lv.sub) + '</p><p><b>Maqsad:</b> ' + goals[n.kind] + '.</p>' + (words ? '<div class="words">' + words + '</div>' : '') +
      (r ? '<p>✅ Tugallangan · eng yaxshi natija: <b>' + r.best + '%</b></p>' : '') +
      '<p class="mute">❤️ Yurakchalar: ' + s.hearts + '/' + G.MAX_HEARTS + (s.hearts < 1 ? ' — avval yurak tiklang' : '') + '</p>' +
      '<div class="grid"><a class="btn block" href="#/lesson/' + id + '" id="go"' + '>' + (r ? 'Qayta mashq qilish' : 'Boshlash') + '</a><button class="btn ghost block" data-act="close">Yopish</button></div>');
  }

  // ---- Takrorlash markazi ----
  function vReview() {
    var s = st(), mk = Object.keys(s.mistakes), learned = G.learnedCount(s), nh = G.nextHeartMs();
    var list = mk.slice(0, 30).map(function (id) { var w = TY.wordById[id]; return '<tr><td>' + esc(w.en) + '</td><td>' + esc(w.uz[0]) + '</td><td>' + s.mistakes[id].n + '×</td></tr>'; }).join('');
    return '<h1>Takrorlash markazi</h1>' +
      '<section class="card"><h3>❤️ Yurakchalar: ' + s.hearts + ' / ' + G.MAX_HEARTS + '</h3><p>Darslarda har bir xato javob 1 ta yurakchani oladi. Yurakchalar tugasa, dars to\'xtaydi.</p>' +
      '<p><b>Tiklash qoidalari:</b></p><ul><li>Har <b>20 daqiqada +1</b> yurakcha o\'zi tiklanadi' + (nh ? ' (keyingisi: <b>' + fmtMs(nh) + '</b>)' : '') + '.</li><li>Xato so\'zlar yoki umumiy mashqni tugatsangiz <b>+1</b> yurakcha (mashq paytida yurakcha ketmaydi).</li><li>Dars, takrorlash yoki sinovni tugatsangiz <b>+1</b> yurakcha.</li></ul></section>' +
      '<div class="grid g2"><section class="card"><h3>🧩 Xato so\'zlar (' + mk.length + ')</h3><p class="mute">Xato qilgan so\'zlar. Ketma-ket 2 marta to\'g\'ri topsangiz ro\'yxatdan chiqadi.</p><a class="btn blue block' + '" ' + (mk.length ? '' : 'aria-disabled="true" style="pointer-events:none;opacity:.5"') + ' href="#/practice/mistakes">Mashq qilish</a></section>' +
      '<section class="card"><h3>🔀 Aralash mashq</h3><p class="mute">O\'rganilgan so\'zlar (' + learned + ') aralashtirilib so\'raladi.</p><a class="btn block" ' + (learned ? '' : 'aria-disabled="true" style="pointer-events:none;opacity:.5"') + ' href="#/practice/practice">Boshlash</a></section></div>' +
      (list ? '<section class="card"><h3>Xato so\'zlar ro\'yxati</h3><table class="t"><tr><th>Inglizcha</th><th>Tarjima</th><th>Xato</th></tr>' + list + '</table></section>' : '<p class="mute center">Hozircha xato so\'zlar yo\'q. Zo\'r! 🎉</p>');
  }

  // ---- Topshiriqlar ----
  function vQuests() {
    var qs = G.quests(), ready = qs.filter(function (q) { return q.cur >= q.goal && !G.questClaimed(q.id); }), xp = ready.reduce(function (a, q) { return a + q.xp; }, 0);
    return '<h1>Kunlik topshiriqlar</h1><p class="mute">Topshiriqlar har kuni yangilanadi va bugungi haqiqiy natijalaringizdan hisoblanadi.</p><section class="card">' + qs.map(questRow).join('') +
      '</section><button class="btn yellow block" data-act="claim"' + (xp ? '' : ' disabled') + '>' + (xp ? 'Mukofotni olish: +' + xp + ' XP' : 'Mukofot hozircha yo\'q') + '</button>';
  }

  // ---- Statistika ----
  function vStats() {
    var s = st(), days = [], i, t = TY.today(), names = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh'];
    for (i = 6; i >= 0; i--) { var k = TY.addDays(t, -i), d = s.days[k] || { xp: 0, secs: 0 }; var p = k.split('-'); days.push({ k: k, xp: d.xp, min: Math.round(d.secs / 60), n: names[new Date(+p[0], p[1] - 1, +p[2]).getDay()] }); }
    var mx = Math.max.apply(null, days.map(function (d) { return d.xp; }).concat([10]));
    var cor = G.totalCorrect(s), wr = Object.keys(s.days).reduce(function (a, k) { return a + s.days[k].wrong; }, 0), les = Object.keys(s.days).reduce(function (a, k) { return a + s.days[k].lessons; }, 0), secs = Object.keys(s.days).reduce(function (a, k) { return a + s.days[k].secs; }, 0);
    var d0 = s.days[t] || { xp: 0, secs: 0, lessons: 0, correct: 0, wrong: 0 };
    var hist = s.history.slice(0, 10).map(function (h) { var n = h.node && TY.nodeById[h.node]; var lab = n ? TY.LEVELS[n.level].id + ' · ' + n.title : { practice: 'Aralash mashq', mistakes: 'Xato so\'zlar' }[h.mode] || h.mode; return '<tr><td>' + new Date(h.ts).toLocaleDateString('uz') + '</td><td>' + esc(lab) + '</td><td>' + h.pct + '%</td><td>+' + h.xp + '</td></tr>'; }).join('');
    return '<h1>Statistika</h1><div class="grid g3"><div class="card stat"><b>⚡ ' + s.xp + '</b>jami XP</div><div class="card stat"><b>🔥 ' + G.streakNow() + '</b>seriya (eng yaxshi ' + s.bestStreak + ')</div><div class="card stat"><b>🎯 ' + (cor + wr ? Math.round(100 * cor / (cor + wr)) : 0) + '%</b>aniqlik</div><div class="card stat"><b>📖 ' + G.learnedCount(s) + '</b>so\'z</div><div class="card stat"><b>✅ ' + les + '</b>tugatilgan mashg\'ulot</div><div class="card stat"><b>⏱️ ' + Math.round(secs / 60) + '</b>daqiqa jami</div></div>' +
      '<section class="card"><h3>Bugun</h3><p>⚡ ' + d0.xp + ' XP · ⏱️ ' + Math.floor(d0.secs / 60) + ' daq · ✅ ' + d0.correct + ' to\'g\'ri · ❌ ' + d0.wrong + ' xato · 📘 ' + d0.lessons + ' mashg\'ulot</p></section>' +
      '<section class="card"><h3>So\'nggi 7 kun (XP)</h3><div class="bars" role="img" aria-label="Haftalik XP grafigi">' + days.map(function (d) { return '<div><span>' + d.xp + '</span><i class="' + (d.k === t ? 'today' : '') + '" style="height:' + Math.max(3, 100 * d.xp / mx) + '%"></i><span>' + d.n + '</span></div>'; }).join('') + '</div></section>' +
      '<section class="card"><h3>Oldingi natijalar</h3>' + (hist ? '<table class="t"><tr><th>Sana</th><th>Mashg\'ulot</th><th>Natija</th><th>XP</th></tr>' + hist + '</table>' : '<p class="mute">Hali natija yo\'q.</p>') + '</section>';
  }

  // ---- Yutuqlar ----
  function vAch() {
    var s = st(), n = Object.keys(s.ach).length;
    return '<h1>Yutuqlar</h1><p class="mute">' + n + ' / ' + TY.ACHIEVEMENTS.length + ' ochilgan</p><div class="grid">' + TY.ACHIEVEMENTS.map(function (a) {
      var on = !!s.ach[a.id]; return '<div class="card ach' + (on ? '' : ' off') + '"><span class="ai" aria-hidden="true">' + a.icon + '</span><div><b>' + esc(a.t) + '</b><br><span class="mute">' + esc(a.d) + '</span>' + (on ? '<br><small>🗓️ ' + new Date(s.ach[a.id]).toLocaleDateString('uz') + '</small>' : '') + '</div></div>';
    }).join('') + '</div>';
  }

  // ---- IELTS ----
  function vIelts() {
    var s = st(), lv = TY.LEVELS[5], ww = 0, tot = 0;
    lv.topics.forEach(function (tp) { tot += tp.words.length; if (s.done[tp.id]) ww += tp.words.length; });
    var status = levelUnlocked(5) ? '' : '<p class="card" style="background:var(--yellow-l)">🔒 IELTS yo\'li C1 sinovidan o\'tgandan keyin ochiladi.</p>';
    var tips = [['✍️ Writing Task 1', "Grafikni 150+ so'zda tasvirlang: umumiy tendensiya, eng yuqori/past nuqta, taqqoslash. 'fluctuate', 'peak', 'approximately' kabi so'zlardan foydalaning."], ['📝 Writing Task 2', "250+ so'z: kirish, 2 ta asosiy paragraf, xulosa. Fikrlarni 'however', 'moreover', 'consequently' bilan bog'lang."], ['🗣️ Speaking', "Qisqa 'ha/yo'q' emas, sabab va misol keltiring. Bilmagan so'zni boshqacha ifodalang (paraphrasing)."], ['👂 Listening', "Savollarni eshitishdan oldin o'qing, kalit so'zlarni belgilang. Imlo va raqamlarga e'tibor bering."], ['📖 Reading', "Avval sarlavha va birinchi gaplarni skanerlang. Har bir savol uchun 1,5 daqiqadan ko'p sarflamang."]];
    return '<h1>IELTS tayyorgarligi</h1><p class="mute">Akademik lug\'at va band oshirish strategiyalari. Bu bo\'lim lug\'at va maslahatlarni beradi — rasmiy IELTS imtihonining o\'rnini bosmaydi.</p>' + status +
      '<section class="card"><h3>Tayyorgarlik</h3><div class="bar blue" role="progressbar" aria-valuemin="0" aria-valuemax="' + tot + '" aria-valuenow="' + ww + '"><i style="width:' + 100 * ww / tot + '%"></i></div><p class="mute" style="margin-top:.5rem">' + ww + ' / ' + tot + ' akademik so\'z o\'rganilgan' + (s.ieltsBest ? ' · IELTS sinovi: ' + s.ieltsBest + '%' : '') + '</p></section>' +
      tips.map(function (t) { return '<section class="card"><h3>' + t[0] + '</h3><p style="margin:0">' + t[1] + '</p></section>'; }).join('') + mapHTML(5);
  }

  // ---- Profil va sozlamalar ----
  function seg(name, opts, cur) { return '<div class="seg" role="group" aria-label="' + name + '">' + opts.map(function (o) { return '<button data-act="set" data-k="' + name + '" data-v="' + o[0] + '" aria-pressed="' + (String(cur) === String(o[0])) + '">' + o[1] + '</button>'; }).join('') + '</div>'; }
  function vProfile() {
    var s = st(), b = G.levelBounds(s.xp);
    return '<h1>Profil va sozlamalar</h1><section class="card row"><div><h2 style="margin:0">' + esc(A.current.name) + '</h2><p class="mute" style="margin:0">Daraja ' + b.lvl + ' · ' + s.xp + ' XP · ' + Object.keys(s.ach).length + ' yutuq</p></div><span style="font-size:3rem" aria-hidden="true">🧑‍🎓</span></section>' +
      '<section class="card"><h3>Kunlik maqsad</h3>' + seg('goalMin', [[5, '5 daq'], [10, '10 daq'], [15, '15 daq'], [20, '20 daq']], s.goalMin) + '</section>' +
      '<section class="card"><h3>Ko\'rinish</h3>' + seg('theme', [['auto', 'Avto'], ['light', '☀️ Yorug\''], ['dark', '🌙 Qorong\'i']], s.theme) + '</section>' +
      '<section class="card"><h3>Ovoz</h3><div class="seg"><button data-act="tog" data-k="sound" aria-pressed="' + s.sound + '">🔔 Effektlar: ' + (s.sound ? 'yoqiq' : 'o\'chiq') + '</button><button data-act="tog" data-k="speech" aria-pressed="' + s.speech + '">🔊 Talaffuz: ' + (s.speech ? 'yoqiq' : 'o\'chiq') + '</button></div>' + (TY.canSpeak() ? '' : '<p class="mute">Bu brauzerda talaffuz (TTS) yo\'q — eshitish mashqlari o\'tkazib yuboriladi.</p>') + '</section>' +
      '<section class="card"><h3>Ma\'lumotlar</h3><p class="mute">Barcha natijalar shu brauzerda (localStorage) saqlanadi. Boshqa qurilmaga ko\'chirish uchun eksport qiling.</p><div class="seg"><button data-act="export">⬇️ Eksport</button><label class="btn ghost small" style="cursor:pointer">⬆️ Import<input type="file" accept="application/json" id="imp" hidden></label><button data-act="reset">♻️ Progressni tozalash</button></div></section>' +
      '<section class="card"><div class="seg">' + (TY.Server.on ? '<a class="btn ghost small" href="/admin">🛠️ Admin panel</a>' : (window.TY_SINGLE ? '<a class="btn ghost small" href="?admin">🛠️ Admin panel</a>' : '')) + '<button data-act="logout">Chiqish</button><button data-act="del">Hisobni o\'chirish</button></div></section>';
  }

  // ---- Dars oynasi ----
  function startRoute(name, arg) {
    var mode, node = null;
    if (name === 'lesson') {
      node = TY.nodeById[arg]; if (!node) { location.hash = '#/learn'; return; }
      if (!G.isUnlocked(node.id)) { toast('🔒 Avval oldingi darsni tugating'); location.hash = '#/learn'; return; }
      mode = node.kind;
    } else mode = arg === 'mistakes' ? 'mistakes' : 'practice';
    if ((mode === 'lesson' || mode === 'review' || mode === 'test') && st().hearts < 1) { outOfHearts(null, true); return; }
    session = new TY.Session(mode, node);
    if (!session.queue.length) { toast('Mashq uchun so\'z yo\'q'); location.hash = '#/review'; return; }
    app.hidden = true; lessonEl.hidden = false;
    if (mode === 'lesson') introScreen(); else nextQuestion();
  }
  function stopLesson() { session = null; lessonEl.hidden = true; lessonEl.innerHTML = ''; if (cleanupLesson) { cleanupLesson(); cleanupLesson = null; } }
  function lHead() {
    return '<div class="l-top"><button class="x" data-act="quit" aria-label="Darsdan chiqish">✕</button><div class="bar" role="progressbar" aria-label="Dars progressi" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(session.progress() * 100) + '"><i style="width:' + session.progress() * 100 + '%"></i></div>' + (session.useHearts ? '<span class="chip heart" aria-label="Yurakchalar">❤️ ' + st().hearts + '</span>' : '<span class="chip">∞</span>') + '</div>';
  }
  function introScreen() {
    var n = session.node, tp = TY.LEVELS[n.level].topics[n.topic];
    lessonEl.innerHTML = lHead() + '<div class="l-body"><h1>' + tp.icon + ' ' + esc(tp.title) + '</h1><div class="card" style="background:var(--blue-l)"><b>Tushuntirish.</b> ' + esc(tp.tip) + '</div>' +
      '<div class="card">' + tp.words.map(function (w) { return '<div class="wcard"><span class="e" aria-hidden="true">' + (w.emoji || '🔤') + '</span><div><b>' + esc(w.en) + '</b> — ' + esc(w.uz.join(', ')) + '<br><small class="mute">' + esc(w.sent) + '</small></div><button class="spk" data-act="say" data-t="' + esc(w.en) + '" aria-label="' + esc(w.en) + ' so\'zini eshitish">🔊</button></div>'; }).join('') + '</div></div>' +
      '<div class="fb"><div class="fb-in"><span class="mute">Maqsad: ' + tp.words.length + ' ta so\'z</span><button class="btn" data-act="begin" id="primary">Mashqni boshlash</button></div></div>';
    $('#primary').focus();
  }

  var cur = null; // joriy savol holati
  function nextQuestion() {
    if (session.over) return finishSession();
    var q = session.current(); cur = { q: q, sel: null, checked: false, picked: [], matched: {}, wrongM: [], mSel: null };
    var body = '', k = q.type;
    var speakBtn = q.speak && q.dir !== 'uz-en' ? '<button class="spk" data-act="say" data-t="' + esc(q.speak) + '" aria-label="Eshitish">🔊</button>' : '';
    if (q.listen && TY.canSpeak()) { setTimeout(function () { TY.speak(q.listen); }, 250); }
    if (k === 'choice') {
      body = '<p class="q-hint">' + esc(q.hint) + '</p><div class="q-prompt' + (q.big ? ' big' : '') + '">' + (q.big ? '<span role="img" aria-label="Rasm">' + q.prompt + '</span>' : '<span>' + esc(q.prompt) + '</span>') + speakBtn + '</div>' + (q.sub ? '<p class="mute">' + esc(q.sub) + '</p>' : '') +
        '<div class="opts" role="radiogroup" aria-label="Javob variantlari">' + q.options.map(function (o, i) { return '<button class="opt" role="radio" aria-checked="false" data-act="opt" data-i="' + i + '"><kbd>' + (i + 1) + '</kbd>' + esc(o) + '</button>'; }).join('') + '</div>';
    } else if (k === 'type') {
      body = '<p class="q-hint">' + esc(q.hint) + '</p>' + (q.listen ? '<div class="q-prompt"><button class="spk" data-act="say" data-t="' + esc(q.listen) + '" aria-label="Qayta eshitish" style="width:80px;height:80px;font-size:2.2rem">🔊</button></div>' : '<div class="q-prompt"><span>' + esc(q.prompt) + '</span>' + speakBtn + '</div>') +
        '<label class="sr" for="ti">Javobingiz</label><input class="inp" id="ti" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="' + esc(q.ph || '') + '">';
    } else if (k === 'scramble' || k === 'build') {
      var items = k === 'scramble' ? q.letters : q.bank;
      body = '<p class="q-hint">' + esc(q.hint) + '</p><div class="q-prompt"><span>' + esc(q.prompt) + '</span>' + speakBtn + '</div><div class="tray" id="tray" aria-label="Sizning javobingiz" aria-live="polite"></div><div class="tray" style="border:0" id="bank">' + items.map(function (t, i) { return '<button class="tile" data-act="tile" data-i="' + i + '">' + esc(t) + '</button>'; }).join('') + '</div>';
    } else if (k === 'match') {
      body = '<p class="q-hint">' + esc(q.hint) + '</p><div class="mcols"><div class="grid" id="ml">' + q.left.map(function (o) { return '<button class="opt" data-act="m" data-side="l" data-id="' + o.id + '">' + esc(o.t) + '</button>'; }).join('') + '</div><div class="grid" id="mr">' + q.right.map(function (o) { return '<button class="opt" data-act="m" data-side="r" data-id="' + o.id + '">' + esc(o.t) + '</button>'; }).join('') + '</div></div>';
    }
    var tag = q.review ? '<p class="mute">🔁 Oldingi xatolarni takrorlash</p>' : q.retry ? '<p class="mute">↩️ Qayta urinib ko\'ring</p>' : '';
    lessonEl.innerHTML = lHead() + '<div class="l-body">' + tag + body + '</div><div class="fb" id="fb"><div class="fb-in"><span class="msg" id="msg" role="status" aria-live="polite"></span>' +
      (k === 'match' ? '' : '<button class="btn" id="primary" data-act="check" disabled>Tekshirish</button>') + '</div></div>';
    if (k === 'type') { var ti = $('#ti'); ti.focus(); ti.oninput = function () { $('#primary').disabled = !ti.value.trim(); }; }
    if (k === 'choice' && q.speak && q.dir === 'en-uz') TY.speak(q.speak);
  }
  function feedback(ok, q, extra) {
    var fb = $('#fb'); fb.className = 'fb pop ' + (ok ? 'good' : 'bad');
    var w = TY.wordById[q.w];
    $('#msg').innerHTML = ok ? '<b>' + esc(['To\'g\'ri!', 'Ajoyib!', 'Zo\'r!', 'Barakalla!'][Math.floor(Math.random() * 4)]) + '</b><small>+' + (extra && extra.xp || 10) + ' XP</small>'
      : '<b>' + (extra && extra.close ? 'Deyarli! Imlo xatosi.' : 'Noto\'g\'ri') + '</b><small>To\'g\'ri javob: <b>' + esc(extra && extra.correct || '') + '</b></small><small>' + esc(w ? TY.explain(q) : '') + '</small>';
    beep(ok ? 'good' : 'bad');
  }
  function afterAnswer(res, ok) {
    var primary = $('#primary');
    if (!primary) { var fbin = $('.fb-in'); primary = document.createElement('button'); primary.className = 'btn'; primary.id = 'primary'; fbin.appendChild(primary); }
    primary.disabled = false; primary.className = 'btn' + (ok ? '' : ' red'); primary.dataset.act = res.outOfHearts ? 'hearts' : 'next'; primary.textContent = res.outOfHearts ? 'Davom etish' : 'Davom etish';
    var hc = $('.l-top .chip.heart'); if (hc) hc.textContent = '❤️ ' + st().hearts;
    var pb = $('.l-top .bar'); pb.firstChild.style.width = Math.min(100, 100 * (session.i + 1) / session.queue.length) + '%';
    primary.focus();
  }
  function check() {
    var q = cur.q; if (cur.checked) return; var input;
    if (q.type === 'choice') { if (cur.sel == null) return; input = q.options[cur.sel]; }
    else if (q.type === 'type') input = $('#ti').value;
    else if (q.type === 'scramble') input = cur.picked.map(function (i) { return q.letters[i]; }).join('');
    else input = cur.picked.map(function (i) { return q.bank[i]; });
    var g = TY.gradeQuestion(q, input); if (g.empty) return;
    cur.checked = true;
    var res = session.answer(q, g.ok, [q.w]);
    if (q.type === 'choice') document.querySelectorAll('.opt').forEach(function (b) { var o = q.options[+b.dataset.i]; b.disabled = true; if (TY.checkText(o, q.answer).ok) b.classList.add('good'); else if (+b.dataset.i === cur.sel) b.classList.add('bad'); });
    if (q.type === 'type') $('#ti').disabled = true;
    feedback(g.ok, q, { xp: res.xp, correct: g.correct, close: g.close });
    afterAnswer(res, g.ok);
  }
  function matchClick(btn) {
    var side = btn.dataset.side, id = btn.dataset.id; if (btn.classList.contains('gone') || cur.checked) return;
    document.querySelectorAll('.opt.sel[data-side="' + side + '"]').forEach(function (b) { b.classList.remove('sel'); });
    btn.classList.add('sel'); cur[side === 'l' ? 'mL' : 'mR'] = btn;
    if (cur.mL && cur.mR) {
      var a = cur.mL, b = cur.mR;
      if (a.dataset.id === b.dataset.id) { a.classList.remove('sel'); b.classList.remove('sel'); a.classList.add('good'); b.classList.add('good'); beep('good'); setTimeout(function () { a.classList.add('gone'); b.classList.add('gone'); }, 350); cur.matched[a.dataset.id] = 1; }
      else { [a, b].forEach(function (x) { x.classList.add('bad', 'shake'); setTimeout(function () { x.classList.remove('bad', 'shake', 'sel'); }, 450); }); beep('bad'); if (cur.wrongM.indexOf(a.dataset.id) < 0) cur.wrongM.push(a.dataset.id); if (cur.wrongM.indexOf(b.dataset.id) < 0) cur.wrongM.push(b.dataset.id); }
      cur.mL = cur.mR = null;
      if (Object.keys(cur.matched).length === cur.q.ws.length) {
        cur.checked = true; var res = session.answerMatch(cur.q, cur.wrongM), ok = !cur.wrongM.length;
        setTimeout(function () { var fb = $('#fb'); fb.className = 'fb pop ' + (ok ? 'good' : 'bad'); $('#msg').innerHTML = ok ? '<b>Hammasi to\'g\'ri!</b><small>+' + res.xp + ' XP</small>' : '<b>Tugadi</b><small>Xato juftliklar xato so\'zlar ro\'yxatiga qo\'shildi. +' + res.xp + ' XP</small>'; afterAnswer(res, ok); }, 450);
      }
    }
  }
  function tileClick(btn) {
    var q = cur.q, i = +btn.dataset.i; if (cur.checked) return;
    if (btn.dataset.in) { cur.picked = cur.picked.filter(function (x) { return x !== i; }); } else { cur.picked.push(i); }
    var items = q.type === 'scramble' ? q.letters : q.bank;
    $('#tray').innerHTML = cur.picked.map(function (j) { return '<button class="tile" data-act="tile" data-in="1" data-i="' + j + '" aria-label="' + esc(items[j]) + ' ni olib tashlash">' + esc(items[j]) + '</button>'; }).join('');
    document.querySelectorAll('#bank .tile').forEach(function (b) { b.disabled = cur.picked.indexOf(+b.dataset.i) >= 0; });
    $('#primary').disabled = !cur.picked.length;
  }
  function next() { session.next(); nextQuestion(); }

  function outOfHearts(sess, fromStart) {
    var nh = G.nextHeartMs();
    app.hidden = fromStart ? false : true;
    modal('<h2>💔 Yurakchalar tugadi</h2><p>Davom etish uchun yurakcha kerak. Tanlang:</p><div class="grid"><a class="btn blue block" href="#/practice/' + (Object.keys(st().mistakes).length ? 'mistakes' : 'practice') + '">🔁 Mashq qilib +1 ❤️ olish</a>' +
      '<p class="mute" style="margin:0">Mashq rejimida yurakcha ketmaydi; uni tugatsangiz +1 ❤️ olasiz.' + (G.learnedCount(st()) ? '' : ' (Avval kamida bitta dars tugating — hozircha mashq uchun so\'z yo\'q.)') + '</p>' +
      '<button class="btn ghost block" data-act="gomap">🗺️ Xaritaga qaytish</button><p class="mute center" style="margin:0">Yoki kuting: keyingi ❤️ ' + fmtMs(nh) + ' dan keyin (har 20 daqiqada +1).</p></div>', function () { if (fromStart && /lesson|practice/.test(location.hash)) location.hash = '#/learn'; });
    if (fromStart) { lessonEl.hidden = true; shell('#/learn', vLearn()); }
  }
  function finishSession() {
    if (session.failed && !session.finished) { outOfHearts(session); lessonEl.innerHTML = ''; return; }
    var s = session, r = s.finish(); s.finished = true;
    var learned = (s.mode === 'lesson' || s.mode === 'test' || s.mode === 'review') ? s.words : s.words;
    var wrongIds = Object.keys(s.wrong), nextN = r.unlockedNext && s.node ? TY.NODES[s.node.order + 1] : null;
    var next = s.node && r.passed ? (nextN || null) : null;
    beep('win');
    lessonEl.innerHTML = '<div class="l-body center"><div class="big-emoji pop">' + (r.passed ? (r.pct >= 90 ? '🏆' : '🎉') : '😕') + '</div><h1>' + (r.passed ? 'Mashg\'ulot tugadi!' : 'Sinovdan o\'ta olmadingiz') + '</h1>' +
      '<div class="grid g3" style="margin:1rem 0"><div class="card stat"><b>⚡ ' + r.xp + '</b>XP</div><div class="card stat"><b>🎯 ' + r.pct + '%</b>aniqlik</div><div class="card stat"><b>⏱️ ' + Math.max(1, Math.round((Date.now() - s.start) / 60000)) + '</b>daqiqa</div></div>' +
      (r.passed ? '<p class="mute">Bonus: +' + r.bonus + ' XP' + (s.useHearts ? ' · +1 ❤️' : ' · +1 ❤️') + '</p>' : '<p>Kamida 75% kerak. Takrorlab, yana urinib ko\'ring.</p>') +
      (r.ach.length ? '<div class="card" style="background:var(--yellow-l)"><b>🏅 Yangi yutuq!</b><br>' + r.ach.map(function (a) { return a.icon + ' ' + esc(a.t); }).join('<br>') + '</div>' : '') +
      '<div class="card" style="text-align:left"><h3>So\'zlar</h3><div class="words">' + (s.words || []).map(function (w) { return '<span class="pill" style="' + (s.wrong[w.id] ? 'border-color:var(--red)' : '') + '">' + esc(w.en) + ' — ' + esc(w.uz[0]) + '</span>'; }).join('') + '</div>' + (wrongIds.length ? '<p class="mute">Qizil bilan — xato qilingan so\'zlar (' + wrongIds.length + ').</p>' : '') + '</div>' +
      '<div class="grid">' + (wrongIds.length ? '<a class="btn blue block" href="#/practice/mistakes">🔁 Xatolarni takrorlash</a>' : '') +
      (next ? '<a class="btn block" href="#/lesson/' + next.id + '">Keyingi: ' + esc(next.title) + ' →</a>' : '') + (!r.passed && s.node ? '<a class="btn block" href="#/lesson/' + s.node.id + '">Qayta urinish</a>' : '') +
      '<button class="btn ghost block" data-act="gomap" id="primary">🗺️ Xaritaga</button></div></div>';
    $('#primary').focus();
    try { history.replaceState(null, '', '#/learn'); } catch (er) {}  // yangilaganda dars qayta boshlanmasin
  }

  // ---- Hodisalar (delegatsiya) ----
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-act]'); if (!b) return; var act = b.dataset.act, q;
    if (act === 'node') nodeSheet(b.dataset.id);
    else if (act === 'close') closeModal();
    else if (act === 'gomap') { closeModal(); if (location.hash === '#/learn') route(); else location.hash = '#/learn'; }
    else if (act === 'begin') nextQuestion();
    else if (act === 'say') TY.speak(b.dataset.t);
    else if (act === 'opt') { if (cur.checked) return; cur.sel = +b.dataset.i; document.querySelectorAll('.opt').forEach(function (o) { var on = o === b; o.classList.toggle('sel', on); o.setAttribute('aria-checked', on); }); $('#primary').disabled = false; }
    else if (act === 'check') check();
    else if (act === 'next') next();
    else if (act === 'hearts') { session.finished = true; outOfHearts(session); }
    else if (act === 'm') matchClick(b);
    else if (act === 'tile') tileClick(b);
    else if (act === 'quit') {
      modal('<h2>Chiqasizmi?</h2><p>Hozirgi mashg\'ulot progressi saqlanmaydi (to\'plangan XP qoladi).</p><div class="grid"><button class="btn block" data-act="close">Davom etish</button><button class="btn red block" data-act="leave">Chiqish</button></div>');
    }
    else if (act === 'leave') { closeModal(); session = null; location.hash = '#/learn'; }
    else if (act === 'more') modal('<h2>Yana</h2><div class="grid">' + [4, 5, 6].map(function (i) { return '<a class="btn ghost block" href="' + NAV[i][0] + '">' + NAV[i][1] + ' ' + NAV[i][2] + '</a>'; }).join('') + '</div>');
    else if (act === 'claim') { var g = G.claimQuests(); if (g) { toast('🎁 +' + g + ' XP olindi!'); beep('win'); } route(); }
    else if (act === 'set') { st()[b.dataset.k] = isNaN(+b.dataset.v) ? b.dataset.v : +b.dataset.v; A.save(); applyTheme(); route(); }
    else if (act === 'tog') { st()[b.dataset.k] = !st()[b.dataset.k]; A.save(); route(); }
    else if (act === 'export') { var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([A.exportData()], { type: 'application/json' })); a.download = 'tilyoli-' + TY.today() + '.json'; a.click(); }
    else if (act === 'reset') modal('<h2>Progressni tozalash?</h2><p>XP, seriya, tugallangan darslar va yutuqlar o\'chadi. Avval eksport qilib oling.</p><div class="grid"><button class="btn red block" data-act="reset2">Ha, tozalash</button><button class="btn ghost block" data-act="close">Bekor qilish</button></div>');
    else if (act === 'reset2') { A.resetProgress(); closeModal(); route(); toast('Progress tozalandi'); }
    else if (act === 'logout') { A.logout(); location.hash = '#/'; route(); }
    else if (act === 'del') modal('<h2>Hisobni o\'chirish?</h2><p>Hisob va barcha ma\'lumotlar butunlay o\'chadi.</p><div class="grid"><button class="btn red block" data-act="del2">Ha, o\'chirish</button><button class="btn ghost block" data-act="close">Bekor qilish</button></div>');
    else if (act === 'del2') { A.deleteAccount(); closeModal(); route(); }
  });
  document.addEventListener('change', function (e) {
    if (e.target.id === 'imp' && e.target.files[0]) { var r = new FileReader(); r.onload = function () { try { A.importData(r.result); applyTheme(); toast('Import qilindi'); route(); } catch (er) { toast('Xato: ' + er.message); } }; r.readAsText(e.target.files[0]); }
  });
  document.addEventListener('keydown', function (e) {
    if (lessonEl.hidden || !cur || !modalEl.hidden) { return; }
    var q = cur.q;
    if (e.key === 'Enter') {
      var p = $('#primary'); if (p && !p.disabled) { e.preventDefault(); p.click(); }
    } else if (q && q.type === 'choice' && !cur.checked && /^[1-4]$/.test(e.key)) { var o = document.querySelectorAll('.opt')[+e.key - 1]; if (o) o.click(); }
    else if (q && (q.type === 'scramble') && !cur.checked && /^[a-z]$/i.test(e.key)) { var t = Array.prototype.find.call(document.querySelectorAll('#bank .tile'), function (x) { return !x.disabled && x.textContent.toLowerCase() === e.key.toLowerCase(); }); if (t) t.click(); }
    else if (e.key === 'Backspace' && q && (q.type === 'scramble' || q.type === 'build') && !cur.checked && cur.picked.length) { var last = $('#tray .tile:last-child'); if (last) last.click(); }
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener && matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { if (st() && st().theme === 'auto') applyTheme(); });

  TY._debug = { get session() { return session; }, route: route };
  TY.onAuthLost = function () { toast('Sessiya tugadi yoki hisob bloklandi. Qayta kiring.'); A.logout(); location.hash = '#/'; route(); };
  TY.ready.then(function () { route(); });
})(window.TY = window.TY || {});
