/* Lug'at sessiyalari: ma'lumotlar modeli va saqlash.
   MUHIM: har bir sessiya o'z so'zlari, progressi, urinishlari va "run" holatini ICHIDA saqlaydi.
   Global so'z ombori YO'Q: hamma funksiya aniq sessionId oladi va faqat shu sessiyaga tegadi. */
(function (V) {
  'use strict';
  var KEY = 'vocab:v1', SCHEMA = 1, DAY = 864e5;
  var mem = {}, db = null;
  var LS = {
    get: function (k) { try { var v = localStorage.getItem(k); return v == null ? null : v; } catch (e) { return mem[k] == null ? null : mem[k]; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { mem[k] = v; } },
    remove: function (k) { try { localStorage.removeItem(k); } catch (e) { delete mem[k]; } },
    keys: function () { var o = []; try { for (var i = 0; i < localStorage.length; i++) o.push(localStorage.key(i)); } catch (e) { o = Object.keys(mem); } return o; }
  };
  V.LS = LS; V.DAY = DAY;
  V.MASTER_BOX = 4;                                  // box >= 4 → "o'zlashtirilgan"
  V.INTERVALS = [0, 1, 2, 4, 8, 16];                 // kunlarda: qutiga qarab keyingi takrorlash
  function uid(p) { return p + '_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
  V.uid = uid;

  function fresh() { return { schema: SCHEMA, created: Date.now(), activeId: null, sessions: {}, settings: { theme: 'auto', sound: true, speech: true }, migrations: [] }; }
  function migrate(o) {
    if (!o || typeof o !== 'object' || !o.sessions) return fresh();
    var from = o.schema || 0;
    if (from < SCHEMA) {   // sxema yangilanishidan oldin zaxira nusxa
      LS.set(KEY + ':backup-v' + from + '-' + Date.now(), JSON.stringify(o));
      var f = fresh(); Object.keys(f).forEach(function (k) { if (o[k] === undefined) o[k] = f[k]; }); o.schema = SCHEMA;
    }
    return o;
  }
  V.load = function () {
    var raw = LS.get(KEY);
    try { db = raw ? migrate(JSON.parse(raw)) : fresh(); }
    catch (e) { LS.set(KEY + ':corrupt-' + Date.now(), raw); db = fresh(); }   // buzilgan ma'lumot o'chirilmaydi
    return db;
  };
  V.db = function () { return db || V.load(); };
  V.save = function () { if (!db) return; db.savedAt = Date.now(); var j = JSON.stringify(db); LS.set(KEY, j); V.mirror(j); };

  // ---- IndexedDB nusxasi ----
  // Sabab: ba'zi brauzerlar (Chromium) juda tez-tez yoziladigan localStorage'ni diskka darhol o'tkazmaydi va sahifa
  // yangilanganda eng oxirgi yozuvlar yo'qolishi mumkin. IndexedDB'dagi nusxa bilan yuklashda eng yangisi tanlanadi.
  var IDBN = 'vocab-store', pending = null, timer = null;
  function idb() {
    return new Promise(function (res, rej) {
      if (typeof indexedDB === 'undefined') return rej(new Error('no idb'));
      var r = indexedDB.open(IDBN, 1); r.onupgradeneeded = function () { r.result.createObjectStore('kv'); }; r.onsuccess = function () { res(r.result); }; r.onerror = function () { rej(r.error); };
    });
  }
  function idbPut(json) { return idb().then(function (d) { return new Promise(function (res) { var tx = d.transaction('kv', 'readwrite'); tx.objectStore('kv').put({ json: json, at: Date.now() }, KEY); tx.oncomplete = function () { d.close(); res(); }; tx.onerror = tx.onabort = function () { d.close(); res(); }; }); }).catch(function () {}); }
  V.mirror = function (json) { pending = json; if (timer || typeof indexedDB === 'undefined') return; timer = setTimeout(V.flushMirror, 0); };
  V.flushMirror = function () { clearTimeout(timer); timer = null; if (pending == null) return Promise.resolve(); var j = pending; pending = null; return idbPut(j); };
  V.restore = function () {   // brauzerda ishga tushirishdan oldin chaqiriladi: IndexedDB nusxasi yangiroq bo'lsa localStorage'ga tiklaydi
    return idb().then(function (d) { return new Promise(function (res) { var g = d.transaction('kv').objectStore('kv').get(KEY); g.onsuccess = function () { d.close(); res(g.result); }; g.onerror = function () { d.close(); res(null); }; }); }).then(function (rec) {
      if (!rec || !rec.json) return false;
      var cur = LS.get(KEY), curAt = 0; try { curAt = cur ? (JSON.parse(cur).savedAt || 0) : 0; } catch (e) {}
      var idbAt = 0; try { idbAt = JSON.parse(rec.json).savedAt || 0; } catch (e) { return false; }
      if (idbAt > curAt) { LS.set(KEY, rec.json); db = null; return true; }
      return false;
    }).catch(function () { return false; });
  };
  if (typeof window !== 'undefined' && window.addEventListener) {
    var fl = function () { if (db) { var j = JSON.stringify(db); LS.set(KEY, j); pending = j; V.flushMirror(); } };
    window.addEventListener('pagehide', fl); document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') fl(); });
  }
  V.reload = function () { db = null; return V.load(); };   // "sahifa yangilanishi"ni taqlid qiladi: faqat saqlangan narsa qoladi

  function need(sid) { var s = V.db().sessions[sid]; if (!s) throw new Error('Sessiya topilmadi: ' + sid); return s; }
  V.session = need;
  V.list = function () { return Object.keys(V.db().sessions).map(function (k) { return V.db().sessions[k]; }); };

  function cleanName(n) { n = String(n == null ? '' : n).replace(/\s+/g, ' ').trim(); if (!n) throw new Error('Sessiya nomini kiriting'); if (n.length > 60) throw new Error('Nom juda uzun (maks. 60)'); return n; }
  V.createSession = function (name, opts) {
    opts = opts || {}; var id = uid('s'), now = Date.now();
    V.db().sessions[id] = { id: id, name: cleanName(name), lang: opts.lang || "O'zbekcha", status: 'active', createdAt: now, updatedAt: now, lastActivity: null, rounds: 0, words: {}, order: [], progress: {}, attempts: [], run: null, lastSummary: null, migratedFrom: opts.migratedFrom || null };
    V.db().activeId = id; V.save(); return id;
  };
  V.renameSession = function (sid, name) { var s = need(sid); s.name = cleanName(name); s.updatedAt = Date.now(); V.save(); };
  V.setStatus = function (sid, st) { var s = need(sid); if (['active', 'paused'].indexOf(st) < 0) throw new Error('status'); s.status = st; if (st === 'paused') s.updatedAt = Date.now(); V.save(); };
  V.deleteSession = function (sid) { need(sid); delete V.db().sessions[sid]; if (V.db().activeId === sid) V.db().activeId = null; V.save(); };
  V.restartSession = function (sid) {   // so'zlar qoladi, progress va urinishlar tozalanadi
    var s = need(sid); s.progress = {}; s.attempts = []; s.run = null; s.rounds = 0; s.lastSummary = null; s.lastActivity = null; s.updatedAt = Date.now(); V.save();
  };
  V.setActive = function (sid) { if (sid != null) need(sid); V.db().activeId = sid; V.save(); };
  V.activeId = function () { var id = V.db().activeId; return id && V.db().sessions[id] ? id : null; };

  // ---- So'zlar (faqat berilgan sessiya ichida) ----
  function cleanTr(tr) {
    var a = Array.isArray(tr) ? tr : String(tr || '').split(/[;]/);
    return a.map(function (x) { return String(x).replace(/\s+/g, ' ').trim(); }).filter(Boolean);
  }
  function mkWord(w) {
    var en = String(w.en || '').replace(/\s+/g, ' ').trim(), tr = cleanTr(w.tr);
    if (!en) throw new Error("Inglizcha so'zni kiriting"); if (!tr.length) throw new Error('Tarjimani kiriting');
    if (en.length > 80 || tr.join(';').length > 200) throw new Error("So'z yoki tarjima juda uzun");
    return { id: uid('w'), en: en, tr: tr, example: String(w.example || '').trim().slice(0, 200), exampleTr: String(w.exampleTr || '').trim().slice(0, 200), pron: String(w.pron || '').trim().slice(0, 60), variants: cleanTr(w.variants), emoji: String(w.emoji || '').slice(0, 8), createdAt: Date.now() };
  }
  V.addWord = function (sid, w) { var s = need(sid), x = mkWord(w); s.words[x.id] = x; s.order.push(x.id); s.updatedAt = Date.now(); V.save(); return x.id; };
  V.updateWord = function (sid, wid, patch) {
    var s = need(sid), w = s.words[wid]; if (!w) throw new Error("So'z topilmadi");
    var n = mkWord(Object.assign({}, w, patch)); n.id = w.id; n.createdAt = w.createdAt; s.words[wid] = n; s.updatedAt = Date.now(); V.save();
  };
  V.deleteWord = function (sid, wid) {
    var s = need(sid); if (!s.words[wid]) throw new Error("So'z topilmadi");
    delete s.words[wid]; delete s.progress[wid]; s.order = s.order.filter(function (x) { return x !== wid; });
    if (s.run) { s.run = null; }   // yaroqsiz bo'lib qolgan davom etayotgan raund bekor qilinadi (saqlangan progress qoladi)
    s.updatedAt = Date.now(); V.save();
  };
  V.words = function (sid) { var s = need(sid); return s.order.map(function (id) { return s.words[id]; }); };
  V.prog = function (s, wid) { return s.progress[wid] || { box: 0, seen: 0, correct: 0, wrong: 0, streak: 0, fix: 0, due: null, last: null, mistake: false }; };

  // ---- Sessiya statistikasi (faqat shu sessiya) ----
  V.stats = function (sid, now) {
    var s = need(sid), t = now || Date.now(), r = { total: s.order.length, fresh: 0, learning: 0, mastered: 0, mistakes: 0, correct: 0, wrong: 0, accuracy: null, dueNow: 0, nextDue: null, rounds: s.rounds, lastActivity: s.lastActivity };
    s.order.forEach(function (id) {
      var p = V.prog(s, id);
      if (!p.seen) r.fresh++; else if (p.box >= V.MASTER_BOX) r.mastered++; else r.learning++;
      if (p.mistake) r.mistakes++;
      r.correct += p.correct; r.wrong += p.wrong;
      if (p.seen) { if (p.due != null && p.due <= t) r.dueNow++; else if (p.due != null && (r.nextDue == null || p.due < r.nextDue)) r.nextDue = p.due; }
    });
    if (r.correct + r.wrong) r.accuracy = Math.round(100 * r.correct / (r.correct + r.wrong));
    r.percent = r.total ? Math.round(100 * r.mastered / r.total) : 0;
    return r;
  };

  // ---- Eski "Til Yo'li" kursidan migratsiya (eski ma'lumot O'QILADI, hech qachon o'zgartirilmaydi/o'chirilmaydi) ----
  V.migrateLegacy = function () {
    var out = { found: 0, sessions: [], words: 0, skipped: 0 };
    var legacy = (typeof window !== 'undefined' ? window.LEGACY_WORDS : globalThis.LEGACY_WORDS) || {}, custom = null;
    try { custom = JSON.parse(LS.get('tilyoli:local-content') || 'null'); } catch (e) {}
    var extra = {}; if (custom && custom.words) custom.words.forEach(function (w) { extra[w.id] = [w.en, (w.uz || []).join('; '), w.sent, w.sentUz, w.emoji]; });
    LS.keys().forEach(function (k) {
      var m = /^tilyoli:data:(.+)$/.exec(k); if (!m || /:backup|:corrupt/.test(k)) return;
      var st; try { st = JSON.parse(LS.get(k)); } catch (e) { return; }
      if (!st || !st.words) return; out.found++;
      var tag = 'tilyoli:' + m[1]; if (V.list().some(function (s) { return s.migratedFrom === tag; })) { out.skipped++; return; }
      var ids = Object.keys(st.words).filter(function (id) { var p = st.words[id]; return p && (p.c || p.w) && (legacy[id] || extra[id]); });
      if (!ids.length) return;
      var sid = V.createSession("Til Yo'li kursidan (" + m[1] + ')', { migratedFrom: tag }), s = V.session(sid), now = Date.now();
      ids.forEach(function (id) {
        var d = legacy[id] || extra[id], p = st.words[id], wid = V.addWord(sid, { en: d[0], tr: d[1], example: d[2], exampleTr: d[3], emoji: d[4] });
        var c = p.c || 0, w = p.w || 0, mis = !!(st.mistakes && st.mistakes[id]);
        s.progress[wid] = { box: c >= 4 ? 3 : c >= 2 ? 2 : c >= 1 ? 1 : 0, seen: c + w, correct: c, wrong: w, streak: 0, fix: 0, due: now, last: now, mistake: mis };
      });
      V.db().migrations.push({ id: 'legacy-' + tag, time: now, from: tag, sessionId: sid, words: ids.length });
      out.sessions.push({ id: sid, name: V.session(sid).name, words: ids.length }); out.words += ids.length;
    });
    if (out.sessions.length) V.save();
    return out;
  };
  V.runInitialMigration = function () {
    var d = V.db(); if (d.migrations.some(function (m) { return m.id === 'initial-check'; })) return null;
    var r = V.migrateLegacy(); d.migrations.push({ id: 'initial-check', time: Date.now(), result: r }); V.save(); return r;
  };

  // ---- Zaxira nusxa (eksport/import) ----
  V.exportJSON = function () { return JSON.stringify(V.db(), null, 2); };
  V.importJSON = function (text) {
    var o = JSON.parse(text); if (!o || !o.sessions || typeof o.sessions !== 'object') throw new Error("Fayl noto'g'ri");
    LS.set(KEY + ':backup-before-import-' + Date.now(), JSON.stringify(V.db()));   // joriy ma'lumot avval zaxiraga olinadi
    db = migrate(o); V.save();
  };
})(typeof window !== 'undefined' ? (window.V = window.V || {}) : (globalThis.V = globalThis.V || {}));
