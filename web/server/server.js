'use strict';
// Til Yo'li serveri: statik fayllar + JSON API (o'quvchilar va admin panel). Qo'shimcha paket talab qilinmaydi (Node 22+).
const http = require('http');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { open } = require('./db');
const sec = require('./security');

const ROOT = path.join(__dirname, '..');
const PORT = +process.env.PORT || 8080;
const HTTPS = process.env.COOKIE_SECURE === '1';
const TRUST_PROXY = process.env.TRUST_PROXY === '1';
const SESSION_MS = { learner: 30 * 864e5, admin: 8 * 36e5 };
const MAX_BODY = 600 * 1024;
const KINDS = ['mc_en_uz', 'mc_uz_en', 'picture', 'type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'listen'];
const EASY = ['mc_en_uz', 'mc_uz_en', 'picture'], HARD = ['type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'listen'];
const PERMS = {
  editor: ['dashboard', 'content', 'exercises'],
  admin: ['dashboard', 'content', 'exercises', 'users', 'stats', 'announcements', 'audit'],
  super_admin: ['dashboard', 'content', 'exercises', 'users', 'stats', 'announcements', 'audit', 'admins', 'settings']
};
const STATIC = new Set(['index.html', 'app.css', 'theme.js', 'data.js', 'content.js', 'store.js', 'engine.js', 'ui.js', 'admin/admin.html', 'admin/admin.css', 'admin/admin.js']);
const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };

function createApp(dbFile) {
  const db = open(dbFile);
  // Kurs ma'lumotlari serverda ham bir xil kod bilan (data.js + content.js) birlashtiriladi
  function loadCourse() {
    const ctx = vm.createContext({ TY: undefined }); ctx.globalThis = ctx;
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8'), ctx);
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'content.js'), 'utf8'), ctx);
    return ctx.TY;
  }
  const TY = loadCourse();

  const now = () => Date.now();
  const setting = (k, d) => { const r = db.prepare('SELECT value FROM settings WHERE key = ?').get(k); return r ? JSON.parse(r.value) : d; };
  const setSetting = (k, v) => db.prepare('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value').run(k, JSON.stringify(v));
  function audit(actor, action, target, ok, detail) {
    db.prepare('INSERT INTO audit_log (ts, user_id, user_name, action, target, ok, detail) VALUES (?,?,?,?,?,?,?)')
      .run(now(), actor ? actor.id : null, actor ? actor.name : null, action, target == null ? null : String(target).slice(0, 200), ok === false ? 0 : 1, detail ? String(detail).slice(0, 300) : null);
  }
  class HttpError extends Error { constructor(status, msg, extra) { super(msg); this.status = status; this.extra = extra; } }
  const bad = (m, extra) => new HttpError(400, m, extra);

  // ---- Kontent qatlami ----
  function contentRows() {
    return {
      levels: db.prepare('SELECT idx, title, sub FROM content_levels').all(),
      topics: db.prepare('SELECT level, idx, title, icon, tip FROM content_topics').all(),
      words: db.prepare('SELECT id, level, topic, en, uz, emoji, sent, sentUz, hidden, pos FROM content_words ORDER BY pos, rowid').all().map((w) => Object.assign({}, w, { uz: JSON.parse(w.uz) })),
      disabled: setting('disabledKinds', [])
    };
  }
  function mergedCourse(keepHidden) { TY.applyContent(contentRows(), keepHidden); return TY.LEVELS; }

  // ---- Sessiya, CSRF, cheklov ----
  function parseCookies(req) { const o = {}; (req.headers.cookie || '').split(';').forEach((p) => { const i = p.indexOf('='); if (i > 0) o[p.slice(0, i).trim()] = p.slice(i + 1).trim(); }); return o; }
  const COOKIE = { learner: 'tl_sid', admin: 'tl_admin' };
  function cookieHeader(kind, value, maxAgeSec) {
    return `${COOKIE[kind]}=${value}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${maxAgeSec}${HTTPS ? '; Secure' : ''}`;
  }
  function createSession(res, user, kind) {
    const t = sec.token(), csrf = sec.token();
    db.prepare('INSERT INTO sessions (id_hash, user_id, kind, csrf, created, expires) VALUES (?,?,?,?,?,?)').run(sec.sha(t), user.id, kind, csrf, now(), now() + SESSION_MS[kind]);
    res.cookies.push(cookieHeader(kind, t, SESSION_MS[kind] / 1000));
    return csrf;
  }
  function getSession(req, kind) {
    const t = parseCookies(req)[COOKIE[kind]]; if (!t) return null;
    const s = db.prepare('SELECT s.csrf, s.expires, s.id_hash, u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id_hash = ? AND s.kind = ?').get(sec.sha(t), kind);
    if (!s) return null;
    if (s.expires < now()) { db.prepare('DELETE FROM sessions WHERE id_hash = ?').run(s.id_hash); return null; }
    if (s.status !== 'active') return null;
    if (kind === 'admin' && s.role === 'user') return null;
    return s;
  }
  function clientIp(req) { return (TRUST_PROXY && String(req.headers['x-forwarded-for'] || '').split(',')[0].trim()) || req.socket.remoteAddress || '?'; }
  // Kirishga urinishlar: 15 daqiqada 5 ta xato (ism+IP) yoki 30 ta (IP) → vaqtincha bloklash
  function checkRate(ip, name) {
    const since = now() - 15 * 6e4;
    const a = db.prepare('SELECT COUNT(*) c FROM login_attempts WHERE key = ? AND ts > ? AND ok = 0').get(ip + '|' + name, since).c;
    const b = db.prepare('SELECT COUNT(*) c FROM login_attempts WHERE ip = ? AND ts > ? AND ok = 0').get(ip, since).c;
    if (a >= 5 || b >= 30) throw new HttpError(429, "Urinishlar ko'p. 15 daqiqadan keyin qayta urining.");
  }
  const noteAttempt = (ip, name, ok, kind) => db.prepare('INSERT INTO login_attempts (key, ip, ts, ok, kind) VALUES (?,?,?,?,?)').run(ip + '|' + name, ip, now(), ok ? 1 : 0, kind);

  function sameOrigin(req) {
    const o = req.headers.origin; if (!o) return true;
    try { return new URL(o).host === req.headers.host; } catch (e) { return false; }
  }

  // ---- Tekshiruv (validation) ----
  const NAME_RE = /^[\p{L}\p{N}][\p{L}\p{N} _.'-]{1,23}$/u;
  function str(v, max, label, required) {
    if (v == null || v === '') { if (required) throw bad(label + ' kiritilishi shart'); return ''; }
    if (typeof v !== 'string') throw bad(label + " noto'g'ri turda");
    v = v.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').trim();
    if (required && !v) throw bad(label + ' kiritilishi shart');
    if (v.length > max) throw bad(label + ' juda uzun (maks. ' + max + ')');
    return v;
  }
  function validWord(b) {
    const en = str(b.en, 40, 'Inglizcha so\'z', true);
    if (!/^[A-Za-z][A-Za-z '\-.]*$/.test(en)) throw bad("Inglizcha so'zda faqat lotin harflari, bo'shliq, ' - . bo'lishi mumkin");
    let uz = Array.isArray(b.uz) ? b.uz : String(b.uz || '').split(';');
    uz = uz.map((x) => str(x, 60, 'Tarjima')).filter(Boolean);
    if (!uz.length) throw bad('Kamida bitta tarjima kerak'); if (uz.length > 8) throw bad('Tarjimalar 8 tadan oshmasin');
    const sent = str(b.sent, 160, 'Misol gap'), sentUz = str(b.sentUz, 160, 'Gap tarjimasi');
    if (sent && !new RegExp('\\b' + en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(sent)) throw bad("Misol gapda so'zning o'zi bo'lishi kerak (bo'sh joyni to'ldirish mashqi uchun)");
    if (sent && !sentUz) throw bad('Misol gap tarjimasini kiriting');
    return { en, uz, emoji: str(b.emoji, 8, 'Emoji'), sent, sentUz };
  }
  const intIn = (v, min, max, label) => { v = Number(v); if (!Number.isInteger(v) || v < min || v > max) throw bad(label + " noto'g'ri"); return v; };

  // ---- Marshrutlar ----
  const routes = [];
  const route = (method, pattern, opts, handler) => routes.push({ method, re: new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), opts, handler });

  // ===== O'quvchilar API =====
  route('GET', '/api/ping', {}, (c) => ({ server: true, registrationOpen: setting('registrationOpen', true) }));
  route('GET', '/api/content', {}, () => ({
    rows: contentRows(),
    announcements: db.prepare('SELECT id, title, body, created FROM announcements WHERE active = 1 ORDER BY id DESC LIMIT 5').all()
  }));
  route('POST', '/api/register', { nocsrf: true }, (c) => {
    if (!setting('registrationOpen', true)) throw new HttpError(403, "Ro'yxatdan o'tish vaqtincha yopiq");
    const name = str(c.body.name, 24, 'Ism', true), pass = c.body.pass;
    if (!NAME_RE.test(name)) throw bad("Ism 2–24 belgi: harf, raqam, bo'shliq va _ . ' - ruxsat etiladi");
    if (typeof pass !== 'string' || pass.length < 6 || pass.length > 128) throw bad("Parol kamida 6 belgi bo'lsin");
    const ip = clientIp(c.req); checkRate(ip, name.toLowerCase());
    if (db.prepare('SELECT 1 FROM users WHERE name_lc = ?').get(name.toLowerCase())) throw new HttpError(409, 'Bu ism band');
    const r = db.prepare('INSERT INTO users (name, name_lc, pass_hash, created_at, last_seen) VALUES (?,?,?,?,?)').run(name, name.toLowerCase(), sec.hashPassword(pass), now(), now());
    const user = { id: Number(r.lastInsertRowid), name };
    return { user: { name }, state: null, csrf: createSession(c.res, user, 'learner') };
  });
  route('POST', '/api/login', { nocsrf: true }, (c) => {
    const name = str(c.body.name, 24, 'Ism', true).toLowerCase(), ip = clientIp(c.req); checkRate(ip, name);
    const u = db.prepare('SELECT * FROM users WHERE name_lc = ?').get(name);
    const ok = sec.verifyPassword(String(c.body.pass || ''), u && u.pass_hash);
    noteAttempt(ip, name, ok && u.status === 'active', 'learner');
    if (!ok) throw new HttpError(401, "Ism yoki parol noto'g'ri");
    if (u.status !== 'active') throw new HttpError(403, 'Hisob bloklangan. Administratorga murojaat qiling.');
    db.prepare('UPDATE users SET last_seen = ? WHERE id = ?').run(now(), u.id);
    return { user: { name: u.name }, state: u.state ? JSON.parse(u.state) : null, csrf: createSession(c.res, u, 'learner') };
  });
  route('POST', '/api/logout', {}, (c) => { const t = parseCookies(c.req)[COOKIE.learner]; if (t) db.prepare('DELETE FROM sessions WHERE id_hash = ?').run(sec.sha(t)); c.res.cookies.push(cookieHeader('learner', '', 0)); return { ok: true }; });
  route('GET', '/api/me', { learner: true }, (c) => ({ user: { name: c.me.name }, state: c.me.state ? JSON.parse(c.me.state) : null, csrf: c.me.csrf }));
  route('PUT', '/api/state', { learner: true }, (c) => {
    const s = c.body.state; if (!s || typeof s !== 'object' || Array.isArray(s)) throw bad("Holat noto'g'ri");
    const xp = Number(s.xp); if (!Number.isFinite(xp) || xp < 0 || xp > 1e7) throw bad("XP noto'g'ri");
    const json = JSON.stringify(s); if (json.length > 400 * 1024) throw bad('Holat juda katta');
    const lessons = Object.keys(s.done || {}).length, learned = Object.values(s.words || {}).filter((w) => w && w.c > 0).length;
    db.prepare('UPDATE users SET state = ?, xp = ?, streak = ?, lessons = ?, words_learned = ?, last_seen = ? WHERE id = ?')
      .run(json, Math.floor(xp), Math.max(0, Math.floor(Number(s.streak) || 0)), lessons, learned, now(), c.me.id);
    return { ok: true };
  });
  route('POST', '/api/event', { learner: true }, (c) => {
    const b = c.body; if (!['lesson', 'review', 'test', 'practice', 'mistakes'].includes(b.mode)) throw bad('mode');
    const node = b.node == null ? null : str(b.node, 12, 'node');
    db.prepare('INSERT INTO events (user_id, ts, mode, node, pct, xp, ok) VALUES (?,?,?,?,?,?,?)').run(c.me.id, now(), b.mode, node, intIn(b.pct, 0, 100, 'pct'), intIn(b.xp, 0, 1000, 'xp'), b.ok ? 1 : 0);
    return { ok: true };
  });
  route('DELETE', '/api/me', { learner: true }, (c) => {
    if (c.me.role !== 'user') throw new HttpError(403, "Administrator hisobini bu yerdan o'chirib bo'lmaydi");
    db.prepare('DELETE FROM users WHERE id = ?').run(c.me.id); c.res.cookies.push(cookieHeader('learner', '', 0)); return { ok: true };
  });

  // ===== Admin: kirish =====
  route('POST', '/api/admin/login', { nocsrf: true }, (c) => {
    const name = str(c.body.name, 24, 'Ism', true).toLowerCase(), ip = clientIp(c.req); checkRate(ip, name);
    const u = db.prepare("SELECT * FROM users WHERE name_lc = ? AND role != 'user'").get(name);
    const ok = sec.verifyPassword(String(c.body.pass || ''), u && u.pass_hash) && u && u.status === 'active';
    noteAttempt(ip, name, ok, 'admin');
    if (!ok) { audit(null, 'admin.login', name, false, ip); throw new HttpError(401, "Ism yoki parol noto'g'ri"); }
    db.prepare('UPDATE users SET last_seen = ? WHERE id = ?').run(now(), u.id);
    audit(u, 'admin.login', u.name, true);
    return { admin: { name: u.name, role: u.role, perms: PERMS[u.role] }, csrf: createSession(c.res, u, 'admin') };
  });
  route('POST', '/api/admin/logout', { admin: true }, (c) => {
    db.prepare('DELETE FROM sessions WHERE id_hash = ?').run(c.me.id_hash); audit(c.me, 'admin.logout', c.me.name, true);
    c.res.cookies.push(cookieHeader('admin', '', 0)); return { ok: true };
  });
  route('GET', '/api/admin/me', { admin: true }, (c) => ({ admin: { name: c.me.name, role: c.me.role, perms: PERMS[c.me.role] }, csrf: c.me.csrf }));

  // ===== Admin: boshqaruv paneli va statistika =====
  const DAY = 864e5;
  function dayKey(ts) { const d = new Date(ts); return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0'); }
  function series(days) {
    const out = {}, start = now() - (days - 1) * DAY;
    for (let i = 0; i < days; i++) out[dayKey(start + i * DAY)] = { date: dayKey(start + i * DAY), registrations: 0, active: 0, lessons: 0, xp: 0 };
    db.prepare("SELECT created_at FROM users WHERE role = 'user' AND created_at >= ?").all(start - DAY).forEach((r) => { const k = dayKey(r.created_at); if (out[k]) out[k].registrations++; });
    const act = {};
    db.prepare('SELECT user_id, ts, ok, xp FROM events WHERE ts >= ?').all(start - DAY).forEach((e) => {
      const k = dayKey(e.ts); if (!out[k]) return; (act[k] = act[k] || new Set()).add(e.user_id); out[k].xp += e.xp; if (e.ok) out[k].lessons++;
    });
    Object.keys(act).forEach((k) => { out[k].active = act[k].size; });
    return Object.values(out);
  }
  function wordStats() { // barcha foydalanuvchilarning haqiqiy javoblaridan
    const agg = {};
    db.prepare("SELECT state FROM users WHERE state IS NOT NULL AND role = 'user'").all().forEach((r) => {
      try { const w = JSON.parse(r.state).words || {}; Object.keys(w).forEach((id) => { const a = agg[id] || (agg[id] = { c: 0, w: 0, users: 0 }); a.c += w[id].c || 0; a.w += w[id].w || 0; a.users++; }); } catch (e) {}
    });
    return agg;
  }
  function dashboard(me, days) {
    const out = { role: me.role };
    mergedCourse(false);
    const lessonNodes = TY.NODES.filter((n) => n.kind === 'lesson').length;
    out.content = { levels: TY.LEVELS.length, lessons: lessonNodes, tests: TY.LEVELS.length, exercises: KINDS.length + 1, words: TY.allWords.length, hiddenWords: db.prepare('SELECT COUNT(*) c FROM content_words WHERE hidden = 1').get().c, edits: db.prepare('SELECT COUNT(*) c FROM content_words').get().c };
    if (!PERMS[me.role].includes('users')) return out;
    const t = now(), total = db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user'").get().c;
    const act = (d) => db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user' AND last_seen >= ?").get(t - d * DAY).c;
    const doneAvg = db.prepare("SELECT state FROM users WHERE role = 'user' AND state IS NOT NULL").all().map((r) => { try { return Object.keys(JSON.parse(r.state).done || {}).length; } catch (e) { return 0; } });
    out.users = { total, active7: act(7), active30: act(30), new7: db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user' AND created_at >= ?").get(t - 7 * DAY).c, disabled: db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user' AND status = 'disabled'").get().c };
    out.learning = {
      lessonsCompleted: db.prepare('SELECT COUNT(*) c FROM events WHERE ok = 1').get().c,
      avgProgress: total ? Math.round(100 * doneAvg.reduce((a, b) => a + b, 0) / (total * TY.NODES.length) * 10) / 10 : 0,
      totalXp: db.prepare("SELECT COALESCE(SUM(xp),0) s FROM users WHERE role = 'user'").get().s
    };
    const nodeTitle = (id) => { const n = TY.nodeById[id]; return n ? TY.LEVELS[n.level].id + ' · ' + n.title : id; };
    out.popularLessons = db.prepare("SELECT node, COUNT(*) n FROM events WHERE node IS NOT NULL GROUP BY node ORDER BY n DESC LIMIT 5").all().map((r) => ({ node: r.node, title: nodeTitle(r.node), count: r.n }));
    out.hardLessons = db.prepare('SELECT node, COUNT(*) n, ROUND(AVG(pct)) avg FROM events WHERE node IS NOT NULL GROUP BY node HAVING n >= 3 ORDER BY avg ASC LIMIT 5').all().map((r) => ({ node: r.node, title: nodeTitle(r.node), attempts: r.n, avgScore: r.avg }));
    const ws = wordStats();
    out.hardWords = Object.keys(ws).filter((id) => TY.wordById[id] && ws[id].c + ws[id].w >= 5).map((id) => ({ id, en: TY.wordById[id].en, uz: TY.wordById[id].uz[0], attempts: ws[id].c + ws[id].w, wrongRate: Math.round(100 * ws[id].w / (ws[id].c + ws[id].w)) })).sort((a, b) => b.wrongRate - a.wrongRate).slice(0, 8);
    out.recentUsers = db.prepare("SELECT id, name, created_at, xp FROM users WHERE role = 'user' ORDER BY id DESC LIMIT 8").all();
    out.recentActivity = db.prepare('SELECT e.ts, e.mode, e.node, e.pct, e.xp, e.ok, u.name, u.id uid FROM events e JOIN users u ON u.id = e.user_id ORDER BY e.id DESC LIMIT 10').all().map((e) => Object.assign(e, { title: e.node ? nodeTitle(e.node) : { practice: 'Aralash mashq', mistakes: 'Xato so\'zlar' }[e.mode] }));
    out.series = series(days);
    // Daraja bo'yicha taqsimot: foydalanuvchi yetgan eng yuqori daraja
    const dist = TY.LEVELS.map((lv) => ({ level: lv.id, users: 0 }));
    db.prepare("SELECT state FROM users WHERE role = 'user' AND state IS NOT NULL").all().forEach((r) => {
      try { const d = JSON.parse(r.state).done || {}; let top = 0; Object.keys(d).forEach((id) => { const m = /^L(\d)/.exec(id); if (m) top = Math.max(top, +m[1]); }); if (Object.keys(d).length) dist[top].users++; } catch (e) {}
    });
    out.levelDistribution = dist;
    return out;
  }
  route('GET', '/api/admin/dashboard', { admin: true, perm: 'dashboard' }, (c) => dashboard(c.me, intIn(c.q.days || 30, 7, 90, 'days')));
  route('GET', '/api/admin/achievements', { admin: true, perm: 'stats' }, () => {
    const counts = {}; let total = 0;
    db.prepare("SELECT state FROM users WHERE role = 'user' AND state IS NOT NULL").all().forEach((r) => { total++; try { Object.keys(JSON.parse(r.state).ach || {}).forEach((id) => { counts[id] = (counts[id] || 0) + 1; }); } catch (e) {} });
    return { counts, users: total };
  });
  route('GET', '/api/admin/notifications', { admin: true, perm: 'dashboard' }, (c) => {
    const list = [], t = now(); const can = PERMS[c.me.role];
    if (can.includes('users')) {
      const n = db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user' AND created_at >= ?").get(t - DAY).c; if (n) list.push({ type: 'info', text: `Oxirgi 24 soatda ${n} ta yangi foydalanuvchi`, ts: t });
      const f = db.prepare("SELECT COUNT(*) c FROM login_attempts WHERE ok = 0 AND ts >= ? AND kind = 'admin'").get(t - DAY).c; if (f) list.push({ type: 'warn', text: `Admin kirishida ${f} ta muvaffaqiyatsiz urinish (24 soat)`, ts: t });
      const d = db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'user' AND status = 'disabled'").get().c; if (d) list.push({ type: 'info', text: `${d} ta bloklangan hisob`, ts: t });
    }
    if (can.includes('audit')) db.prepare('SELECT ts, action, target, user_name FROM audit_log WHERE ok = 0 ORDER BY id DESC LIMIT 5').all().forEach((a) => list.push({ type: 'err', text: `Muvaffaqiyatsiz: ${a.action} ${a.target || ''}`, ts: a.ts }));
    return { items: list };
  });

  // ===== Admin: foydalanuvchilar =====
  route('GET', '/api/admin/users', { admin: true, perm: 'users' }, (c) => {
    const page = intIn(c.q.page || 1, 1, 10000, 'page'), size = 20, q = String(c.q.q || '').toLowerCase().slice(0, 40).replace(/[%_\\]/g, '\\$&');
    const status = ['active', 'disabled'].includes(c.q.status) ? c.q.status : null;
    const sort = { name: 'name_lc', xp: 'xp DESC', created: 'created_at DESC', seen: 'last_seen DESC' }[c.q.sort] || 'created_at DESC';
    const where = "role = 'user' AND name_lc LIKE ? ESCAPE '\\'" + (status ? ' AND status = ?' : ''), args = ['%' + q + '%'].concat(status ? [status] : []);
    const total = db.prepare('SELECT COUNT(*) c FROM users WHERE ' + where).get(...args).c;
    const rows = db.prepare(`SELECT id, name, status, created_at, last_seen, xp, streak, lessons, words_learned FROM users WHERE ${where} ORDER BY ${sort} LIMIT ? OFFSET ?`).all(...args, size, (page - 1) * size);
    return { rows, total, page, pages: Math.max(1, Math.ceil(total / size)) };
  });
  route('GET', '/api/admin/users/:id', { admin: true, perm: 'users' }, (c) => {
    const u = db.prepare("SELECT id, name, status, created_at, last_seen, xp, streak, lessons, words_learned, state FROM users WHERE id = ? AND role = 'user'").get(intIn(c.params.id, 1, 1e9, 'id'));
    if (!u) throw new HttpError(404, 'Foydalanuvchi topilmadi');
    const s = u.state ? JSON.parse(u.state) : {}; delete u.state; mergedCourse(false);
    const days = Object.keys(s.days || {}).sort().slice(-14).map((d) => Object.assign({ date: d }, s.days[d]));
    const hard = Object.keys(s.words || {}).filter((id) => TY.wordById[id] && s.words[id].w > 0).map((id) => ({ en: TY.wordById[id].en, uz: TY.wordById[id].uz[0], wrong: s.words[id].w, right: s.words[id].c })).sort((a, b) => b.wrong - a.wrong).slice(0, 10);
    const done = Object.keys(s.done || {}).map((id) => ({ id, title: TY.nodeById[id] ? TY.LEVELS[TY.nodeById[id].level].id + ' · ' + TY.nodeById[id].title : id, best: s.done[id].best }));
    return {
      user: u, progress: { hearts: s.hearts, bestStreak: s.bestStreak, goalMin: s.goalMin, achievements: Object.keys(s.ach || {}), mistakes: Object.keys(s.mistakes || {}).length, done, percent: Math.round(100 * done.length / TY.NODES.length) },
      days, hardWords: hard, events: db.prepare('SELECT ts, mode, node, pct, xp, ok FROM events WHERE user_id = ? ORDER BY id DESC LIMIT 15').all(u.id)
    };
  });
  route('POST', '/api/admin/users/:id/status', { admin: true, perm: 'users' }, (c) => {
    const id = intIn(c.params.id, 1, 1e9, 'id'), st = c.body.status; if (!['active', 'disabled'].includes(st)) throw bad('status');
    const r = db.prepare("UPDATE users SET status = ? WHERE id = ? AND role = 'user'").run(st, id); if (!r.changes) throw new HttpError(404, 'Topilmadi');
    if (st === 'disabled') db.prepare('DELETE FROM sessions WHERE user_id = ?').run(id);
    audit(c.me, 'user.' + st, id, true); return { ok: true };
  });
  route('POST', '/api/admin/users/:id/reset-progress', { admin: true, perm: 'users' }, (c) => {
    const id = intIn(c.params.id, 1, 1e9, 'id');
    const r = db.prepare("UPDATE users SET state = NULL, xp = 0, streak = 0, lessons = 0, words_learned = 0 WHERE id = ? AND role = 'user'").run(id); if (!r.changes) throw new HttpError(404, 'Topilmadi');
    db.prepare('DELETE FROM events WHERE user_id = ?').run(id); audit(c.me, 'user.reset-progress', id, true); return { ok: true };
  });
  route('DELETE', '/api/admin/users/:id', { admin: true, perm: 'admins' }, (c) => {
    const id = intIn(c.params.id, 1, 1e9, 'id'); const r = db.prepare("DELETE FROM users WHERE id = ? AND role = 'user'").run(id);
    if (!r.changes) throw new HttpError(404, 'Topilmadi'); audit(c.me, 'user.delete', id, true); return { ok: true };
  });
  route('GET', '/api/admin/export/users.csv', { admin: true, perm: 'users', raw: true }, (c) => {
    const rows = db.prepare("SELECT id, name, status, created_at, last_seen, xp, streak, lessons, words_learned FROM users WHERE role = 'user' ORDER BY id").all();
    audit(c.me, 'export.users', rows.length, true);
    const iso = (t) => (t ? new Date(t).toISOString() : '');
    return { csv: ['id,name,status,created,last_seen,xp,streak,lessons,words_learned'].concat(rows.map((r) => [r.id, r.name, r.status, iso(r.created_at), iso(r.last_seen), r.xp, r.streak, r.lessons, r.words_learned].map(sec.csvCell).join(','))).join('\n'), file: 'users.csv' };
  });

  // ===== Admin: kurs mazmuni =====
  route('GET', '/api/admin/content', { admin: true, perm: 'content' }, () => {
    const L = mergedCourse(true);
    const edited = new Set(db.prepare('SELECT id FROM content_words').all().map((r) => r.id));
    return {
      levels: L.map((lv, li) => ({ idx: li, id: lv.id, title: lv.title, sub: lv.sub, color: lv.color, topics: lv.topics.map((tp, ti) => ({ idx: ti, title: tp.title, icon: tp.icon, tip: tp.tip, visible: tp.words.filter((w) => !w.hidden).length, published: tp.words.filter((w) => !w.hidden).length >= TY.MIN_WORDS, words: tp.words.map((w) => Object.assign({}, w, { edited: edited.has(w.id), custom: /\.a\d+$/.test(w.id) })) })) })),
      disabled: setting('disabledKinds', []), kinds: KINDS, minWords: TY.MIN_WORDS
    };
  });
  function findTopic(level, topic) {
    const L = mergedCourse(true); const lv = L[intIn(level, 0, L.length - 1, 'Daraja')], tp = lv.topics[intIn(topic, 0, lv.topics.length - 1, 'Mavzu')]; return { lv, tp };
  }
  function duplicateOf(level, en, exceptId) {
    const L = mergedCourse(true); const key = en.toLowerCase();
    for (const tp of L[level].topics) for (const w of tp.words) if (w.id !== exceptId && w.en.toLowerCase() === key) return { id: w.id, topic: tp.title, hidden: !!w.hidden };
    return null;
  }
  const nextPos = () => (db.prepare('SELECT COALESCE(MAX(pos),0)+1 p FROM content_words').get().p);
  function upsertWord(id, level, topic, v, base, hidden, pos) {
    db.prepare(`INSERT INTO content_words (id, level, topic, en, uz, emoji, sent, sentUz, hidden, base, pos) VALUES (?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET en = excluded.en, uz = excluded.uz, emoji = excluded.emoji, sent = excluded.sent, sentUz = excluded.sentUz, hidden = excluded.hidden`)
      .run(id, level, topic, v.en, JSON.stringify(v.uz), v.emoji, v.sent, v.sentUz, hidden ? 1 : 0, base ? 1 : 0, pos);
  }
  function newWordId(level, topic) { const n = db.prepare('SELECT COUNT(*) c FROM content_words WHERE base = 0').get().c; let k = n + 1, id; do { id = `${level}.${topic}.a${k++}`; } while (db.prepare('SELECT 1 FROM content_words WHERE id = ?').get(id)); return id; }

  route('POST', '/api/admin/words', { admin: true, perm: 'content' }, (c) => {
    const { tp } = findTopic(c.body.level, c.body.topic), level = +c.body.level, topic = +c.body.topic, v = validWord(c.body);
    const dup = duplicateOf(level, v.en); if (dup && !c.body.allowDuplicate) throw new HttpError(409, `«${v.en}» bu darajada allaqachon bor (${dup.topic}). Baribir qo'shish uchun tasdiqlang.`, { duplicate: dup });
    const id = newWordId(level, topic); upsertWord(id, level, topic, v, false, false, nextPos()); audit(c.me, 'word.create', id + ' ' + v.en, true); return { id };
  });
  route('PUT', '/api/admin/words/:id', { admin: true, perm: 'content' }, (c) => {
    const L = mergedCourse(true); let found = null;
    L.forEach((lv, li) => lv.topics.forEach((tp, ti) => tp.words.forEach((w) => { if (w.id === c.params.id) found = { li, ti, w, tp }; })));
    if (!found) throw new HttpError(404, "So'z topilmadi");
    const v = validWord(c.body), hidden = !!c.body.hidden;
    if (hidden && !found.w.hidden && found.tp.words.filter((w) => !w.hidden).length - 1 < TY.MIN_WORDS) throw new HttpError(409, `Mavzuda kamida ${TY.MIN_WORDS} ta ko'rinadigan so'z qolishi kerak`);
    const dup = duplicateOf(found.li, v.en, found.w.id); if (dup && !c.body.allowDuplicate && v.en.toLowerCase() !== found.w.en.toLowerCase()) throw new HttpError(409, `«${v.en}» allaqachon bor`, { duplicate: dup });
    const row = db.prepare('SELECT pos, base FROM content_words WHERE id = ?').get(found.w.id);
    upsertWord(found.w.id, found.li, found.ti, v, row ? row.base : 1, hidden, row ? row.pos : nextPos());
    audit(c.me, hidden !== !!found.w.hidden ? (hidden ? 'word.hide' : 'word.restore') : 'word.update', found.w.id + ' ' + v.en, true); return { ok: true };
  });
  route('DELETE', '/api/admin/words/:id', { admin: true, perm: 'content' }, (c) => {
    const L = mergedCourse(true); let found = null;
    L.forEach((lv, li) => lv.topics.forEach((tp, ti) => tp.words.forEach((w) => { if (w.id === c.params.id) found = { li, ti, w, tp }; })));
    if (!found) throw new HttpError(404, "So'z topilmadi");
    if (!found.w.hidden && found.tp.words.filter((w) => !w.hidden).length - 1 < TY.MIN_WORDS) throw new HttpError(409, `Mavzuda kamida ${TY.MIN_WORDS} ta ko'rinadigan so'z qolishi kerak`);
    const row = db.prepare('SELECT base FROM content_words WHERE id = ?').get(found.w.id);
    if (row && row.base === 0) { db.prepare('DELETE FROM content_words WHERE id = ?').run(found.w.id); audit(c.me, 'word.delete', found.w.id, true); return { deleted: true }; }
    // Asosiy kurs so'zi: foydalanuvchilar progressi buzilmasligi uchun yashiriladi (qaytarish mumkin)
    upsertWord(found.w.id, found.li, found.ti, found.w, true, true, row ? 0 : nextPos());
    audit(c.me, 'word.hide', found.w.id + ' ' + found.w.en, true); return { hidden: true };
  });
  route('POST', '/api/admin/import', { admin: true, perm: 'content' }, (c) => {
    const { tp } = findTopic(c.body.level, c.body.topic), level = +c.body.level, topic = +c.body.topic;
    const rows = c.body.rows; if (!Array.isArray(rows) || !rows.length) throw bad('Qatorlar yo\'q'); if (rows.length > 500) throw bad('Bir martada 500 tadan ko\'p qator mumkin emas');
    const mode = ['report', 'skip', 'allow'].includes(c.body.duplicates) ? c.body.duplicates : 'report', dry = !!c.body.dryRun;
    const result = { added: [], duplicates: [], invalid: [] }, seen = new Set();
    const apply = [];
    rows.forEach((r, i) => {
      try {
        const v = validWord({ en: r[0], uz: String(r[1] || '').split(/[;,]/), emoji: r[2], sent: r[3], sentUz: r[4] });
        const key = v.en.toLowerCase(), dup = duplicateOf(level, v.en) || (seen.has(key) ? { topic: 'importdagi takror' } : null); seen.add(key);
        if (dup) { result.duplicates.push({ row: i + 1, en: v.en, where: dup.topic }); if (mode !== 'allow') return; }
        apply.push(v); result.added.push({ row: i + 1, en: v.en });
      } catch (e) { result.invalid.push({ row: i + 1, en: String(r[0] || ''), error: e.message }); }
    });
    if (dry || (mode === 'report' && result.duplicates.length)) { result.applied = false; return result; }
    db.tx(() => { apply.forEach((v) => upsertWord(newWordId(level, topic), level, topic, v, false, false, nextPos())); });
    result.applied = true; audit(c.me, 'word.import', `L${level}T${topic} +${apply.length}`, true, `takror: ${result.duplicates.length}, xato: ${result.invalid.length}`); return result;
  });
  route('POST', '/api/admin/topics', { admin: true, perm: 'content' }, (c) => {
    const L = mergedCourse(true), level = intIn(c.body.level, 0, L.length - 1, 'Daraja');
    const idx = L[level].topics.length; if (idx >= 12) throw bad('Bir darajada 12 tadan ko\'p mavzu mumkin emas');
    db.prepare('INSERT INTO content_topics (level, idx, title, icon, tip) VALUES (?,?,?,?,?)').run(level, idx, str(c.body.title, 40, 'Mavzu nomi', true), str(c.body.icon, 8, 'Belgi') || '📘', str(c.body.tip, 400, 'Tushuntirish'));
    audit(c.me, 'topic.create', `L${level}T${idx}`, true); return { idx };
  });
  route('PUT', '/api/admin/topics/:level/:idx', { admin: true, perm: 'content' }, (c) => {
    findTopic(c.params.level, c.params.idx);
    db.prepare(`INSERT INTO content_topics (level, idx, title, icon, tip) VALUES (?,?,?,?,?) ON CONFLICT(level, idx) DO UPDATE SET title = excluded.title, icon = excluded.icon, tip = excluded.tip`)
      .run(+c.params.level, +c.params.idx, str(c.body.title, 40, 'Mavzu nomi', true), str(c.body.icon, 8, 'Belgi') || '📘', str(c.body.tip, 400, 'Tushuntirish'));
    audit(c.me, 'topic.update', `L${c.params.level}T${c.params.idx}`, true); return { ok: true };
  });
  route('PUT', '/api/admin/levels/:idx', { admin: true, perm: 'content' }, (c) => {
    const L = mergedCourse(true), idx = intIn(c.params.idx, 0, L.length - 1, 'Daraja');
    db.prepare('INSERT INTO content_levels (idx, title, sub) VALUES (?,?,?) ON CONFLICT(idx) DO UPDATE SET title = excluded.title, sub = excluded.sub').run(idx, str(c.body.title, 40, 'Nom', true), str(c.body.sub, 60, 'Tavsif', true));
    audit(c.me, 'level.update', idx, true); return { ok: true };
  });
  route('PUT', '/api/admin/exercises', { admin: true, perm: 'exercises' }, (c) => {
    const d = c.body.disabled; if (!Array.isArray(d) || d.some((k) => !KINDS.includes(k))) throw bad("Mashq turi noto'g'ri");
    if (EASY.every((k) => d.includes(k)) || HARD.every((k) => d.includes(k))) throw bad("Yengil va murakkab guruhlarning har birida kamida bitta mashq turi yoqiq bo'lsin");
    setSetting('disabledKinds', Array.from(new Set(d))); audit(c.me, 'exercises.update', d.join(',') || '-', true); return { ok: true };
  });

  // ===== Admin: e'lonlar, audit, sozlamalar, adminlar =====
  route('GET', '/api/admin/announcements', { admin: true, perm: 'announcements' }, () => ({ rows: db.prepare('SELECT * FROM announcements ORDER BY id DESC LIMIT 100').all() }));
  route('POST', '/api/admin/announcements', { admin: true, perm: 'announcements' }, (c) => {
    const r = db.prepare('INSERT INTO announcements (title, body, active, created, author) VALUES (?,?,?,?,?)').run(str(c.body.title, 80, 'Sarlavha', true), str(c.body.body, 500, 'Matn', true), c.body.active === false ? 0 : 1, now(), c.me.name);
    audit(c.me, 'announcement.create', r.lastInsertRowid, true); return { id: Number(r.lastInsertRowid) };
  });
  route('PUT', '/api/admin/announcements/:id', { admin: true, perm: 'announcements' }, (c) => {
    const r = db.prepare('UPDATE announcements SET title = ?, body = ?, active = ? WHERE id = ?').run(str(c.body.title, 80, 'Sarlavha', true), str(c.body.body, 500, 'Matn', true), c.body.active ? 1 : 0, intIn(c.params.id, 1, 1e9, 'id'));
    if (!r.changes) throw new HttpError(404, 'Topilmadi'); audit(c.me, 'announcement.update', c.params.id, true); return { ok: true };
  });
  route('DELETE', '/api/admin/announcements/:id', { admin: true, perm: 'announcements' }, (c) => { db.prepare('DELETE FROM announcements WHERE id = ?').run(intIn(c.params.id, 1, 1e9, 'id')); audit(c.me, 'announcement.delete', c.params.id, true); return { ok: true }; });
  route('GET', '/api/admin/audit', { admin: true, perm: 'audit' }, (c) => {
    const page = intIn(c.q.page || 1, 1, 10000, 'page'), size = 30, total = db.prepare('SELECT COUNT(*) c FROM audit_log').get().c;
    return { rows: db.prepare('SELECT id, ts, user_name, action, target, ok, detail FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?').all(size, (page - 1) * size), total, page, pages: Math.max(1, Math.ceil(total / size)) };
  });
  route('GET', '/api/admin/settings', { admin: true, perm: 'settings' }, () => ({ registrationOpen: setting('registrationOpen', true) }));
  route('PUT', '/api/admin/settings', { admin: true, perm: 'settings' }, (c) => { setSetting('registrationOpen', !!c.body.registrationOpen); audit(c.me, 'settings.update', 'registrationOpen=' + !!c.body.registrationOpen, true); return { ok: true }; });
  route('GET', '/api/admin/admins', { admin: true, perm: 'admins' }, () => ({ rows: db.prepare("SELECT id, name, role, status, created_at, last_seen FROM users WHERE role != 'user' ORDER BY id").all() }));
  route('POST', '/api/admin/admins', { admin: true, perm: 'admins' }, (c) => {
    const name = str(c.body.name, 24, 'Ism', true); if (!NAME_RE.test(name)) throw bad("Ism noto'g'ri");
    if (!['editor', 'admin', 'super_admin'].includes(c.body.role)) throw bad('Rol');
    const p = sec.passwordProblem(c.body.pass); if (p) throw bad(p);
    if (db.prepare('SELECT 1 FROM users WHERE name_lc = ?').get(name.toLowerCase())) throw new HttpError(409, 'Bu ism band');
    db.prepare('INSERT INTO users (name, name_lc, pass_hash, role, created_at) VALUES (?,?,?,?,?)').run(name, name.toLowerCase(), sec.hashPassword(c.body.pass), c.body.role, now());
    audit(c.me, 'admin.create', name + ':' + c.body.role, true); return { ok: true };
  });
  route('PUT', '/api/admin/admins/:id', { admin: true, perm: 'admins' }, (c) => {
    const id = intIn(c.params.id, 1, 1e9, 'id'), u = db.prepare("SELECT * FROM users WHERE id = ? AND role != 'user'").get(id); if (!u) throw new HttpError(404, 'Topilmadi');
    const role = c.body.role || u.role, status = c.body.status || u.status;
    if (!['editor', 'admin', 'super_admin'].includes(role) || !['active', 'disabled'].includes(status)) throw bad("Qiymat noto'g'ri");
    if (id === c.me.id && (role !== u.role || status !== 'active')) throw new HttpError(409, "O'zingizning rolingiz yoki holatingizni o'zgartira olmaysiz");
    if (u.role === 'super_admin' && (role !== 'super_admin' || status !== 'active') && db.prepare("SELECT COUNT(*) c FROM users WHERE role = 'super_admin' AND status = 'active'").get().c <= 1) throw new HttpError(409, "Oxirgi faol Super Admin'ni o'zgartirib bo'lmaydi");
    if (c.body.pass) { const p = sec.passwordProblem(c.body.pass); if (p) throw bad(p); db.prepare('UPDATE users SET pass_hash = ? WHERE id = ?').run(sec.hashPassword(c.body.pass), id); }
    db.prepare('UPDATE users SET role = ?, status = ? WHERE id = ?').run(role, status, id);
    if (role !== u.role || status !== 'active' || c.body.pass) db.prepare('DELETE FROM sessions WHERE user_id = ?').run(id);
    audit(c.me, 'admin.update', `${u.name} → ${role}/${status}${c.body.pass ? ' +parol' : ''}`, true); return { ok: true };
  });

  // ---- Dispetcher ----
  function readBody(req) {
    return new Promise((resolve, reject) => {
      const chunks = []; let n = 0;
      req.on('data', (d) => { n += d.length; if (n > MAX_BODY) { reject(new HttpError(413, "So'rov juda katta")); req.destroy(); } else chunks.push(d); });
      req.on('end', () => { if (!n) return resolve({}); try { const o = JSON.parse(Buffer.concat(chunks).toString('utf8')); resolve(o && typeof o === 'object' ? o : {}); } catch (e) { reject(bad('JSON noto\'g\'ri')); } });
      req.on('error', reject);
    });
  }
  const HEADERS = {
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
  };
  function send(res, status, body, type, extra) {
    const h = Object.assign({}, HEADERS, { 'Content-Type': type || 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }, extra || {});
    if (res.cookies && res.cookies.length) h['Set-Cookie'] = res.cookies;
    res.writeHead(status, h); res.end(body);
  }
  function serveStatic(req, res, pathname) {
    let rel = pathname === '/' ? 'index.html' : pathname === '/admin' || pathname === '/admin/' ? 'admin/admin.html' : pathname.replace(/^\/+/, '');
    if (!STATIC.has(rel)) return send(res, 404, 'Topilmadi', 'text/plain; charset=utf-8');
    try { send(res, 200, fs.readFileSync(path.join(ROOT, rel)), MIME[path.extname(rel)]); } catch (e) { send(res, 404, 'Topilmadi', 'text/plain; charset=utf-8'); }
  }
  async function handler(req, res) {
    res.cookies = [];
    const url = new URL(req.url, 'http://x'), pathname = url.pathname;
    if (!pathname.startsWith('/api/')) { if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Method not allowed', 'text/plain'); return serveStatic(req, res, pathname); }
    try {
      const r = routes.find((x) => x.method === req.method && x.re.test(pathname));
      if (!r) throw new HttpError(404, 'API topilmadi');
      const params = Object.assign({}, r.re.exec(pathname).groups), q = Object.fromEntries(url.searchParams);
      const c = { req, res, params, q, body: {}, me: null };
      if (req.method !== 'GET') {
        if (!sameOrigin(req)) throw new HttpError(403, "Noto'g'ri manba (Origin)");
        c.body = await readBody(req);
      }
      if (r.opts.admin || r.opts.learner) {
        const kind = r.opts.admin ? 'admin' : 'learner'; c.me = getSession(req, kind);
        if (!c.me) throw new HttpError(401, 'Kirish talab qilinadi');
        if (req.method !== 'GET' && !sec.safeEq(req.headers['x-csrf-token'], c.me.csrf)) throw new HttpError(403, 'CSRF tokeni noto\'g\'ri');
        if (r.opts.perm && !PERMS[c.me.role].includes(r.opts.perm)) { audit(c.me, 'forbidden', req.method + ' ' + pathname, false); throw new HttpError(403, "Bu amal uchun ruxsat yo'q"); }
      }
      const out = r.handler(c);
      if (out && out.csv != null) return send(res, 200, '﻿' + out.csv, 'text/csv; charset=utf-8', { 'Content-Disposition': `attachment; filename="${out.file}"` });
      send(res, 200, JSON.stringify(out == null ? {} : out));
    } catch (e) {
      if (e instanceof HttpError) return send(res, e.status, JSON.stringify(Object.assign({ error: e.message }, e.extra || {})));
      console.error('Ichki xato:', e && e.stack || e); send(res, 500, JSON.stringify({ error: 'Ichki server xatosi' }));
    }
  }
  // Muddati o'tgan sessiya va eski urinishlarni tozalash
  const gc = setInterval(() => { try { db.prepare('DELETE FROM sessions WHERE expires < ?').run(now()); db.prepare('DELETE FROM login_attempts WHERE ts < ?').run(now() - DAY); } catch (e) {} }, 6e5); gc.unref();
  return { server: http.createServer(handler), db, TY };
}

if (require.main === module) {
  const { server } = createApp(process.env.TILYOLI_DB || path.join(__dirname, 'data', 'tilyoli.db'));
  server.listen(PORT, process.env.HOST || '127.0.0.1', () => console.log(`Til Yo'li: http://localhost:${PORT}/   Admin panel: http://localhost:${PORT}/admin`));
}
module.exports = { createApp };
