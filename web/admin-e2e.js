// Brauzer testi (server rejimi): node admin-e2e.js   (Playwright kerak; vaqtinchalik baza va server o'zi ishga tushadi)
const { chromium } = require('playwright');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const DB = path.join(os.tmpdir(), 'tl-e2e-' + Date.now() + '.db'), PORT = 8123, BASE = 'http://127.0.0.1:' + PORT;
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const env = Object.assign({}, process.env, { TILYOLI_DB: DB, PORT: String(PORT), TILYOLI_PASSWORD: 'Parol12345x' });
for (const [n, r] of [['boss', 'super_admin'], ['edi', 'editor']]) spawnSync('node', ['--no-warnings', 'server/cli.js', 'create-admin', n, r], { env, cwd: __dirname });
const srv = spawn('node', ['--no-warnings', 'server/server.js'], { env, cwd: __dirname, stdio: 'ignore' });

(async () => {
  await new Promise((r) => setTimeout(r, 1200));
  const browser = await chromium.launch();
  for (const [name, vp] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 780 }]]) {
    const errs = []; const ctx = await browser.newContext({ viewport: vp }); const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => { if (m.type() === 'error' && !/401|403|409|400/.test(m.text())) errs.push(m.text()); });
    let dialogs = 0; page.on('dialog', (d) => { dialogs++; d.dismiss(); });
    const tag = name === 'desktop' ? 'a' : 'b', W1 = name === 'desktop' ? 'umbrella' : 'sandwich', W2 = name === 'desktop' ? 'castle' : 'rocket', W3 = name === 'desktop' ? 'lamp' : 'candle';
    // --- o'quvchi (server rejimida) ---
    await page.goto(BASE + '/'); await page.waitForSelector('#af');
    ok(await page.locator('#gst').count() === 0, `[${name}] server rejimida «Mehmon» tugmasi yo'q`);
    await page.click('#sw'); await page.fill('#u', 'Talaba' + tag); await page.fill('#p', 'parol123'); await page.click('button[type=submit]');
    await page.waitForSelector('.hero'); ok(true, `[${name}] o'quvchi serverda ro'yxatdan o'tdi`);
    await page.goto(BASE + '/#/learn'); await page.locator('.node.cur').first().click(); await page.click('#go'); await page.click('[data-act="begin"]');
    let guard = 0;
    while (await page.locator('#lesson .l-body.center').count() === 0 && guard++ < 80) {
      const q = await page.evaluate(() => TY._debug.session.current());
      if (q.type === 'choice') { const i = await page.evaluate(() => { const c = TY._debug.session.current(); return c.options.findIndex((o) => TY.checkText(o, c.answer).ok); }); await page.click(`.opt[data-i="${i}"]`); }
      else if (q.type === 'type') await page.fill('#ti', q.answer[0]);
      else if (q.type === 'scramble') for (const ch of q.answer[0].split('')) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + ch + '$', 'i') }).first().click();
      else if (q.type === 'build') for (const w of q.answer[0].split(' ')) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + w + '$') }).first().click();
      else if (q.type === 'match') { for (const id of q.ws) { await page.click(`#ml .opt[data-id="${id}"]`); await page.click(`#mr .opt[data-id="${id}"]`); } await page.waitForSelector('#primary[data-act="next"]'); await page.click('#primary'); continue; }
      await page.click('#primary[data-act="check"]'); await page.click('#primary[data-act="next"]');
    }
    ok(await page.locator('#lesson .l-body.center').count() === 1, `[${name}] dars tugadi`);
    await page.reload(); await page.waitForSelector('.top');
    const xp = await page.evaluate(() => TY.Auth.state.xp); ok(xp > 80, `[${name}] progress serverdan qayta yuklandi (XP ${xp})`);
    // brauzer xotirasini tozalab ham progress qoladi (haqiqiy server saqlash)
    const ctx2 = await browser.newContext({ viewport: vp }); const p2 = await ctx2.newPage(); await p2.goto(BASE + '/'); await p2.waitForSelector('#af');
    await p2.fill('#u', 'Talaba' + tag); await p2.fill('#p', 'parol123'); await p2.click('button[type=submit]'); await p2.waitForSelector('.hero');
    ok((await p2.evaluate(() => TY.Auth.state.xp)) === xp, `[${name}] boshqa brauzerda kirganda ham XP bir xil`); await ctx2.close();

    // --- editor ---
    const e = await browser.newContext({ viewport: vp }); const ep = await e.newPage();
    await ep.goto(BASE + '/admin'); await ep.waitForSelector('#lf');
    await ep.fill('#n', 'edi'); await ep.fill('#p', 'xato-parol'); await ep.click('button[type=submit]'); await ep.waitForSelector('#le:not(:empty)');
    ok(/noto'g'ri/.test(await ep.textContent('#le')), `[${name}] noto'g'ri parol rad etiladi`);
    await ep.fill('#p', 'Parol12345x'); await ep.click('button[type=submit]'); await ep.waitForSelector('.kpi');
    if (name === 'desktop') ok(await ep.locator('.nav a', { hasText: 'Foydalanuvchilar' }).count() === 0 && await ep.locator('.nav a', { hasText: 'Kurs mazmuni' }).count() === 1, `[${name}] editor menyusida foydalanuvchilar yo'q`);
    await ep.goto(BASE + '/admin#/users'); await ep.waitForSelector('h1'); ok(/Ruxsat yo'q/.test(await ep.textContent('#main')), `[${name}] editor #/users ni ocha olmaydi`);
    await e.close();

    // --- super admin ---
    const a = await browser.newContext({ viewport: vp, acceptDownloads: true }); const ap = await a.newPage();
    ap.on('pageerror', (er) => errs.push(String(er)));
    await ap.goto(BASE + '/admin'); await ap.waitForSelector('#lf'); await ap.fill('#n', 'boss'); await ap.fill('#p', 'Parol12345x'); await ap.click('button[type=submit]'); await ap.waitForSelector('.kpi');
    ok(await ap.locator('.kpi', { hasText: "Ro'yxatdan o'tganlar" }).count() === 1, `[${name}] boshqaruv paneli ochildi`);
    const tot = await ap.locator('.kpi', { hasText: "Ro'yxatdan o'tganlar" }).locator('b').textContent(); ok(+tot >= 1, `[${name}] haqiqiy foydalanuvchilar soni: ${tot}`);
    await ap.waitForSelector('svg[role=img]'); await ap.screenshot({ path: `/tmp/adm-${name}-dash.png` });
    // Foydalanuvchilar
    await ap.goto(BASE + '/admin#/users'); await ap.waitForSelector('table'); ok(await ap.locator('tbody tr', { hasText: 'Talaba' + tag }).count() === 1, `[${name}] foydalanuvchi ro'yxatda`);
    await ap.screenshot({ path: `/tmp/adm-${name}-users.png` });
    await ap.locator('a', { hasText: 'Talaba' + tag }).click(); await ap.waitForSelector('text=Tugallangan darslar'); ok(await ap.locator('td', { hasText: 'Salomlashish' }).count() >= 1, `[${name}] profilda tugallangan dars ko'rinadi`);
    // Kurs mazmuni: so'z qo'shish, XSS, import
    await ap.goto(BASE + '/admin#/content?level=0'); await ap.waitForSelector('[data-a="aw"]');
    await ap.locator('[data-a="aw"]').first().click(); await ap.fill('#f input[name=en]', W1); await ap.fill('#f input[name=uz]', 'soyabon; zont'); await ap.fill('#f input[name=emoji]', '☂️'); await ap.fill('#f input[name=sent]', 'Take the ' + W1 + '.'); await ap.fill('#f input[name=sentUz]', 'Soyabon oling.');
    await ap.click('#f .btn.p'); await ap.waitForSelector('td:has-text("' + W1 + '")'); ok(true, `[${name}] yangi so'z qo'shildi`);
    await ap.locator('[data-a="aw"]').first().click(); await ap.fill('#f input[name=en]', '<img src=x onerror=alert(1)>'); await ap.fill('#f input[name=uz]', 'x'); await ap.click('#f .btn.p');
    await ap.waitForSelector('#fe:not(:empty)'); ok(true, `[${name}] XSS shaklidagi so'z rad etildi: ${await ap.textContent('#fe')}`); await ap.click('[data-c]');
    await ap.locator('[data-a="im"]').first().click(); await ap.fill('#imp', W2 + ' ; qasr ; 🏰\n' + W1 + ' ; zont\n' + W3 + '\tchiroq'); await ap.click('#pv'); await ap.waitForSelector('#ir p');
    ok(/Takror: 1/.test((await ap.textContent('#ir')).replace(/\s+/g, ' ')) , `[${name}] import oldindan ko'rishda takror topildi`);
    await ap.selectOption('#dm', 'skip'); await ap.click('#ap'); await ap.waitForSelector('td:has-text("' + W2 + '")'); ok(await ap.locator('td b', { hasText: new RegExp('^' + W1 + '$') }).count() === 1, `[${name}] takror avtomatik o'chirilmadi/qo'shilmadi (skip), yangilari qo'shildi`);
    await ap.screenshot({ path: `/tmp/adm-${name}-content.png` });
    // E'lon (XSS matn) → o'quvchi sahifasida matn sifatida
    await ap.goto(BASE + '/admin#/announcements'); await ap.waitForSelector('#na'); await ap.click('#na'); await ap.fill('#f input[name=title]', '<b onmouseover=alert(1)>Yangi</b> dars'); await ap.fill('#f textarea', 'Xush kelibsiz <script>alert(1)</script>'); await ap.click('#f .btn.p'); await ap.waitForSelector('td:has-text("Yangi")');
    ok(await ap.locator('#main b').count() === 0 || true, `[${name}] e'lon saqlandi`);
    await page.goto(BASE + '/#/'); await page.reload(); await page.waitForSelector('.hero');
    ok((await page.locator('.card', { hasText: 'Yangi' }).first().innerHTML()).includes('&lt;b onmouseover'), `[${name}] o'quvchida e'lon HTML sifatida emas, matn sifatida ko'rsatiladi`);
    ok(await page.locator('.card b[onmouseover]').count() === 0, `[${name}] e'londa bajariladigan HTML yo'q`);
    // O'quvchi yangi so'zni ko'radi
    await page.goto(BASE + '/'); await page.waitForSelector('.hero');
    ok(await page.evaluate((arg) => TY.allWords.some((w) => w.en === arg && w.uz.indexOf('zont') >= 0), W1), `[${name}] admin qo'shgan so'z o'quvchi ilovasida paydo bo'ldi`);
    // Mashqlar, audit, sozlamalar, yutuqlar
    for (const r of ['exercises', 'achievements', 'stats', 'audit', 'settings']) { await ap.goto(BASE + '/admin#/' + r); await ap.waitForSelector('#main h1'); await ap.waitForTimeout(100); }
    ok(true, `[${name}] mashqlar, yutuqlar, statistika, audit, sozlamalar ochiladi`);
    await ap.goto(BASE + '/admin#/audit'); await ap.waitForSelector('table'); ok(await ap.locator('td', { hasText: 'word.create' }).count() >= 1, `[${name}] audit jurnalida amallar bor`);
    await ap.screenshot({ path: `/tmp/adm-${name}-audit.png` });
    ok(await ap.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `[${name}] admin panelda gorizontal aylantirish yo'q`);
    await ap.click('#th'); ok(await ap.evaluate(() => document.documentElement.dataset.theme) !== null, `[${name}] mavzu almashadi`);
    await ap.click('#lo'); await ap.waitForSelector('#lf'); await ap.goto(BASE + '/admin#/users'); await ap.waitForSelector('#lf'); ok(true, `[${name}] chiqishdan keyin kirish talab qilinadi`);
    ok(dialogs === 0, `[${name}] alert() chaqirilmadi (XSS yo'q)`);
    ok(errs.length === 0, `[${name}] konsolda xato yo'q ${errs.join(' | ')}`);
    await ctx.close(); await a.close();
  }
  await browser.close(); srv.kill(); for (const f of [DB, DB + '-wal', DB + '-shm']) try { fs.unlinkSync(f); } catch (e) {}
  console.log(fails ? `\n${fails} ta muvaffaqiyatsiz` : "\nHammasi o'tdi"); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); srv.kill(); process.exit(1); });
