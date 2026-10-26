/* Mashqlar mexanikasi: javobni tekshirish, savollarni tuzish va sessiya. UI'dan mustaqil (test qilish oson). */
(function (TY) {
  var G = TY.Game;

  function shuffle(a) { a = a.slice(); for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function pick(a) { return a[Math.floor(Math.random() * a.length)]; }
  TY.shuffle = shuffle;

  // Katta-kichik harf, ortiqcha bo'shliq va barcha apostrof turlari farq qilmaydi
  function norm(s) {
    return String(s == null ? '' : s).toLowerCase().replace(/[‘’ʻʼʹ`´′]/g, "'")
      .replace(/[.!?,;:]+$/g, '').replace(/\s+/g, ' ').trim();
  }
  TY.norm = norm;
  function lev1(a, b) { // tahrir masofasi <= 1 mi (faqat maslahat uchun, javobni to'g'ri qilmaydi)
    if (Math.abs(a.length - b.length) > 1) return false;
    var i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    if (a.length === b.length) return a.slice(i + 1) === b.slice(i + 1) || (a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2));
    return a.length > b.length ? a.slice(i + 1) === b.slice(i) : b.slice(i + 1) === a.slice(i);
  }
  // Kiritilgan matn qabul qilinadigan javoblardan biriga mosmi
  function checkText(input, accepted) {
    var n = norm(input);
    if (!n) return { ok: false, empty: true };
    for (var i = 0; i < accepted.length; i++) if (norm(accepted[i]) === n) return { ok: true };
    var close = accepted.some(function (a) { return lev1(n, norm(a)); });
    return { ok: false, close: close };
  }
  TY.checkText = checkText;

  // ---- Ovoz (brauzer TTS; bo'lmasa eshitish mashqi tuzilmaydi) ----
  TY.canSpeak = function () { return !!(window.speechSynthesis && window.SpeechSynthesisUtterance); };
  TY.speak = function (text) {
    if (!TY.canSpeak() || !TY.Auth.state || !TY.Auth.state.speech) return;
    try { speechSynthesis.cancel(); var u = new SpeechSynthesisUtterance(text); u.lang = 'en-US'; u.rate = 0.9; speechSynthesis.speak(u); } catch (e) {}
  };

  function levelPool(w) { return TY.allWords.filter(function (x) { return x.level === w.level && x.id !== w.id; }); }
  function distract(w, key, n) {
    var bad = w.uz.map(norm), seen = {}, out = [];
    shuffle(levelPool(w).concat(shuffle(TY.allWords.filter(function (x) { return x.level !== w.level; })).slice(0, 12))).forEach(function (x) {
      var v = key === 'uz' ? x.uz[0] : x.en, nk = norm(v);
      if (out.length >= n || seen[nk]) return;
      if (key === 'uz' && x.uz.some(function (u) { return bad.indexOf(norm(u)) >= 0; })) return;
      seen[nk] = 1; out.push(v);
    });
    return out;
  }
  function blankSentence(w) {
    var re = new RegExp('\\b' + w.en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
    return re.test(w.sent) ? w.sent.replace(re, '_____') : null;
  }
  function tokens(sent) { return sent.replace(/[.!?]+$/, '').split(/\s+/); }

  // Bitta so'z uchun savol turlari
  var MAKERS = {
    mc_en_uz: function (w) { return { type: 'choice', dir: 'en-uz', w: w.id, prompt: w.en, hint: 'Tarjimasini tanlang', options: shuffle([w.uz[0]].concat(distract(w, 'uz', 3))), answer: w.uz, speak: w.en }; },
    mc_uz_en: function (w) { return { type: 'choice', dir: 'uz-en', w: w.id, prompt: w.uz[0], hint: 'Inglizcha so\'zni toping', options: shuffle([w.en].concat(distract(w, 'en', 3))), answer: [w.en] }; },
    type_en_uz: function (w) { return { type: 'type', w: w.id, prompt: w.en, hint: 'Tarjimasini yozing', answer: w.uz, ph: "O'zbekcha tarjimasi", speak: w.en }; },
    type_uz_en: function (w) { return { type: 'type', w: w.id, prompt: w.uz[0], hint: 'Inglizcha yozing', answer: [w.en], ph: 'Inglizcha so\'z' }; },
    scramble: function (w) {
      var letters = w.en.replace(/[^a-z]/gi, '').split(''); if (letters.length < 3) return null;
      var s, tries = 0; do { s = shuffle(letters); tries++; } while (s.join('') === letters.join('') && tries < 10);
      return { type: 'scramble', w: w.id, prompt: w.uz[0], hint: 'Harflardan so\'z tuzing', letters: s, answer: [w.en.replace(/[^a-z]/gi, '')] };
    },
    cloze: function (w) {
      var b = blankSentence(w); if (!b) return null;
      return { type: 'choice', dir: 'cloze', w: w.id, prompt: b, sub: w.sentUz, hint: "Bo'sh joyni to'ldiring", options: shuffle([w.en].concat(distract(w, 'en', 3))), answer: [w.en] };
    },
    build: function (w) {
      var tk = tokens(w.sent); if (tk.length < 3) return null;
      var extra = shuffle(TY.allWords.filter(function (x) { return x.id !== w.id; })).slice(0, 12).reduce(function (a, x) { return a.concat(tokens(x.sent)); }, []).filter(function (t) { return tk.map(function (z) { return z.toLowerCase(); }).indexOf(t.toLowerCase()) < 0 && /^[a-z]+$/i.test(t); });
      var bank = shuffle(tk.concat(extra.slice(0, 2)));
      return { type: 'build', w: w.id, prompt: w.sentUz, hint: "Gapni inglizcha tuzing", bank: bank, answer: [tk.join(' ')], speak: w.sent };
    },
    listen: function (w) { return TY.canSpeak() ? { type: 'type', w: w.id, prompt: '', listen: w.en, hint: 'Eshitganingizni yozing', answer: [w.en], ph: 'Eshitgan so\'zingiz', speak: w.en } : null; },
    picture: function (w) { return w.emoji ? { type: 'choice', dir: 'picture', w: w.id, prompt: w.emoji, big: true, hint: 'Bu rasm qaysi so\'z?', options: shuffle([w.en].concat(distract(w, 'en', 3))), answer: [w.en] } : null; }
  };
  var EASY = ['mc_en_uz', 'mc_uz_en', 'picture'], HARD = ['type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'listen'];

  function make(kind, w) { return MAKERS[kind] ? MAKERS[kind](w) : null; }
  function makeAny(w, kinds, avoid) {
    var order = shuffle(kinds);
    if (avoid) order.sort(function (a, b) { return (a === avoid) - (b === avoid); });
    for (var i = 0; i < order.length; i++) { var q = make(order[i], w); if (q) { q.kind = order[i]; return q; } }
    return null;
  }
  function matchQ(ws) {
    var left = ws.map(function (w) { return { id: w.id, t: w.en }; }), right = ws.map(function (w) { return { id: w.id, t: w.uz[0] }; });
    return { type: 'match', kind: 'match', hint: 'Juftlarini toping', left: shuffle(left), right: shuffle(right), ws: ws.map(function (w) { return w.id; }) };
  }
  function nonRepeat(qs) { // ketma-ket bir xil turdagi savollarni kamaytirish
    for (var i = 1; i < qs.length; i++) if (qs[i].kind === qs[i - 1].kind) { for (var j = i + 1; j < qs.length; j++) if (qs[j].kind !== qs[i - 1].kind) { var t = qs[i]; qs[i] = qs[j]; qs[j] = t; break; } }
    return qs;
  }

  // Sessiya tuzish. mode: lesson | review | test | mistakes | practice
  function build(mode, node) {
    var s = TY.Auth.state, words, qs = [];
    if (mode === 'lesson') {
      words = TY.LEVELS[node.level].topics[node.topic].words;
      var easy = shuffle(words).map(function (w) { var q = makeAny(w, EASY); q.firstSeen = true; return q; });
      var mt = matchQ(shuffle(words).slice(0, 5));
      var hard = shuffle(words).map(function (w) { return makeAny(w, HARD); });
      qs = nonRepeat(easy).concat([mt], nonRepeat(hard));
      var old = Object.keys(s.mistakes).filter(function (id) { return !words.some(function (w) { return w.id === id; }); });
      shuffle(old).slice(0, 3).forEach(function (id) { var q = makeAny(TY.wordById[id], EASY.concat(['type_en_uz'])); if (q) { q.review = true; qs.push(q); } });
    } else if (mode === 'review' || mode === 'test') {
      var lv = TY.LEVELS[node.level], all = [];
      lv.topics.forEach(function (tp) { all = all.concat(tp.words); });
      var weighted = shuffle(all).sort(function (a, b) { return (s.mistakes[b.id] ? 1 : 0) - (s.mistakes[a.id] ? 1 : 0); });
      var n = mode === 'test' ? 14 : 10; words = weighted.slice(0, n);
      var kinds = mode === 'test' ? HARD.concat(['mc_en_uz', 'mc_uz_en', 'cloze']) : EASY.concat(HARD);
      qs = nonRepeat(shuffle(words).map(function (w) { return makeAny(w, kinds); }));
      qs.splice(Math.floor(qs.length / 2), 0, matchQ(shuffle(all).slice(0, 5)));
    } else { // mistakes | practice
      var ids = mode === 'mistakes' ? Object.keys(s.mistakes) : [];
      if (mode === 'practice') TY.LEVELS.forEach(function (lv) { lv.topics.forEach(function (tp) { if (s.done[tp.id]) ids = ids.concat(tp.words.map(function (w) { return w.id; })); }); });
      words = shuffle(ids).slice(0, 12).map(function (id) { return TY.wordById[id]; });
      qs = nonRepeat(words.map(function (w) { var q = makeAny(w, EASY.concat(HARD)); return q; }));
      if (words.length >= 4) qs.splice(Math.min(3, qs.length), 0, matchQ(words.slice(0, 5)));
    }
    qs = qs.filter(Boolean);
    return { mode: mode, node: node || null, words: words, queue: qs };
  }
  TY.buildSession = build;

  // ---- Sessiya holati ----
  function Session(mode, node) {
    var b = build(mode, node);
    this.mode = mode; this.node = node; this.words = b.words; this.queue = b.queue; this.total = b.queue.length;
    this.i = 0; this.firstTry = 0; this.xp = 0; this.wrong = {}; this.right = {}; this.start = Date.now(); this.qStart = Date.now();
    this.over = false; this.failed = false; this.useHearts = (mode === 'lesson' || mode === 'review' || mode === 'test');
  }
  Session.prototype.current = function () { return this.queue[this.i]; };
  Session.prototype.progress = function () { return this.total ? Math.min(1, (this.i) / this.total) : 1; };
  Session.prototype.tick = function () { var now = Date.now(); G.addTime((now - this.qStart) / 1000); this.qStart = now; };
  // wordIds: savoldagi so'zlar; ok: to'g'ri/noto'g'ri. Qaytaradi: {xp, heartsLeft, outOfHearts}
  Session.prototype.answer = function (q, ok, wordIds, firstAttempt) {
    var self = this; this.tick();
    (wordIds || [q.w]).forEach(function (id) { G.recordAnswer(id, ok); (ok ? self.right : self.wrong)[id] = 1; });
    var res = { xp: 0, outOfHearts: false };
    if (ok) {
      res.xp = q.retry ? 5 : 10; this.xp += res.xp; G.addXP(res.xp); if (!q.retry) this.firstTry++;
    } else if (this.useHearts && !q.heartLost) {
      q.heartLost = true; G.loseHeart();
      if (TY.Auth.state.hearts <= 0) { res.outOfHearts = true; this.over = true; this.failed = true; }
    }
    if (!ok && !q.retry) { // xato savol bir marta oxiriga qaytariladi
      var copy = JSON.parse(JSON.stringify(q)); copy.retry = true; copy.heartLost = true; delete copy.firstSeen;
      if (copy.type === 'match') copy.left = shuffle(copy.left), copy.right = shuffle(copy.right);
      this.queue.push(copy);
    }
    TY.Auth.save();
    res.heartsLeft = TY.Auth.state.hearts; return res;
  };
  // Juftlashtirish: butun savol bir marta hisoblanadi (xato juftliklar so'z bo'yicha yoziladi)
  Session.prototype.answerMatch = function (q, wrongIds) {
    var self = this, ok = wrongIds.length === 0; this.tick();
    q.ws.forEach(function (id) { var bad = wrongIds.indexOf(id) >= 0; G.recordAnswer(id, !bad); (bad ? self.wrong : self.right)[id] = 1; });
    var res = { xp: ok ? 10 : 5, outOfHearts: false };
    this.xp += res.xp; G.addXP(res.xp); if (ok && !q.retry) this.firstTry++;
    if (!ok && this.useHearts) { G.loseHeart(); if (TY.Auth.state.hearts <= 0) { res.outOfHearts = true; this.over = true; this.failed = true; } }
    TY.Auth.save(); res.heartsLeft = TY.Auth.state.hearts; return res;
  };
  Session.prototype.next = function () { this.i++; this.qStart = Date.now(); if (this.i >= this.queue.length) this.over = true; };
  Session.prototype.percent = function () { return this.total ? Math.round(100 * this.firstTry / this.total) : 100; };
  // Dars yakuni: bonus XP, saqlash, yutuqlar
  Session.prototype.finish = function () {
    var pct = this.percent(), m = this.mode, out = { pct: pct, passed: true, bonus: 0, ach: [], unlockedNext: false };
    if (m === 'test' && pct < 75) out.passed = false;
    if (out.passed) {
      out.bonus = m === 'test' ? 40 : m === 'review' ? 25 : m === 'lesson' ? 20 : 15;
      if (pct === 100 && m !== 'practice' && m !== 'mistakes') out.bonus += 10;
      this.xp += out.bonus;
      var r = (m === 'lesson' || m === 'review' || m === 'test') ? G.completeNode(this.node.id, pct, out.bonus, 0) : G.completePractice(out.bonus);
      out.ach = r.ach; out.unlockedNext = !!(this.node && r.first);
    } else { TY.Auth.save(); }
    this.tick(); TY.Auth.save();
    var st = TY.Auth.state; st.history.unshift({ ts: Date.now(), mode: m, node: this.node && this.node.id, pct: pct, xp: this.xp, ok: out.passed }); st.history = st.history.slice(0, 50); TY.Auth.save();
    out.xp = this.xp; return out;
  };
  TY.Session = Session;

  // Yagona javob tekshiruvi (UI tomonidan chaqiriladi)
  TY.gradeQuestion = function (q, input) {
    if (q.type === 'choice') { var ok = checkText(input, q.answer).ok; return { ok: ok, correct: q.answer[0] }; }
    if (q.type === 'type') { var r = checkText(input, q.answer); r.correct = q.answer[0]; return r; }
    if (q.type === 'scramble') { var rs = checkText(input, q.answer); rs.correct = q.answer[0]; return rs; }
    if (q.type === 'build') { var rb = norm(input.join(' ')) === norm(q.answer[0]); return { ok: rb, correct: q.answer[0] }; }
    return { ok: false };
  };
  // Xato javobdan keyin ko'rsatiladigan qisqa tushuntirish
  TY.explain = function (q) {
    var w = TY.wordById[q.w]; if (!w) return '';
    return w.en + ' — ' + w.uz.join(', ') + '. Misol: ' + w.sent + ' (' + w.sentUz + ')';
  };
})(window.TY = window.TY || {});
