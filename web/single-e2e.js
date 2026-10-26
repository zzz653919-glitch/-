// Bitta fayl testi (server yo'q, file://): node single-e2e.js
const { chromium } = require('playwright');
const path = require('path');
const URL_ = 'file://' + path.join(__dirname, 'tilyoli.html');
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const browser = await chromium.launch();
  for (const [name, vp] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 780 }]]) {
    const errs = []; const ctx = await browser.newContext({ viewport: vp }); const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e.stack).split('\n').slice(0, 3).join(' | '))); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    let dialogs = 0; page.on('dialog', (d) => { dialogs++; d.dismiss(); });
    // o'quvchi: ro'yxat + dars
    await page.goto(URL_); await page.waitForSelector('#af'); await page.click('#sw'); await page.fill('#u', 'Dilnoza'); await page.fill('#p', 'parol123'); await page.click('button[type=submit]'); await page.waitForSelector('.hero');
    await page.goto(URL_ + '#/learn'); await page.reload(); await page.waitForSelector('.node.cur'); await page.locator('.node.cur').first().click(); await page.click('#go'); await page.click('[data-act="begin"]');
    let g = 0;
    while (await page.locator('#lesson .l-body.center').count() === 0 && g++ < 80) {
      const q = await page.evaluate(() => TY._debug.session.current());
      if (q.type === 'choice') { const i = await page.evaluate(() => { const c = TY._debug.session.current(); return c.options.findIndex((o) => TY.checkText(o, c.answer).ok); }); await page.click(`.opt[data-i="${i}"]`); }
      else if (q.type === 'type') await page.fill('#ti', q.answer[0]);
      else if (q.type === 'scramble') for (const ch of q.answer[0].split('')) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + ch + '$', 'i') }).first().click();
      else if (q.type === 'build') for (const w of q.answer[0].split(' ')) await page.locator('#bank .tile:not([disabled])', { hasText: new RegExp('^' + w + '$') }).first().click();
      else if (q.type === 'match') { for (const id of q.ws) { await page.click(`#ml .opt[data-id="${id}"]`); await page.click(`#mr .opt[data-id="${id}"]`); } await page.waitForSelector('#primary[data-act="next"]'); await page.click('#primary'); continue; }
      await page.click('#primary[data-act="check"]'); await page.click('#primary[data-act="next"]');
    }
    ok(await page.locator('#lesson .l-body.center').count() === 1, `[${name}] o'quvchi darsi bitta fayl ichida ishladi`);
    // admin
    await page.goto(URL_ + '?admin'); await page.waitForSelector('#lf');
    ok(/Birinchi kirish/.test(await page.textContent('#main')), `[${name}] admin: birinchi kirish ko'rsatmasi`);
    await page.fill('#n', 'boss'); await page.fill('#p', 'qisqa'); await page.click('button[type=submit]'); await page.waitForSelector('#le:not(:empty)'); ok(/10 belgi/.test(await page.textContent('#le')), `[${name}] zaif parol rad etildi`);
    await page.fill('#p', 'Parol12345x'); await page.click('button[type=submit]'); await page.waitForSelector('.kpi');
    ok(await page.locator('.kpi', { hasText: "Ro'yxatdan o'tganlar" }).locator('b').textContent() === '1', `[${name}] boshqaruv paneli: 1 ta foydalanuvchi (haqiqiy ma'lumot)`);
    await page.waitForSelector('svg[role=img]'); await page.screenshot({ path: `/tmp/single-${name}-dash.png` });
    await page.goto(URL_ + '?admin#/users'); await page.reload(); await page.waitForSelector('table'); ok(await page.locator('td a', { hasText: 'Dilnoza' }).count() === 1, `[${name}] foydalanuvchi ro'yxatda`);
    await page.locator('a', { hasText: 'Dilnoza' }).click(); await page.waitForSelector('text=Tugallangan darslar'); ok(await page.locator('td', { hasText: 'Salomlashish' }).count() >= 1, `[${name}] profil: tugallangan dars`);
    // so'z qo'shish + import
    await page.goto(URL_ + '?admin#/content?level=0'); await page.reload(); await page.waitForSelector('[data-a="aw"]'); await page.locator('[data-a="aw"]').first().click();
    await page.fill('#f input[name=en]', 'umbrella'); await page.fill('#f input[name=uz]', 'soyabon; zont'); await page.fill('#f input[name=sent]', 'Take an umbrella.'); await page.fill('#f input[name=sentUz]', 'Soyabon oling.'); await page.click('#f .btn.p'); await page.waitForSelector('td:has-text("umbrella")');
    ok(true, `[${name}] yangi so'z qo'shildi`);
    await page.locator('[data-a="aw"]').first().click(); await page.fill('#f input[name=en]', '<img src=x onerror=alert(1)>'); await page.fill('#f input[name=uz]', 'x'); await page.click('#f .btn.p'); await page.waitForSelector('#fe:not(:empty)'); ok(true, `[${name}] XSS shaklidagi so'z rad etildi`); await page.click('[data-c]');
    await page.locator('[data-a="im"]').first().click(); await page.fill('#imp', 'castle ; qasr\numbrella ; zont\nlamp\tchiroq'); await page.click('#pv'); await page.waitForSelector('#ir p');
    ok(/Takror: 1/.test((await page.textContent('#ir')).replace(/\s+/g, ' ')), `[${name}] import: takror topildi`);
    await page.selectOption('#dm', 'skip'); await page.click('#ap'); await page.waitForSelector('td:has-text("castle")'); ok(await page.locator('td b', { hasText: /^umbrella$/ }).count() === 1, `[${name}] takror avtomatik o'chirilmadi, yangilar qo'shildi`);
    // e'lon, bloklash
    await page.goto(URL_ + '?admin#/announcements'); await page.reload(); await page.waitForSelector('#na'); await page.click('#na'); await page.fill('#f input[name=title]', '<b>Yangi</b> dars'); await page.fill('#f textarea', 'Salom <script>alert(1)</script>'); await page.click('#f .btn.p'); await page.waitForSelector('td:has-text("Yangi")');
    await page.goto(URL_ + '?admin#/users'); await page.reload(); await page.waitForSelector('table'); await page.locator('a', { hasText: 'Dilnoza' }).click(); await page.waitForSelector('#st'); await page.click('#st'); await page.waitForSelector('text=Blokdan chiqarish');
    for (const r of ['exercises', 'achievements', 'stats', 'audit', 'settings']) { await page.goto(URL_ + '?admin#/' + r); await page.reload(); await page.waitForSelector('#main h1'); await page.waitForTimeout(80); }
    ok(true, `[${name}] barcha bo'limlar ochiladi`); await page.goto(URL_ + '?admin#/audit'); await page.reload(); await page.waitForSelector('table'); ok(await page.locator('td', { hasText: 'word.import' }).count() >= 1, `[${name}] audit jurnali`);
    await page.screenshot({ path: `/tmp/single-${name}-audit.png` });
    ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `[${name}] gorizontal aylantirish yo'q`);
    // saytga qaytish: bloklangan o'quvchi kira olmaydi, yangi so'z va e'lon ko'rinadi
    await page.goto(URL_); await page.waitForSelector('#af'); await page.fill('#u', 'Dilnoza'); await page.fill('#p', 'parol123'); await page.click('button[type=submit]'); await page.waitForSelector('#af .err:not(:empty), #err:not(:empty)');
    ok(/bloklangan/.test(await page.textContent('#err')), `[${name}] bloklangan o'quvchi kira olmaydi`);
    await page.goto(URL_ + '?admin#/users'); await page.reload(); await page.waitForSelector('table'); await page.locator('a', { hasText: 'Dilnoza' }).click(); await page.waitForSelector('#st'); await page.click('#st'); await page.waitForSelector('text=Bloklash');
    await page.goto(URL_); await page.waitForSelector('.hero');
    ok((await page.locator('.card', { hasText: 'Yangi' }).first().innerHTML()).includes('&lt;b&gt;Yangi'), `[${name}] e'lon matn sifatida ko'rsatildi (HTML emas)`);
    ok(await page.evaluate(() => TY.allWords.some((w) => w.en === 'umbrella' && w.uz.includes('zont'))), `[${name}] admin so'zi o'quvchi ilovasida bor`);
    await page.goto(URL_ + '#/profile'); await page.reload(); await page.waitForSelector('a[href="?admin"]'); ok(true, `[${name}] profilda Admin panel havolasi bor`);
    await page.goto(URL_ + '?admin'); await page.waitForSelector('.kpi'); ok(true, `[${name}] sessiya saqlanadi`);
    await page.click('#lo'); await page.waitForSelector('#lf'); ok(!(await page.textContent('#main')).includes('Birinchi kirish'), `[${name}] chiqish → kirish talab qilinadi`);
    ok(dialogs === 0, `[${name}] alert() chaqirilmadi`);
    ok(errs.length === 0, `[${name}] konsolda xato yo'q ${errs.join(' | ')}`);
    await ctx.close();
  }
  await browser.close(); console.log(fails ? `\n${fails} ta muvaffaqiyatsiz` : "\nHammasi o'tdi"); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
