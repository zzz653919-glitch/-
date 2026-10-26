/* Saqlash qatlami. Hozir: brauzer localStorage (har bir foydalanuvchi uchun alohida kalit).
   Backend qo'shish uchun faqat TY.Storage adapterini (read/write/list/remove) almashtirish kifoya. */
(function (TY) {
  var SCHEMA = 2, PREFIX = 'tilyoli:';
  var MAX_HEARTS = 5, HEART_MS = 20 * 60 * 1000;

  // ---- Saqlash adapteri (localStorage; bo'lmasa xotirada) ----
  var mem = {};
  var Storage = {
    get: function (k) { try { var v = window.localStorage.getItem(PREFIX + k); return v == null ? null : v; } catch (e) { return mem[k] == null ? null : mem[k]; } },
    set: function (k, v) { try { window.localStorage.setItem(PREFIX + k, v); } catch (e) { mem[k] = v; } },
    remove: function (k) { try { window.localStorage.removeItem(PREFIX + k); } catch (e) { delete mem[k]; } }
  };
  TY.Storage = Storage;

  function today(d) { d = d || new Date(); var m = d.getMonth() + 1, day = d.getDate(); return d.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (day < 10 ? '0' : '') + day; }
  function daysBetween(a, b) { var pa = a.split('-'), pb = b.split('-'); return Math.round((Date.UTC(+pb[0], pb[1] - 1, +pb[2]) - Date.UTC(+pa[0], pa[1] - 1, +pa[2])) / 864e5); }
  function addDays(s, n) { var p = s.split('-'); return today(new Date(+p[0], p[1] - 1, +p[2] + n)); }
  TY.today = today; TY.daysBetween = daysBetween; TY.addDays = addDays;

  function newState() {
    return { v: SCHEMA, xp: 0, hearts: MAX_HEARTS, heartTs: Date.now(), streak: 0, bestStreak: 0, lastDay: null,
      goalMin: 10, theme: 'auto', sound: true, speech: true,
      done: {},            // nodeId -> {best: %, times: n, ts}
      words: {},           // wordId -> {c: to'g'ri, w: xato}
      mistakes: {},        // wordId -> {n: xatolar, ok: ketma-ket to'g'ri}
      days: {},            // 'YYYY-MM-DD' -> {xp, secs, lessons, correct, wrong}
      ach: {},             // yutuqId -> ts
      quests: {},          // 'YYYY-MM-DD' -> {claimed:true}
      history: [],         // oxirgi sessiyalar natijasi
      ieltsBest: 0 };
  }

  // Migratsiya: eski ma'lumot hech qachon o'chirilmaydi; avval zaxira nusxa olinadi.
  function migrate(s, key) {
    if (!s || typeof s !== 'object') return newState();
    var from = s.v || 1;
    if (from < SCHEMA) {
      Storage.set(key + ':backup-v' + from, JSON.stringify(s));
      var base = newState();
      Object.keys(base).forEach(function (k) { if (s[k] === undefined) s[k] = base[k]; });
      s.v = SCHEMA;
    }
    return s;
  }

  // ---- Hisoblar (lokal, xavfsizlik serversiz emas) ----
  function hash(str) {
    if (window.crypto && crypto.subtle && window.TextEncoder) {
      return crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)).then(function (b) {
        return Array.prototype.map.call(new Uint8Array(b), function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
      });
    }
    var h = 5381; for (var i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) | 0;
    return Promise.resolve('x' + (h >>> 0).toString(16));
  }
  function users() { try { return JSON.parse(Storage.get('users') || '{}'); } catch (e) { return {}; } }
  function saveUsers(u) { Storage.set('users', JSON.stringify(u)); }
  function ukey(name) { return name.trim().toLowerCase(); }

  // ---- Server rejimi: server bor bo'lsa hisoblar va progress serverda (SQLite), aks holda localStorage ----
  var Server = TY.Server = { on: false, csrf: null, timer: null, announcements: [], registrationOpen: true };
  function api(method, url, body) {
    return fetch(url, { method: method, credentials: 'same-origin', keepalive: true, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': Server.csrf || '' }, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) { var e = new Error(j.error || ('Server xatosi ' + r.status)); e.status = r.status; throw e; } return j; }); });
  }
  TY.api = api;
  Server.flush = function () {
    if (!Server.on || !Auth.state || !Server.dirty) return Promise.resolve();
    Server.dirty = false; clearTimeout(Server.timer);
    return api('PUT', 'api/state', { state: Auth.state }).catch(function (e) { Server.dirty = true; if ((e.status === 401 || e.status === 403) && TY.onAuthLost) TY.onAuthLost(e); });
  };
  Server.event = function (ev) { if (Server.on && Auth.current) api('POST', 'api/event', ev).catch(function () {}); };
  window.addEventListener('pagehide', function () { Server.flush(); });
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') Server.flush(); });
  TY.ready = (function () {
    var local = function (on) { if (!on && TY.localRows) { TY.applyContent(TY.localRows()); Server.announcements = TY.localAnnouncements(); } return on; };
    if (!window.fetch || location.protocol === 'file:') return Promise.resolve(local(false));
    return fetch('api/ping', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (p) {
      if (!p || !p.server) return local(false);
      Server.on = true; Server.registrationOpen = p.registrationOpen;
      return api('GET', 'api/content').then(function (c) { TY.applyContent(c.rows); Server.announcements = c.announcements || []; }).catch(function () {})
        .then(function () { return api('GET', 'api/me'); }).then(function (me) { Auth.openServer(me.user.name, me.state, me.csrf); }).catch(function () {}).then(function () { return true; });
    });
  })();

  var Auth = {
    current: null, state: null,
    openServer: function (name, state, csrf) {
      Server.csrf = csrf; Auth.current = { name: name }; Auth.key = 'data:' + ukey(name);
      var s = state;
      if (!s) { var raw = Storage.get(Auth.key); try { s = raw ? JSON.parse(raw) : null; } catch (e) { s = null; } }  // mavjud lokal progressni yo'qotmaslik
      Auth.state = s ? migrate(s, Auth.key) : newState(); Server.dirty = true; Game.regen(); Game.rollStreak(); Auth.save();
    },
    register: function (name, pass) {
      if (Server.on) return api('POST', 'api/register', { name: name, pass: pass }).then(function (r) { Auth.openServer(r.user.name, r.state, r.csrf); });
      name = (name || '').trim();
      if (name.length < 2) return Promise.reject(new Error("Ism kamida 2 belgi bo'lsin"));
      if (!pass || pass.length < 4) return Promise.reject(new Error("Parol kamida 4 belgi bo'lsin"));
      var lset = null; try { lset = JSON.parse(Storage.get('local-settings') || 'null'); } catch (e) {}
      if (lset && lset.registrationOpen === false) return Promise.reject(new Error("Ro'yxatdan o'tish vaqtincha yopiq"));
      var u = users(); if (u[ukey(name)]) return Promise.reject(new Error('Bu ism band'));
      return hash(ukey(name) + ':' + pass).then(function (h) { u[ukey(name)] = { name: name, h: h, created: Date.now() }; saveUsers(u); Auth.open(name); });
    },
    login: function (name, pass) {
      if (Server.on) return api('POST', 'api/login', { name: name, pass: pass }).then(function (r) { Auth.openServer(r.user.name, r.state, r.csrf); });
      var u = users()[ukey(name || '')];
      if (!u) return Promise.reject(new Error('Foydalanuvchi topilmadi'));
      if (u.disabled) return Promise.reject(new Error('Hisob bloklangan. Administratorga murojaat qiling.'));
      return hash(ukey(name) + ':' + pass).then(function (h) { if (h !== u.h) throw new Error("Parol noto'g'ri"); Auth.open(u.name); });
    },
    guest: function () { var u = users(); if (!u['mehmon']) { u['mehmon'] = { name: 'Mehmon', h: null, created: Date.now() }; saveUsers(u); } Auth.open('Mehmon'); },
    open: function (name) {
      Storage.set('session', ukey(name)); Auth.current = users()[ukey(name)];
      var key = 'data:' + ukey(name), raw = Storage.get(key), s;
      try { s = raw ? migrate(JSON.parse(raw), key) : newState(); } catch (e) { Storage.set(key + ':corrupt', raw); s = newState(); }
      Auth.state = s; Auth.key = key; Game.regen(); Game.rollStreak(); Auth.save();
    },
    restore: function () { if (Server.on) return false; var k = Storage.get('session'); if (k && users()[k] && !users()[k].disabled) { Auth.open(users()[k].name); return true; } return false; },
    logout: function () {
      if (Server.on && Auth.current) { var p = Server.flush(); p = (p || Promise.resolve()).then(function () { return api('POST', 'api/logout').catch(function () {}); }); Auth.pending = p; }
      Storage.remove('session'); Auth.current = null; Auth.state = null; Server.csrf = null;
    },
    save: function () {
      if (!Auth.state) return; Storage.set(Auth.key, JSON.stringify(Auth.state));
      if (Server.on && Auth.current) { Server.dirty = true; clearTimeout(Server.timer); Server.timer = setTimeout(Server.flush, 1200); }
    },
    exportData: function () { return JSON.stringify({ user: Auth.current && Auth.current.name, data: Auth.state }, null, 2); },
    importData: function (text) { var o = JSON.parse(text); if (!o || !o.data || typeof o.data.xp !== 'number') throw new Error("Noto'g'ri fayl"); Auth.state = migrate(o.data, Auth.key); Auth.save(); },
    resetProgress: function () { Auth.state = newState(); Auth.save(); },
    deleteAccount: function () { if (Server.on) { api('DELETE', 'api/me').catch(function () {}); Storage.remove(Auth.key); Auth.logout(); return; } var u = users(); delete u[ukey(Auth.current.name)]; saveUsers(u); Storage.remove(Auth.key); Auth.logout(); }
  };
  TY.Auth = Auth;

  // ---- O'yin mantig'i ----
  var ACH = [
    { id: 'first', icon: '🌱', t: 'Birinchi qadam', d: 'Birinchi darsni tugating', f: function (s) { return Object.keys(s.done).length >= 1; } },
    { id: 'xp100', icon: '⭐', t: '100 XP', d: '100 XP to\'plang', f: function (s) { return s.xp >= 100; } },
    { id: 'xp500', icon: '🌟', t: '500 XP', d: '500 XP to\'plang', f: function (s) { return s.xp >= 500; } },
    { id: 'xp2000', icon: '💫', t: '2000 XP', d: '2000 XP to\'plang', f: function (s) { return s.xp >= 2000; } },
    { id: 'streak3', icon: '🔥', t: '3 kunlik seriya', d: 'Ketma-ket 3 kun shug\'ullaning', f: function (s) { return s.bestStreak >= 3; } },
    { id: 'streak7', icon: '🚀', t: '7 kunlik seriya', d: 'Ketma-ket 7 kun', f: function (s) { return s.bestStreak >= 7; } },
    { id: 'streak30', icon: '👑', t: '30 kunlik seriya', d: 'Ketma-ket 30 kun', f: function (s) { return s.bestStreak >= 30; } },
    { id: 'perfect', icon: '💎', t: 'Mukammal dars', d: 'Darsni bitta ham xatosiz tugating', f: function (s) { return Object.keys(s.done).some(function (k) { return s.done[k].best === 100; }); } },
    { id: 'correct100', icon: '🎯', t: '100 ta to\'g\'ri javob', d: '100 ta to\'g\'ri javob bering', f: function (s) { return Game.totalCorrect(s) >= 100; } },
    { id: 'words50', icon: '📖', t: '50 ta so\'z', d: '50 ta so\'zni o\'rganing', f: function (s) { return Game.learnedCount(s) >= 50; } },
    { id: 'words100', icon: '📚', t: '100 ta so\'z', d: '100 ta so\'zni o\'rganing', f: function (s) { return Game.learnedCount(s) >= 100; } },
    { id: 'goal', icon: '⏱️', t: 'Kunlik maqsad', d: 'Kunlik maqsadni bajaring', f: function (s) { return Object.keys(s.days).some(function (d) { return s.days[d].secs >= s.goalMin * 60; }); } },
    { id: 'test', icon: '🏆', t: 'Sinovdan o\'tdi', d: 'Biror daraja sinovidan o\'ting', f: function (s) { return Object.keys(s.done).some(function (k) { return /X$/.test(k); }); } },
    { id: 'A1', icon: '🥉', t: 'A1 tugadi', d: 'A1 sinovidan o\'ting', f: function (s) { return !!s.done.L0X; } },
    { id: 'IELTS', icon: '🎓', t: 'IELTS yo\'li', d: 'IELTS sinovidan o\'ting', f: function (s) { return !!s.done.L5X; } },
    { id: 'fixer', icon: '🛠️', t: 'Xatolar ustasi', d: 'Xato qilingan so\'zni qayta to\'g\'ri toping', f: function (s) { return Object.keys(s.words).some(function (k) { return s.words[k].w > 0 && s.mistakes[k] == null; }); } }
  ];
  TY.ACHIEVEMENTS = ACH;

  function S() { return Auth.state; }
  function day(d) { var s = S(); d = d || today(); return s.days[d] || (s.days[d] = { xp: 0, secs: 0, lessons: 0, correct: 0, wrong: 0 }); }

  var Game = {
    MAX_HEARTS: MAX_HEARTS, HEART_MS: HEART_MS,
    levelOf: function (xp) { return Math.floor(Math.sqrt(xp / 50)) + 1; },
    levelBounds: function (xp) { var l = Game.levelOf(xp); return { lvl: l, from: 50 * (l - 1) * (l - 1), to: 50 * l * l }; },
    // Yurakcha tiklanishi: har 20 daqiqada +1 (vaqt bo'yicha, oynada ochiq bo'lmasa ham)
    regen: function () {
      var s = S(); if (!s) return;
      if (s.hearts >= MAX_HEARTS) { s.hearts = MAX_HEARTS; s.heartTs = Date.now(); return; }
      var n = Math.floor((Date.now() - s.heartTs) / HEART_MS);
      if (n > 0) { s.hearts = Math.min(MAX_HEARTS, s.hearts + n); s.heartTs = s.hearts >= MAX_HEARTS ? Date.now() : s.heartTs + n * HEART_MS; }
    },
    nextHeartMs: function () { var s = S(); if (s.hearts >= MAX_HEARTS) return 0; return Math.max(0, HEART_MS - (Date.now() - s.heartTs)); },
    loseHeart: function () { var s = S(); if (s.hearts >= MAX_HEARTS) s.heartTs = Date.now(); s.hearts = Math.max(0, s.hearts - 1); Auth.save(); },
    gainHeart: function () { var s = S(); if (s.hearts < MAX_HEARTS) { s.hearts++; if (s.hearts >= MAX_HEARTS) s.heartTs = Date.now(); Auth.save(); return true; } return false; },
    // Seriya faqat haqiqiy kalendar kunlari va tugatilgan dars/sinov/takrorlash bo'yicha
    rollStreak: function () {
      var s = S(); if (!s || !s.lastDay) return;
      if (daysBetween(s.lastDay, today()) > 1) s.streak = 0;   // kun o'tkazib yuborilgan
    },
    streakNow: function () { var s = S(); if (!s.lastDay) return 0; return daysBetween(s.lastDay, today()) > 1 ? 0 : s.streak; },
    markActiveDay: function () {
      var s = S(), t = today();
      if (s.lastDay === t) return;
      if (s.lastDay && daysBetween(s.lastDay, t) === 1) s.streak++; else s.streak = 1;
      s.lastDay = t; s.bestStreak = Math.max(s.bestStreak, s.streak);
    },
    addXP: function (n) { var s = S(); s.xp += n; day().xp += n; },
    addTime: function (secs) { day().secs += Math.max(0, Math.min(secs, 90)); },
    recordAnswer: function (wordId, ok) {
      var s = S(), w = s.words[wordId] || (s.words[wordId] = { c: 0, w: 0 }), d = day();
      if (ok) {
        w.c++; d.correct++;
        var m = s.mistakes[wordId]; if (m) { m.ok++; if (m.ok >= 2) delete s.mistakes[wordId]; }
      } else {
        w.w++; d.wrong++;
        var mm = s.mistakes[wordId] || (s.mistakes[wordId] = { n: 0, ok: 0 }); mm.n++; mm.ok = 0;
      }
    },
    totalCorrect: function (s) { return Object.keys(s.days).reduce(function (a, k) { return a + s.days[k].correct; }, 0); },
    learnedCount: function (s) {
      var n = 0; TY.LEVELS.forEach(function (lv) { lv.topics.forEach(function (tp) { if (s.done[tp.id]) n += tp.words.length; }); }); return n;
    },
    isDone: function (id) { return !!S().done[id]; },
    // Qulf: oldingi tugun tugatilgan bo'lishi kerak
    isUnlocked: function (id) { var n = TY.nodeById[id]; return n.order === 0 || !!S().done[TY.NODES[n.order - 1].id]; },
    currentNode: function () { for (var i = 0; i < TY.NODES.length; i++) if (!S().done[TY.NODES[i].id]) return TY.NODES[i]; return null; },
    completeNode: function (id, pct, xp, secs) {
      var s = S(), first = !s.done[id], r = s.done[id] || { best: 0, times: 0 };
      r.best = Math.max(r.best, pct); r.times++; r.ts = Date.now(); s.done[id] = r;
      day().lessons++; Game.markActiveDay(); Game.addXP(xp);
      if (/X$/.test(id) && id === 'L5X') s.ieltsBest = Math.max(s.ieltsBest, pct);
      Game.gainHeart();
      var added = Game.checkAchievements(); Auth.save();
      return { first: first, ach: added };
    },
    completePractice: function (xp) {
      day().lessons++; Game.markActiveDay(); Game.addXP(xp); Game.gainHeart();
      var added = Game.checkAchievements(); Auth.save(); return { ach: added };
    },
    checkAchievements: function () {
      var s = S(), added = [];
      ACH.forEach(function (a) { if (!s.ach[a.id] && a.f(s)) { s.ach[a.id] = Date.now(); added.push(a); } });
      return added;
    },
    // Kunlik topshiriqlar: bugungi haqiqiy statistikadan hisoblanadi
    quests: function () {
      var d = day(), s = S();
      return [
        { id: 'q1', icon: '📘', t: 'Bitta dars yoki takrorlashni tugating', cur: d.lessons, goal: 1, xp: 10 },
        { id: 'q2', icon: '🎯', t: '15 ta to\'g\'ri javob bering', cur: d.correct, goal: 15, xp: 15 },
        { id: 'q3', icon: '⚡', t: '40 XP to\'plang', cur: d.xp, goal: 40, xp: 20 },
        { id: 'q4', icon: '⏱️', t: 'Kunlik maqsad: ' + s.goalMin + ' daqiqa', cur: Math.floor(d.secs / 60), goal: s.goalMin, xp: 25 }
      ];
    },
    claimQuests: function () {
      var s = S(), t = today(), q = s.quests[t] || (s.quests[t] = { claimed: {} });
      var gain = 0;
      Game.quests().forEach(function (x) { if (x.cur >= x.goal && !q.claimed[x.id]) { q.claimed[x.id] = 1; gain += x.xp; } });
      if (gain) { Game.addXP(gain); Game.checkAchievements(); Auth.save(); }
      return gain;
    },
    questClaimed: function (id) { var q = S().quests[today()]; return !!(q && q.claimed && q.claimed[id]); }
  };
  TY.Game = Game;
})(window.TY = window.TY || {});
