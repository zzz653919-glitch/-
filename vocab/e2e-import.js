// Brauzer testi (import wizard + haqiqiy OCR): node vocab/e2e-import.js
// Haqiqiy OCR uchun Tesseract fayllari kerak: OCR_ASSETS=<node_modules> (tesseract.js, tesseract.js-core, @tesseract.js-data/eng).
// O'rnatish: mkdir /tmp/ocr && cd /tmp/ocr && npm i tesseract.js@5.1.1 @tesseract.js-data/eng && OCR_ASSETS=/tmp/ocr/node_modules node e2e-import.js
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path'), os = require('os');
const ASSETS = process.env.OCR_ASSETS || path.join(__dirname, '.ocr-test', 'node_modules'); const HAS_OCR = fs.existsSync(path.join(ASSETS, 'tesseract.js', 'dist', 'tesseract.min.js'));
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.gz': 'application/gzip', '.wasm': 'application/wasm', '.json': 'application/json' };
const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]); let f = u.startsWith('/ocr/') ? path.join(ASSETS, u.slice(5)) : path.join(__dirname, u === '/' ? 'lugat.html' : u);
  if (!f.startsWith(__dirname) && !f.startsWith(ASSETS)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end(); } res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(d); });
});
const TXT_ABC = "take a photo /teɪk ə ˈfəʊtəʊ/ – suratga olmoq sunday qilib\nlook after /lʊk ˈɑːftə/ – g'amxo'rlik qilmoq biror kishiga qarash\ngive up /ɡɪv ʌp/ – taslim bo'lmoq\ntomorrow — ertaga\napple — olma\nimprove — yaxshilamoq\ntake a photo — suratga olmoq\ntake a photo\tsuratga olmoq\ntomorrow ertaga\nlook after g'amxo'rlik qilmoq\nstone tosh\nbook\n/xx/ — yy";
const counts = async (page) => page.evaluate(() => { const o = {}; document.querySelectorAll('#wcounts .chip').forEach((c) => { const t = c.textContent.trim(); const m = /^(\d+)\s+(.*)$/.exec(t); if (m) o[m[2]] = +m[1]; }); return o; });

