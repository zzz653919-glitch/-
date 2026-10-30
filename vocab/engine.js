/* Mashqlar mexanikasi. HAR BIR funksiya aniq sessionId oladi va FAQAT shu sessiyaning so'zlarini ishlatadi.
   (Global so'z ombori yo'q; distraktorlar ham, takrorlash ham, test ham shu sessiyadan.) */
(function (V) {
  'use strict';
  var DAY = V.DAY;
  function shuffle(a) { a = a.slice(); for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  V.shuffle = shuffle;

  // ================= Javobni tekshirish =================
  // Katta-kichik harf, ortiqcha bo'shliq va barcha apostrof turlari farq qilmaydi; "o'" "oʻ" "o‘" bir xil.
  function norm(s) {
    return String(s == null ? '' : s).normalize('NFKC').toLowerCase().replace(/[‘’ʻʼʹ`´′]/g, "'").replace(/[.!?,;:]+$/g, '').replace(/\s+/g, ' ').trim();
  }
  V.norm = norm;
  // Tarjima variantlari: "ta'mirlamoq (qilmoq)" → ["ta'mirlamoq (qilmoq)", "ta'mirlamoq", "ta'mirlamoq qilmoq"]
  function trForms(t) {
    var out = [t], m = /^(.*?)\s*\(([^)]*)\)\s*(.*)$/.exec(t);
    if (m) { out.push((m[1] + ' ' + m[3]).trim()); out.push((m[1] + ' ' + m[2] + ' ' + m[3]).replace(/\s+/g, ' ').trim()); }
    return out;
  }
  V.acceptedTr = function (w) { var a = []; w.tr.forEach(function (t) { trForms(t).forEach(function (x) { a.push(norm(x)); }); }); return a; };
  // Aniq sozlangan imlo variantlari + ingliz/amerika farqlari (colour/color, realise/realize, centre/center)
  function enVariants(en) {
    var base = norm(en), out = [base];
    var rules = [[/our\b/g, 'or'], [/or\b/g, 'our'], [/ise\b/g, 'ize'], [/ize\b/g, 'ise'], [/yse\b/g, 'yze'], [/yze\b/g, 'yse'], [/tre\b/g, 'ter'], [/ter\b/g, 'tre']];
    rules.forEach(function (r) { if (r[0].test(base)) out.push(base.replace(r[0], r[1])); r[0].lastIndex = 0; });
    return out;
  }
  V.acceptedEn = function (w) { var a = enVariants(w.en); (w.variants || []).forEach(function (v) { a.push(norm(v)); }); return a; };
  function dist1(a, b) {   // faqat "deyarli" maslahati uchun; javobni to'g'ri QILMAYDI
    if (Math.abs(a.length - b.length) > 1) return false; var i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    if (a.length === b.length) return a.slice(i + 1) === b.slice(i + 1) || (a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2));
    return a.length > b.length ? a.slice(i + 1) === b.slice(i) : b.slice(i + 1) === a.slice(i);
  }
  V.checkText = function (input, accepted) {
    var n = norm(input); if (!n) return { ok: false, empty: true };
    if (accepted.indexOf(n) >= 0) return { ok: true };
    return { ok: false, close: accepted.some(function (a) { return dist1(n, a); }) };
  };

  // ================= Import =================
  var HEADER = /^(english|inglizcha|word|so'z|soz)\b.*\b(translation|tarjima|meaning|ma'no)\b/i;
  var DELIMS = ['\t', '|', ' = ', '=', ' - ', ' – ', ' — ', ' : ', ';', ','];
  V.parseImport = function (text) {
    var rows = [];
    String(text || '').split(/\r?\n/).forEach(function (raw, i) {
      var line = raw.trim(); if (!line || HEADER.test(line)) return;
      var d = null; for (var k = 0; k < DELIMS.length; k++) if (line.indexOf(DELIMS[k]) > 0) { d = DELIMS[k]; break; }
      if (!d) { rows.push({ line: i + 1, raw: line, error: 'Ajratuvchi topilmadi (tab, |, =, -, ; yoki ,)' }); return; }
      var cols = (d === '\t' || d === '|') ? line.split(d).map(function (x) { return x.trim(); }) : (function () { var p = line.indexOf(d); return [line.slice(0, p).trim(), line.slice(p + d.length).trim()]; })();
      var en = cols[0], tr = (cols[1] || '').split(/[;,]/).map(function (x) { return x.trim(); }).filter(Boolean);
      if (!en) rows.push({ line: i + 1, raw: line, error: "Inglizcha so'z yo'q" });
      else if (!tr.length) rows.push({ line: i + 1, raw: line, error: "Tarjima yo'q" });
      else if (en.length > 80) rows.push({ line: i + 1, raw: line, error: "So'z juda uzun" });
      else rows.push({ line: i + 1, en: en, tr: tr, example: cols[2] || '', exampleTr: '', pron: cols[3] || '' });
    });
    return rows;
  };
  // Takrorlar FAQAT shu sessiya ichida aniqlanadi. mode: report (hech narsa qo'shmaydi) | skip | allow | update
  V.importInto = function (sid, text, mode, dry) {
    var s = V.session(sid), rows = V.parseImport(text), res = { added: [], duplicates: [], updated: [], invalid: [], applied: false };
    var byEn = {}; s.order.forEach(function (id) { byEn[norm(s.words[id].en)] = id; });
    var seen = {}, plan = [];
    rows.forEach(function (r) {
      if (r.error) { res.invalid.push({ line: r.line, raw: r.raw, error: r.error }); return; }
      var k = norm(r.en), dup = byEn[k] || seen[k];
      if (dup) { res.duplicates.push({ line: r.line, en: r.en }); if (mode === 'skip') return; if (mode === 'update' && byEn[k]) { plan.push({ upd: byEn[k], r: r }); return; } if (mode !== 'allow') return; }
      seen[k] = 1; plan.push({ r: r });
    });
    res.toAdd = plan.filter(function (p) { return !p.upd; }).length; res.toUpdate = plan.filter(function (p) { return p.upd; }).length;
    if (dry || (!mode || mode === 'report') && res.duplicates.length) return res;
    plan.forEach(function (p) {
      try { if (p.upd) { V.updateWord(sid, p.upd, { tr: p.r.tr, example: p.r.example || s.words[p.upd].example, pron: p.r.pron || s.words[p.upd].pron }); res.updated.push(p.r.en); } else { V.addWord(sid, p.r); res.added.push(p.r.en); } }
      catch (e) { res.invalid.push({ line: p.r.line, raw: p.r.en, error: e.message }); }
    });
    res.applied = true; return res;
  };
  V.previewImport = function (sid, text) { return V.importInto(sid, text, 'report', true); };

  // ================= Savollar =================
  function W(s, id) { return s.words[id]; }
  function distractors(s, w, key, n) {
    var bad = key === 'tr' ? V.acceptedTr(w) : V.acceptedEn(w), seen = {}, out = [];
    shuffle(s.order.filter(function (id) { return id !== w.id; })).forEach(function (id) {
      var o = W(s, id); if (out.length >= n) return;
      var acc = key === 'tr' ? V.acceptedTr(o) : V.acceptedEn(o);
      if (key === 'en' && V.acceptedTr(o).some(function (x) { return V.acceptedTr(w).indexOf(x) >= 0; })) return;   // bir xil tarjimali so'z "ikkinchi to'g'ri javob" bo'lmasin
      if (acc.some(function (x) { return bad.indexOf(x) >= 0; })) return;
      var disp = key === 'tr' ? o.tr[0] : o.en, nk = norm(disp); if (seen[nk]) return; seen[nk] = 1; out.push(disp);
    });
    return out;
  }
  var MK = {
    study: function (s, w) { return { type: 'study', w: w.id }; },
    flash: function (s, w) { var rev = Math.random() < 0.5; return { type: 'flash', w: w.id, dir: rev ? 'tr-en' : 'en-tr' }; },
    mc_en_tr: function (s, w) { var d = distractors(s, w, 'tr', 3); if (!d.length) return null; return { type: 'mc', dir: 'en-tr', w: w.id, options: shuffle([w.tr[0]].concat(d)) }; },
    mc_tr_en: function (s, w) { var d = distractors(s, w, 'en', 3); if (!d.length) return null; return { type: 'mc', dir: 'tr-en', w: w.id, options: shuffle([w.en].concat(d)) }; },
    type_en_tr: function (s, w) { return { type: 'type', dir: 'en-tr', w: w.id }; },
    type_tr_en: function (s, w) { return { type: 'type', dir: 'tr-en', w: w.id }; },
    spell: function (s, w) { return { type: 'spell', w: w.id, pattern: w.en.replace(/[A-Za-z]/g, '_ ').replace(/ +/g, ' ').trim() }; },
    scramble: function (s, w) {
      var L = w.en.replace(/[^A-Za-z]/g, '').split(''); if (L.length < 3 || /\s/.test(w.en.trim()) || new Set(L.join('').toLowerCase()).size < 2) return null;
      var x, n = 0; do { x = shuffle(L); n++; } while (x.join('') === L.join('') && n < 12); return { type: 'scramble', w: w.id, letters: x };
    }
  };
  var EASY = ['mc_en_tr', 'mc_tr_en', 'flash'], MID = ['type_en_tr', 'mc_tr_en', 'spell'], HARD = ['type_tr_en', 'spell', 'scramble', 'type_en_tr'];
  function make(s, kinds, w, avoid) {
    var order = shuffle(kinds); if (avoid) order.sort(function (a, b) { return (a === avoid) - (b === avoid); });
    for (var i = 0; i < order.length; i++) { var q = MK[order[i]](s, w); if (q) { q.kind = order[i]; return q; } }
    return MK.type_en_tr(s, w) && Object.assign(MK.type_en_tr(s, w), { kind: 'type_en_tr' });   // zaxira: yozma mashq (har doim mumkin)
  }
  function matchQ(s, ids) {
    var seen = {}, ws = [];
    ids.forEach(function (id) { var k = norm(W(s, id).tr[0]); if (!seen[k]) { seen[k] = 1; ws.push(id); } });
    ws = ws.slice(0, 5); if (ws.length < 2) return null;
    return { type: 'match', kind: 'match', ws: ws, left: shuffle(ws.map(function (id) { return { id: id, t: W(s, id).en }; })), right: shuffle(ws.map(function (id) { return { id: id, t: W(s, id).tr[0] }; })) };
  }
  function tier(p) { return p.box >= 3 ? HARD : p.box >= 1 ? MID : EASY; }

  // ================= Raund tuzish =================
  function select(s, mode, now) {
    var ids = s.order.slice(), P = function (id) { return V.prog(s, id); };
    if (mode === 'mistakes') return ids.filter(function (id) { return P(id).mistake; });
    if (mode === 'review') return ids.filter(function (id) { var p = P(id); return p.seen && (p.mistake || (p.due != null && p.due <= now)); }).sort(function (a, b) { return (P(a).due || 0) - (P(b).due || 0); });
    if (mode === 'test') return shuffle(ids).slice(0, 30);
    // learn: avval muddati kelganlar, keyin yangilar (5 tagacha), keyin eng past qutidagilar
    var due = ids.filter(function (id) { var p = P(id); return p.seen && p.due != null && p.due <= now; }), fresh = ids.filter(function (id) { return !P(id).seen; }), rest = ids.filter(function (id) { var p = P(id); return p.seen && (p.due == null || p.due > now); }).sort(function (a, b) { return P(a).box - P(b).box; });
    var pick = due.slice(0, 6).concat(fresh.slice(0, 5)); if (pick.length < 8) pick = pick.concat(rest.slice(0, 8 - pick.length));
    return pick.slice(0, 11);
  }
  V.select = select;

  V.startRun = function (sid, mode, opts) {
    opts = opts || {}; var s = V.session(sid), now = Date.now();
    if (!s.order.length) return { error: 'empty', message: "Bu sessiyada hali so'z yo'q. Avval so'z qo'shing yoki import qiling." };
    if (s.status === 'paused') return { error: 'paused', message: 'Sessiya to\'xtatilgan. Davom ettiring.' };
    if (s.run && !opts.fresh && s.run.mode === mode && s.run.i < s.run.queue.length) { V.setActive(sid); return { ok: true, run: s.run, resumed: true }; }
    var ids = select(s, mode, now);
    if (!ids.length) return { error: 'nothing', message: mode === 'mistakes' ? "Bu sessiyada xato so'zlar yo'q." : mode === 'review' ? "Hozir takrorlash uchun so'z yo'q." : "So'z yo'q." };
    var queue = [], P = function (id) { return V.prog(s, id); };
    if (mode === 'learn') {
      ids.filter(function (id) { return !P(id).seen; }).forEach(function (id) { queue.push(Object.assign(MK.study(s, W(s, id)), { kind: 'study' })); });
      var a = ids.map(function (id) { return make(s, EASY, W(s, id)); }), m = matchQ(s, shuffle(ids)), b = ids.map(function (id) { return make(s, tier(P(id)).concat(MID), W(s, id)); });
      queue = queue.concat(shuffle(a), m ? [m] : [], shuffle(b));
    } else if (mode === 'test') {
      var kinds = ['mc_en_tr', 'mc_tr_en', 'type_tr_en', 'type_en_tr', 'scramble', 'spell'];
      queue = ids.map(function (id) { return make(s, kinds, W(s, id)); });
    } else {   // review | mistakes
      queue = ids.map(function (id) { return make(s, tier(P(id)).concat(EASY), W(s, id)); });
      var m2 = ids.length >= 2 ? matchQ(s, ids) : null; if (m2) queue.splice(Math.min(3, queue.length), 0, m2);
    }
    queue = queue.filter(Boolean).map(function (q, i) { q.sid = sid; q.n = i; return q; });
    var baseBox = {}; ids.forEach(function (id) { baseBox[id] = P(id).box; });
    s.run = { id: V.uid('r'), sid: sid, mode: mode, queue: queue, i: 0, startedAt: now, firstTry: 0, answered: 0, wrong: {}, right: {}, outcome: {}, baseBox: baseBox, words: ids, studied: {} };
    V.setActive(sid); V.save(); return { ok: true, run: s.run };
  };

  // Har bir savol aniq shu sessiyaga tegishli ekanini tekshiradi (aks holda xato — jimgina boshqa so'z aralashmaydi)
  V.assertQuestion = function (sid, q) {
    var s = V.session(sid); if (q.sid !== sid) throw new Error('Savol boshqa sessiyaga tegishli');
    var ids = q.ws || (q.w ? [q.w] : []); ids.forEach(function (id) { if (!s.words[id]) throw new Error("Savoldagi so'z bu sessiyaga tegishli emas"); });
    var set = {}; s.order.forEach(function (id) { var w = s.words[id]; set[norm(w.en)] = 1; w.tr.forEach(function (t) { trForms(t).forEach(function (x) { set[norm(x)] = 1; }); }); });
    (q.options || []).forEach(function (o) { if (!set[norm(o)]) throw new Error('Variant boshqa sessiyadan kelgan: ' + o); });
    (q.left || []).concat(q.right || []).forEach(function (o) { if (!set[norm(o.t)] || !s.words[o.id]) throw new Error('Juftlik boshqa sessiyadan'); });
    return true;
  };

  // ================= Javob qabul qilish =================
  V.grade = function (sid, q, input) {
    var s = V.session(sid), w = s.words[q.w], r;
    if (q.type === 'mc') { r = V.checkText(input, q.dir === 'en-tr' ? V.acceptedTr(w) : V.acceptedEn(w)); r.correct = q.dir === 'en-tr' ? w.tr[0] : w.en; }
    else if (q.type === 'type') { r = V.checkText(input, q.dir === 'en-tr' ? V.acceptedTr(w) : V.acceptedEn(w)); r.correct = q.dir === 'en-tr' ? w.tr[0] : w.en; }
    else if (q.type === 'spell' || q.type === 'scramble') { r = V.checkText(input, V.acceptedEn(w)); r.correct = w.en; }
    else if (q.type === 'flash') {   // yozma javob (matn) yoki o'zini baholash (true/false)
      var corr = q.dir === 'en-tr' ? w.tr.join('; ') : w.en;
      if (typeof input === 'string') { r = V.checkText(input, q.dir === 'en-tr' ? V.acceptedTr(w) : V.acceptedEn(w)); r.correct = corr; } else r = { ok: !!input, correct: corr };
    }
    else r = { ok: false };
    r.explain = V.explain(s, q, w, input, r); return r;
  };
  V.explain = function (s, q, w, input, r) {
    var t = w.en + ' — ' + w.tr.join('; ');
    if (w.example) t += '. Misol: ' + w.example + (w.exampleTr ? ' (' + w.exampleTr + ')' : '');
    if (!r.ok && r.close) t = "Deyarli to'g'ri — imlo xatosi bor. " + t;
    return t;
  };
  // Progressni yangilash (faqat shu sessiya, faqat shu so'z). Qutidagi o'zgarish raundda so'z uchun bir marta hisoblanadi.
  function applyProgress(s, run, wid, ok, firstAttempt) {
    var p = s.progress[wid] || (s.progress[wid] = { box: 0, seen: 0, correct: 0, wrong: 0, streak: 0, fix: 0, due: null, last: null, mistake: false }), now = Date.now();
    p.seen++; p.last = now;
    if (ok) { p.correct++; p.streak++; if (p.mistake) { p.fix++; if (p.fix >= 2) { p.mistake = false; p.fix = 0; } } if (!run.outcome[wid] && firstAttempt) run.outcome[wid] = 'up'; }
    else { p.wrong++; p.streak = 0; p.fix = 0; p.mistake = true; run.outcome[wid] = 'down'; }
    var base = run.baseBox[wid] == null ? p.box : run.baseBox[wid], o = run.outcome[wid];
    if (o === 'up') { p.box = Math.min(5, base + 1); p.due = now + V.INTERVALS[p.box] * DAY; }
    else if (o === 'down') { p.box = Math.max(0, base - 2); p.due = now; }
    else if (p.due == null) p.due = now;
  }
  V.studyDone = function (sid, q) {   // yangi so'z ko'rsatildi: "yangi" → "o'rganilmoqda"
    var s = V.session(sid), run = s.run; if (!run) return;
    var p = s.progress[q.w] || (s.progress[q.w] = { box: 0, seen: 0, correct: 0, wrong: 0, streak: 0, fix: 0, due: null, last: null, mistake: false });
    if (!p.seen) p.seen = 1; p.last = Date.now(); if (p.due == null) p.due = Date.now(); s.lastActivity = Date.now(); V.save();
  };
  V.answer = function (sid, q, ok, wordIds, input) {
    var s = V.session(sid), run = s.run; if (!run || run.sid !== sid) throw new Error('Faol raund yo\'q');
    V.assertQuestion(sid, q);
    var ids = wordIds || [q.w], now = Date.now();
    ids.forEach(function (id) {
      var good = typeof ok === 'object' ? !ok[id] : ok;
      applyProgress(s, run, id, good, !q.retry);
      (good ? run.right : run.wrong)[id] = 1;
      s.attempts.push({ ts: now, w: id, kind: q.kind || q.type, ok: good, a: input == null ? null : String(input).slice(0, 80) });
    });
    if (s.attempts.length > 500) s.attempts = s.attempts.slice(-500);
    var allOk = typeof ok === 'object' ? Object.keys(ok).length === 0 : ok;
    run.answered++; if (allOk && !q.retry) run.firstTry++;
    if (!allOk && !q.retry && run.mode !== 'test') {   // xato savol raund oxirida bir marta qaytariladi
      var c = JSON.parse(JSON.stringify(q)); c.retry = true; if (c.left) { c.left = shuffle(c.left); c.right = shuffle(c.right); } run.queue.push(c);
    }
    s.lastActivity = now; V.save(); return { ok: allOk };
  };
  V.next = function (sid) { var s = V.session(sid); if (!s.run) return; s.run.i++; V.save(); };
  V.runDone = function (sid) { var s = V.session(sid); return !s.run || s.run.i >= s.run.queue.length; };
  V.stopRun = function (sid) { V.setActive(sid); V.save(); };   // run saqlanadi; keyin davom ettirish mumkin

  // Raund yakuni: faqat shu sessiya uchun xulosa
  V.finishRun = function (sid) {
    var s = V.session(sid), run = s.run; if (!run) throw new Error("Raund yo'q");
    var firstQ = run.queue.filter(function (q) { return !q.retry && q.type !== 'study'; }).length;
    var pct = firstQ ? Math.round(100 * run.firstTry / firstQ) : 100, st = V.stats(sid);
    var sum = { mode: run.mode, ts: Date.now(), durationMs: Date.now() - run.startedAt, total: firstQ, correct: run.firstTry, accuracy: pct, wordIds: run.words.filter(function (id) { return s.words[id]; }), wrongIds: Object.keys(run.wrong).filter(function (id) { return s.words[id]; }), mastered: st.mastered, learning: st.learning, fresh: st.fresh, passed: run.mode === 'test' ? pct >= 70 : null };
    s.lastSummary = sum; s.rounds++; s.lastActivity = Date.now(); s.run = null; V.save(); return sum;
  };
})(typeof window !== 'undefined' ? (window.V = window.V || {}) : (globalThis.V = globalThis.V || {}));
