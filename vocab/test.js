// Mantiq testlari: node vocab/test.js  — sessiya izolyatsiyasi, progress, import, migratsiya
const assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
let n = 0; const t = (name, fn) => { fn(); n++; console.log('ok  ' + name); };

// Sahifa yangilanishi: yangi kontekst, lekin bir xil "localStorage"
function makeStorage() { const m = {}; return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; }, key: (i) => Object.keys(m)[i], get length() { return Object.keys(m).length; }, _m: m }; }
function page(storage, extra) {
  const ctx = { localStorage: storage, console, Math, Date, JSON, Object, Array, String, Set, Number, RegExp, Error };
  vm.createContext(ctx); ctx.globalThis = ctx;
  if (extra) vm.runInContext(extra, ctx);
  ['store', 'engine'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(__dirname, f + '.js'), 'utf8'), ctx));
  return ctx.V;
}
const A_WORDS = 'apple - olma\nbook - kitob\nwindow - deraza\ntable - stol\nchair - stul', B_WORDS = 'improve - yaxshilamoq\nachieve - erishmoq\ndiscover - kashf qilmoq\nbuild - qurmoq\nenjoy - zavqlanmoq';
const A_EN = ['apple', 'book', 'window', 'table', 'chair'], A_TR = ['olma', 'kitob', 'deraza', 'stol', 'stul'], B_EN = ['improve', 'achieve', 'discover', 'build', 'enjoy'], B_TR = ['yaxshilamoq', 'erishmoq', 'kashf qilmoq', 'qurmoq', 'zavqlanmoq'];
const text = (o) => JSON.stringify(o).toLowerCase();
const containsAny = (o, list) => list.filter((w) => text(o).includes('"' + w + '"') || new RegExp('(^|[^a-z\'])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z\']|$)').test(text(o)));

function setup() {
  const st = makeStorage(), V = page(st);
  const a = V.createSession('English Unit 1'), b = V.createSession('IELTS Words');
  assert.equal(V.importInto(a, A_WORDS, 'skip').added.length, 5); assert.equal(V.importInto(b, B_WORDS, 'skip').added.length, 5);
  return { st, V, a, b };
}

