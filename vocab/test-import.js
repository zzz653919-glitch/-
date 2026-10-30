// Ko'p so'z import testlari: node vocab/test-import.js
const assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
let n = 0; const t = async (name, fn) => { await fn(); n++; console.log('ok  ' + name); };
function makeStorage() { const m = {}; return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; }, key: (i) => Object.keys(m)[i], get length() { return Object.keys(m).length; }, _m: m }; }
function page(storage) {
  const ctx = { localStorage: storage, console, Math, Date, JSON, Object, Array, String, Set, Map, Number, RegExp, Error, Promise, setTimeout, performance };
  vm.createContext(ctx); ctx.globalThis = ctx;
  ['store', 'engine', 'importer', 'ocr'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(__dirname, f + '.js'), 'utf8'), ctx));
  return ctx.V;
}
const pick = (rows) => rows.map((e) => [e.en, e.tr]);
const FMT_A = "take a photo /teɪk ə ˈfəʊtəʊ/ – suratga olmoq sunday qilib\nlook after /lʊk ˈɑːftə/ – g'amxo'rlik qilmoq biror kishiga qarash\ngive up /ɡɪv ʌp/ – taslim bo'lmoq";
const FMT_B = 'tomorrow — ertaga\napple — olma\nimprove — yaxshilamoq\ntake a photo — suratga olmoq';
const FMT_C = "take a photo\tsuratga olmoq\ntomorrow ertaga\nlook after g'amxo'rlik qilmoq";

