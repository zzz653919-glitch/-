// Brauzer testi: (web/ papkasida `python3 -m http.server 8080` ishlab turganda) node tests/e2e.js
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:8080/';
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };

async function solveCurrent(page, wrong) {
  // Joriy savolni haqiqiy UI orqali yechadi (javobni sessiya ichidan oladi)
  const q = await page.evaluate(() => { const c = TY._debug.session.current(); return c; });
  if (q.type === 'choice') {
    const idx = await page.evaluate((w) => { const c = TY._debug.session.current(); return c.options.findIndex(o => TY.checkText(o, c.answer).ok === !w); }, wrong);
    await page.click(`.opt[data-i="${idx}"]`);
  } else if (q.type === 'type') {
    await page.fill('#ti', wrong ? 'xxxx' : q.answer[0]);
  } else if (q.type === 'scramble') {
    const target = q.answer[0].toLowerCase().split('');
    for (const ch of (wrong ? target.reverse().concat([]) : target)) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + ch + '$', 'i') }).first().click();
  } else if (q.type === 'build') {
    for (const wd of (wrong ? q.answer[0].split(' ').reverse() : q.answer[0].split(' '))) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + wd + '$') }).first().click();
  } else if (q.type === 'match') {
    for (const id of q.ws) { await page.click(`#ml .opt[data-id="${id}"]`); await page.click(`#mr .opt[data-id="${id}"]`); }
    await page.waitForSelector('#primary[data-act="next"]'); return 'match';
  }
  await page.click('#primary[data-act="check"]');
  await page.waitForSelector('#primary[data-act="next"],#primary[data-act="hearts"]');
  return q.type;
}