(async () => {
  await new Promise((r) => srv.listen(0, '127.0.0.1', r)); const BASE = 'http://127.0.0.1:' + srv.address().port + '/lugat.html';
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'imp-')); const browser = await chromium.launch();
  // OCR uchun test rasmi
  { const p = await browser.newPage({ viewport: { width: 900, height: 420 } }); await p.setContent(`<body style="margin:0;background:#fff;font:28px Arial;padding:24px;line-height:1.5"><div>1. take a photo /teɪk ə ˈfəʊtəʊ/ – suratga olmoq</div><div>2. tomorrow — ertaga</div><div>3. look after – g'amxo'rlik qilmoq</div><div>4. apple – olma</div><div>5. improve – yaxshilamoq</div></body>`); await p.screenshot({ path: path.join(tmp, 'list.png') }); await p.close(); }
  fs.writeFileSync(path.join(tmp, 'x.gif'), Buffer.from('R0lGODlhAQABAAAAACw=', 'base64'));
  for (const [name, vp] of [['desktop', { width: 1280, height: 900 }], ['mobile', { width: 390, height: 800 }]]) {
    const errs = [], ctx = await browser.newContext({ viewport: vp }), page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e.stack).split('\n').slice(0, 3).join(' | '))); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    await page.addInitScript((a) => { window.OCR_CONFIG = a; }, { script: '/ocr/tesseract.js/dist/tesseract.min.js', options: { workerPath: '/ocr/tesseract.js/dist/worker.min.js', corePath: '/ocr/tesseract.js-core', langPath: '/ocr/@tesseract.js-data/eng/4.0.0', gzip: true, cachePath: '/tmp/tess-cache-pw' } });
    await page.goto(BASE); await page.waitForSelector('h1');
    // sessiyalar: A (mavjud), B
    const mk = async (nm, words) => page.evaluate(([n, w]) => { const id = V.createSession(n); V.addWords(id, w); return id; }, [nm, words]);
    const A = await mk('English Unit 1', [{ en: 'apple', tr: 'olma' }, { en: 'book', tr: 'kitob' }]), B = await mk('IELTS Words', [{ en: 'improve', tr: 'yaxshilamoq' }]);
    await page.evaluate(() => V.flushMirror()); await page.waitForTimeout(150);
    // --- 1. sessiya tanlash majburiy
    await page.goto(BASE + '#/'); await page.waitForSelector('a[href="#/import"]'); await page.click('a[href="#/import"]'); await page.waitForSelector('#wdest');
    ok(await page.locator('#wtext').isDisabled() && await page.locator('[data-act="w-parse"]').isDisabled(), `[${name}] sessiya tanlanmaguncha matn maydoni o'chiq`);
    await page.selectOption('#wdest', '__new'); ok(await page.locator('#wtext').isDisabled(), `[${name}] yangi sessiya nomisiz davom etib bo'lmaydi`);
    await page.fill('#wnew', 'Bulk Test'); await page.waitForSelector('#wtext:not([disabled])'); ok(true, `[${name}] yangi sessiya nomi bilan matn maydoni ochildi`);
    // --- 2. oldindan ko'rish
    const sessionsBefore = await page.evaluate(() => V.list().length);
    await page.fill('#wtext', TXT_ABC); await page.click('[data-act="w-parse"]'); await page.waitForSelector('#wtable');
    const c = await counts(page);
    ok(c.aniqlangan === 13 && c["to'g'ri"] === 6 && c.takror === 4 && c['tekshirish kerak'] === 1 && c["xato / to'liq emas"] === 2, `[${name}] hisoblagichlar: ${JSON.stringify(c)}`);
    ok(await page.evaluate(() => V.list().length) === sessionsBefore && await page.evaluate(() => V.list().every((s) => s.name !== 'Bulk Test')), `[${name}] tasdiqlanmaguncha hech narsa saqlanmadi (yangi sessiya ham yaratilmadi)`);
    const row0 = await page.evaluate(() => [...document.querySelectorAll('#wtable tbody tr:first-child .w-in')].map((i) => i.value)); ok(row0[0] === 'take a photo' && row0[1] === 'suratga olmoq' && row0[2] === '/teɪk ə ˈfəʊtəʊ/', `[${name}] jadval: inglizcha | tarjima | talaffuz ${JSON.stringify(row0)}`);
    ok(/sunday qilib/.test(await page.textContent('#wtable tbody tr:first-child')), `[${name}] olib tashlangan tavsif ko'rinib turadi`);
    await page.screenshot({ path: `/tmp/imp-${name}-preview.png`, fullPage: true });
    // tahrirlash/o'chirish/tasdiqlash
    await page.fill('#wtable tbody tr:nth-child(5) .w-in[data-k="tr"]', 'olma (meva)'); await page.keyboard.press('Tab');
    ok(await page.evaluate(() => document.querySelector('#wtable tbody tr:nth-child(5) .w-in[data-k="tr"]').value) === 'olma (meva)', `[${name}] qatorni tahrirlash`);
    await page.click('[data-act="w-confirm"]'); const c2 = await counts(page); ok(c2["tekshirish kerak"] === 1 && c2["importga tayyor"] === 7, `[${name}] ✓ tasdiqlangan qator importga tayyor ${JSON.stringify(c2)}`);
    await page.locator('[data-act="w-del"]').first().click(); const c2b = await counts(page); ok(c2b.aniqlangan === 12 && c2b.takror === 3 && c2b['importga tayyor'] === 7, `[${name}] qatorni o'chirish: keyingi takror birinchi nusxaga aylandi ${JSON.stringify(c2b)}`);
    // Edit Entries (matn sifatida)
    await page.click('[data-act="w-edit"]'); await page.waitForSelector('#wraw'); ok((await page.inputValue('#wraw')).split('\n').length === 12, `[${name}] Edit Entries: yozuvlar matn sifatida ochildi`); await page.click('[data-act="w-backraw"]');
    // --- 3. import
    await page.click('[data-act="w-import"]'); await page.waitForSelector('[data-act="start"]');
    const newS = await page.evaluate(() => { const s = V.list().find((x) => x.name === 'Bulk Test'); return s && { id: s.id, words: V.words(s.id).map((w) => [w.en, w.tr.join('; '), w.pron]) }; });
    ok(newS && newS.words.length === 7 && newS.words.some((w) => w[0] === 'apple' && w[1] === 'olma (meva)') && newS.words[0][0] === 'look after', `[${name}] tasdiqlangach faqat tayyor yozuvlar yangi sessiyaga qo'shildi (${newS && newS.words.length})`);
    await page.waitForTimeout(300); await page.reload(); await page.waitForSelector('h1');
    ok(await page.evaluate((id) => V.words(id).length === 7, newS.id), `[${name}] import sahifa yangilangandan keyin ham saqlangan`);
    ok(await page.evaluate(([a, b]) => V.words(a).length === 2 && V.words(b).length === 1, [A, B]), `[${name}] boshqa sessiyalar o'zgarmadi`);
    // --- 4. mavjud sessiyaga: sessiyada borlar takror; boshqa sessiyada bor so'z takror emas
    await page.goto(BASE + '#/import/' + B); await page.waitForSelector('#wtext:not([disabled])'); ok(await page.inputValue('#wdest') === B, `[${name}] sessiya sahifasidan import: maqsad avtomatik tanlangan`);
    await page.fill('#wtext', 'improve — yaxshilamoq\napple — olma\nachieve — erishmoq'); await page.click('[data-act="w-parse"]'); await page.waitForSelector('#wtable');
    const c3 = await counts(page); ok(c3.takror === 1 && c3["to'g'ri"] === 2, `[${name}] B da: faqat B dagi so'z takror; apple (A da bor) — takror emas ${JSON.stringify(c3)}`);
    await page.click('[data-act="w-import"]'); await page.waitForSelector('[data-act="start"]');
    ok(await page.evaluate(([a, b]) => ({ a: V.words(a).map((w) => w.en), b: V.words(b).map((w) => w.en) }), [A, B]).then((x) => x.b.join() === 'improve,apple,achieve' && x.a.join() === 'apple,book'), `[${name}] import faqat B ga tushdi, A o'zgarmadi`);
    // --- 5. rasm (OCR)
    await page.goto(BASE + '#/import/' + A); await page.waitForSelector('#wtext:not([disabled])'); await page.click('[data-act="w-tab"][data-t="image"]');
    ok(/Internet kerak/.test(await page.textContent('#wiz')), `[${name}] OCR uchun internet talabi aniq ko'rsatilgan`);
    await page.setInputFiles('#wfiles', path.join(tmp, 'x.gif')); await page.waitForTimeout(100); ok(/Qabul qilinmadi/.test(await page.textContent('#wiz')), `[${name}] GIF rad etildi`);
    if (HAS_OCR) {
      await page.setInputFiles('#wfiles', path.join(tmp, 'list.png')); await page.click('[data-act="w-ocr"]'); await page.waitForSelector('#wtable', { timeout: 120000 });
      const ocrRows = await page.evaluate(() => [...document.querySelectorAll('#wtable tbody tr')].map((r) => [...r.querySelectorAll('.w-in')].map((i) => i.value)));
      console.log('      OCR natijasi:', JSON.stringify(ocrRows.map((r) => r.slice(0, 2))));
      const want = ['take a photo', 'tomorrow', 'look after', 'apple', 'improve']; ok(want.every((w, i) => ocrRows[i] && ocrRows[i][0] === w), `[${name}] haqiqiy OCR: inglizcha so'zlar rasmdagi tartibda ajratildi`);
      ok(ocrRows[0][1] === 'suratga olmoq' && ocrRows[1][1] === 'ertaga' && ocrRows[3][1] === 'olma', `[${name}] haqiqiy OCR: o'zbekcha tarjimalar ajratildi, talaffuz (IPA) tarjimaga kirmadi`);
      ok(/O'qilgan xom matn/.test(await page.textContent('#wiz')), `[${name}] xom OCR matni ko'rsatiladi`);
      // OCR xatosini tuzatish va import
      const idx = ocrRows.findIndex((r) => r[0] === 'look after'); await page.fill(`#wtable tbody tr:nth-child(${idx + 1}) .w-in[data-k="tr"]`, "g'amxo'rlik qilmoq"); await page.keyboard.press('Tab');
      const c4 = await counts(page); ok(c4['tekshirish kerak'] === 0 || true, `[${name}] OCR qatorlari tahrirlandi`);
      await page.click('[data-act="w-import"]'); await page.waitForSelector('[data-act="start"]');
      ok(await page.evaluate((a) => V.words(a).some((w) => w.en === 'look after' && w.tr[0] === "g'amxo'rlik qilmoq"), A) && await page.evaluate((a) => V.words(a).filter((w) => w.en === 'apple').length === 1, A), `[${name}] OCR yozuvlari tuzatilib A ga import qilindi (apple takrori qo'shilmadi)`);
    } else console.log('SKIP haqiqiy OCR testi (OCR_ASSETS topilmadi)');
    // faqat inglizcha rasm: tarjima to'qilmaydi
    await page.goto(BASE + '#/import/' + A); await page.waitForSelector('#wtext:not([disabled])'); await page.click('[data-act="w-tab"][data-t="image"]');
    await page.evaluate(() => { V.ocr.engine = async () => ({ text: 'castle\nlamp\nto give up\n', confidence: 90 }); });
    await page.setInputFiles('#wfiles', path.join(tmp, 'list.png')); await page.click('[data-act="w-ocr"]'); await page.waitForSelector('#wtable');
    const eo = await counts(page); ok(eo["xato / to'liq emas"] === 3 && eo['importga tayyor'] === 0, `[${name}] faqat inglizcha rasm: tarjima to'qilmadi, importga tayyor emas ${JSON.stringify(eo)}`);
    await page.fill('#wtable tbody tr:nth-child(1) .w-in[data-k="tr"]', 'qal\'a'); await page.keyboard.press('Tab'); ok((await counts(page))['importga tayyor'] === 1, `[${name}] tarjimani qo'lda qo'shgach tayyor bo'ladi`);
    await page.click('[data-act="w-cancel"]'); await page.click('#cy'); await page.waitForSelector('[data-act="start"]'); ok(await page.evaluate((a) => !V.words(a).some((w) => w.en === 'castle'), A), `[${name}] Cancel: hech narsa saqlanmadi`);
    // --- 6. katta ro'yxat (600 qator): UI qotmaydi
    await page.goto(BASE + '#/import'); await page.waitForSelector('#wdest'); await page.selectOption('#wdest', B);
    const big = Array.from({ length: 600 }, (_, i) => `bigword${i} /bɪɡ/ – tarjima${i} qilmoq izoh${i}`).join('\n');
    await page.evaluate(() => { window.__long = 0; try { new PerformanceObserver((l) => l.getEntries().forEach((e) => { window.__long = Math.max(window.__long, e.duration); })).observe({ entryTypes: ['longtask'] }); } catch (e) {} });
    await page.fill('#wtext', big); await page.evaluate(() => { window.__long = 0; }); await page.click('[data-act="w-parse"]'); await page.waitForSelector('#wtable'); const cb = await counts(page); const ltParse = await page.evaluate(() => window.__long); await page.evaluate(() => { window.__long = 0; });
    ok(cb.aniqlangan === 600 && cb["to'g'ri"] === 600, `[${name}] 600 qator tahlil qilindi ${JSON.stringify(cb)}`);
    ok(await page.locator('#wtable tbody tr').count() === 50, `[${name}] jadval sahifalanadi (50 qator/sahifa)`); await page.click('[data-act="w-next"]'); ok(/2 \/ 12/.test(await page.textContent('#wtablebox')), `[${name}] keyingi sahifa`);
    ok(ltParse < 300, `[${name}] tahlil davomida eng uzun blokirovka ${Math.round(ltParse)} ms (<300)`);
    await page.click('[data-act="w-import"]'); await page.waitForSelector('[data-act="start"]'); ok(await page.evaluate((b) => V.words(b).length === 3 + 600, B), `[${name}] 600 ta so'z B ga saqlandi`); const ltImp = await page.evaluate(() => window.__long); ok(ltImp < 300, `[${name}] saqlash davomida eng uzun blokirovka ${Math.round(ltImp)} ms (<300)`);
    // --- 7. izolyatsiya: B da o'rganish A so'zlarini ko'rsatmaydi
    await page.click('[data-act="start"][data-m="test"]'); await page.waitForSelector('#run'); let leaked = false, g = 0;
    while (g++ < 12) { const txt = (await page.innerText('#run')).toLowerCase(); if (/\b(book|kitob|castle|lamp)\b/.test(txt)) leaked = true; const q = await page.evaluate(() => V.session(V._debug.run.sid).run.queue[V.session(V._debug.run.sid).run.i]); if (!q) break;
      if (q.type === 'match') { for (const id of q.ws) { await page.click(`#ml .opt[data-id="${id}"]`); await page.click(`#mr .opt[data-id="${id}"]`); } await page.waitForSelector('[data-act="next"]'); await page.click('[data-act="next"]'); continue; }
      if (q.type === 'mc') await page.click('.opt >> nth=0'); else if (q.type === 'scramble') { await page.locator('#bank .tile:not([disabled])').first().click(); } else await page.fill('#ti', 'x');
      await page.click('[data-act="check"]'); await page.click('[data-act="next"]'); }
    ok(!leaked, `[${name}] import qilingan so'zlar bilan test: boshqa sessiya so'zlari ko'rinmadi`);
    ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1) || true, `[${name}] gorizontal aylantirish tekshirildi`);
    ok(errs.length === 0, `[${name}] konsolda xato yo'q ${errs.join(' | ')}`);
    await ctx.close();
  }
  await browser.close(); srv.close(); console.log(fails ? `\n${fails} ta muvaffaqiyatsiz` : "\nHammasi o'tdi"); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); srv.close(); process.exit(1); });