(async () => {
  const V = page(makeStorage());
  await t('Format A: so\'z + talaffuz + tarjima + tavsif', () => {
    const r = V.imp.parse(FMT_A);
    assert.deepEqual(pick(r), [['take a photo', 'suratga olmoq'], ['look after', "g'amxo'rlik qilmoq"], ['give up', "taslim bo'lmoq"]]);
    assert(r.every((e) => e.status === 'valid' && e.ok));
  });
  await t('Format B: so\'z — tarjima (—, –, -, :, =, |)', () => {
    assert.deepEqual(pick(V.imp.parse(FMT_B)), [['tomorrow', 'ertaga'], ['apple', 'olma'], ['improve', 'yaxshilamoq'], ['take a photo', 'suratga olmoq']]);
    const seps = V.imp.parse('tomorrow—ertaga\napple - olma\nbook: kitob\nchair = stul\nwindow | deraza\nsun – quyosh\nmoon — oy');
    assert.deepEqual(pick(seps), [['tomorrow', 'ertaga'], ['apple', 'olma'], ['book', 'kitob'], ['chair', 'stul'], ['window', 'deraza'], ['sun', 'quyosh'], ['moon', 'oy']]);
  });
  await t('Format C: TAB, ko\'p bo\'shliq va ajratuvchisiz jadvalga o\'xshash qatorlar', () => {
    const r = V.imp.parse(FMT_C);
    assert.deepEqual(pick(r), [['take a photo', 'suratga olmoq'], ['tomorrow', 'ertaga'], ["look after", "g'amxo'rlik qilmoq"]]);
    assert.equal(r[0].status, 'valid'); assert.equal(r[1].status, 'valid'); assert.equal(r[2].status, 'valid');
    assert.deepEqual(pick(V.imp.parse('take a photo     suratga olmoq\ngive up   taslim bo\'lmoq')), [['take a photo', 'suratga olmoq'], ['give up', "taslim bo'lmoq"]]);
    assert.deepEqual(pick(V.imp.parse('1. window: deraza\n2) apple\tolma\n• sun - quyosh')), [['window', 'deraza'], ['apple', 'olma'], ['sun', 'quyosh']]);
  });
  await t('Talaffuz belgilari saqlanadi alohida va ingliz/o\'zbek matnidan olib tashlanadi', () => {
    const r = V.imp.parse(FMT_A); assert.equal(r[0].pron, '/teɪk ə ˈfəʊtəʊ/'); assert.equal(r[2].pron, '/ɡɪv ʌp/');
    r.forEach((e) => { assert(!/[\/ɪəʊˈ]/.test(e.en + e.tr), 'talaffuz qoldi: ' + e.en + '|' + e.tr); });
    const b = V.imp.parse('colour [ˈkʌlə] — rang'); assert.equal(b[0].en, 'colour'); assert.equal(b[0].pron, '[ˈkʌlə]');
    const keep = V.imp.parse('and/or — va/yoki'); assert.equal(keep[0].en, 'and/or', "so'z ichidagi / talaffuz emas");
  });
  await t('Tavsif olib tashlanadi, lekin ko\'rinib turadi; muqobil tarjimalar saqlanadi', () => {
    const r = V.imp.parse(FMT_A); assert.equal(r[0].removed, 'sunday qilib'); assert.equal(r[1].removed, 'biror kishiga qarash'); assert.equal(r[2].removed, '');
    const alt = V.imp.parse("take a photo — suratga olmoq, rasmga tushirmoq\ngive up (v) – taslim bo'lmoq; voz kechmoq");
    assert.equal(alt[0].tr, 'suratga olmoq; rasmga tushirmoq'); assert.equal(alt[1].tr, "taslim bo'lmoq; voz kechmoq"); assert.equal(alt[1].en, 'give up'); assert(alt.every((e) => e.status === 'valid'));
    const sent = V.imp.parse('apple — olma. Men olma yeyman.'); assert.equal(sent[0].tr, 'olma'); assert.equal(sent[0].removed, 'Men olma yeyman.');
    // olib tashlangan matn qaytarilishi mumkin (hech narsa yo'qolmaydi)
    assert(r[0].removed.length > 0);
  });
  await t('Ishonchsiz ajratish: yo\'qotmaydi, "tekshirish" holatiga qo\'yadi', () => {
    const r = V.imp.parse("kitob — o'qish uchun mo'ljallangan narsa bu\nbook — kitob — o'qish uchun narsa");
    assert.equal(r[0].tr, "o'qish uchun mo'ljallangan narsa bu", 'hech narsa o\'chirilmadi'); assert.equal(r[0].status, 'review');
    assert.equal(r[1].status, 'review'); assert(r[1].removed.includes("o'qish uchun narsa"));
    const amb = V.imp.parse('stone tosh'); assert.equal(amb[0].status, 'review', "chegarasi noaniq qator tekshirishga");
    assert.equal(amb[0].en + '|' + amb[0].tr, 'stone|tosh'); assert.equal(amb[0].ok, false); assert(amb[0].reasons.length);
  });
  await t('Ko\'p so\'zli iboralar to\'liq saqlanadi (a, up, after, to ... olib tashlanmaydi)', () => {
    const r = V.imp.parse('take a photo — suratga olmoq\nlook after — qaramoq\ngive up — taslim bo\'lmoq\nto be or not to be — bo\'lish yoki bo\'lmaslik\nlook forward to — intilib kutmoq\nin spite of — qaramay');
    assert.deepEqual(r.map((e) => e.en), ['take a photo', 'look after', 'give up', 'to be or not to be', 'look forward to', 'in spite of']);
  });
  await t('O\'zbek harflari va apostrof variantlari saqlanadi', () => {
    const txt = "choose — tanlamoq\ngrow — o‘smoq\nway — yo‘l\nhelp — g‘amxo‘rlik qilmoq\nlook after — g'amxo’rlik qilmoq\nshare — ulashmoq (bo'lishmoq)\ncity — shahar, ʻmegapolisʼ";
    const r = V.imp.parse(txt);
    assert.equal(r[1].tr, 'o‘smoq'); assert.equal(r[2].tr, 'yo‘l'); assert.equal(r[3].tr, 'g‘amxo‘rlik qilmoq'); assert.equal(r[4].tr, 'g\'amxo’rlik qilmoq'); assert.equal(r[5].tr, "ulashmoq (bo'lishmoq)");
    assert(V.norm('o‘smoq') === V.norm("o'smoq") && V.norm('g‘amxo‘rlik') === V.norm("g'amxo'rlik"), 'variantlar tekshiruvda teng');
    const s = V.createSession('Uz'); V.imp.commitSync(s, r); assert.equal(V.words(s)[1].tr[0], 'o‘smoq');
    assert(V.grade(s, { type: 'type', dir: 'en-tr', w: V.words(s)[1].id }, "o'smoq").ok, "o‘ va o' bir xil qabul qilinadi");
  });
  await t('Takrorlar: importda va sessiyada aniqlanadi; hech narsa o\'chirilmaydi/qayta yozilmaydi', () => {
    const s = V.createSession('S'); V.addWord(s, { en: 'apple', tr: 'olma' }); const wid = V.words(s)[0].id; V.session(s).progress[wid] = { box: 3, seen: 5, correct: 4, wrong: 1, streak: 2, fix: 0, due: 1, last: 1, mistake: false }; V.save();
    const r = V.imp.parse('Apple — qizil meva\nbook — kitob\nbook — kitob\nBOOK - kitob', { existing: V.imp.existingMap(s) });
    assert.deepEqual(r.map((e) => e.status), ['duplicate', 'valid', 'duplicate', 'duplicate']); assert.equal(r[0].dup.kind, 'session'); assert.equal(r[2].dup.kind, 'import');
    const c = V.imp.counts(r); assert.equal(c.total, 4); assert.equal(c.valid, 1); assert.equal(c.duplicates, 3); assert.equal(c.ready, 1);
    V.imp.commitSync(s, r); assert.equal(V.words(s).length, 2); assert.deepEqual(V.session(s).words[wid].tr, ['olma'], 'mavjud so\'z o\'zgarmadi'); assert.equal(V.session(s).progress[wid].correct, 4, 'progress saqlandi');
    r[0].allowDup = true; V.imp.revalidate(r, V.imp.existingMap(s)); assert(r[0].ok === true, 'foydalanuvchi tanlasa takror qo\'shiladi');
  });
  await t('Matnda tarjima yo\'q (faqat inglizcha) — tarjima to\'qilmaydi; noto\'g\'ri qatorlar yo\'qolmaydi', () => {
    const r = V.imp.parse('apple\nbanana\n/teɪk/ — olma\n— ertaga\n12345 — 678');
    assert.deepEqual(r.map((e) => e.status), ['incomplete', 'incomplete', 'invalid', 'invalid', 'invalid']); assert.equal(r[0].tr, ''); assert.equal(r.length, 5, 'hech qator jimgina tashlab yuborilmadi');
    assert(r.every((e) => !e.ok)); assert.equal(V.imp.commitSync(V.createSession('E'), r).added.length, 0);
    r[0].tr = 'olma'; V.imp.revalidate(r, null); assert.equal(r[0].status, 'valid', 'qo\'lda kiritilgach to\'g\'ri');
  });
  await t('Qator tartibi va bo\'sh qatorlar, \\r\\n, ortiqcha bo\'shliqlar', () => {
    const r = V.imp.parse('\r\n  b — 2  \r\n\r\n\t\t\r\n a  —  1\r\nc — 3\r\n'); assert.deepEqual(r.map((e) => e.en), ['b', 'a', 'c']); assert.deepEqual(r.map((e) => e.line), [2, 5, 6]);
    assert.deepEqual(r.map((e) => e.tr), ['2', '1', '3']);
  });
  await t('Ko\'p miqdor: 100, 500, 2000 yozuv tez tahlil qilinadi va saqlanadi (O(n) saqlash)', async () => {
    const mk = (N) => Array.from({ length: N }, (_, i) => `word${String.fromCharCode(97 + i % 26)}${i} /wɜːd/ – tarjima${i} qilmoq izoh ${i}`).join('\n');
    for (const N of [100, 500, 2000]) {
      const T = Date.now(); const rows = await V.imp.parseAsync(mk(N), {}, () => {}); const tp = Date.now() - T;
      assert.equal(rows.length, N); assert(rows.every((e) => e.status === 'valid')); assert.equal(rows[N - 1].tr, `tarjima${N - 1} qilmoq`.replace('tarjima', 'tarjima')); assert(tp < 3000, `parse ${N}: ${tp}ms`);
      const s = V.createSession('Big' + N); let progress = 0; const T2 = Date.now(); const r = await V.imp.commit(s, rows, (p) => { progress = p; }); const tc = Date.now() - T2;
      assert.equal(r.added, N); assert.equal(V.words(s).length, N); assert.equal(progress, 1); assert(tc < 3000, `commit ${N}: ${tc}ms`);
      assert.deepEqual(V.words(s).slice(0, 3).map((w) => w.en), rows.slice(0, 3).map((e) => e.en), 'tartib saqlandi');
      console.log(`      ${N} ta: tahlil ${tp} ms, saqlash ${tc} ms`);
    }
  });
  await t('Import saqlanishidan oldin hech narsa yozilmaydi (oldindan ko\'rish)', () => {
    const st = makeStorage(), W = page(st), s = W.createSession('Pre'); const before = JSON.stringify(st._m);
    const rows = W.imp.parse(FMT_A + '\n' + FMT_B, { existing: W.imp.existingMap(s) }); W.imp.revalidate(rows, W.imp.existingMap(s)); W.imp.counts(rows);
    assert.equal(JSON.stringify(st._m), before, 'tahlil/tuzatish storage\'ni o\'zgartirmadi'); assert.equal(W.words(s).length, 0);
    W.imp.commitSync(s, rows); assert(W.words(s).length > 0);
  });
  await t('Sessiya izolyatsiyasi: A ga import B ga ta\'sir qilmaydi; bir xil so\'z turli sessiyalarda mustaqil', () => {
    const W = page(makeStorage()), a = W.createSession('A'), b = W.createSession('B');
    W.imp.commitSync(a, W.imp.parse(FMT_B)); assert.equal(W.words(a).length, 4); assert.equal(W.words(b).length, 0);
    W.imp.commitSync(b, W.imp.parse('apple — olma\ndiscover — kashf qilmoq', { existing: W.imp.existingMap(b) })); assert.equal(W.words(b).length, 2, 'apple A da bo\'lsa ham B ga qo\'shiladi (takror emas)');
    const wa = W.words(a).find((w) => w.en === 'apple'), wb = W.words(b).find((w) => w.en === 'apple'); assert.notEqual(wa.id, wb.id);
    W.session(a).progress[wa.id] = { box: 4, seen: 9, correct: 9, wrong: 0, streak: 9, fix: 0, due: 1, last: 1, mistake: false }; W.save();
    assert.equal(W.stats(b).mastered, 0); assert.equal(W.stats(a).mastered, 1);
    for (const sid of [a, b]) for (const mode of ['learn', 'test']) { const other = sid === a ? ['discover', 'kashf'] : ['tomorrow', 'ertaga', 'improve', 'yaxshilamoq']; const q = JSON.stringify(W.startRun(sid, mode, { fresh: true }).run.queue).toLowerCase(); other.forEach((x) => assert(!q.includes(x), `${mode}: ${x} sizib chiqdi`)); }
    const dup = W.imp.parse('apple — olma', { existing: W.imp.existingMap(a) }); assert.equal(dup[0].status, 'duplicate', 'A ichida takror');
  });
  await t('OCR: rasm matni (shovqinli) — tartib, talaffuz va tavsif tozalanadi; ro\'yxat tahrirlanadi', async () => {
    // Haqiqiy Tesseract natijasi (brauzer testida o'lchangan): IPA buzilgan, o→a, q→g xatolari
    const real = "1. take a photo /te1k a 'fautau/ — suratga olmoq\n2. tomorrow — ertaga\n\n3. look after — g'amxa'rlik gilmoq\n\n4. apple — olma\n\n5. improve — yaxshilamoq\n";
    V.ocr.engine = async (file) => ({ text: real, confidence: 88 });
    const out = await V.ocr.recognize({ name: 'list.png', type: 'image/png' }); assert.equal(out.confidence, 88);
    const rows = V.imp.parse(out.text, { src: 'rasm: list.png' });
    assert.deepEqual(pick(rows), [['take a photo', 'suratga olmoq'], ['tomorrow', 'ertaga'], ['look after', "g'amxa'rlik gilmoq"], ['apple', 'olma'], ['improve', 'yaxshilamoq']]);
    assert.equal(rows[0].pron, "/te1k a 'fautau/"); assert(rows.every((e) => e.src === 'rasm: list.png'));
    rows[2].tr = "g'amxo'rlik qilmoq"; V.imp.revalidate(rows); assert.equal(V.imp.counts(rows).ready, 5, 'OCR xatosi tuzatilgach import qilinadi');
    // faqat inglizcha rasm: tarjima to'qilmaydi
    V.ocr.engine = async () => 'apple\nbanana\nto give up\n'; const eo = V.imp.parse((await V.ocr.recognize({ name: 'e.jpg', type: 'image/jpeg' })).text);
    assert.deepEqual(eo.map((e) => e.status), ['incomplete', 'incomplete', 'incomplete']); assert(eo.every((e) => e.tr === ''));
    // qo'llab-quvvatlanmaydigan format rad etiladi (haqiqiy yo'lda)
    V.ocr.engine = null; await assert.rejects(V.ocr.recognize({ name: 'a.gif', type: 'image/gif', size: 10 }), /JPG, PNG va WebP/);
    assert(V.ocr.accepted({ name: 'x.JPEG', type: '' }) && V.ocr.accepted({ name: 'x.webp', type: 'image/webp' }) && !V.ocr.accepted({ name: 'x.pdf', type: 'application/pdf' }));
    assert.equal(V.ocr.needsInternet(), true, 'standart sozlama internet talab qiladi');
  });
  await t('Import saqlanganidan keyin sahifa yangilanganda ham qoladi', () => {
    const st = makeStorage(); let W = page(st); const s = W.createSession('Persist'); const r = W.imp.parse(FMT_A + '\n' + FMT_B); W.imp.commitSync(s, r);
    const before = JSON.stringify(W.words(s).map((w) => [w.en, w.tr, w.pron]));
    W = page(st); W.load();   // yangi kontekst = "sahifa yangilandi"
    assert.equal(JSON.stringify(W.words(s).map((w) => [w.en, w.tr, w.pron])), before); assert.equal(W.words(s)[0].pron, '/teɪk ə ˈfəʊtəʊ/'); assert.equal(W.words(s).length, 6, 'FMT_A+FMT_B: 7 qator, 1 tasi takror → 6 so\'z');
  });
  console.log('\n' + n + " ta import testi o'tdi");
})().catch((e) => { console.error('XATO:', e); process.exit(1); });