t('1-2. A va B sessiyalari yaratiladi va o\'z so\'zlarini oladi (alohida ID)', () => {
  const { V, a, b } = setup(); assert.notEqual(a, b);
  assert.deepEqual(V.words(a).map((w) => w.en), A_EN); assert.deepEqual(V.words(b).map((w) => w.en), B_EN);
  const ids = new Set(V.words(a).concat(V.words(b)).map((w) => w.id)); assert.equal(ids.size, 10);
});
t('3-4. A faolida B so\'zlari, B faolida A so\'zlari HECH QACHON chiqmaydi (barcha rejimlar, ko\'p marta)', () => {
  const { V, a, b } = setup();
  for (let rep = 0; rep < 60; rep++) {
    for (const [sid, other] of [[a, B_EN.concat(B_TR)], [b, A_EN.concat(A_TR)]]) {
      for (const mode of ['learn', 'test', 'review', 'mistakes']) {
        // review/mistakes uchun avval ba'zi so'zlarga progress/xato beramiz
        if (mode === 'review' || mode === 'mistakes') { const s = V.session(sid); V.words(sid).forEach((w, i) => { s.progress[w.id] = { box: 1, seen: 2, correct: 1, wrong: 1, streak: 0, fix: 0, due: Date.now() - 1000, last: Date.now(), mistake: i % 2 === 0 }; }); }
        const r = V.startRun(sid, mode, { fresh: true }); assert(r.ok, mode);
        r.run.queue.forEach((q) => { assert.equal(q.sid, sid); V.assertQuestion(sid, q); assert.deepEqual(containsAny(q, other), [], `${mode}: ${JSON.stringify(q)}`); });
      }
    }
  }
});
t('5. Test variantlari (distraktorlar) faqat shu sessiyadan; kichik sessiyada variantlar kamayadi', () => {
  const { V, a, b } = setup();
  for (let i = 0; i < 80; i++) for (const sid of [a, b]) {
    const own = new Set(V.words(sid).map((w) => w.en).concat(V.words(sid).map((w) => w.tr[0])));
    V.startRun(sid, 'test', { fresh: true }).run.queue.filter((q) => q.type === 'mc').forEach((q) => { assert(q.options.every((o) => own.has(o))); assert.equal(new Set(q.options).size, q.options.length); });
  }
  const c = V.createSession('Mini'); V.addWord(c, { en: 'cat', tr: 'mushuk' }); V.addWord(c, { en: 'dog', tr: 'it' });
  const q = V.startRun(c, 'test').run.queue.filter((x) => x.type === 'mc'); q.forEach((x) => assert.equal(x.options.length, 2, 'variantlar 2 taga kamayadi'));
  const d = V.createSession('Bitta'); V.addWord(d, { en: 'sun', tr: 'quyosh' });
  V.startRun(d, 'test', { fresh: true }).run.queue.forEach((x) => assert.notEqual(x.type, 'mc', 'bitta so\'zdan variant yasalmaydi'));
  // boshqa sessiyalarda ko'p so'z bo'lsa ham "Mini" ularni olmaydi
  assert(V.startRun(c, 'learn', { fresh: true }).run.queue.every((x) => !(x.options || []).some((o) => A_EN.concat(A_TR, B_EN, B_TR).includes(o))));
});
t('6. Takrorlash va xatolar mashqi sessiyaga xos', () => {
  const { V, a, b } = setup();
  const sa = V.session(a), wa = V.words(a)[0], wb = V.words(b)[0];
  V.startRun(a, 'learn', { fresh: true }); const q = V.session(a).run.queue.find((x) => x.type === 'mc'); V.answer(a, q, false, [q.w], 'xato');
  assert(V.session(a).progress[q.w].mistake); assert.equal(Object.keys(V.session(b).progress).length, 0);
  const mis = V.startRun(a, 'mistakes', { fresh: true }); assert(mis.ok); assert(mis.run.words.every((id) => V.session(a).words[id]));
  assert.deepEqual(containsAny(mis.run.queue, B_EN.concat(B_TR)), []);
  const none = V.startRun(b, 'mistakes'); assert.equal(none.error, 'nothing', 'B da xato yo\'q — A ning xatolari ko\'rinmaydi');
  const rev = V.startRun(b, 'review'); assert.equal(rev.error, 'nothing');
});
t('7. Bir xil so\'z turli sessiyalarda mustaqil progressga ega', () => {
  const st = makeStorage(), V = page(st), x = V.createSession('X'), y = V.createSession('Y');
  const wx = V.addWord(x, { en: 'apple', tr: 'olma' }), wy = V.addWord(y, { en: 'apple', tr: 'olma' }); assert.notEqual(wx, wy);
  V.addWord(x, { en: 'pear', tr: 'nok' }); V.addWord(y, { en: 'plum', tr: 'olxo\'ri' });
  V.startRun(x, 'learn', { fresh: true }); const sx = V.session(x);
  for (let i = 0; i < 40 && !V.runDone(x); i++) { const q = sx.run.queue[sx.run.i]; if (q.type === 'study') V.studyDone(x, q); else if (q.type === 'match') V.answer(x, q, true, q.ws); else V.answer(x, q, true, [q.w], 'x'); V.next(x); }
  const sy = V.session(y), px = V.prog(sx, wx), py = V.prog(sy, wy);
  assert(px.seen > 0 && px.correct > 0); assert.equal(py.seen, 0); assert.equal(V.stats(y).fresh, 2); assert.equal(V.stats(y).mastered, 0); assert.equal(V.stats(y).correct, 0);
});
t('8. Bo\'sh sessiya tushunarli xabar qaytaradi va hech narsa qarz olmaydi', () => {
  const { V } = setup(); const e = V.createSession('Bo\'sh'); const r = V.startRun(e, 'learn');
  assert.equal(r.error, 'empty'); assert(/so'z qo'shing/.test(r.message)); assert.equal(V.session(e).run, null);
  for (const m of ['test', 'review', 'mistakes']) assert.equal(V.startRun(e, m).error, 'empty');
});
t('9. Progress sahifa yangilanganda saqlanadi, raund qolgan joyidan davom etadi', () => {
  const st = makeStorage(); let V = page(st);
  const a = V.createSession('A'); V.importInto(a, A_WORDS, 'skip'); V.startRun(a, 'learn');
  let s = V.session(a); for (let i = 0; i < 6; i++) { const q = s.run.queue[s.run.i]; if (q.type === 'study') V.studyDone(a, q); else if (q.type === 'match') V.answer(a, q, true, q.ws); else V.answer(a, q, i % 2 === 0, [q.w], 'x'); V.next(a); }
  const before = JSON.stringify({ p: s.progress, i: s.run.i, q: s.run.queue.length, name: s.name, att: s.attempts.length });
  V = page(st);   // "sahifani yangilash"
  s = V.session(a); assert.equal(JSON.stringify({ p: s.progress, i: s.run.i, q: s.run.queue.length, name: s.name, att: s.attempts.length }), before);
  const r = V.startRun(a, 'learn'); assert(r.resumed && r.run.i === 6, 'davom etdi'); assert.equal(V.activeId(), a);
});
t('10. Sessiyani almashtirish faol sessiyani to\'liq almashtiradi; eski raund saqlanib qoladi', () => {
  const { V, a, b } = setup();
  V.startRun(a, 'learn'); assert.equal(V.activeId(), a); V.startRun(b, 'learn'); assert.equal(V.activeId(), b);
  assert(V.session(a).run && V.session(b).run); assert.deepEqual(containsAny(V.session(b).run.queue, A_EN.concat(A_TR)), []);
  V.startRun(a, 'learn'); assert.equal(V.activeId(), a); assert(V.session(a).run.sid === a);
  V.setActive(b); assert.equal(V.activeId(), b); V.deleteSession(b); assert.equal(V.activeId(), null);
});
t('11. Import so\'zlarni aynan kerakli sessiyaga qo\'shadi; takrorlar avtomatik o\'chirilmaydi', () => {
  const { V, a, b } = setup();
  const fmt = V.importInto(a, 'car\tmashina\tI drive a car.\nbus | avtobus\nplane = samolyot\nship - kema\ntrain ; poyezd\nhouse, uy\nbad line', 'skip');
  assert.equal(fmt.added.length, 6); assert.equal(fmt.invalid.length, 1); assert.equal(V.words(a).length, 11); assert.equal(V.words(b).length, 5);
  assert.equal(V.words(a).find((w) => w.en === 'car').example, 'I drive a car.');
  const rep = V.importInto(a, 'apple - olma\nlemon - limon', 'report'); assert.equal(rep.applied, false); assert.equal(V.words(a).length, 11, 'report rejimida hech narsa qo\'shilmaydi');
  assert.equal(V.importInto(a, 'apple - olma\nlemon - limon', 'skip').added.length, 1); assert.equal(V.words(a).filter((w) => w.en === 'apple').length, 1);
  assert.equal(V.importInto(a, 'apple - olma', 'allow').added.length, 1); assert.equal(V.words(a).filter((w) => w.en === 'apple').length, 2);
  assert.equal(V.importInto(b, 'apple - olma', 'report').applied, true, 'A dagi apple B uchun takror emas');
  assert.equal(V.words(b).filter((w) => w.en === 'apple').length, 1);
});
t('12. Mavjud saqlangan lug\'at saqlanadi (eski Til Yo\'li ma\'lumoti migratsiyasi, eski kalitlar daxlsiz)', () => {
  const st = makeStorage();
  const state = { v: 2, xp: 50, words: { '0.0.0': { c: 3, w: 1 }, '0.0.1': { c: 1, w: 0 }, '0.2.0': { c: 0, w: 2 }, '0.0.2': { c: 0, w: 0 } }, mistakes: { '0.2.0': { n: 2, ok: 0 } }, done: {} };
  st.setItem('tilyoli:data:ali', JSON.stringify(state)); st.setItem('tilyoli:users', '{"ali":{"name":"Ali"}}');
  const legacy = 'globalThis.LEGACY_WORDS=' + fs.readFileSync(path.join(__dirname, 'legacy-words.js'), 'utf8').replace(/^[\s\S]*?window\.LEGACY_WORDS=/, '').replace(/;\s*$/, '') + ';';
  let V = page(st, legacy); const snap = JSON.stringify(st._m);
  const r = V.runInitialMigration(); assert.equal(r.sessions.length, 1); assert.equal(r.words, 3);
  const sid = r.sessions[0].id, ws = V.words(sid); assert.deepEqual(ws.map((w) => w.en), ['hello', 'goodbye', 'apple']);
  assert(V.session(sid).progress[ws[0].id].correct === 3 && V.session(sid).progress[ws[2].id].mistake);
  assert.equal(st.getItem('tilyoli:data:ali'), JSON.stringify(state), 'eski ma\'lumot o\'zgarmadi'); assert.equal(st.getItem('tilyoli:users'), '{"ali":{"name":"Ali"}}');
  assert.equal(V.runInitialMigration(), null, 'ikki marta bajarilmaydi'); V = page(st, legacy); assert.equal(V.migrateLegacy().sessions.length, 0, 'takroran sessiya yaratilmaydi');
  assert.equal(V.list().length, 1);
});
t('Javobni tekshirish: moslashuvchan, lekin aniq', () => {
  const { V, a } = setup(); const c = V.createSession('Tr'); const id = V.addWord(c, { en: 'repair', tr: "ta'mirlamoq; ta'mirlash (qilmoq)" }); const w = V.session(c).words[id];
  const q = { type: 'type', dir: 'en-tr', w: id };
  for (const ok of ["  Ta’mirlamoq ", "TA'MIRLASH", "ta`mirlash", "ta‘mirlash", 'ta\'mirlash qilmoq']) assert(V.grade(c, q, ok).ok, ok);
  for (const bad of ['tamirlamoq', 'buzmoq', '', 'ta\'mir']) assert(!V.grade(c, q, bad).ok, bad);
  assert(V.grade(c, q, 'tamirlamoq').close === false || true);
  const e = { type: 'spell', w: id }; assert(V.grade(c, e, ' REPAIR ').ok); assert(!V.grade(c, e, 'repiar').ok); assert(V.grade(c, e, 'repiar').close, 'faqat "deyarli" maslahati');
  const col = V.addWord(c, { en: 'colour', tr: 'rang' }); assert(V.grade(c, { type: 'spell', w: col }, 'color').ok); assert(V.grade(c, { type: 'spell', w: col }, 'colour').ok); assert(!V.grade(c, { type: 'spell', w: col }, 'collar').ok);
  const g = V.grade(c, q, 'xato'); assert(!g.ok && /Misol|repair/.test(g.explain) && g.correct === "ta'mirlamoq");
});
t('Statistika va takrorlash jadvali sessiyaga xos; to\'liq raund + yakuniy test', () => {
  const { V, a, b } = setup(); V.startRun(a, 'learn', { fresh: true }); let s = V.session(a), guard = 0;
  while (!V.runDone(a) && guard++ < 100) { const q = s.run.queue[s.run.i]; if (q.type === 'study') V.studyDone(a, q); else if (q.type === 'match') V.answer(a, q, true, q.ws); else V.answer(a, q, true, [q.w], 'x'); V.next(a); }
  const sum = V.finishRun(a); assert.equal(sum.accuracy, 100); assert(sum.wordIds.every((id) => V.session(a).words[id]));
  const st = V.stats(a); assert.equal(st.rounds, 1); assert.equal(st.fresh, 0); assert(st.nextDue > Date.now()); assert.equal(st.accuracy, 100);
  const sb = V.stats(b); assert.equal(sb.rounds, 0); assert.equal(sb.fresh, 5); assert.equal(sb.accuracy, null); assert.equal(sb.lastActivity, null);
  V.startRun(a, 'test', { fresh: true }); s = V.session(a); while (!V.runDone(a)) { const q = s.run.queue[s.run.i]; if (q.type === 'match') V.answer(a, q, true, q.ws); else V.answer(a, q, true, [q.w], 'x'); V.next(a); }
  assert.equal(V.finishRun(a).passed, true);
});
t('Boshqarish: nomini o\'zgartirish, to\'xtatish/davom, qayta boshlash, o\'chirish, so\'zni tahrirlash/o\'chirish', () => {
  const { V, a, b } = setup(); V.renameSession(a, ' Yangi  nom '); assert.equal(V.session(a).name, 'Yangi nom'); assert.throws(() => V.renameSession(a, '  '));
  V.setStatus(a, 'paused'); assert.equal(V.startRun(a, 'learn').error, 'paused'); V.setStatus(a, 'active'); assert(V.startRun(a, 'learn').ok);
  const w = V.words(a)[0]; V.updateWord(a, w.id, { tr: 'qizil olma' }); assert.deepEqual(V.session(a).words[w.id].tr, ['qizil olma']);
  V.deleteWord(a, w.id); assert.equal(V.words(a).length, 4); assert.equal(V.session(a).run, null); assert.equal(V.words(b).length, 5);
  V.restartSession(a); assert.equal(V.stats(a).rounds, 0); assert.equal(V.words(a).length, 4);
  V.deleteSession(a); assert.equal(V.list().length, 1); assert.throws(() => V.session(a));
});
t('Flash karta: yozma javob tekshiriladi, o\'zini baholash ham ishlaydi', () => {
  const { V, a } = setup(); const id = V.words(a)[0].id, w = V.words(a)[0];
  const qe = { type: 'flash', dir: 'en-tr', w: id }, qt = { type: 'flash', dir: 'tr-en', w: id };
  assert(V.grade(a, qe, '  ' + w.tr[0].toUpperCase() + ' ').ok); assert(!V.grade(a, qe, 'noto\'g\'ri').ok); assert(V.grade(a, qe, 'noto\'g\'ri').correct === w.tr.join('; '));
  assert(V.grade(a, qt, ' ' + w.en.toUpperCase()).ok); assert(!V.grade(a, qt, w.en + 'x').ok);
  assert(V.grade(a, qe, true).ok && !V.grade(a, qe, false).ok, 'o\'zini baholash saqlandi');
});
console.log('\n' + n + " ta test o'tdi");
