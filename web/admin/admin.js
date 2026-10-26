/* Admin panel (frontend). Barcha ma'lumotlar /api/admin/* dan keladi; ruxsatlar serverda tekshiriladi,
   bu yerda faqat menyu va tugmalar ruxsatga qarab ko'rsatiladi. Har bir matn esc() bilan qochiriladi (XSS). */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var root = $('#root'), dlg = $('#dlg');
  var me = null, csrf = null, hbTimer = null;
  var ACH = { first: 'Birinchi qadam', xp100: '100 XP', xp500: '500 XP', xp2000: '2000 XP', streak3: '3 kunlik seriya', streak7: '7 kunlik seriya', streak30: '30 kunlik seriya', perfect: 'Mukammal dars', correct100: "100 ta to'g'ri javob", words50: "50 ta so'z", words100: "100 ta so'z", goal: 'Kunlik maqsad', test: 'Sinovdan o\'tdi', A1: 'A1 tugadi', IELTS: "IELTS yo'li", fixer: 'Xatolar ustasi' };
  var ROLE = { super_admin: 'Super Admin', admin: 'Admin', editor: 'Editor' };
  var KIND = { mc_en_uz: 'Tarjima tanlash (en→uz)', mc_uz_en: "O'zbekchadan inglizchani topish", picture: 'Rasm bo\'yicha topish', type_en_uz: 'Tarjimani yozish', type_uz_en: 'Inglizchasini yozish', scramble: "Harflardan so'z tuzish", cloze: "Bo'sh joyni to'ldirish", build: 'Gap tuzish', listen: 'Eshitib yozish' };
  var NAV = [['dashboard', '', 'Bosh panel', 'dashboard'], ['users', 'users', 'Foydalanuvchilar', 'users'], ['content', 'content', 'Kurs mazmuni', 'content'], ['exercises', 'exercises', 'Mashqlar', 'exercises'], ['achievements', 'ach', 'Yutuqlar', 'stats'], ['stats', 'stats', 'Statistika', 'stats'], ['announcements', 'ann', "E'lonlar", 'announcements'], ['audit', 'audit', 'Audit jurnali', 'audit'], ['settings', 'settings', 'Sozlamalar', 'settings']];
  var ICON = { dashboard: '▦', users: '👥', content: '📚', exercises: '🧩', achievements: '🏅', stats: '📈', announcements: '📣', audit: '🧾', settings: '⚙️' };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fdate(t) { return t ? new Date(t).toLocaleString('uz', { dateStyle: 'short', timeStyle: 'short' }) : '—'; }
  function can(p) { return me && me.perms.indexOf(p) >= 0; }
  function toast(m, err) { var d = document.createElement('div'); d.className = 'toast' + (err ? ' err' : ''); d.textContent = m; $('#toasts').appendChild(d); setTimeout(function () { d.remove(); }, 3500); }
  function api(method, url, body) {
    return fetch(url, { method: method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf || '' }, body: body ? JSON.stringify(body) : undefined }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) { var e = new Error(j.error || 'Xato ' + r.status); e.status = r.status; e.data = j; if (r.status === 401 && me) { me = null; renderLogin('Sessiya tugadi, qayta kiring'); } throw e; }
        return j;
      });
    });
  }
  function modal(html) { dlg.hidden = false; dlg.innerHTML = '<div class="box" role="dialog" aria-modal="true">' + html + '</div>'; var f = $('input,select,textarea,button', dlg); if (f) f.focus(); }
  function closeModal() { dlg.hidden = true; dlg.innerHTML = ''; }
  dlg.addEventListener('click', function (e) { if (e.target === dlg) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });
  function confirmBox(text, label, danger) {
    return new Promise(function (res) {
      modal('<h2>Tasdiqlang</h2><p>' + esc(text) + '</p><div class="row"><button class="btn ' + (danger ? 'd' : 'p') + '" id="cy">' + esc(label || 'Ha') + '</button><button class="btn" id="cn">Bekor qilish</button></div>');
      $('#cy').onclick = function () { closeModal(); res(true); }; $('#cn').onclick = function () { closeModal(); res(false); };
    });
  }
  function fail(e) { toast(e.message, true); }

  // ---- Kirish ----
  function renderLogin(msg) {
    clearInterval(hbTimer);
    root.innerHTML = '<main class="login" id="main"><div class="brand" style="color:var(--ink)"><span class="logo">T</span>Til Yo\'li · Admin</div><div class="card"><h1>Administrator kirishi</h1><form id="lf" novalidate><label for="n">Foydalanuvchi nomi</label><input id="n" autocomplete="username" style="width:100%" required><label for="p">Parol</label><input id="p" type="password" autocomplete="current-password" style="width:100%" required><p class="err" role="alert" id="le">' + esc(msg || '') + '</p><button class="btn p" style="width:100%;justify-content:center" type="submit">Kirish</button></form></div><p class="mute">Faqat vakolatli administratorlar uchun. Barcha kirishlar qayd etiladi.</p></main>';
    $('#n').focus();
    $('#lf').onsubmit = function (e) {
      e.preventDefault(); var b = $('button', e.target); b.disabled = true;
      api('POST', '/api/admin/login', { name: $('#n').value, pass: $('#p').value }).then(function (r) { me = r.admin; csrf = r.csrf; location.hash = '#/'; start(); }).catch(function (er) { $('#le').textContent = er.message; b.disabled = false; });
    };
  }

  // ---- Qobiq ----
  var cur = { name: '', q: {} };
  function parseHash() { var h = (location.hash || '#/').slice(2), qi = h.indexOf('?'), q = {}; if (qi >= 0) { new URLSearchParams(h.slice(qi + 1)).forEach(function (v, k) { q[k] = v; }); h = h.slice(0, qi); } var p = h.split('/'); return { name: p[0] || 'dashboard', arg: p[1], q: q }; }
  function shell() {
    var r = parseHash(), nav = NAV.filter(function (n) { return can(n[3]); }).map(function (n) { return '<a href="#/' + (n[0] === 'dashboard' ? '' : n[0]) + '"' + (r.name === n[0] || (r.name === '' && n[0] === 'dashboard') ? ' aria-current="page"' : '') + '><span aria-hidden="true">' + ICON[n[0]] + '</span>' + n[2] + '</a>'; }).join('');
    root.innerHTML = '<div class="shell"><aside class="side" id="side"><div class="brand"><span class="logo">T</span>Til Yo\'li Admin</div><nav class="nav" aria-label="Admin menyusi">' + nav + '</nav></aside><div><header class="top"><button class="btn menu" id="mn" aria-label="Menyu">☰</button><input type="search" id="gs" placeholder="' + (can('users') ? 'Foydalanuvchi qidirish…' : "So'z qidirish…") + '" aria-label="Qidiruv"><span class="sp"></span><div class="bell"><button class="btn" id="bl" aria-label="Bildirishnomalar">🔔<span class="n" id="bn" hidden></span></button><div class="pop" id="bp" hidden></div></div><button class="btn" id="th" aria-label="Mavzuni almashtirish">◐</button><span class="mute">' + esc(me.name) + ' <span class="tag">' + ROLE[me.role] + '</span></span><button class="btn" id="lo">Chiqish</button></header><main class="main" id="main" tabindex="-1"><div class="spin">Yuklanmoqda…</div></main></div></div>';
    $('#mn').onclick = function () { $('#side').classList.toggle('open'); };
    $('#side').onclick = function (e) { if (e.target.closest('a')) $('#side').classList.remove('open'); };
    $('#lo').onclick = function () { api('POST', '/api/admin/logout').catch(function () {}).then(function () { me = null; csrf = null; renderLogin(); }); };
    $('#th').onclick = function () { var d = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = d; try { localStorage.setItem('tilyoli:pref', JSON.stringify({ theme: d })); } catch (e) {} };
    $('#gs').onkeydown = function (e) { if (e.key === 'Enter') { var v = encodeURIComponent(e.target.value.trim()); location.hash = can('users') ? '#/users?q=' + v : '#/content?q=' + v; } };
    $('#bl').onclick = function () { var p = $('#bp'); p.hidden = !p.hidden; };
    loadNotifs();
  }
  function loadNotifs() {
    api('GET', '/api/admin/notifications').then(function (r) {
      $('#bn').hidden = !r.items.length; $('#bn').textContent = r.items.length;
      $('#bp').innerHTML = r.items.length ? r.items.map(function (i) { return '<p><span class="tag ' + (i.type === 'err' ? 'r' : i.type === 'warn' ? 'y' : '') + '">' + (i.type === 'err' ? 'Xato' : i.type === 'warn' ? 'Ogohlantirish' : 'Ma\'lumot') + '</span> ' + esc(i.text) + '</p>'; }).join('') : '<p class="mute">Yangi bildirishnoma yo\'q</p>';
    }).catch(function () {});
  }
  function page(html) { var m = $('#main'); m.innerHTML = html; }

  // ---- Grafiklar (SVG) ----
  function lineChart(data, keys, colors) {
    var W = 640, H = 170, P = 24, mx = Math.max(1, Math.max.apply(null, data.map(function (d) { return Math.max.apply(null, keys.map(function (k) { return d[k]; })); })));
    var x = function (i) { return P + i * (W - 2 * P) / Math.max(1, data.length - 1); }, y = function (v) { return H - P - v * (H - 2 * P) / mx; };
    var lines = keys.map(function (k, ki) { return '<polyline fill="none" stroke="' + colors[ki] + '" stroke-width="2.5" stroke-linejoin="round" points="' + data.map(function (d, i) { return x(i) + ',' + y(d[k]); }).join(' ') + '"/>'; }).join('');
    var grid = [0, .5, 1].map(function (f) { return '<line x1="' + P + '" x2="' + (W - P) + '" y1="' + y(mx * f) + '" y2="' + y(mx * f) + '" stroke="var(--line)"/><text x="2" y="' + (y(mx * f) + 4) + '" font-size="10" fill="var(--mute)">' + Math.round(mx * f) + '</text>'; }).join('');
    var lab = '<text x="' + P + '" y="' + (H - 6) + '" font-size="10" fill="var(--mute)">' + esc(data[0].date.slice(5)) + '</text><text x="' + (W - P) + '" y="' + (H - 6) + '" font-size="10" text-anchor="end" fill="var(--mute)">' + esc(data[data.length - 1].date.slice(5)) + '</text>';
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="Grafik">' + grid + lines + lab + '</svg>';
  }
  function legend(items) { return '<div class="legend">' + items.map(function (i) { return '<span><span class="dot" style="background:' + i[1] + '"></span>' + esc(i[0]) + '</span>'; }).join('') + '</div>'; }
  function table(head, rows, empty) { return rows.length ? '<div class="tw"><table><thead><tr>' + head.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') + '</tr></thead><tbody>' + rows.join('') + '</tbody></table></div>' : '<div class="empty">' + esc(empty || "Ma'lumot yo'q") + '</div>'; }
  function pager(r, base) {
    if (r.pages <= 1) return ''; var q = function (p) { var o = Object.assign({}, cur.q, { page: p }); return '#/' + base + '?' + new URLSearchParams(o).toString(); };
    return '<div class="row" style="margin-top:.8rem"><a class="btn s' + (r.page <= 1 ? '" aria-disabled="true" style="pointer-events:none;opacity:.5' : '') + '" href="' + q(r.page - 1) + '">← Oldingi</a><span class="mute">' + r.page + ' / ' + r.pages + ' (' + r.total + ')</span><a class="btn s" href="' + q(r.page + 1) + '"' + (r.page >= r.pages ? ' aria-disabled="true" style="pointer-events:none;opacity:.5"' : '') + '>Keyingi →</a></div>';
  }

  // ---- Sahifalar ----
  var V = {};
  V.dashboard = function (r) {
    var days = +(r.q.days || 30);
    api('GET', '/api/admin/dashboard?days=' + days).then(function (d) {
      var c = d.content, k = function (v, l) { return '<div class="card kpi"><b>' + esc(v) + '</b><span>' + esc(l) + '</span></div>'; };
      var h = '<h1>Bosh panel</h1><div class="grid g4">' + k(c.levels, 'Darajalar') + k(c.lessons + c.tests, 'Darslar va sinovlar') + k(c.exercises, 'Mashq turlari') + k(c.words, "Lug'at so'zlari") + '</div>';
      if (d.users) {
        h += '<div class="grid g4">' + k(d.users.total, "Ro'yxatdan o'tganlar") + k(d.users.active7, 'Faol (7 kun)') + k(d.users.active30, 'Faol (30 kun)') + k(d.learning.lessonsCompleted, 'Tugatilgan mashg\'ulotlar') + k(d.learning.avgProgress + '%', "O'rtacha progress") + k(d.learning.totalXp, 'Jami XP') + k(d.users.new7, 'Yangi (7 kun)') + k(d.users.disabled, 'Bloklangan') + '</div>';
        h += '<div class="row" style="margin-bottom:.6rem"><span class="mute">Davr:</span>' + [7, 30, 90].map(function (n) { return '<a class="btn s' + (n === days ? ' p' : '') + '" href="#/?days=' + n + '">' + n + ' kun</a>'; }).join('') + '</div>';
        h += '<div class="grid g2"><div class="card"><h2>Foydalanuvchilar o\'sishi va faolligi</h2>' + lineChart(d.series, ['registrations', 'active'], ['#2563eb', '#16a34a']) + legend([["Yangi ro'yxatdan o'tganlar", '#2563eb'], ['Faol foydalanuvchilar', '#16a34a']]) + '</div>' +
          '<div class="card"><h2>Darslar va XP</h2>' + lineChart(d.series, ['lessons', 'xp'], ['#eab308', '#9333ea']) + legend([['Tugatilgan mashg\'ulotlar', '#eab308'], ['XP', '#9333ea']]) + '</div></div>';
        var mxu = Math.max(1, Math.max.apply(null, d.levelDistribution.map(function (x) { return x.users; })));
        h += '<div class="grid g2"><div class="card"><h2>Foydalanuvchilar eng yuqori darajasi</h2>' + d.levelDistribution.map(function (x) { return '<div class="row sb"><span>' + esc(x.level) + '</span><span>' + x.users + '</span></div><div class="hbar"><i style="width:' + 100 * x.users / mxu + '%"></i></div>'; }).join('') + '</div>' +
          '<div class="card"><h2>Mashhur darslar</h2>' + table(['Dars', 'Urinish'], d.popularLessons.map(function (x) { return '<tr><td>' + esc(x.title) + '</td><td>' + x.count + '</td></tr>'; }), "Hali urinishlar yo'q") + '</div></div>';
        h += '<div class="grid g2"><div class="card"><h2>Eng qiyin darslar</h2>' + table(['Dars', "O'rtacha natija", 'Urinish'], d.hardLessons.map(function (x) { return '<tr><td>' + esc(x.title) + '</td><td>' + x.avgScore + '%</td><td>' + x.attempts + '</td></tr>'; }), 'Yetarli ma\'lumot yo\'q (kamida 3 urinish)') + '</div>' +
          '<div class="card"><h2>Eng qiyin so\'zlar</h2>' + table(["So'z", 'Tarjima', 'Xato %', 'Javob'], d.hardWords.map(function (x) { return '<tr><td>' + esc(x.en) + '</td><td>' + esc(x.uz) + '</td><td>' + x.wrongRate + '%</td><td>' + x.attempts + '</td></tr>'; }), "Yetarli ma'lumot yo'q (kamida 5 javob)") + '</div></div>';
        h += '<div class="grid g2"><div class="card"><h2>Yangi foydalanuvchilar</h2>' + table(['Ism', 'Sana', 'XP'], d.recentUsers.map(function (u) { return '<tr><td><a href="#/users/' + u.id + '">' + esc(u.name) + '</a></td><td>' + fdate(u.created_at) + '</td><td>' + u.xp + '</td></tr>'; }), "Hali foydalanuvchi yo'q") + '</div>' +
          '<div class="card"><h2>So\'nggi faollik</h2>' + table(['Kim', 'Nima', 'Natija', 'Vaqt'], d.recentActivity.map(function (e) { return '<tr><td><a href="#/users/' + e.uid + '">' + esc(e.name) + '</a></td><td>' + esc(e.title) + '</td><td>' + e.pct + '%' + (e.ok ? '' : ' <span class="tag r">o\'tmadi</span>') + '</td><td>' + fdate(e.ts) + '</td></tr>'; }), "Hali faollik yo'q") + '</div></div>';
      } else h += '<p class="mute">Foydalanuvchi statistikasi sizning rolingiz uchun ochiq emas.</p>';
      page(h);
    }).catch(function (e) { page('<p class="err">' + esc(e.message) + '</p>'); });
  };

  V.users = function (r) {
    if (r.arg) return userProfile(r.arg);
    var qs = new URLSearchParams(cur.q).toString();
    api('GET', '/api/admin/users?' + qs).then(function (d) {
      var q = cur.q;
      page('<h1>Foydalanuvchilar</h1><form class="row card" id="uf"><input name="q" placeholder="Ism bo\'yicha qidirish" value="' + esc(q.q || '') + '" aria-label="Qidirish"><select name="status" aria-label="Holat"><option value="">Barcha holatlar</option><option value="active"' + (q.status === 'active' ? ' selected' : '') + '>Faol</option><option value="disabled"' + (q.status === 'disabled' ? ' selected' : '') + '>Bloklangan</option></select><select name="sort" aria-label="Saralash">' + [['created', "Ro'yxatdan o'tgan sana"], ['xp', 'XP'], ['seen', 'Oxirgi faollik'], ['name', 'Ism']].map(function (o) { return '<option value="' + o[0] + '"' + (q.sort === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select><button class="btn p">Qidirish</button><a class="btn" href="/api/admin/export/users.csv">⬇️ CSV</a></form>' +
        '<div class="card">' + table(['Ism', 'Holat', 'XP', 'Seriya', 'Darslar', "So'zlar", "Ro'yxatdan o'tgan", 'Oxirgi faollik'], d.rows.map(function (u) { return '<tr><td><a href="#/users/' + u.id + '">' + esc(u.name) + '</a></td><td><span class="tag ' + (u.status === 'active' ? 'g' : 'r') + '">' + (u.status === 'active' ? 'Faol' : 'Bloklangan') + '</span></td><td>' + u.xp + '</td><td>' + u.streak + '</td><td>' + u.lessons + '</td><td>' + u.words_learned + '</td><td>' + fdate(u.created_at) + '</td><td>' + fdate(u.last_seen) + '</td></tr>'; }), 'Foydalanuvchilar topilmadi') + pager(d, 'users') + '</div>');
      $('#uf').onsubmit = function (e) { e.preventDefault(); var o = {}; new FormData(e.target).forEach(function (v, k) { if (v) o[k] = v; }); location.hash = '#/users?' + new URLSearchParams(o).toString(); };
    }).catch(function (e) { page('<p class="err">' + esc(e.message) + '</p>'); });
  };
  function userProfile(id) {
    api('GET', '/api/admin/users/' + encodeURIComponent(id)).then(function (d) {
      var u = d.user, p = d.progress;
      page('<p><a href="#/users">← Foydalanuvchilar</a></p><h1>' + esc(u.name) + ' <span class="tag ' + (u.status === 'active' ? 'g' : 'r') + '">' + (u.status === 'active' ? 'Faol' : 'Bloklangan') + '</span></h1>' +
        '<div class="grid g4"><div class="card kpi"><b>' + u.xp + '</b><span>XP</span></div><div class="card kpi"><b>' + u.streak + '</b><span>Seriya (eng yaxshi ' + (p.bestStreak || 0) + ')</span></div><div class="card kpi"><b>' + p.percent + '%</b><span>Kurs progressi</span></div><div class="card kpi"><b>' + (p.hearts == null ? '—' : p.hearts) + '</b><span>Yurakchalar</span></div></div>' +
        '<div class="card row"><span class="mute">Ro\'yxatdan o\'tgan: ' + fdate(u.created_at) + ' · Oxirgi faollik: ' + fdate(u.last_seen) + ' · Xato so\'zlar: ' + p.mistakes + ' · Kunlik maqsad: ' + (p.goalMin || '—') + ' daq</span><span class="sp" style="flex:1"></span><button class="btn" id="st">' + (u.status === 'active' ? 'Bloklash' : 'Blokdan chiqarish') + '</button><button class="btn" id="rp">Progressni tozalash</button>' + (me.role === 'super_admin' ? '<button class="btn d" id="dl">Hisobni o\'chirish</button>' : '') + '</div>' +
        '<div class="grid g2"><div class="card"><h2>Tugallangan darslar</h2>' + table(['Dars', 'Eng yaxshi'], d.progress.done.map(function (x) { return '<tr><td>' + esc(x.title) + '</td><td>' + x.best + '%</td></tr>'; }), 'Hali dars tugatilmagan') + '</div>' +
        '<div class="card"><h2>Qiyin so\'zlar</h2>' + table(["So'z", 'Tarjima', 'Xato', "To'g'ri"], d.hardWords.map(function (x) { return '<tr><td>' + esc(x.en) + '</td><td>' + esc(x.uz) + '</td><td>' + x.wrong + '</td><td>' + x.right + '</td></tr>'; }), "Xatolar yo'q") + '</div></div>' +
        '<div class="grid g2"><div class="card"><h2>Kunlik faollik (14 kun)</h2>' + table(['Sana', 'XP', 'Daq', "To'g'ri", 'Xato'], d.days.map(function (x) { return '<tr><td>' + esc(x.date) + '</td><td>' + x.xp + '</td><td>' + Math.round(x.secs / 60) + '</td><td>' + x.correct + '</td><td>' + x.wrong + '</td></tr>'; }), "Ma'lumot yo'q") + '</div>' +
        '<div class="card"><h2>So\'nggi natijalar</h2>' + table(['Vaqt', 'Rejim', 'Natija', 'XP'], d.events.map(function (x) { return '<tr><td>' + fdate(x.ts) + '</td><td>' + esc(x.node || x.mode) + '</td><td>' + x.pct + '%</td><td>' + x.xp + '</td></tr>'; }), "Ma'lumot yo'q") + '</div></div>' +
        '<div class="card"><h2>Yutuqlar (' + p.achievements.length + ')</h2>' + (p.achievements.map(function (a) { return '<span class="tag y" style="margin:.15rem">' + esc(ACH[a] || a) + '</span>'; }).join('') || '<span class="mute">Yo\'q</span>') + '</div>');
      $('#st').onclick = function () { api('POST', '/api/admin/users/' + id + '/status', { status: u.status === 'active' ? 'disabled' : 'active' }).then(function () { toast('Saqlandi'); route(); }).catch(fail); };
      $('#rp').onclick = function () { confirmBox("Foydalanuvchining barcha progressi (XP, seriya, darslar) o'chadi. Davom etasizmi?", 'Tozalash', true).then(function (y) { if (y) api('POST', '/api/admin/users/' + id + '/reset-progress').then(function () { toast('Progress tozalandi'); route(); }).catch(fail); }); };
      if ($('#dl')) $('#dl').onclick = function () { confirmBox("Hisob butunlay o'chiriladi. Bu amalni qaytarib bo'lmaydi.", "O'chirish", true).then(function (y) { if (y) api('DELETE', '/api/admin/users/' + id).then(function () { toast("O'chirildi"); location.hash = '#/users'; }).catch(fail); }); };
    }).catch(function (e) { page('<p class="err">' + esc(e.message) + '</p>'); });
  }

  // Kurs mazmuni
  var contentLevel = 0;
  V.content = function (r) {
    api('GET', '/api/admin/content').then(function (d) {
      if (r.q.level != null) contentLevel = Math.min(+r.q.level || 0, d.levels.length - 1);
      var lv = d.levels[contentLevel], f = (r.q.q || '').toLowerCase();
      var tabs = d.levels.map(function (l) { return '<a class="btn s' + (l.idx === contentLevel ? ' p' : '') + '" href="#/content?level=' + l.idx + (f ? '&q=' + encodeURIComponent(f) : '') + '">' + esc(l.id) + '</a>'; }).join(' ');
      var h = '<h1>Kurs mazmuni</h1><div class="row sb card"><div class="row">' + tabs + '</div><input type="search" id="wf" placeholder="So\'z qidirish…" value="' + esc(r.q.q || '') + '" aria-label="So\'z qidirish"></div>' +
        '<div class="row sb"><h2>' + esc(lv.title) + ' <span class="mute">· ' + esc(lv.sub) + '</span></h2><div class="row"><button class="btn s" id="el">Darajani tahrirlash</button><button class="btn s" id="nt">+ Yangi mavzu</button></div></div>';
      lv.topics.forEach(function (tp) {
        var words = tp.words.filter(function (w) { return !f || w.en.toLowerCase().indexOf(f) >= 0 || w.uz.join(' ').toLowerCase().indexOf(f) >= 0; });
        if (f && !words.length) return;
        h += '<div class="card"><div class="row sb"><h3>' + esc(tp.icon) + ' ' + esc(tp.title) + ' <span class="tag ' + (tp.published ? 'g' : 'y') + '">' + (tp.published ? 'Nashr etilgan' : 'Nashr etilmagan (kamida ' + d.minWords + ' so\'z kerak)') + '</span> <span class="mute">' + tp.visible + " ta so'z</span></h3><div class=\"row\"><button class=\"btn s\" data-a=\"et\" data-t=\"" + tp.idx + "\">Mavzu</button><button class=\"btn s\" data-a=\"aw\" data-t=\"" + tp.idx + "\">+ So'z</button><button class=\"btn s\" data-a=\"im\" data-t=\"" + tp.idx + "\">⬆ Import</button></div></div>" +
          table(["Inglizcha", 'Tarjima', 'Misol', 'Holat', ''], words.map(function (w) { return '<tr' + (w.hidden ? ' style="opacity:.55"' : '') + '><td>' + esc(w.emoji) + ' <b>' + esc(w.en) + '</b></td><td>' + esc(w.uz.join('; ')) + '</td><td class="mute">' + esc(w.sent) + '</td><td>' + (w.hidden ? '<span class="tag r">Yashirin</span>' : w.custom ? '<span class="tag g">Yangi</span>' : w.edited ? '<span class="tag y">Tahrirlangan</span>' : '') + '</td><td style="white-space:nowrap"><button class="btn s" data-a="ew" data-id="' + esc(w.id) + '">Tahrir</button> ' + (w.hidden ? '<button class="btn s" data-a="rw" data-id="' + esc(w.id) + '">Qaytarish</button>' : '<button class="btn s d" data-a="dw" data-id="' + esc(w.id) + '">' + (w.custom ? "O'chirish" : 'Yashirish') + '</button>') + '</td></tr>'; }), "So'z yo'q") + '</div>';
      });
      page(h);
      var find = function (id) { var x = null; lv.topics.forEach(function (t) { t.words.forEach(function (w) { if (w.id === id) x = w; }); }); return x; };
      $('#wf').onkeydown = function (e) { if (e.key === 'Enter') location.hash = '#/content?level=' + contentLevel + '&q=' + encodeURIComponent(e.target.value.trim()); };
      $('#el').onclick = function () { modal('<h2>Darajani tahrirlash</h2><form id="f"><label>Nomi<input name="title" value="' + esc(lv.title) + '" maxlength="40" required style="width:100%"></label><label>Tavsif<input name="sub" value="' + esc(lv.sub) + '" maxlength="60" required style="width:100%"></label><p class="err" id="fe"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-c>Bekor</button></div></form>'); formSubmit('PUT', '/api/admin/levels/' + lv.idx); };
      $('#nt').onclick = function () { topicForm(null); };
      $('#main').onclick = function (e) {
        var b = e.target.closest('[data-a]'); if (!b) return; var a = b.dataset.a, t = +b.dataset.t;
        if (a === 'et') topicForm(lv.topics[t]); else if (a === 'aw') wordForm(null, t); else if (a === 'im') importForm(t);
        else if (a === 'ew') { var w = find(b.dataset.id); wordForm(w); }
        else if (a === 'rw') { var w2 = find(b.dataset.id); api('PUT', '/api/admin/words/' + encodeURIComponent(w2.id), Object.assign({}, w2, { hidden: false })).then(function () { toast('Qaytarildi'); route(); }).catch(fail); }
        else if (a === 'dw') { var w3 = find(b.dataset.id); confirmBox(w3.custom ? '«' + w3.en + '» butunlay o\'chiriladi.' : '«' + w3.en + "» yashiriladi (foydalanuvchilar progressi saqlanadi, keyin qaytarish mumkin).", w3.custom ? "O'chirish" : 'Yashirish', true).then(function (y) { if (y) api('DELETE', '/api/admin/words/' + encodeURIComponent(w3.id)).then(function () { toast('Bajarildi'); route(); }).catch(fail); }); }
      };
      function topicForm(tp) {
        modal('<h2>' + (tp ? 'Mavzuni tahrirlash' : 'Yangi mavzu') + '</h2><form id="f"><label>Nomi<input name="title" value="' + esc(tp ? tp.title : '') + '" maxlength="40" required style="width:100%"></label><label>Belgi (emoji)<input name="icon" value="' + esc(tp ? tp.icon : '📘') + '" maxlength="8"></label><label>Tushuntirish (dars boshida ko\'rsatiladi)<textarea name="tip" maxlength="400" style="min-height:90px">' + esc(tp ? tp.tip : '') + '</textarea></label><p class="err" id="fe"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-c>Bekor</button></div></form>');
        if (tp) formSubmit('PUT', '/api/admin/topics/' + lv.idx + '/' + tp.idx); else formSubmit('POST', '/api/admin/topics', { level: lv.idx });
      }
      function wordForm(w, topic) {
        var ed = !!w;
        modal('<h2>' + (ed ? "So'zni tahrirlash" : "Yangi so'z") + '</h2><form id="f"><label>Inglizcha so\'z<input name="en" value="' + esc(ed ? w.en : '') + '" maxlength="40" required style="width:100%"></label><label>Tarjimalar (";" bilan ajrating — barchasi to\'g\'ri javob hisoblanadi)<input name="uz" value="' + esc(ed ? w.uz.join('; ') : '') + '" required style="width:100%"></label><label>Emoji (rasm mashqi uchun, ixtiyoriy)<input name="emoji" value="' + esc(ed ? w.emoji : '') + '" maxlength="8"></label><label>Misol gap (so\'zni o\'z ichiga olsin)<input name="sent" value="' + esc(ed ? w.sent : '') + '" maxlength="160" style="width:100%"></label><label>Gap tarjimasi<input name="sentUz" value="' + esc(ed ? w.sentUz : '') + '" maxlength="160" style="width:100%"></label><p class="err" id="fe"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-c>Bekor</button></div></form>');
        formSubmit(ed ? 'PUT' : 'POST', ed ? '/api/admin/words/' + encodeURIComponent(w.id) : '/api/admin/words', ed ? { hidden: !!w.hidden } : { level: lv.idx, topic: topic }, true);
      }
      function importForm(topic) {
        modal('<h2>Jadvaldan import</h2><p class="mute">Har qatorda: <code>inglizcha ; tarjima(lar) ; emoji ; misol gap ; gap tarjimasi</code> (faqat birinchi ikkitasi majburiy). Excel/Sheets\'dan nusxalangan jadval (TAB) ham ishlaydi. Tarjimalar ichida "," bilan ajrating.</p><textarea id="imp" placeholder="apple ; olma ; 🍎&#10;table\tstol"></textarea><label>Takrorlangan so\'zlar bo\'lsa<select id="dm"><option value="report">Faqat ko\'rsat — hech narsa qo\'shma</option><option value="skip">Takrorlarni o\'tkazib yubor</option><option value="allow">Takrorlarni ham qo\'sh</option></select></label><div id="ir"></div><div class="row" style="margin-top:.6rem"><button class="btn" id="pv">Oldindan ko\'rish</button><button class="btn p" id="ap">Import qilish</button><button class="btn" data-c>Yopish</button></div>');
        var rows = function () { return $('#imp').value.split('\n').map(function (l) { return l.replace(/\r$/, ''); }).filter(function (l) { return l.trim(); }).map(function (l) { return (l.indexOf('\t') >= 0 ? l.split('\t') : l.split(';')).map(function (x) { return x.trim(); }); }); };
        var run = function (dry) {
          api('POST', '/api/admin/import', { level: lv.idx, topic: topic, rows: rows(), duplicates: $('#dm').value, dryRun: dry }).then(function (r) {
            $('#ir').innerHTML = '<p>✅ Qo\'shiladi: <b>' + r.added.length + '</b> · 🔁 Takror: <b>' + r.duplicates.length + '</b> · ❌ Xato: <b>' + r.invalid.length + '</b></p>' + (r.duplicates.length ? '<p class="mute">Takror: ' + r.duplicates.map(function (x) { return esc(x.en) + ' (' + esc(x.where) + ')'; }).join(', ') + '</p>' : '') + (r.invalid.length ? '<p class="err">' + r.invalid.map(function (x) { return x.row + '-qator: ' + esc(x.error); }).join('<br>') + '</p>' : '') + (!dry && !r.applied ? '<p class="err">Takrorlar bor — hech narsa qo\'shilmadi. Yuqoridan variantni tanlang.</p>' : '');
            if (!dry && r.applied) { toast(r.added.length + " ta so'z import qilindi"); closeModal(); route(); }
          }).catch(fail);
        };
        $('#pv').onclick = function () { run(true); }; $('#ap').onclick = function () { run(false); };
      }
    }).catch(function (e) { page('<p class="err">' + esc(e.message) + '</p>'); });
  };
  function formSubmit(method, url, extra, word) {
    var f = $('#f', dlg); var c = $('[data-c]', dlg); if (c) c.onclick = closeModal;
    f.onsubmit = function (e) {
      e.preventDefault(); var o = Object.assign({}, extra || {}); new FormData(f).forEach(function (v, k) { o[k] = v; });
      if (word) o.uz = String(o.uz).split(';').map(function (s) { return s.trim(); }).filter(Boolean);
      var go = function (allow) { if (allow) o.allowDuplicate = true; api(method, url, o).then(function () { closeModal(); toast('Saqlandi'); route(); }).catch(function (er) { if (er.status === 409 && er.data && er.data.duplicate && !allow) { confirmBox(er.message, "Baribir qo'shish").then(function (y) { if (y) go(true); else { modalBack(); } }); } else $('#fe').textContent = er.message; }); };
      function modalBack() { route(); }
      go(false);
    };
  }

  V.exercises = function () {
    api('GET', '/api/admin/content').then(function (d) {
      page('<h1>Mashq turlari</h1><div class="card"><p class="mute">O\'chirilgan mashq turlari yangi darslarda chiqmaydi. Yengil guruh (tarjima/rasm) va murakkab guruh (yozish, harf, bo\'sh joy, gap, eshitish) har birida kamida bittadan tur yoqiq bo\'lishi shart. Juftlashtirish va xatolarni takrorlash doim yoqiq.</p><form id="ef">' + d.kinds.map(function (k) { return '<label style="font-weight:500"><input type="checkbox" name="' + k + '"' + (d.disabled.indexOf(k) < 0 ? ' checked' : '') + '> ' + esc(KIND[k]) + '</label>'; }).join('') + '<p class="err" id="ee"></p><button class="btn p">Saqlash</button></form></div>');
      $('#ef').onsubmit = function (e) { e.preventDefault(); var off = d.kinds.filter(function (k) { return !e.target.elements[k].checked; }); api('PUT', '/api/admin/exercises', { disabled: off }).then(function () { toast('Saqlandi'); }).catch(function (er) { $('#ee').textContent = er.message; }); };
    }).catch(fail);
  };
  V.achievements = function () {
    api('GET', '/api/admin/achievements').then(function (d) {
      page('<h1>Yutuqlar</h1><div class="card">' + table(['Yutuq', 'Ochgan foydalanuvchilar', ''], Object.keys(ACH).map(function (id) { var n = d.counts[id] || 0; return '<tr><td>' + esc(ACH[id]) + '</td><td>' + n + ' / ' + d.users + '</td><td style="width:35%"><div class="hbar"><i style="width:' + (d.users ? 100 * n / d.users : 0) + '%"></i></div></td></tr>'; })) + '<p class="mute">Yutuq shartlari dastur kodida (store.js) belgilangan; bu yerda faqat ochilish statistikasi ko\'rsatiladi.</p></div>');
    }).catch(fail);
  };
  V.stats = function (r) { V.dashboard(r); };
  V.announcements = function () {
    api('GET', '/api/admin/announcements').then(function (d) {
      page('<div class="row sb"><h1>E\'lonlar</h1><button class="btn p" id="na">+ Yangi e\'lon</button></div><p class="mute">Faol e\'lonlar o\'quvchilarning bosh sahifasida ko\'rinadi (oxirgi 5 ta).</p><div class="card">' + table(['Sarlavha', 'Matn', 'Holat', 'Sana', ''], d.rows.map(function (a) { return '<tr><td>' + esc(a.title) + '</td><td>' + esc(a.body) + '</td><td><span class="tag ' + (a.active ? 'g' : '') + '">' + (a.active ? 'Faol' : 'Nofaol') + '</span></td><td>' + fdate(a.created) + '</td><td style="white-space:nowrap"><button class="btn s" data-e="' + a.id + '">Tahrir</button> <button class="btn s d" data-d="' + a.id + '">O\'chirish</button></td></tr>'; }), "E'lon yo'q") + '</div>');
      var form = function (a) { modal('<h2>' + (a ? "E'lonni tahrirlash" : "Yangi e'lon") + '</h2><form id="f"><label>Sarlavha<input name="title" maxlength="80" required style="width:100%" value="' + esc(a ? a.title : '') + '"></label><label>Matn<textarea name="body" maxlength="500" required style="min-height:90px">' + esc(a ? a.body : '') + '</textarea></label><label style="font-weight:500"><input type="checkbox" name="active"' + (!a || a.active ? ' checked' : '') + '> Faol</label><p class="err" id="fe"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-c>Bekor</button></div></form>'); var f = $('#f', dlg); $('[data-c]', dlg).onclick = closeModal; f.onsubmit = function (e) { e.preventDefault(); var o = { title: f.title.value, body: f.body.value, active: f.active.checked }; api(a ? 'PUT' : 'POST', '/api/admin/announcements' + (a ? '/' + a.id : ''), o).then(function () { closeModal(); toast('Saqlandi'); route(); }).catch(function (er) { $('#fe').textContent = er.message; }); }; };
      $('#na').onclick = function () { form(null); };
      $('#main').onclick = function (e) { var b = e.target.closest('button'); if (!b) return; if (b.dataset.e) form(d.rows.filter(function (x) { return x.id == b.dataset.e; })[0]); if (b.dataset.d) confirmBox("E'lon o'chiriladi.", "O'chirish", true).then(function (y) { if (y) api('DELETE', '/api/admin/announcements/' + b.dataset.d).then(function () { route(); }).catch(fail); }); };
    }).catch(fail);
  };
  V.audit = function () {
    api('GET', '/api/admin/audit?page=' + (cur.q.page || 1)).then(function (d) {
      page('<h1>Audit jurnali</h1><div class="card">' + table(['Vaqt', 'Administrator', 'Amal', 'Obyekt', 'Natija', 'Izoh'], d.rows.map(function (a) { return '<tr><td>' + fdate(a.ts) + '</td><td>' + esc(a.user_name || '—') + '</td><td>' + esc(a.action) + '</td><td>' + esc(a.target || '') + '</td><td><span class="tag ' + (a.ok ? 'g' : 'r') + '">' + (a.ok ? 'OK' : 'Xato') + '</span></td><td class="mute">' + esc(a.detail || '') + '</td></tr>'; }), 'Yozuv yo\'q') + pager(d, 'audit') + '</div>');
    }).catch(fail);
  };
  V.settings = function () {
    Promise.all([api('GET', '/api/admin/settings'), api('GET', '/api/admin/admins')]).then(function (res) {
      var s = res[0], a = res[1];
      page('<h1>Sozlamalar</h1><div class="card"><h2>Platforma</h2><label style="font-weight:500"><input type="checkbox" id="ro"' + (s.registrationOpen ? ' checked' : '') + '> Yangi foydalanuvchilar ro\'yxatdan o\'ta oladi</label><button class="btn p" id="ss" style="margin-top:.6rem">Saqlash</button></div>' +
        '<div class="card"><div class="row sb"><h2>Administratorlar</h2><button class="btn p" id="aa">+ Administrator qo\'shish</button></div>' + table(['Ism', 'Rol', 'Holat', 'Oxirgi kirish', ''], a.rows.map(function (u) { return '<tr><td>' + esc(u.name) + '</td><td>' + esc(ROLE[u.role]) + '</td><td><span class="tag ' + (u.status === 'active' ? 'g' : 'r') + '">' + (u.status === 'active' ? 'Faol' : 'Bloklangan') + '</span></td><td>' + fdate(u.last_seen) + '</td><td><button class="btn s" data-u="' + u.id + '">Tahrir</button></td></tr>'; })) +
        '<p class="mute">Rollar: <b>Super Admin</b> — hammasi; <b>Admin</b> — mazmun, foydalanuvchilar, statistika, e\'lonlar, audit; <b>Editor</b> — faqat kurs mazmuni va mashqlar.</p></div>');
      $('#ss').onclick = function () { api('PUT', '/api/admin/settings', { registrationOpen: $('#ro').checked }).then(function () { toast('Saqlandi'); }).catch(fail); };
      var form = function (u) {
        modal('<h2>' + (u ? esc(u.name) : 'Yangi administrator') + '</h2><form id="f">' + (u ? '' : '<label>Ism<input name="name" maxlength="24" required style="width:100%"></label>') + '<label>Rol<select name="role">' + ['editor', 'admin', 'super_admin'].map(function (r) { return '<option value="' + r + '"' + (u && u.role === r ? ' selected' : '') + '>' + ROLE[r] + '</option>'; }).join('') + '</select></label>' + (u ? '<label>Holat<select name="status"><option value="active"' + (u.status === 'active' ? ' selected' : '') + '>Faol</option><option value="disabled"' + (u.status === 'disabled' ? ' selected' : '') + '>Bloklangan</option></select></label>' : '') + '<label>' + (u ? 'Yangi parol (ixtiyoriy)' : 'Parol') + '<input name="pass" type="password" autocomplete="new-password" style="width:100%"' + (u ? '' : ' required') + '></label><p class="mute">Kamida 10 belgi, harf va raqam.</p><p class="err" id="fe"></p><div class="row"><button class="btn p">Saqlash</button><button type="button" class="btn" data-c>Bekor</button></div></form>');
        var f = $('#f', dlg); $('[data-c]', dlg).onclick = closeModal;
        f.onsubmit = function (e) { e.preventDefault(); var o = {}; new FormData(f).forEach(function (v, k) { if (v !== '') o[k] = v; }); api(u ? 'PUT' : 'POST', '/api/admin/admins' + (u ? '/' + u.id : ''), o).then(function () { closeModal(); toast('Saqlandi'); route(); }).catch(function (er) { $('#fe').textContent = er.message; }); };
      };
      $('#aa').onclick = function () { form(null); };
      $('#main').onclick = function (e) { var b = e.target.closest('[data-u]'); if (b) form(a.rows.filter(function (x) { return x.id == b.dataset.u; })[0]); };
    }).catch(fail);
  };

  function route() {
    if (!me) return;
    var r = parseHash(); cur = { name: r.name, q: r.q };
    var nav = NAV.filter(function (n) { return n[0] === r.name; })[0];
    shell();
    if (!nav || !can(nav[3])) { page('<h1>Ruxsat yo\'q</h1><p>Bu bo\'limga kirish huquqingiz yo\'q.</p>'); return; }
    closeModal(); (V[r.name] || V.dashboard)(r);
  }
  window.addEventListener('hashchange', route);
  function start() { route(); clearInterval(hbTimer); hbTimer = setInterval(loadNotifsSafe, 60000); }
  function loadNotifsSafe() { if (me && $('#bn')) loadNotifs(); }
  api('GET', '/api/admin/me').then(function (r) { me = r.admin; csrf = r.csrf; start(); }).catch(function () { renderLogin(); });
})();