(async () => {
  const browser = await chromium.launch();
  for (const [name, vp] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 780 }]]) {
    const ctx = await browser.newContext({ viewport: vp, hasTouch: name === 'mobile' });
    const page = await ctx.newPage(); await page.addInitScript(() => { try { localStorage.setItem('tilyoli:noauto', '1'); } catch (e) {} }); const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); }); page.on('pageerror', e => errs.push(String(e)));
    await page.goto(BASE); await page.waitForSelector('#af');
    ok(true, `[${name}] kirish oynasi ochildi`);
    await page.screenshot({ path: `/tmp/shot-${name}-login.png` });
    await page.click('#sw'); await page.fill('#u', 'Test' + name); await page.fill('#p', 'abcd'); await page.click('button[type=submit]');
    await page.waitForSelector('.hero'); ok(true, `[${name}] ro'yxatdan o'tish → bosh sahifa`);
    await page.screenshot({ path: `/tmp/shot-${name}-home.png`, fullPage: false });
    // Xarita
    await page.goto(BASE + '#/learn'); await page.waitForSelector('.node');
    ok(await page.locator('.node.lock').count() > 20, `[${name}] qulflangan darslar ko'rinadi`);
    await page.locator('.node.lock').first().click(); ok(await page.locator('.toast').count() > 0, `[${name}] qulflangan dars toast beradi`);
    await page.screenshot({ path: `/tmp/shot-${name}-map.png` });
    await page.locator('.node.cur').first().click(); await page.click('#go');
    await page.waitForSelector('[data-act="begin"]'); ok(true, `[${name}] dars tushuntirish ekrani`);
    await page.screenshot({ path: `/tmp/shot-${name}-intro.png` });
    await page.click('[data-act="begin"]');
    // Dars: 1 ta xato qilib, qolganini to'g'ri
    const types = new Set(); let n = 0, wrongDone = false, xpBefore = await page.evaluate(() => TY.Auth.state.xp);
    while (await page.locator('#lesson .l-body.center').count() === 0) {
      const t0 = await page.evaluate(() => TY._debug.session.current().type);
      const doWrong = !wrongDone && t0 === 'choice'; if (doWrong) wrongDone = true;
      const t = await solveCurrent(page, doWrong); types.add(t);
      if (doWrong) { const msg = await page.textContent('#msg'); ok(/To'g'ri javob/.test(msg) && /Misol/.test(msg), `[${name}] xato javobda to'g'ri javob va tushuntirish ko'rsatiladi`); await page.screenshot({ path: `/tmp/shot-${name}-wrong.png` }); }
      if (n === 3) await page.screenshot({ path: `/tmp/shot-${name}-q.png` });
      await page.click('#primary[data-act="next"]'); n++;
      if (n > 80) throw new Error('cheksiz tsikl');
    }
    ok(true, `[${name}] dars tugadi (${n} savol, turlari: ${[...types].join(',')})`);
    await page.screenshot({ path: `/tmp/shot-${name}-result.png` });
    const s = await page.evaluate(() => ({ xp: TY.Auth.state.xp, hearts: TY.Auth.state.hearts, done: Object.keys(TY.Auth.state.done), streak: TY.Auth.state.streak, mk: Object.keys(TY.Auth.state.mistakes).length }));
    ok(s.xp > xpBefore + 80 && s.done.includes('L0T0') && s.streak === 1, `[${name}] XP=${s.xp}, tugallangan=${s.done}, streak=${s.streak}`);
    ok(await page.evaluate(() => Object.values(TY.Auth.state.words).some(w => w.w > 0)), `[${name}] xato statistikasi saqlandi`);
    // Yangilash
    await page.reload(); await page.waitForSelector('.top');
    const after = await page.evaluate(() => TY.Auth.state.xp); ok(after === s.xp, `[${name}] sahifani yangilagach XP saqlandi (${after})`);
    await page.goto(BASE + '#/learn'); await page.waitForSelector('.node');
    ok(await page.locator('.node.done').count() === 1 && (await page.locator('.node.cur').count()) >= 1, `[${name}] xaritada tugallangan/joriy farqlanadi`);
    // Barcha sahifalar
    for (const r of ['', 'learn', 'review', 'quests', 'ielts', 'stats', 'achievements', 'profile']) {
      await page.goto(BASE + '#/' + r); await page.waitForSelector('h1'); await page.waitForTimeout(50);
      if (r === 'review' || r === 'stats' || r === 'profile' || r === 'ielts') await page.screenshot({ path: `/tmp/shot-${name}-${r}.png` });
    }
    ok(true, `[${name}] barcha 8 sahifa ochiladi`);
    // Xato so'zlar mashqi
    await page.evaluate(() => { const w = TY.Auth.state.words; Object.keys(w).slice(0, 3).forEach(k => TY.Auth.state.mistakes[k] = { n: 1, ok: 0 }); TY.Auth.save(); });
    await page.goto(BASE + '#/practice/mistakes'); await page.waitForSelector('.l-body');
    ok(await page.evaluate(() => TY._debug.session.mode) === 'mistakes', `[${name}] xato so'zlar mashqi ishga tushdi`);
    // Yurakchalar tugashi
    await page.evaluate(() => { TY.Auth.state.hearts = 1; TY.Auth.save(); });
    await page.goto(BASE + '#/lesson/L0T1'); await page.waitForSelector('[data-act="begin"]'); await page.click('[data-act="begin"]');
    while (await page.locator('#modal:not([hidden])').count() === 0) {
      const t0 = await page.evaluate(() => TY._debug.session.current().type);
      if (t0 === 'match') { const q = await page.evaluate(() => TY._debug.session.current()); await page.click(`#ml .opt[data-id="${q.ws[0]}"]`); await page.click(`#mr .opt[data-id="${q.ws[1]}"]`); await page.waitForTimeout(600); for (const id of q.ws) { const l = page.locator(`#ml .opt[data-id="${id}"]:not(.gone)`); if (await l.count()) { await l.click(); await page.click(`#mr .opt[data-id="${id}"]`); } } await page.waitForSelector('#primary[data-act="next"],#primary[data-act="hearts"]'); }
      else await solveCurrent(page, true);
      const p = await page.$('#primary'); const act = await p.getAttribute('data-act');
      await p.click(); if (act === 'hearts') break;
    }
    await page.waitForSelector('#modal:not([hidden])');
    ok(/Yurakchalar tugadi/.test(await page.textContent('#modal')), `[${name}] yurakchalar tugasa tanlov oynasi chiqadi`);
    await page.screenshot({ path: `/tmp/shot-${name}-hearts.png` });
    await page.goto(BASE + '#/lesson/L0T1'); await page.waitForTimeout(300);
    ok(/Yurakchalar tugadi/.test(await page.textContent('#modal')), `[${name}] yurak 0 bo'lsa dars boshlanmaydi`);
    // Qorong'i rejim
    await page.evaluate(() => { TY.Auth.state.hearts = 5; TY.Auth.state.theme = 'dark'; TY.Auth.save(); }); await page.goto(BASE + '#/profile'); await page.reload();
    ok(await page.evaluate(() => document.documentElement.dataset.theme) === 'dark', `[${name}] qorong'i rejim`);
    await page.screenshot({ path: `/tmp/shot-${name}-dark.png` });
    const sw = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1); ok(sw, `[${name}] gorizontal aylantirish yo'q`);
    ok(errs.length === 0, `[${name}] konsolda xato yo'q ${errs.join(' | ')}`);
    await ctx.close();
  }
  await browser.close(); console.log(fails ? `\n${fails} ta muvaffaqiyatsiz` : '\nHammasi o\'tdi'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
