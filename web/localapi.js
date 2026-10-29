/* Lokal admin rejimi: server yo'q (bitta fayl / file://) bo'lganda /api/admin/* so'rovlarini brauzer ichida (localStorage) bajaradi.
   Bu serverdagi mantiqning qisqartirilgan nusxasi. Xavfsizlik FAQAT shu brauzer darajasida (haqiqiy himoya emas). */
(function (TY) {
  'use strict';
  var P = 'tilyoli:', DAY = 864e5, MIN_WORDS = TY.MIN_WORDS || 4;
  var KINDS = ['mc_en_uz', 'mc_uz_en', 'picture', 'type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'listen'];
  var EASY = ['mc_en_uz', 'mc_uz_en', 'picture'], HARD = ['type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'listen'];
  function ls(k, d) { try { var v = localStorage.getItem(P + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function sv(k, v) { try { localStorage.setItem(P + k, JSON.stringify(v)); } catch (e) {} }
  function rm(k) { try { localStorage.removeItem(P + k); } catch (e) {} }
  var now = Date.now;
  function HttpErr(status, msg, extra) { var e = new Error(msg); e.status = status; e.extra = extra; return e; }
  var bad = function (m) { return HttpErr(400, m); };

  // ---- Ma'lumot qatlami ----
  function content() { var c = ls('local-content', null) || {}; c.levels = c.levels || []; c.topics = c.topics || []; c.words = c.words || []; c.disabled = c.disabled || []; c.announcements = c.announcements || []; c.seq = c.seq || 0; return c; }
  function saveContent(c) { sv('local-content', c); }
  TY.localRows = function () { var c = content(); return { levels: c.levels, topics: c.topics, words: c.words, disabled: c.disabled }; };
  TY.localAnnouncements = function () { return content().announcements.filter(function (a) { return a.active; }).slice(-5).reverse(); };
  function audit(action, target, ok, detail) { var a = ls('local-audit', []); a.unshift({ id: now(), ts: now(), user_name: (ls('local-admin', {}) || {}).name, action: action, target: target == null ? null : String(target), ok: ok === false ? 0 : 1, detail: detail || null }); sv('local-audit', a.slice(0, 500)); }
  function learners() {
    var u = ls('users', {}), out = [];
    Object.keys(u).forEach(function (k, i) {
      var st = ls('data:' + k, null) || null, last = 0;
      if (st) { (st.history || []).forEach(function (h) { last = Math.max(last, h.ts); }); Object.keys(st.days || {}).forEach(function (d) { var t = new Date(d + 'T12:00:00').getTime(); if (st.days[d].secs || st.days[d].xp) last = Math.max(last, t); }); }
      out.push({ id: i + 1, key: k, name: u[k].name, status: u[k].disabled ? 'disabled' : 'active', created_at: u[k].created, last_seen: last || null, state: st, xp: st ? st.xp : 0, streak: TY.Game ? 0 : 0, lessons: st ? Object.keys(st.done || {}).length : 0, words_learned: st ? Object.keys(st.words || {}).filter(function (w) { return st.words[w].c > 0; }).length : 0 });
      out[out.length - 1].streak = st ? (st.streak || 0) : 0;
    });
    return out;
  }
  function events() { var ev = []; learners().forEach(function (u) { if (u.state) (u.state.history || []).forEach(function (h) { ev.push({ ts: h.ts, mode: h.mode, node: h.node, pct: h.pct, xp: h.xp, ok: h.ok ? 1 : 0, uid: u.id, name: u.name }); }); }); return ev.sort(function (a, b) { return b.ts - a.ts; }); }
  function merged(keep) { var c = content(); TY.applyContent({ levels: c.levels, topics: c.topics, words: c.words, disabled: c.disabled }, keep); return TY.LEVELS; }
  function dayKey(ts) { var d = new Date(ts); return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0'); }

  // ---- Tekshiruv ----
  function str(v, max, label, req) {
    if (v == null || v === '') { if (req) throw bad(label + ' kiritilishi shart'); return ''; }
    if (typeof v !== 'string') throw bad(label + " noto'g'ri turda");
    v = v.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').trim(); if (req && !v) throw bad(label + ' kiritilishi shart');
    if (v.length > max) throw bad(label + ' juda uzun (maks. ' + max + ')'); return v;
  }
  function validWord(b) {
    var en = str(b.en, 40, "Inglizcha so'z", true);
    if (!/^[A-Za-z][A-Za-z '\-.]*$/.test(en)) throw bad("Inglizcha so'zda faqat lotin harflari, bo'shliq, ' - . bo'lishi mumkin");
    var uz = (Array.isArray(b.uz) ? b.uz : String(b.uz || '').split(';')).map(function (x) { return str(x, 60, 'Tarjima'); }).filter(Boolean);
    if (!uz.length) throw bad('Kamida bitta tarjima kerak'); if (uz.length > 8) throw bad('Tarjimalar 8 tadan oshmasin');
    var sent = str(b.sent, 160, 'Misol gap'), sentUz = str(b.sentUz, 160, 'Gap tarjimasi');
    if (sent && !new RegExp('\\b' + en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(sent)) throw bad("Misol gapda so'zning o'zi bo'lishi kerak (bo'sh joyni to'ldirish mashqi uchun)");
    if (sent && !sentUz) throw bad('Misol gap tarjimasini kiriting');
    return { en: en, uz: uz, emoji: str(b.emoji, 8, 'Emoji'), sent: sent, sentUz: sentUz };
  }
  function intIn(v, min, max, label) { v = Number(v); if (!Number.isInteger(v) || v < min || v > max) throw bad(label + " noto'g'ri"); return v; }
  function dupOf(level, en, exceptId) { var L = merged(true), k = en.toLowerCase(), r = null; L[level].topics.forEach(function (tp) { tp.words.forEach(function (w) { if (!r && w.id !== exceptId && w.en.toLowerCase() === k) r = { id: w.id, topic: tp.title, hidden: !!w.hidden }; }); }); return r; }
  function findWord(id) { var L = merged(true), f = null; L.forEach(function (lv, li) { lv.topics.forEach(function (tp, ti) { tp.words.forEach(function (w) { if (w.id === id) f = { li: li, ti: ti, w: w, tp: tp }; }); }); }); return f; }
  function upsert(c, id, level, topic, v, base, hidden) {
    var r = c.words.filter(function (x) { return x.id === id; })[0];
    if (r) { r.en = v.en; r.uz = v.uz; r.emoji = v.emoji; r.sent = v.sent; r.sentUz = v.sentUz; r.hidden = hidden ? 1 : 0; }
    else c.words.push({ id: id, level: level, topic: topic, en: v.en, uz: v.uz, emoji: v.emoji, sent: v.sent, sentUz: v.sentUz, hidden: hidden ? 1 : 0, base: base ? 1 : 0, pos: ++c.seq });
  }
  function newId(c, level, topic) { var k = c.words.filter(function (x) { return !x.base; }).length + 1, id; do { id = level + '.' + topic + '.a' + (k++); } while (c.words.some(function (x) { return x.id === id; })); return id; }

  // ---- Admin sessiyasi ----
  function hash(s) {
    if (window.crypto && crypto.subtle && window.TextEncoder) return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(function (b) { return Array.prototype.map.call(new Uint8Array(b), function (x) { return ('0' + x.toString(16)).slice(-2); }).join(''); });
    var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return Promise.resolve('x' + (h >>> 0).toString(16));
  }
  function pwProblem(p) { if (typeof p !== 'string' || p.length < 10) return "Parol kamida 10 belgidan iborat bo'lsin"; if (!/[A-Za-z]/.test(p) || !/[0-9]/.test(p)) return "Parolda harf va raqam bo'lsin"; return null; }
  function session() { try { return sessionStorage.getItem(P + 'local-admin-session') === '1'; } catch (e) { return false; } }
  function setSession(v) { try { v ? sessionStorage.setItem(P + 'local-admin-session', '1') : sessionStorage.removeItem(P + 'local-admin-session'); } catch (e) {} }
  var ADMIN = function () { var a = ls('local-admin', null); return { name: a ? a.name : 'Admin', role: 'super_admin', perms: ['dashboard', 'content', 'exercises', 'users', 'stats', 'announcements', 'audit', 'admins', 'settings'] }; };
  var CSRF = 'local';

  // ---- Statistika ----
  function dashboard(days) {
    var L = merged(false), us = learners(), t = now(), ev = events(), out = {};
    var lessonNodes = TY.NODES.filter(function (n) { return n.kind === 'lesson'; }).length;
    out.content = { levels: L.length, lessons: lessonNodes, tests: L.length, exercises: KINDS.length + 1, words: TY.allWords.length, hiddenWords: content().words.filter(function (w) { return w.hidden; }).length, edits: content().words.length };
    var act = function (d) { return us.filter(function (u) { return u.last_seen && u.last_seen >= t - d * DAY; }).length; };
    var doneSum = us.reduce(function (a, u) { return a + u.lessons; }, 0);
    out.users = { total: us.length, active7: act(7), active30: act(30), new7: us.filter(function (u) { return u.created_at >= t - 7 * DAY; }).length, disabled: us.filter(function (u) { return u.status === 'disabled'; }).length };
    out.learning = { lessonsCompleted: ev.filter(function (e) { return e.ok; }).length, avgProgress: us.length ? Math.round(1000 * doneSum / (us.length * TY.NODES.length)) / 10 : 0, totalXp: us.reduce(function (a, u) { return a + u.xp; }, 0) };
    var title = function (id) { var n = TY.nodeById[id]; return n ? L[n.level].id + ' · ' + n.title : id; };
    var byNode = {}; ev.forEach(function (e) { if (!e.node) return; var b = byNode[e.node] || (byNode[e.node] = { n: 0, s: 0 }); b.n++; b.s += e.pct; });
    out.popularLessons = Object.keys(byNode).sort(function (a, b) { return byNode[b].n - byNode[a].n; }).slice(0, 5).map(function (k) { return { node: k, title: title(k), count: byNode[k].n }; });
    out.hardLessons = Object.keys(byNode).filter(function (k) { return byNode[k].n >= 3; }).sort(function (a, b) { return byNode[a].s / byNode[a].n - byNode[b].s / byNode[b].n; }).slice(0, 5).map(function (k) { return { node: k, title: title(k), attempts: byNode[k].n, avgScore: Math.round(byNode[k].s / byNode[k].n) }; });
    var ws = {}; us.forEach(function (u) { if (u.state) Object.keys(u.state.words || {}).forEach(function (id) { var a = ws[id] || (ws[id] = { c: 0, w: 0 }); a.c += u.state.words[id].c || 0; a.w += u.state.words[id].w || 0; }); });
    out.hardWords = Object.keys(ws).filter(function (id) { return TY.wordById[id] && ws[id].c + ws[id].w >= 5; }).map(function (id) { return { id: id, en: TY.wordById[id].en, uz: TY.wordById[id].uz[0], attempts: ws[id].c + ws[id].w, wrongRate: Math.round(100 * ws[id].w / (ws[id].c + ws[id].w)) }; }).sort(function (a, b) { return b.wrongRate - a.wrongRate; }).slice(0, 8);
    out.recentUsers = us.slice().sort(function (a, b) { return b.created_at - a.created_at; }).slice(0, 8).map(function (u) { return { id: u.id, name: u.name, created_at: u.created_at, xp: u.xp }; });
    out.recentActivity = ev.slice(0, 10).map(function (e) { return { ts: e.ts, mode: e.mode, node: e.node, pct: e.pct, xp: e.xp, ok: e.ok, name: e.name, uid: e.uid, title: e.node ? title(e.node) : ({ practice: 'Aralash mashq', mistakes: "Xato so'zlar" }[e.mode] || e.mode) }; });
    var s = {}, start = t - (days - 1) * DAY, i; for (i = 0; i < days; i++) s[dayKey(start + i * DAY)] = { date: dayKey(start + i * DAY), registrations: 0, active: 0, lessons: 0, xp: 0, _u: {} };
    us.forEach(function (u) { var k = dayKey(u.created_at); if (s[k]) s[k].registrations++; });
    ev.forEach(function (e) { var k = dayKey(e.ts); if (s[k]) { s[k].xp += e.xp; if (e.ok) s[k].lessons++; s[k]._u[e.uid] = 1; } });
    out.series = Object.keys(s).map(function (k) { s[k].active = Object.keys(s[k]._u).length; delete s[k]._u; return s[k]; });
    out.levelDistribution = L.map(function (lv) { return { level: lv.id, users: 0 }; });
    us.forEach(function (u) { if (!u.state) return; var d = u.state.done || {}, top = 0, any = false; Object.keys(d).forEach(function (id) { var m = /^L(\d)/.exec(id); if (m) { top = Math.max(top, +m[1]); any = true; } }); if (any && out.levelDistribution[top]) out.levelDistribution[top].users++; });
    out.role = 'super_admin'; return out;
  }

  // ---- Marshrutlar ----
  var R = [];
  function r(method, re, fn, open) { R.push({ method: method, re: new RegExp('^' + re.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn: fn, open: open }); }
  r('POST', '/api/admin/login', function (c) {
    var name = str(c.body.name, 24, 'Ism', true), pass = String(c.body.pass || ''), a = ls('local-admin', null), lock = ls('local-lock', { n: 0, t: 0 });
    if (lock.n >= 5 && now() - lock.t < 15 * 6e4) throw HttpErr(429, "Urinishlar ko'p. 15 daqiqadan keyin qayta urining.");
    if (!a) { var p = pwProblem(pass); if (p) throw bad(p); return hash(name.toLowerCase() + ':' + pass).then(function (h) { sv('local-admin', { name: name, h: h }); setSession(true); audit('admin.setup', name, true); return { admin: ADMIN(), csrf: CSRF }; }); }
    return hash(name.toLowerCase() + ':' + pass).then(function (h) {
      if (name.toLowerCase() !== a.name.toLowerCase() || h !== a.h) { lock = { n: (lock.n || 0) + 1, t: now() }; sv('local-lock', lock); audit('admin.login', name, false); throw HttpErr(401, "Ism yoki parol noto'g'ri"); }
      rm('local-lock'); setSession(true); audit('admin.login', name, true); return { admin: ADMIN(), csrf: CSRF };
    });
  }, true);
  r('POST', '/api/admin/logout', function () { setSession(false); return {}; });
  r('GET', '/api/admin/me', function () { return { admin: ADMIN(), csrf: CSRF }; });
  r('GET', '/api/admin/dashboard', function (c) { return dashboard(intIn(c.q.days || 30, 7, 90, 'days')); });
  r('GET', '/api/admin/notifications', function () {
    var us = learners(), l = [], t = now(), n = us.filter(function (u) { return u.created_at >= t - DAY; }).length;
    if (n) l.push({ type: 'info', text: "Oxirgi 24 soatda " + n + " ta yangi foydalanuvchi", ts: t });
    var d = us.filter(function (u) { return u.status === 'disabled'; }).length; if (d) l.push({ type: 'info', text: d + ' ta bloklangan hisob', ts: t });
    ls('local-audit', []).filter(function (a) { return !a.ok; }).slice(0, 5).forEach(function (a) { l.push({ type: 'err', text: 'Muvaffaqiyatsiz: ' + a.action + ' ' + (a.target || ''), ts: a.ts }); });
    return { items: l };
  });
  r('GET', '/api/admin/users', function (c) {
    var page = intIn(c.q.page || 1, 1, 10000, 'page'), size = 20, q = String(c.q.q || '').toLowerCase().slice(0, 40), us = learners().filter(function (u) { return u.name.toLowerCase().indexOf(q) >= 0 && (!c.q.status || u.status === c.q.status); });
    var cmp = { name: function (a, b) { return a.name.localeCompare(b.name); }, xp: function (a, b) { return b.xp - a.xp; }, seen: function (a, b) { return (b.last_seen || 0) - (a.last_seen || 0); } }[c.q.sort] || function (a, b) { return b.created_at - a.created_at; };
    us.sort(cmp); var total = us.length;
    return { rows: us.slice((page - 1) * size, page * size).map(function (u) { return { id: u.id, name: u.name, status: u.status, created_at: u.created_at, last_seen: u.last_seen, xp: u.xp, streak: u.streak, lessons: u.lessons, words_learned: u.words_learned }; }), total: total, page: page, pages: Math.max(1, Math.ceil(total / size)) };
  });
  function userBy(id) { id = intIn(id, 1, 1e9, 'id'); var u = learners().filter(function (x) { return x.id === id; })[0]; if (!u) throw HttpErr(404, 'Foydalanuvchi topilmadi'); return u; }
  r('GET', '/api/admin/users/:id', function (c) {
    var u = userBy(c.params.id), s = u.state || {}; var L = merged(false);
    var done = Object.keys(s.done || {}).map(function (id) { return { id: id, title: TY.nodeById[id] ? L[TY.nodeById[id].level].id + ' · ' + TY.nodeById[id].title : id, best: s.done[id].best }; });
    var hard = Object.keys(s.words || {}).filter(function (id) { return TY.wordById[id] && s.words[id].w > 0; }).map(function (id) { return { en: TY.wordById[id].en, uz: TY.wordById[id].uz[0], wrong: s.words[id].w, right: s.words[id].c }; }).sort(function (a, b) { return b.wrong - a.wrong; }).slice(0, 10);
    return { user: { id: u.id, name: u.name, status: u.status, created_at: u.created_at, last_seen: u.last_seen, xp: u.xp, streak: u.streak, lessons: u.lessons, words_learned: u.words_learned },
      progress: { hearts: s.hearts, bestStreak: s.bestStreak, goalMin: s.goalMin, achievements: Object.keys(s.ach || {}), mistakes: Object.keys(s.mistakes || {}).length, done: done, percent: Math.round(100 * done.length / TY.NODES.length) },
      days: Object.keys(s.days || {}).sort().slice(-14).map(function (d) { return Object.assign({ date: d }, s.days[d]); }), hardWords: hard, events: events().filter(function (e) { return e.uid === u.id; }).slice(0, 15) };
  });
  r('POST', '/api/admin/users/:id/status', function (c) { var u = userBy(c.params.id); if (['active', 'disabled'].indexOf(c.body.status) < 0) throw bad('status'); var us = ls('users', {}); us[u.key].disabled = c.body.status === 'disabled'; sv('users', us); audit('user.' + c.body.status, u.name, true); return {}; });
  r('POST', '/api/admin/users/:id/reset-progress', function (c) { var u = userBy(c.params.id); rm('data:' + u.key); audit('user.reset-progress', u.name, true); return {}; });
  r('DELETE', '/api/admin/users/:id', function (c) { var u = userBy(c.params.id), us = ls('users', {}); delete us[u.key]; sv('users', us); rm('data:' + u.key); audit('user.delete', u.name, true); return {}; });
  r('GET', '/api/admin/export/users.csv', function () { audit('export.users', '', true); return { csv: TY.localCsv() }; });
  TY.localCsv = function () {
    var cell = function (v) { var s = v == null ? '' : String(v); if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }, iso = function (t) { return t ? new Date(t).toISOString() : ''; };
    return ['id,name,status,created,last_seen,xp,streak,lessons,words_learned'].concat(learners().map(function (u) { return [u.id, u.name, u.status, iso(u.created_at), iso(u.last_seen), u.xp, u.streak, u.lessons, u.words_learned].map(cell).join(','); })).join('\n');
  };
  r('GET', '/api/admin/content', function () {
    var L = merged(true), c = content(), ed = {}; c.words.forEach(function (w) { ed[w.id] = 1; });
    return { levels: L.map(function (lv, li) { return { idx: li, id: lv.id, title: lv.title, sub: lv.sub, color: lv.color, topics: lv.topics.map(function (tp, ti) { var vis = tp.words.filter(function (w) { return !w.hidden; }).length; return { idx: ti, title: tp.title, icon: tp.icon, tip: tp.tip, visible: vis, published: vis >= MIN_WORDS, words: tp.words.map(function (w) { return Object.assign({}, w, { edited: !!ed[w.id], custom: /\.a\d+$/.test(w.id) }); }) }; }) }; }), disabled: c.disabled, kinds: KINDS, minWords: MIN_WORDS };
  });
  function topicOf(level, topic) { var L = merged(true), lv = L[intIn(level, 0, L.length - 1, 'Daraja')]; return { lv: lv, tp: lv.topics[intIn(topic, 0, lv.topics.length - 1, 'Mavzu')] }; }
  r('POST', '/api/admin/words', function (c) {
    topicOf(c.body.level, c.body.topic); var level = +c.body.level, topic = +c.body.topic, v = validWord(c.body), d = dupOf(level, v.en);
    if (d && !c.body.allowDuplicate) throw HttpErr(409, '«' + v.en + "» bu darajada allaqachon bor (" + d.topic + "). Baribir qo'shish uchun tasdiqlang.", { duplicate: d });
    var cc = content(), id = newId(cc, level, topic); upsert(cc, id, level, topic, v, false, false); saveContent(cc); audit('word.create', id + ' ' + v.en, true); return { id: id };
  });
  r('PUT', '/api/admin/words/:id', function (c) {
    var f = findWord(decodeURIComponent(c.params.id)); if (!f) throw HttpErr(404, "So'z topilmadi");
    var v = validWord(c.body), hidden = !!c.body.hidden;
    if (hidden && !f.w.hidden && f.tp.words.filter(function (w) { return !w.hidden; }).length - 1 < MIN_WORDS) throw HttpErr(409, 'Mavzuda kamida ' + MIN_WORDS + " ta ko'rinadigan so'z qolishi kerak");
    var d = dupOf(f.li, v.en, f.w.id); if (d && !c.body.allowDuplicate && v.en.toLowerCase() !== f.w.en.toLowerCase()) throw HttpErr(409, '«' + v.en + '» allaqachon bor', { duplicate: d });
    var cc = content(), row = cc.words.filter(function (x) { return x.id === f.w.id; })[0]; upsert(cc, f.w.id, f.li, f.ti, v, row ? row.base : 1, hidden); saveContent(cc);
    audit(hidden !== !!f.w.hidden ? (hidden ? 'word.hide' : 'word.restore') : 'word.update', f.w.id + ' ' + v.en, true); return {};
  });
  r('DELETE', '/api/admin/words/:id', function (c) {
    var f = findWord(decodeURIComponent(c.params.id)); if (!f) throw HttpErr(404, "So'z topilmadi");
    if (!f.w.hidden && f.tp.words.filter(function (w) { return !w.hidden; }).length - 1 < MIN_WORDS) throw HttpErr(409, 'Mavzuda kamida ' + MIN_WORDS + " ta ko'rinadigan so'z qolishi kerak");
    var cc = content(), row = cc.words.filter(function (x) { return x.id === f.w.id; })[0];
    if (row && !row.base) { cc.words = cc.words.filter(function (x) { return x.id !== f.w.id; }); saveContent(cc); audit('word.delete', f.w.id, true); return { deleted: true }; }
    upsert(cc, f.w.id, f.li, f.ti, f.w, true, true); saveContent(cc); audit('word.hide', f.w.id + ' ' + f.w.en, true); return { hidden: true };
  });
  r('POST', '/api/admin/import', function (c) {
    topicOf(c.body.level, c.body.topic); var level = +c.body.level, topic = +c.body.topic, rows = c.body.rows;
    if (!Array.isArray(rows) || !rows.length) throw bad("Qatorlar yo'q"); if (rows.length > 500) throw bad("Bir martada 500 tadan ko'p qator mumkin emas");
    var mode = ['report', 'skip', 'allow'].indexOf(c.body.duplicates) >= 0 ? c.body.duplicates : 'report', dry = !!c.body.dryRun, res = { added: [], duplicates: [], invalid: [] }, seen = {}, apply = [];
    rows.forEach(function (rw, i) {
      try {
        var v = validWord({ en: rw[0], uz: String(rw[1] || '').split(/[;,]/), emoji: rw[2], sent: rw[3], sentUz: rw[4] }), key = v.en.toLowerCase(), d = dupOf(level, v.en) || (seen[key] ? { topic: 'importdagi takror' } : null); seen[key] = 1;
        if (d) { res.duplicates.push({ row: i + 1, en: v.en, where: d.topic }); if (mode !== 'allow') return; }
        apply.push(v); res.added.push({ row: i + 1, en: v.en });
      } catch (e) { res.invalid.push({ row: i + 1, en: String(rw[0] || ''), error: e.message }); }
    });
    if (dry || (mode === 'report' && res.duplicates.length)) { res.applied = false; return res; }
    var cc = content(); apply.forEach(function (v) { upsert(cc, newId(cc, level, topic), level, topic, v, false, false); }); saveContent(cc);
    res.applied = true; audit('word.import', 'L' + level + 'T' + topic + ' +' + apply.length, true); return res;
  });
  r('POST', '/api/admin/topics', function (c) {
    var L = merged(true), level = intIn(c.body.level, 0, L.length - 1, 'Daraja'), idx = L[level].topics.length; if (idx >= 12) throw bad("Bir darajada 12 tadan ko'p mavzu mumkin emas");
    var cc = content(); cc.topics.push({ level: level, idx: idx, title: str(c.body.title, 40, 'Mavzu nomi', true), icon: str(c.body.icon, 8, 'Belgi') || '📘', tip: str(c.body.tip, 400, 'Tushuntirish') }); saveContent(cc); audit('topic.create', 'L' + level + 'T' + idx, true); return { idx: idx };
  });
  r('PUT', '/api/admin/topics/:level/:idx', function (c) {
    topicOf(c.params.level, c.params.idx); var cc = content(), l = +c.params.level, i = +c.params.idx, row = cc.topics.filter(function (x) { return x.level === l && x.idx === i; })[0], v = { level: l, idx: i, title: str(c.body.title, 40, 'Mavzu nomi', true), icon: str(c.body.icon, 8, 'Belgi') || '📘', tip: str(c.body.tip, 400, 'Tushuntirish') };
    if (row) Object.assign(row, v); else cc.topics.push(v); saveContent(cc); audit('topic.update', 'L' + l + 'T' + i, true); return {};
  });
  r('PUT', '/api/admin/levels/:idx', function (c) {
    var L = merged(true), idx = intIn(c.params.idx, 0, L.length - 1, 'Daraja'), cc = content(), v = { idx: idx, title: str(c.body.title, 40, 'Nom', true), sub: str(c.body.sub, 60, 'Tavsif', true) }, row = cc.levels.filter(function (x) { return x.idx === idx; })[0];
    if (row) Object.assign(row, v); else cc.levels.push(v); saveContent(cc); audit('level.update', idx, true); return {};
  });
  r('PUT', '/api/admin/exercises', function (c) {
    var d = c.body.disabled; if (!Array.isArray(d) || d.some(function (k) { return KINDS.indexOf(k) < 0; })) throw bad("Mashq turi noto'g'ri");
    if (EASY.every(function (k) { return d.indexOf(k) >= 0; }) || HARD.every(function (k) { return d.indexOf(k) >= 0; })) throw bad("Yengil va murakkab guruhlarning har birida kamida bitta mashq turi yoqiq bo'lsin");
    var cc = content(); cc.disabled = d.filter(function (k, i) { return d.indexOf(k) === i; }); saveContent(cc); audit('exercises.update', d.join(',') || '-', true); return {};
  });
  r('GET', '/api/admin/achievements', function () { var counts = {}, us = learners().filter(function (u) { return u.state; }); us.forEach(function (u) { Object.keys(u.state.ach || {}).forEach(function (k) { counts[k] = (counts[k] || 0) + 1; }); }); return { counts: counts, users: us.length }; });
  r('GET', '/api/admin/announcements', function () { return { rows: content().announcements.slice().reverse() }; });
  r('POST', '/api/admin/announcements', function (c) { var cc = content(), a = { id: ++cc.seq, title: str(c.body.title, 80, 'Sarlavha', true), body: str(c.body.body, 500, 'Matn', true), active: c.body.active === false ? 0 : 1, created: now(), author: ADMIN().name }; cc.announcements.push(a); saveContent(cc); audit('announcement.create', a.id, true); return { id: a.id }; });
  r('PUT', '/api/admin/announcements/:id', function (c) { var cc = content(), a = cc.announcements.filter(function (x) { return x.id == c.params.id; })[0]; if (!a) throw HttpErr(404, 'Topilmadi'); a.title = str(c.body.title, 80, 'Sarlavha', true); a.body = str(c.body.body, 500, 'Matn', true); a.active = c.body.active ? 1 : 0; saveContent(cc); audit('announcement.update', a.id, true); return {}; });
  r('DELETE', '/api/admin/announcements/:id', function (c) { var cc = content(); cc.announcements = cc.announcements.filter(function (x) { return x.id != c.params.id; }); saveContent(cc); audit('announcement.delete', c.params.id, true); return {}; });
  r('GET', '/api/admin/audit', function (c) { var page = intIn(c.q.page || 1, 1, 10000, 'page'), a = ls('local-audit', []); return { rows: a.slice((page - 1) * 30, page * 30), total: a.length, page: page, pages: Math.max(1, Math.ceil(a.length / 30)) }; });
  r('GET', '/api/admin/settings', function () { return { registrationOpen: ls('local-settings', { registrationOpen: true }).registrationOpen !== false }; });
  r('PUT', '/api/admin/settings', function (c) { sv('local-settings', { registrationOpen: !!c.body.registrationOpen }); audit('settings.update', 'registrationOpen=' + !!c.body.registrationOpen, true); return {}; });
  r('GET', '/api/admin/admins', function () { var a = ls('local-admin', {}); return { rows: [{ id: 1, name: a.name || 'Admin', role: 'super_admin', status: 'active', created_at: null, last_seen: now() }] }; });
  r('POST', '/api/admin/admins', function () { throw bad("Lokal rejimda faqat bitta administrator bo'ladi. Ko'p administrator va rollar uchun server rejimidan foydalaning."); });
  r('PUT', '/api/admin/admins/:id', function (c) {
    if (!c.body.pass) throw bad("Lokal rejimda faqat parolni almashtirish mumkin"); var p = pwProblem(c.body.pass); if (p) throw bad(p);
    var a = ls('local-admin', {}); return hash(a.name.toLowerCase() + ':' + c.body.pass).then(function (h) { a.h = h; sv('local-admin', a); audit('admin.update', a.name + ' +parol', true); return {}; });
  });

  // fetch o'rnini bosuvchi (Response'ga o'xshash obyekt qaytaradi)
  function resp(status, j) { return { ok: status < 400, status: status, json: function () { return Promise.resolve(j); }, text: function () { return Promise.resolve(JSON.stringify(j)); } }; }
  TY.localFetch = function (url, o) {
    o = o || {}; var u = new URL(url, 'http://x'), path = u.pathname, method = (o.method || 'GET').toUpperCase(), q = {}; u.searchParams.forEach(function (v, k) { q[k] = v; });
    var body = {}; try { body = o.body ? JSON.parse(o.body) : {}; } catch (e) {}
    for (var i = 0; i < R.length; i++) {
      var m = R[i].method === method && R[i].re.exec(path); if (!m) continue;
      if (!R[i].open && !session()) return Promise.resolve(resp(401, { error: 'Kirish talab qilinadi' }));
      try { return Promise.resolve(R[i].fn({ params: Object.assign({}, m.groups), q: q, body: body })).then(function (j) { return resp(200, j || {}); }, function (e) { return resp(e.status || 500, Object.assign({ error: e.message }, e.extra || {})); }); }
      catch (e) { return Promise.resolve(resp(e.status || 500, Object.assign({ error: e.message }, e.extra || {}))); }
    }
    return Promise.resolve(resp(404, { error: 'API topilmadi' }));
  };
  TY.localSetupNeeded = function () { return !ls('local-admin', null); };
  TY.LOCAL_ADMIN = true;
})(window.TY = window.TY || {});
