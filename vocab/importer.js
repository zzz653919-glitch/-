/* Ko'p so'z import: matnni tahlil qilish (parser), tekshirish (validatsiya), takrorlarni aniqlash va sessiyaga qo'shish.
   Parser hech narsani jimgina o'chirmaydi: olib tashlangan tavsif `removed` maydonida ko'rinib turadi, ishonchsiz qatorlar `review` bo'ladi. */
(function (V) {
  'use strict';
  var I = V.imp = {};
  var norm = function (s) { return V.norm(s); };

  // ---------- Til belgilari (inglizcha / o'zbekcha) ----------
  var EN = new Set(("a an the to of in on up down out off over after before with for at by from about into onto through across against between under above around away back be do get make take look give go put set turn come run keep let bring call carry cut fall find hold pull push show stand tell think try use want work one one's someone something somebody oneself my your his her its our their and or not no i you he she it we they is are was were will can have has had this that these those there here how what when where who why which more most some any all each every other another such than then so very just only also too as if because while until since are am been being does did done doing going gone got made took taken").split(' '));
  var UZ = new Set("va bilan uchun bir biror kishi kishiga kishini kishining narsa narsani narsaga qilib qilish qilmoq bo'lmoq bo'lib emas ham yoki lekin ammo bu shu u men sen biz siz ular ichida kabi kerak mumkin yaxshi yomon katta kichik juda har hech nima kim qayer qachon nega qanday ertaga bugun kecha hozir ko'p oz bor yo'q uni unga undan ichida ustida tagida".split(' '));
  function nt(t) { return String(t).toLowerCase().replace(/[‘’ʻʼʹ`´′]/g, "'").replace(/^[^\p{L}']+|[^\p{L}']+$/gu, ''); }
  // musbat = o'zbekcha, manfiy = inglizcha
  function uzScore(token, hints) {
    var t = nt(token); if (!t) return 0;
    if (hints) { if (hints.en.has(t)) return -2.5; if (hints.uz.has(t)) return 2.5; }
    if (EN.has(t)) return -2; if (UZ.has(t)) return 2;
    var s = 0;
    if (/^[a-z]+'(s|t|re|ve|ll|d|m)$/.test(t)) return -2;
    if (/\p{L}'\p{L}/u.test(t)) s += 2;
    if (/(moq|mak)$/.test(t) && t.length > 4) s += 2.5;
    if (t.length >= 5 && /(lik|siz|chi|lar|ning|dan)$/.test(t)) s += 1;
    if (t.length >= 5 && /(ga|qa|ka)$/.test(t)) s += 1;
    if (t.length >= 6 && /(ni|da)$/.test(t)) s += 0.5;
    if (/q/.test(t) && !/qu/.test(t)) s += 1.2;
    if (/x/.test(t)) s += 0.5;
    if (/[wc]/.test(t.replace(/ch/g, ''))) s -= 1.2;
    if (/th|ph|ck|wh|tion|sion|ough|ight|ee|oo|ss|ll|tt|pp|ff|mm|rr|dd|gg|bb/.test(t)) s -= 0.7;
    if (t.length >= 5 && /(ing|ed|ly|ness|ment|able|ful|ize|ise)$/.test(t)) s -= 1.2;
    return s;
  }
  I.uzScore = uzScore;

  // ---------- Qator tozalash ----------
  function clean(s) { return String(s).replace(/[ ​‌‍﻿]/g, ' ').replace(/\s+$/g, '').replace(/^\s+/, ''); }
  function squash(s) { return s.replace(/[ \t]+/g, ' ').trim(); }

  // Talaffuz: /…/ yoki […] (IPA belgilari bo'lsa). Yopilmagan "/..." bo'lsa review.
  var IPA = /[ˈˌːəɪʊɒɔɑæʌʃʒθðŋɜɛɐɚ]/;
  function extractPron(line) {
    var prons = [], flags = [];
    var out = line.replace(/(^|\s)(\/[^\/\n]{1,80}\/)(?=\s|$|[—–\-:;,.=|])/g, function (m, pre, p) { prons.push(p); return pre; });
    out = out.replace(/(^|\s)(\[[^\]\n]{1,80}\])(?=\s|$|[—–\-:;,.=|])/g, function (m, pre, p) { if (IPA.test(p)) { prons.push(p); return pre; } return m; });
    var un = /(^|\s)(\/[^\s\/][^\n]*)$/.exec(out);          // OCR yopuvchi chiziqni tushirib qoldirgan: "word /te1k a ... — tarjima"
    if (!prons.length && un === null) { var u2 = /(^|\s)(\/\S[^—–\n]*?)(?=\s[—–-]\s|\s[—–]|$)/.exec(out); if (u2) { prons.push(u2[2].trim()); out = out.replace(u2[2], ''); flags.push('Talaffuz yopilmagan (/)'); } }
    return { text: out.replace(/^\s+|\s+$/g, ''), pron: prons[0] || '', flags: flags };
  }

  // ---------- Ajratuvchi ----------
  // Eng chapdagi ajratuvchi tanlanadi (teng bo'lsa — ustuvorlik bo'yicha).
  var SEPS = [
    { re: /\t+/, kind: 'tab' }, { re: /\s*[—–]\s*/, kind: 'dash' }, { re: /\s+-\s+/, kind: 'hyphen' }, { re: /\s*=\s*/, kind: 'eq' },
    { re: /\s*\|\s*/, kind: 'pipe' }, { re: /\s*:\s+|\s*:(?=\p{L})/u, kind: 'colon' }
  ];
  function findSep(s) {
    var best = null;
    SEPS.forEach(function (sp, pri) { var m = sp.re.exec(s); if (m && (!best || m.index < best.index)) best = { index: m.index, len: m[0].length, kind: sp.kind, pri: pri }; });
    if (best) return best;
    var m2 = /\s{2,}/.exec(s); if (m2 && m2.index > 0) return { index: m2.index, len: m2[0].length, kind: 'cols' };
    return null;
  }

  // ---------- Tarjima va tavsifni ajratish ----------
  function splitAlts(s) {            // ; va , bo'yicha (qavs ichida emas)
    var out = [], depth = 0, cur = '';
    for (var i = 0; i < s.length; i++) { var c = s[i]; if (c === '(') depth++; if (c === ')') depth = Math.max(0, depth - 1); if ((c === ';' || c === ',') && !depth) { out.push(cur); cur = ''; } else cur += c; }
    out.push(cur); return out.map(squash).filter(Boolean);
  }
  var INF = /(moq|mak)$/;
  // Qaytaradi: {tr:[...], removed:'...', review:[sabablar]}
  function cleanTranslation(right) {
    var res = { tr: [], removed: [], review: [] }, text = squash(right);
    // 1) birinchi gap oxiridan keyingi qism — izoh (".  Keyingi gap")
    var sm = /^(.*?[^\s.])\.\s+(\S.*)$/.exec(text); if (sm) { text = sm[1]; res.removed.push(sm[2]); }
    var alts = splitAlts(text), cutAny = false;
    alts.forEach(function (alt) {
      var tk = alt.split(' '), k = -1;
      for (var i = 0; i < tk.length; i++) if (INF.test(nt(tk[i])) && nt(tk[i]).length > 4) { k = i; break; }
      if (k >= 0 && k < tk.length - 1 && tk[k + 1][0] === '(') {          // fe'ldan keyingi qavs ichidagi izoh tarjimaning qismi (ixtiyoriy variant) — saqlanadi
        var q = k + 1; while (q < tk.length - 1 && !/\)$/.test(tk[q])) q++; k = q;
      }
      if (k >= 0 && k < tk.length - 1) {            // fe'l (…moq) dan keyingi so'zlar — tavsif (ishonchli qoida)
        res.tr.push(tk.slice(0, k + 1).join(' ')); res.removed.push(tk.slice(k + 1).join(' ')); cutAny = true;
      } else {
        if (k < 0 && tk.length >= 4) res.review.push("Tarjima uzun va tavsifdan ajratib bo'lmadi: \"" + alt + '"');
        res.tr.push(alt);
      }
    });
    if (cutAny && alts.length > 1) res.review.push("Tavsif olib tashlangan qatorda bir nechta variant bor — tekshiring");
    return res;
  }

  // POS belgilari inglizcha tomondan olib tashlanadi: "give up (v)" -> "give up"
  function cleanEnglish(s) {
    var removed = '', out = s;
    out = out.replace(/\s*\(\s*(n|v|adj|adv|prep|conj|pron|phr\.? ?v|idiom|phr)\.?\s*\)\s*$/i, function (m) { removed = m.trim(); return ''; });
    out = out.replace(/\s+(n|v|adj|adv|prep|conj)\.\s*$/i, function (m) { removed = m.trim(); return ''; });
    return { en: squash(out), removed: removed };
  }

  // ---------- Bitta qatorni tahlil qilish ----------
  function parseLine(raw, lineNo, ctx) {
    var e = { id: ctx.nextId++, line: lineNo, raw: raw, en: '', tr: '', pron: '', removed: '', status: 'valid', reasons: [], confirmed: false, allowDup: false, src: ctx.src || 'text' };
    var s = clean(raw);
    s = s.replace(/^\s*(?:\d{1,4}\s*[.)]|[•·▪●■►▶*]|-\s)\s*/, '');     // "1. ", "2) ", "• "
    var pr = extractPron(s); s = pr.text; e.pron = pr.pron; pr.flags.forEach(function (f) { e.reasons.push(f); });
    var left = '', right = '', how = '';
    var sep = findSep(s);
    if (sep) { left = s.slice(0, sep.index); right = s.slice(sep.index + sep.len); how = sep.kind; }
    else if (/[;,]/.test(s) && /[;,]/.exec(s).index > 0 && s.split(/[;,]/)[1].trim()) {
      var ci = /[;,]/.exec(s).index; left = s.slice(0, ci); right = s.slice(ci + 1); how = 'comma';
      e.reasons.push('Ajratuvchi vergul/nuqtali vergul — tekshiring');
    } else if (ctx.splitSpaces) {
      var tk = s.split(' ');
      if (tk.length === 1) { left = s; right = ''; how = 'single'; }
      else {
        var sc = tk.map(function (t) { return uzScore(t, ctx.hints); }), best = null, second = -1e9, i, total;
        for (i = 1; i < tk.length; i++) {
          total = 0; for (var j = 0; j < tk.length; j++) total += (j < i ? -sc[j] : sc[j]);
          if (!best || total > best.total) { if (best) second = best.total; best = { i: i, total: total }; } else if (total > second) second = total;
        }
        var lMean = best.i ? -sc.slice(0, best.i).reduce(function (a, b) { return a + b; }, 0) / best.i : 0, rMean = sc.slice(best.i).reduce(function (a, b) { return a + b; }, 0) / (tk.length - best.i);
        if (rMean < 0) { left = s; right = ''; how = 'single'; }     // o'ng tomon ham inglizcha ko'rinadi — butun qator inglizcha ibora, tarjima yo'q
        else {
        left = tk.slice(0, best.i).join(' '); right = tk.slice(best.i).join(' '); how = 'guess';
        var confident = (tk.length === 2 ? (lMean >= 0 && rMean >= 0 && best.total >= 0.7) : (best.total - second >= 1.5 && lMean > 0 && rMean > 0));
        if (!confident) e.reasons.push("Inglizcha va o'zbekcha qismlar chegarasi aniq emas — tekshiring (taxmin: «" + left + '» | «' + right + '»)');
        }
      }
    } else { left = s; right = ''; how = 'single'; }

    // inglizcha tomon
    var ce = cleanEnglish(left); e.en = ce.en; if (ce.removed) e.removed = ce.removed;
    // izoh ko'rinishidagi "/..." yopilmagan talaffuz chap tomonda qolgan bo'lsa
    var un = /^(.*?\S)\s+(\/\S.*)$/.exec(e.en); if (un) { e.en = squash(un[1]); if (!e.pron) e.pron = squash(un[2]); e.reasons.push('Talaffuz yopilmagan (/)'); }
    // tarjima tomon
    if (right) {
      var rest = '', m2 = findSep(right);   // ikkinchi ajratuvchi: undan keyingisi tavsif bo'lishi mumkin (ishonchsiz)
      if (m2 && (how === 'dash' || how === 'hyphen' || how === 'colon') && m2.kind === how) { rest = right.slice(m2.index + m2.len); right = right.slice(0, m2.index); e.reasons.push('Qatorda ikkinchi ajratuvchi bor — «' + squash(rest) + '» tavsif deb olib tashlandi, tekshiring'); }
      var ct = cleanTranslation(right); e.tr = ct.tr.join('; ');
      var rem = ct.removed.concat(rest ? [rest] : []).filter(Boolean).join(' · '); if (rem) e.removed = (e.removed ? e.removed + ' · ' : '') + rem;
      ct.review.forEach(function (r) { e.reasons.push(r); });
    }
    return e;
  }

  // ---------- Tekshirish (alohida entry uchun) ----------
  var MAXEN = 80;
  function baseStatus(e) {
    var hasLetters = /\p{L}/u.test(e.en);
    if (!e.en || !hasLetters) return { s: 'invalid', r: ["Inglizcha so'z topilmadi"] };
    if (e.en.length > MAXEN) return { s: 'invalid', r: ["Inglizcha qism juda uzun (maks. " + MAXEN + ')'] };
    if (!e.tr) return { s: 'incomplete', r: ["Tarjima yo'q — qo'lda kiriting"] };
    if (e.tr.length > 200) return { s: 'invalid', r: ['Tarjima juda uzun'] };
    return { s: 'ok', r: [] };
  }
  function suspicious(e) {   // ustunlar almashgan yoki til mos emas
    var r = [], et = e.en.split(' ').filter(Boolean), tt = e.tr.split(/[ ;]+/).filter(Boolean);
    if (et.length >= 7) r.push("Inglizcha qism juda uzun (gap bo'lishi mumkin)");
    if (et.length && tt.length) {
      var em = et.reduce(function (a, t) { return a + uzScore(t); }, 0) / et.length, tm = tt.reduce(function (a, t) { return a + uzScore(t); }, 0) / tt.length;
      if (em >= 1.5 && tm <= -1.5) r.push('Ustunlar almashgan bo\'lishi mumkin (chapda o\'zbekcha, o\'ngda inglizcha ko\'rinadi)');
    }
    return r;
  }
  // existing: Map(norm(en) -> tarjima) — faqat DESTINATION sessiya so'zlari
  I.revalidate = function (entries, existing) {
    var seen = {};
    entries.forEach(function (e) {
      var b = baseStatus(e);
      e.dup = null; e.status = b.s === 'ok' ? 'valid' : b.s;
      var why = b.r.slice(); if (b.s === 'ok') { suspicious(e).forEach(function (x) { why.push(x); }); (e._parseReasons || []).forEach(function (x) { why.push(x); }); if (why.length) e.status = 'review'; }
      var k = norm(e.en);
      if (b.s === 'ok') {
        if (existing && existing.has(k)) { e.dup = { kind: 'session', tr: existing.get(k) }; e.status = 'duplicate'; why = ["Sessiyada allaqachon bor: «" + existing.get(k) + '»'].concat(why); }
        else if (seen[k]) { e.dup = { kind: 'import', line: seen[k] }; e.status = 'duplicate'; why = ['Importda takrorlangan (' + seen[k] + '-qator bilan bir xil)'].concat(why); }
        else seen[k] = e.line;
      }
      e.reasons = why;
      e.ok = (e.status === 'valid') || (e.status === 'review' && e.confirmed && b.s === 'ok') || (e.status === 'duplicate' && e.allowDup && b.s === 'ok');
    });
    return entries;
  };
  I.counts = function (entries) {
    var c = { total: entries.length, valid: 0, duplicates: 0, review: 0, invalid: 0, incomplete: 0, ready: 0 };
    entries.forEach(function (e) {
      if (e.status === 'valid') c.valid++; else if (e.status === 'duplicate') c.duplicates++; else if (e.status === 'review') c.review++; else if (e.status === 'incomplete') c.incomplete++; else c.invalid++;
      if (e.ok) c.ready++;
    });
    c.bad = c.invalid + c.incomplete; return c;
  };
  I.existingMap = function (sid) {
    var m = new Map(); if (!sid) return m; V.words(sid).forEach(function (w) { var k = norm(w.en); if (!m.has(k)) m.set(k, w.tr.join('; ')); }); return m;
  };

  // ---------- Matn → yozuvlar ----------
  function makeCtx(text, opts) {
    var ctx = { nextId: opts.startId || 1, src: opts.src, splitSpaces: true, hints: { en: new Set(), uz: new Set() } };
    // ko'rsatmalar: shu ro'yxatdagi aniq ajratuvchili qatorlar va destination sessiya so'zlari
    if (opts.existing) opts.existing.forEach(function (tr, en) { en.split(' ').forEach(function (t) { ctx.hints.en.add(nt(t)); }); tr.split(/[ ;]+/).forEach(function (t) { ctx.hints.uz.add(nt(t)); }); });
    return ctx;
  }
  function learnHints(lines, ctx) {
    lines.forEach(function (l) {
      var s = clean(l).replace(/^\s*(?:\d{1,4}\s*[.)]|[•·▪●■►▶*]|-\s)\s*/, ''); s = extractPron(s).text; var sp = findSep(s); if (!sp) return;
      s.slice(0, sp.index).split(/\s+/).forEach(function (t) { t = nt(t); if (t) ctx.hints.en.add(t); });
      s.slice(sp.index + sp.len).split(/[\s;,]+/).forEach(function (t) { t = nt(t); if (t && !INF.test(t) || t.length > 4) ctx.hints.uz.add(t); });
    });
    // Ikkala tomonda uchraydigan so'zlar ishonchsiz — olib tashlanadi
    ctx.hints.en.forEach(function (t) { if (ctx.hints.uz.has(t)) { ctx.hints.en.delete(t); ctx.hints.uz.delete(t); } });
  }
  I.parse = function (text, opts) {
    opts = opts || {}; var lines = String(text == null ? '' : text).replace(/\r\n?/g, '\n').split('\n'), ctx = makeCtx(text, opts);
    learnHints(lines, ctx); var out = [];
    lines.forEach(function (l, i) { if (!clean(l)) return; var e = parseLine(l, i + 1, ctx); e._parseReasons = e.reasons.slice(); e.reasons = []; out.push(e); });
    return I.revalidate(out, opts.existing);
  };
  // Katta ro'yxatlar uchun: bo'laklab (UI qotmaydi) + progress
  I.parseAsync = function (text, opts, onProgress) {
    opts = opts || {}; var lines = String(text == null ? '' : text).replace(/\r\n?/g, '\n').split('\n'), ctx = makeCtx(text, opts), out = [], i = 0, CH = 300;
    learnHints(lines, ctx);
    return new Promise(function (res) {
      (function step() {
        var end = Math.min(lines.length, i + CH);
        for (; i < end; i++) { if (!clean(lines[i])) continue; var e = parseLine(lines[i], i + 1, ctx); e._parseReasons = e.reasons.slice(); e.reasons = []; out.push(e); }
        if (onProgress) onProgress(i / Math.max(1, lines.length), out.length);
        if (i < lines.length) setTimeout(step, 0); else res(I.revalidate(out, opts.existing));
      })();
    });
  };
  I.toText = function (entries) { return entries.map(function (e) { return e.en + (e.pron ? ' ' + e.pron : '') + ' — ' + e.tr; }).join('\n'); };

  // ---------- Saqlash ----------
  // Faqat tanlangan (e.ok) yozuvlar, FAQAT berilgan sessiyaga. Mavjud so'zlar va ularning progressiga tegilmaydi.
  I.commitSync = function (sid, entries) { return V.addWords(sid, entries.filter(function (e) { return e.ok; }).map(toWord)); };
  function toWord(e) { return { en: e.en, tr: e.tr.split(';').map(function (x) { return x.trim(); }).filter(Boolean), pron: e.pron }; }
  I.commit = function (sid, entries, onProgress) {
    var list = entries.filter(function (e) { return e.ok; }).map(toWord), CH = 200, i = 0, added = 0, failed = [];
    return new Promise(function (res) {
      (function step() {
        var r = V.addWords(sid, list.slice(i, i + CH), { save: false }); added += r.added.length; failed = failed.concat(r.failed); i += CH;
        if (onProgress) onProgress(Math.min(1, i / Math.max(1, list.length)), added);
        if (i < list.length) setTimeout(step, 0); else { V.save(); res({ added: added, failed: failed }); }
      })();
    });
  };
})(typeof window !== "undefined" ? (window.V = window.V || {}) : (globalThis.V = globalThis.V || {}));
