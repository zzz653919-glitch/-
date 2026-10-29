// API testlari: node server.test.js  (har safar yangi vaqtinchalik baza)
const assert = require('assert');
const { createApp } = require('./server/server');
const sec = require('./server/security');
let n = 0; const t = async (name, fn) => { await fn(); n++; console.log('ok  ' + name); };

(async () => {
  const { server, db } = createApp(':memory:');
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = 'http://127.0.0.1:' + server.address().port;
  const mk = (role, name) => db.prepare('INSERT INTO users (name, name_lc, pass_hash, role, created_at) VALUES (?,?,?,?,?)').run(name, name.toLowerCase(), sec.hashPassword('Parol12345x'), role, Date.now());
  mk('super_admin', 'boss'); mk('admin', 'ali'); mk('editor', 'edi');

  class Client {
    constructor() { this.cookies = {}; this.csrf = null; this.bodies = []; }
    async req(method, url, body, opts = {}) {
      const headers = { 'Content-Type': 'application/json' };
      if (Object.keys(this.cookies).length) headers.Cookie = Object.entries(this.cookies).map(([k, v]) => k + '=' + v).join('; ');
      if (this.csrf && !opts.noCsrf) headers['X-CSRF-Token'] = this.csrf;
      if (opts.origin) headers.Origin = opts.origin;
      const r = await fetch(base + url, { method, headers, body: body ? JSON.stringify(body) : undefined });
      (r.headers.getSetCookie() || []).forEach((c) => { const [kv] = c.split(';'); const i = kv.indexOf('='); const v = kv.slice(i + 1); if (v) this.cookies[kv.slice(0, i)] = v; else delete this.cookies[kv.slice(0, i)]; });
      const text = await r.text(); this.bodies.push(text); let j = {}; try { j = JSON.parse(text); } catch (e) { j = { raw: text }; }
      return { status: r.status, j, headers: r.headers, text };
    }
    async adminLogin(name, pass = 'Parol12345x') { const r = await this.req('POST', '/api/admin/login', { name, pass }); if (r.status === 200) this.csrf = r.j.csrf; return r; }
  }
  const clients = {};
  for (const nm of ['boss', 'ali', 'edi']) { clients[nm] = new Client(); assert.equal((await clients[nm].adminLogin(nm)).status, 200); }
  const boss = clients.boss, ali = clients.ali, edi = clients.edi;

  await t('autentifikatsiyasiz admin va o\'quvchi API 401', async () => {
    const c = new Client();
    for (const u of ['/api/admin/dashboard', '/api/admin/users', '/api/admin/content', '/api/admin/audit', '/api/me']) assert.equal((await c.req('GET', u)).status, 401, u);
    assert.equal((await c.req('POST', '/api/admin/words', { en: 'x' })).status, 401);
  });
  await t('oddiy foydalanuvchi admin kira olmaydi', async () => {
    const u = new Client(); assert.equal((await u.req('POST', '/api/register', { name: 'Vali', pass: 'secret1' })).status, 200);
    assert.equal((await new Client().adminLogin('Vali', 'secret1')).status, 401);
    assert.equal((await u.req('GET', '/api/admin/users')).status, 401); // o'quvchi cookie'si admin sessiyasi emas
  });
  await t('rol ruxsatlari serverda majburlanadi', async () => {
    assert.equal((await edi.req('GET', '/api/admin/users')).status, 403);
    assert.equal((await edi.req('GET', '/api/admin/audit')).status, 403);
    assert.equal((await edi.req('GET', '/api/admin/content')).status, 200);
    assert.equal((await edi.req('GET', '/api/admin/dashboard')).status, 200);
    assert.equal((await ali.req('GET', '/api/admin/users')).status, 200);
    assert.equal((await ali.req('GET', '/api/admin/settings')).status, 403);
    assert.equal((await ali.req('GET', '/api/admin/admins')).status, 403);
    assert.equal((await ali.req('POST', '/api/admin/admins', { name: 'x1', role: 'super_admin', pass: 'Parol12345x' })).status, 403);
    assert.equal((await boss.req('GET', '/api/admin/admins')).status, 200);
    const ed = await edi.req('GET', '/api/admin/dashboard'); assert(!ed.j.users && !ed.j.recentUsers, 'editor foydalanuvchi ma\'lumotini ko\'rmasligi kerak');
    assert.equal((await edi.req('PUT', '/api/admin/announcements/1', { title: 'a', body: 'b' })).status, 403);
  });
  await t('CSRF va Origin himoyasi', async () => {
    assert.equal((await boss.req('POST', '/api/admin/words', {}, { noCsrf: true })).status, 403);
    boss.csrf = 'xato'; assert.equal((await boss.req('PUT', '/api/admin/settings', { registrationOpen: true })).status, 403);
    const real = (await boss.req('GET', '/api/admin/me')).j.csrf; boss.csrf = real;
    assert.equal((await boss.req('PUT', '/api/admin/settings', { registrationOpen: true }, { origin: 'http://evil.example' })).status, 403);
    assert.equal((await boss.req('PUT', '/api/admin/settings', { registrationOpen: true })).status, 200);
  });
  await t('kirishga urinishlar cheklanadi (429)', async () => {
    const c = new Client(); let last;
    for (let i = 0; i < 6; i++) last = await c.adminLogin('ali', 'noto\'g\'ri' + i);
    assert.equal(last.status, 429);
    assert.equal((await c.adminLogin('ali')).status, 429, "to'g'ri parol ham bloklangan davrda rad etiladi");
    db.prepare('DELETE FROM login_attempts').run();
  });
  await t('parollar xeshlanadi va hech qayerda qaytmaydi', async () => {
    const rows = db.prepare('SELECT pass_hash FROM users').all(); assert(rows.every((r) => r.pass_hash.startsWith('scrypt$') && !r.pass_hash.includes('Parol12345x')));
    for (const c of [boss, ali, edi]) c.bodies.forEach((b) => { assert(!/scrypt\$|pass_hash/.test(b)); });
  });
  await t('o\'quvchi: ro\'yxat, saqlash, qayta kirish', async () => {
    const u = new Client(); let r = await u.req('POST', '/api/register', { name: 'Gulnora', pass: 'sirli123' }); u.csrf = r.j.csrf;
    assert.equal((await u.req('POST', '/api/register', { name: 'gulnora', pass: 'boshqa12' })).status, 409);
    assert.equal((await u.req('PUT', '/api/state', { state: { xp: 'x' } })).status, 400);
    const st = { v: 2, xp: 120, streak: 3, done: { L0T0: { best: 90 }, L0T1: { best: 80 } }, words: { '0.0.0': { c: 5, w: 6 }, '0.0.1': { c: 1, w: 0 } }, ach: { first: 1 }, days: {}, mistakes: {} };
    assert.equal((await u.req('PUT', '/api/state', { state: st })).status, 200);
    assert.equal((await u.req('PUT', '/api/state', { state: st }, { noCsrf: true })).status, 403);
    for (const [node, pct, ok] of [['L0T0', 90, 1], ['L0T0', 40, 1], ['L0T0', 50, 1], ['L0X', 60, 0]]) assert.equal((await u.req('POST', '/api/event', { mode: node.endsWith('X') ? 'test' : 'lesson', node, pct, xp: 30, ok })).status, 200);
    const again = new Client(); r = await again.req('POST', '/api/login', { name: 'GULNORA', pass: 'sirli123' }); assert.equal(r.status, 200); assert.equal(r.j.state.xp, 120);
    assert.equal((await new Client().req('POST', '/api/login', { name: 'gulnora', pass: 'xato' })).status, 401);
  });
  await t('boshqaruv paneli statistikasi haqiqiy yozuvlardan', async () => {
    const d = (await boss.req('GET', '/api/admin/dashboard?days=7')).j;
    assert.equal(d.users.total, 2); assert.equal(d.learning.lessonsCompleted, 3); assert.equal(d.series.length, 7);
    assert.equal(d.popularLessons[0].node, 'L0T0'); assert.equal(d.popularLessons[0].count, 3);
    assert.equal(d.hardLessons[0].node, 'L0T0'); assert.equal(d.hardLessons[0].avgScore, 60);
    assert.equal(d.hardWords[0].en, 'hello'); assert.equal(d.hardWords[0].wrongRate, 55);
    assert.equal(d.content.words, 192); assert(d.recentUsers.length === 2 && d.recentActivity.length === 4);
    assert.equal(d.levelDistribution[0].users, 1);
    assert.equal(d.series.reduce((a, x) => a + x.registrations, 0), 2);
  });
  await t('foydalanuvchilar: qidiruv, sahifalash, SQL in\'ektsiya', async () => {
    for (let i = 0; i < 25; i++) db.prepare('INSERT INTO users (name, name_lc, pass_hash, created_at, xp) VALUES (?,?,?,?,?)').run('u' + i, 'u' + i, 'x', Date.now() - i, i);
    let r = (await ali.req('GET', '/api/admin/users?sort=xp')).j; assert.equal(r.rows.length, 20); assert.equal(r.total, 27); assert.equal(r.pages, 2);
    r = (await ali.req('GET', '/api/admin/users?q=gul')).j; assert.equal(r.total, 1);
    r = await ali.req('GET', "/api/admin/users?q=" + encodeURIComponent("' OR 1=1 --")); assert.equal(r.status, 200); assert.equal(r.j.total, 0);
    r = await ali.req('GET', '/api/admin/users?sort=' + encodeURIComponent('xp; DROP TABLE users')); assert.equal(r.status, 200);
    assert.equal(db.prepare('SELECT COUNT(*) c FROM users').get().c, 30);
    assert.equal((await ali.req('GET', '/api/admin/users/abc')).status, 400);
  });
  await t('foydalanuvchini bloklash sessiyani yopadi', async () => {
    const u = new Client(); let r = await u.req('POST', '/api/login', { name: 'gulnora', pass: 'sirli123' }); u.csrf = r.j.csrf;
    const id = db.prepare("SELECT id FROM users WHERE name_lc = 'gulnora'").get().id;
    assert.equal((await ali.req('POST', `/api/admin/users/${id}/status`, { status: 'disabled' })).status, 200);
    assert.equal((await u.req('GET', '/api/me')).status, 401); assert.equal((await new Client().req('POST', '/api/login', { name: 'gulnora', pass: 'sirli123' })).status, 403);
    assert.equal((await ali.req('POST', `/api/admin/users/${id}/status`, { status: 'active' })).status, 200);
    assert.equal((await ali.req('DELETE', `/api/admin/users/${id}`)).status, 403, "Admin foydalanuvchini o'chira olmaydi");
    const prof = (await ali.req('GET', `/api/admin/users/${id}`)).j; assert.equal(prof.user.xp, 120); assert(!('state' in prof.user) && !('pass_hash' in prof.user));
  });
  await t('kurs mazmuni: qo\'shish, takror, tahrir, yashirish, himoya', async () => {
    const add = (o) => edi.req('POST', '/api/admin/words', Object.assign({ level: 0, topic: 0, en: 'umbrella', uz: ['soyabon'], emoji: '☂️', sent: 'Take an umbrella.', sentUz: 'Soyabon oling.' }, o));
    let r = await add(); assert.equal(r.status, 200); const id = r.j.id; assert(/^0\.0\.a\d+$/.test(id));
    r = await add({ en: 'Umbrella' }); assert.equal(r.status, 409); assert(r.j.duplicate);
    assert.equal((await add({ en: 'Umbrella', allowDuplicate: true })).status, 200);
    assert.equal((await add({ en: 'hello', sent: 'Hello there.', sentUz: 'Salom.' })).status, 409, 'asosiy kursdagi so\'z bilan takror');
    assert.equal((await add({ en: '<script>alert(1)</script>' })).status, 400);
    assert.equal((await add({ en: 'rain', sent: 'No match here.' })).status, 400);
    assert.equal((await add({ en: 'rain', uz: [] })).status, 400);
    assert.equal((await add({ level: 99 })).status, 400);
    assert.equal((await edi.req('PUT', '/api/admin/words/' + id, { en: 'umbrella', uz: ['soyabon', 'zont'], emoji: '☂️', sent: 'Take an umbrella.', sentUz: 'Soyabon oling.' })).status, 200);
    const c = (await edi.req('GET', '/api/admin/content')).j; const w = c.levels[0].topics[0].words.find((x) => x.id === id); assert.deepEqual(w.uz, ['soyabon', 'zont']);
    // asosiy so'zni yashirish (progress saqlanadi) va tiklash
    assert.equal((await edi.req('DELETE', '/api/admin/words/0.0.7')).j.hidden, true);
    const pub = (await new Client().req('GET', '/api/content')).j; assert(pub.rows.words.some((x) => x.id === '0.0.7' && x.hidden === 1));
    assert.equal((await edi.req('DELETE', '/api/admin/words/' + id)).j.deleted, true);
    const w7 = c.levels[0].topics[0].words.find((x) => x.id === '0.0.7');
    assert.equal((await edi.req('PUT', '/api/admin/words/0.0.7', Object.assign({}, w7, { hidden: false }))).status, 200);
    // mavzuda minimum so'z
    for (const k of [0, 1, 2, 3]) assert.equal((await edi.req('DELETE', '/api/admin/words/0.3.' + k)).status, 200, 'yashirish ' + k);
    assert.equal((await edi.req('DELETE', '/api/admin/words/0.3.4')).status, 409, 'mavzuda kamida 4 ta so\'z qolishi kerak');
  });
  await t('import: oldindan ko\'rish, takrorlar avtomatik o\'chirilmaydi', async () => {
    const rows = [['castle', 'qasr', '🏰', 'The castle is old.', 'Qasr eski.'], ['hello', 'salom'], ['bad word!', 'x'], ['castle', 'qal\'a'], ['lamp', 'chiroq, lampa']];
    const imp = (o) => edi.req('POST', '/api/admin/import', Object.assign({ level: 0, topic: 1, rows }, o));
    let r = (await imp({ dryRun: true })).j; assert.equal(r.applied, false); assert.equal(r.added.length, 2); assert.equal(r.duplicates.length, 2); assert.equal(r.invalid.length, 1);
    r = (await imp({})).j; assert.equal(r.applied, false, 'takror bo\'lsa "report" rejimida hech narsa qo\'shilmaydi');
    r = (await imp({ duplicates: 'skip' })).j; assert.equal(r.applied, true);
    const c = (await edi.req('GET', '/api/admin/content')).j; const names = c.levels[0].topics[1].words.map((x) => x.en);
    assert(names.includes('castle') && names.includes('lamp') && names.filter((x) => x === 'castle').length === 1 && names.includes('brother'));
    assert.equal((await imp({ rows: [] })).status, 400);
  });
  await t('mavzu qo\'shish, daraja tahriri, mashq turlari', async () => {
    assert.equal((await edi.req('POST', '/api/admin/topics', { level: 0, title: 'Yangi mavzu', icon: '🆕', tip: 'Test' })).j.idx, 4);
    assert.equal((await edi.req('PUT', '/api/admin/topics/0/0', { title: 'Salomlashuv', icon: '💬', tip: 'Yangi tavsif' })).status, 200);
    assert.equal((await edi.req('PUT', '/api/admin/levels/0', { title: 'Beginner+', sub: 'A1' })).status, 200);
    assert.equal((await edi.req('PUT', '/api/admin/exercises', { disabled: ['listen', 'build'] })).status, 200);
    assert.equal((await edi.req('PUT', '/api/admin/exercises', { disabled: ['mc_en_uz', 'mc_uz_en', 'picture'] })).status, 400);
    assert.equal((await edi.req('PUT', '/api/admin/exercises', { disabled: ['hack'] })).status, 400);
    const pub = (await new Client().req('GET', '/api/content')).j.rows; assert.deepEqual(pub.disabled, ['listen', 'build']);
    // mijoz tomonidagi birlashtirish serverdagi bilan bir xil natija beradi
    const { TY } = createApp(':memory:'); TY.applyContent(pub); assert.equal(TY.LEVELS[0].title, 'Beginner+'); assert.equal(TY.LEVELS[0].topics[0].title, 'Salomlashuv');
    assert(TY.allWords.some((w) => w.en === 'castle')); assert(!TY.LEVELS[0].topics[4].words.length); assert(TY.disabledKinds.listen);
  });
  await t('e\'lonlar va XSS: matn xom saqlanadi, JSON sifatida qaytadi', async () => {
    const xss = '<img src=x onerror=alert(1)>';
    assert.equal((await ali.req('POST', '/api/admin/announcements', { title: xss, body: xss + '<script>1</script>' })).status, 200);
    const pub = (await new Client().req('GET', '/api/content')).j; assert.equal(pub.announcements[0].title, xss);
    assert((await new Client().req('GET', '/api/content')).headers.get('content-type').startsWith('application/json'));
    assert.equal((await ali.req('POST', '/api/admin/announcements', { title: '', body: 'x' })).status, 400);
    assert.equal((await ali.req('POST', '/api/admin/announcements', { title: 'a'.repeat(200), body: 'x' })).status, 400);
  });
  await t('administratorlar: rol almashtirish, himoyalar', async () => {
    assert.equal((await boss.req('POST', '/api/admin/admins', { name: 'zayif', role: 'admin', pass: 'qisqa' })).status, 400);
    assert.equal((await boss.req('POST', '/api/admin/admins', { name: 'yangi', role: 'admin', pass: 'Parol12345x' })).status, 200);
    assert.equal((await boss.req('POST', '/api/admin/admins', { name: 'yangi', role: 'admin', pass: 'Parol12345x' })).status, 409);
    const bossId = db.prepare("SELECT id FROM users WHERE name_lc = 'boss'").get().id, ediId = db.prepare("SELECT id FROM users WHERE name_lc = 'edi'").get().id;
    assert.equal((await boss.req('PUT', '/api/admin/admins/' + bossId, { role: 'admin' })).status, 409, "o'zini pasaytira olmaydi");
    assert.equal((await boss.req('PUT', '/api/admin/admins/' + ediId, { role: 'admin', status: 'disabled' })).status, 200);
    assert.equal((await edi.req('GET', '/api/admin/me')).status, 401, 'bloklangan adminning sessiyasi yopiladi');
    assert.equal((await new Client().req('POST', '/api/admin/admins', { name: 'q', role: 'admin', pass: 'Parol12345x' })).status, 401);
  });
  await t('audit jurnali: amallar yoziladi, parol yo\'q', async () => {
    const a = (await boss.req('GET', '/api/admin/audit')).j; const acts = a.rows.map((r) => r.action);
    for (const x of ['admin.login', 'word.create', 'word.import', 'user.disabled', 'exercises.update', 'forbidden']) assert(acts.includes(x), 'audit: ' + x);
    assert(a.rows.some((r) => r.action === 'admin.login' && r.ok === 0)); assert(!JSON.stringify(a).includes('Parol12345x'));
  });
  await t('CSV eksport (in\'ektsiyadan himoyalangan) va xavfsizlik sarlavhalari', async () => {
    db.prepare('INSERT INTO users (name, name_lc, pass_hash, created_at) VALUES (?,?,?,?)').run('=HYPERLINK("x")', '=hyperlink("x")', 'x', Date.now());
    const r = await ali.req('GET', '/api/admin/export/users.csv'); assert.equal(r.status, 200); assert(r.headers.get('content-type').startsWith('text/csv')); assert(r.text.includes("'=HYPERLINK"));
    assert.equal((await edi.req('GET', '/api/admin/export/users.csv')).status, 401);
    const s = await fetch(base + '/'); assert(/script-src 'self'/.test(s.headers.get('content-security-policy'))); assert.equal(s.headers.get('x-frame-options'), 'DENY');
  });
  await t('statik fayllar: faqat ruxsat etilganlari', async () => {
    for (const p of ['/server/server.js', '/server/data/tilyoli.db', '/../server/db.js', '/%2e%2e/server/db.js', '/README.md', '/logic.test.js', '/server.test.js']) assert.equal((await fetch(base + p)).status, 404, p);
    for (const p of ['/', '/admin', '/ui.js', '/admin/admin.js', '/content.js', '/localapi.js']) assert.equal((await fetch(base + p)).status, 200, p);
  });
  await t('chiqish sessiyani bekor qiladi; juda katta so\'rov rad etiladi', async () => {
    assert.equal((await ali.req('POST', '/api/admin/logout')).status, 200); assert.equal((await ali.req('GET', '/api/admin/users')).status, 401);
    const big = await boss.req('POST', '/api/admin/announcements', { title: 'a', body: 'x'.repeat(700000) }).catch(() => ({ status: 413 })); assert([413, 400].includes(big.status));
  });
  console.log('\n' + n + " ta server testi o'tdi"); server.close(); process.exit(0);
})().catch((e) => { console.error('XATO:', e); process.exit(1); });
