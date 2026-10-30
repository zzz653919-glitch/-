// Brauzer testi: node vocab/e2e.js  (lugat.html ni file:// orqali ochadi; Playwright kerak)
const { chromium } = require('playwright'); const path = require('path');
const URL_ = 'file://' + path.join(__dirname, 'lugat.html');
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const A = 'apple - olma\nbook - kitob\nwindow - deraza\ntable - stol\nchair - stul', B = 'improve - yaxshilamoq\nachieve - erishmoq\ndiscover - kashf qilmoq\nbuild - qurmoq\nenjoy - zavqlanmoq';
const A_ALL = ['apple', 'book', 'window', 'table', 'chair', 'olma', 'kitob', 'deraza', 'stol', 'stul'], B_ALL = ['improve', 'achieve', 'discover', 'build', 'enjoy', 'yaxshilamoq', 'erishmoq', 'kashf qilmoq', 'qurmoq', 'zavqlanmoq'];
const leak = (text, list) => list.filter((w) => new RegExp("(^|[^a-z'])" + w + "([^a-z']|$)", 'i').test(text));

async function answerCurrent(page) {
  const q = await page.evaluate(() => { const s = V.session(V._debug.run.sid); return { q: s.run.queue[s.run.i], sid: s.id }; });
  const w = await page.evaluate(({ sid, id }) => V.session(sid).words[id], { sid: q.sid, id: q.q.w });
  const t = q.q.type;
  if (t === 'study') { await page.click('[data-act="study-next"]'); return; }
  if (t === 'flash') {
    if (q.q.n % 2 === 0) {   // yozma javob
      ok(await page.locator('#ti').count() === 1, `flash karta: javob yozish maydoni bor`);
      await page.fill('#ti', q.q.dir === 'en-tr' ? w.tr[0] : w.en); await page.click('[data-act="check"]'); await page.click('[data-act="next"]'); return;
    }
    await page.click('[data-act="reveal"]'); await page.click('[data-act="know"]'); await page.click('[data-act="next"]'); return;   // ko'rsatib, o'zini baholash
  }
  if (t === 'mc') { const i = await page.evaluate(({ sid, qn }) => qn.options.findIndex((o) => V.grade(sid, qn, o).ok), { sid: q.sid, qn: q.q }); await page.click(`.opt[data-i="${i}"]`); }
  else if (t === 'type') await page.fill('#ti', q.q.dir === 'en-tr' ? w.tr[0] : w.en);
  else if (t === 'spell') await page.fill('#ti', w.en);
  else if (t === 'scramble') for (const ch of w.en.replace(/[^A-Za-z]/g, '')) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + ch + '$') }).first().click();
  else if (t === 'match') { for (const id of q.q.ws) { await page.click(`#ml .opt[data-id="${id}"]`); await page.click(`#mr .opt[data-id="${id}"]`); } await page.waitForSelector('[data-act="next"]'); await page.click('[data-act="next"]'); return; }
  if (t !== 'match') { await page.click('[data-act="check"]'); await page.click('[data-act="next"]'); }
}
async function createSession(page, name, text) {
  await page.goto(URL_ + '#/'); await page.click('[data-act="new"]'); await page.fill('#nn', name); await page.click('#nf .btn.p'); await page.waitForSelector('#wform');
  await page.click('a[href^="#/import/"]'); await page.waitForSelector('#wtext:not([disabled])'); await page.fill('#wtext', text); await page.click('[data-act="w-parse"]'); await page.waitForSelector('#wtable'); await page.click('[data-act="w-import"]'); await page.waitForSelector('#wlist table');
}
(async () => {
  const browser = await chromium.launch();
  for (const [name, vp] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 780 }]]) {
    const errs = [], ctx = await browser.newContext({ viewport: vp }), page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e.stack).split('\n').slice(0, 3).join(' | '))); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    // eski Til Yo'li ma'lumoti (migratsiya testi): faqat yangi lug'at ma'lumoti bo'lmasa
    await page.addInitScript(() => { if (!localStorage.getItem('vocab:v1') && !localStorage.getItem('tilyoli:data:ali')) { localStorage.setItem('tilyoli:data:ali', JSON.stringify({ v: 2, xp: 40, words: { '0.0.0': { c: 3, w: 1 }, '0.0.1': { c: 1, w: 0 } }, mistakes: { '0.0.1': { n: 1, ok: 0 } }, done: {} })); localStorage.setItem('tilyoli:users', '{"ali":{"name":"Ali"}}'); } });
    await page.goto(URL_); await page.waitForSelector('h1');
    ok(/Migratsiya/.test(await page.textContent('#main')) && await page.locator('.scard').count() === 1, `[${name}] eski saqlangan lug'at migratsiya qilindi va xabar ko'rsatildi`);
    ok(await page.evaluate(() => localStorage.getItem('tilyoli:data:ali') !== null && localStorage.getItem('tilyoli:users') !== null), `[${name}] eski kalitlar o'chirilmadi`);
    await createSession(page, 'English Unit 1', A); const idA = await page.evaluate(() => V.activeId());
    await createSession(page, 'IELTS Words', B); const idB = await page.evaluate(() => V.activeId());
    ok(idA !== idB, `[${name}] A va B sessiyalari yaratildi`);
    await page.goto(URL_ + '#/'); ok(await page.locator('.scard').count() === 3, `[${name}] panelda 3 ta sessiya kartasi`);
    await page.screenshot({ path: `/tmp/voc-${name}-home.png` });
    await page.fill('#sq', 'ielts'); ok(await page.locator('.scard').count() === 1, `[${name}] sessiya qidirish`); await page.fill('#sq', '');
    // A: butun raund — har bir ekranda B so'zi bo'lmasligi
    for (const [sid, other, nm] of [[idA, B_ALL, 'A'], [idB, A_ALL, 'B']]) {
      await page.goto(URL_ + '#/s/' + sid); await page.waitForSelector('[data-act="start"]');
      ok((await page.locator('.top .chip').first().textContent()).includes(nm === 'A' ? 'English Unit 1' : 'IELTS Words'), `[${name}] faol sessiya yuqorida ko'rinadi (${nm})`);
      const pageLeak = leak(await page.innerText('#main'), other); ok(pageLeak.length === 0, `[${name}] ${nm} sahifasida boshqa sessiya so'zlari yo'q`);
      await page.click('[data-act="start"][data-m="learn"]'); await page.waitForSelector('#run'); let g = 0, leaked = [], types = new Set();
      while (await page.locator('#run .r-body.center').count() === 0 && g++ < 80) {
        leaked = leaked.concat(leak(await page.innerText('#run'), other)); types.add(await page.evaluate(() => V._debug.run && V.session(V._debug.run.sid).run.queue[V.session(V._debug.run.sid).run.i].type));
        if (g === 5) await page.screenshot({ path: `/tmp/voc-${name}-run.png` });
        if (await page.locator('#run .r-body.center').count()) break; await answerCurrent(page);
      }
      ok(await page.locator('#run .r-body.center').count() === 1, `[${name}] ${nm}: raund tugadi (${[...types].join(',')})`);
      ok(leaked.length === 0, `[${name}] ${nm}: butun raund davomida boshqa sessiya so'zlari ekranda chiqmadi ${leaked.join(',')}`);
      await page.screenshot({ path: `/tmp/voc-${name}-result-${nm}.png` });
      ok(!leak(await page.innerText('#run'), other).length, `[${name}] ${nm}: natijalar ekrani faqat o'z so'zlari`);
    }
    // sessiyaga xos statistika
    const stats = await page.evaluate(([a, b]) => ({ a: V.stats(a), b: V.stats(b) }), [idA, idB]);
    ok(stats.a.rounds === 1 && stats.b.rounds === 1 && stats.a.total === 5, `[${name}] progress sessiyaga xos (A: ${stats.a.learning} o'rganilmoqda)`);
    // yangilashdan keyin davom etish
    await page.goto(URL_ + '#/s/' + idA); await page.evaluate((s) => { V.restartSession(s); }, idA); await page.waitForTimeout(300); await page.reload(); await page.waitForSelector('[data-act="start"]', { timeout: 4000 }).catch(async (e) => { console.log('DEBUG', await page.evaluate(() => JSON.stringify({ h: location.hash, keys: Object.keys(localStorage), names: Object.values(JSON.parse(localStorage.getItem('vocab:v1')).sessions).map((s) => s.name), mem: Object.values(V.db().sessions).map((s) => s.name) }))); throw e; });
    await page.click('[data-act="start"][data-m="learn"]'); await page.waitForSelector('#run');
    for (let i = 0; i < 4; i++) await answerCurrent(page);
    const idx = await page.evaluate(() => V.session(V._debug.run.sid).run.i), len = await page.evaluate(() => V.session(V._debug.run.sid).run.queue.length);
    await page.waitForTimeout(300);   // brauzer yozuvni diskka o'tkazishi uchun (odam 0.3 s dan tez yangilay olmaydi)
    await page.reload(); await page.waitForSelector('#run');
    ok(await page.evaluate((i) => V.session(V._debug.run.sid).run.i === i, idx), `[${name}] sahifa yangilanganda raund ${idx}/${len} savoldan davom etdi`);
    ok((await page.textContent('[data-testid="session-chip"]')).includes('English Unit 1'), `[${name}] yangilanishdan keyin ham faol sessiya to'g'ri`);
    ok(!leak(await page.innerText('#run'), B_ALL).length, `[${name}] yangilangandan keyin ham B so'zlari yo'q`);
    // sessiyani almashtirish
    await page.click('[data-act="quit"]'); await page.click('[data-act="leave"]'); await page.waitForSelector('[data-act="resume"]'); ok(/Davom etish/.test(await page.textContent('[data-act="resume"]')), `[${name}] to'xtatilgan raund «Davom etish» bilan qaytadi`);
    await page.goto(URL_ + '#/s/' + idB); await page.waitForSelector('[data-act="start"]');
    ok(await page.evaluate((b) => V.activeId() === b, idB) && (await page.locator('.top .chip').first().textContent()).includes('IELTS Words'), `[${name}] sessiyani almashtirish faol sessiyani yangiladi`);
    // bo'sh sessiya
    await page.goto(URL_ + '#/'); await page.click('[data-act="new"]'); await page.fill('#nn', 'Bo\'sh'); await page.click('#nf .btn.p'); await page.waitForSelector('#wform');
    ok(/hali so'z yo'q/.test(await page.textContent('#main')) && await page.locator('[data-act="start"][data-m="learn"]:disabled').count() === 1, `[${name}] bo'sh sessiya: tushunarli xabar, boshlash o'chiq`);
    // xato javob: to'g'ri javob va tushuntirish
    await page.goto(URL_ + '#/s/' + idB); await page.click('[data-act="start"][data-m="learn"]'); await page.waitForSelector('#run');
    for (let i = 0; i < 40; i++) { const t = await page.evaluate(() => V.session(V._debug.run.sid).run.queue[V.session(V._debug.run.sid).run.i].type); if (t === 'type' || t === 'spell') break; await answerCurrent(page); }
    await page.fill('#ti', 'xatojavob'); await page.click('[data-act="check"]'); const msg = await page.textContent('#msg');
    ok(/To'g'ri javob/.test(msg), `[${name}] xato javobda to'g'ri javob ko'rsatildi`); await page.screenshot({ path: `/tmp/voc-${name}-wrong.png` });
    ok(await page.evaluate((b) => Object.values(V.session(b).progress).some((p) => p.mistake), idB), `[${name}] xato so'z shu sessiyada saqlandi`);
    ok(await page.evaluate((a) => !Object.values(V.session(a).progress).some((p) => p.mistake), idA), `[${name}] xato boshqa sessiyaga tushmadi`);
    // import: aynan kerakli sessiyaga
    ok(await page.evaluate(([a, b]) => V.words(a).length === 5 && V.words(b).length === 5, [idA, idB]), `[${name}] import so'zlarni kerakli sessiyaga qo'shdi`);
    await page.goto(URL_ + '#/settings'); await page.waitForSelector('h1'); await page.screenshot({ path: `/tmp/voc-${name}-settings.png` });
    ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `[${name}] gorizontal aylantirish yo'q`);
    await page.click('[data-act="theme"]'); ok(await page.evaluate(() => ['dark', 'light'].includes(document.documentElement.dataset.theme)), `[${name}] mavzu almashadi`);
    ok(errs.length === 0, `[${name}] konsolda xato yo'q ${errs.join(' | ')}`);
    await ctx.close();
  }
  await browser.close(); console.log(fails ? `\n${fails} ta muvaffaqiyatsiz` : "\nHammasi o'tdi"); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
