'use strict';
// Birinchi administratorni xavfsiz yaratish (ochiq standart akkaunt YO'Q):
//   node server/cli.js create-admin <ism> [super_admin|admin|editor]   (parol so'raladi, ekranda ko'rinmaydi)
//   node server/cli.js reset-password <ism>
//   node server/cli.js list-admins
const readline = require('readline');
const path = require('path');
const { open } = require('./db');
const sec = require('./security');
const db = open(process.env.TILYOLI_DB || path.join(__dirname, 'data', 'tilyoli.db'));

function askHidden(q) {
  return new Promise((res) => {
    if (process.env.TILYOLI_PASSWORD) return res(process.env.TILYOLI_PASSWORD); // avtomatlashtirish uchun
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    rl._writeToOutput = (s) => { if (s.includes(q)) rl.output.write(s); };
    rl.question(q, (a) => { rl.output.write('\n'); rl.close(); res(a); });
  });
}
(async () => {
  const [cmd, name, role = 'super_admin'] = process.argv.slice(2);
  if (cmd === 'create-admin') {
    if (!name || !['super_admin', 'admin', 'editor'].includes(role)) throw new Error('Foydalanish: create-admin <ism> [super_admin|admin|editor]');
    const pass = await askHidden('Parol (kamida 10 belgi, harf va raqam): ');
    const prob = sec.passwordProblem(pass); if (prob) throw new Error(prob);
    db.prepare('INSERT INTO users (name, name_lc, pass_hash, role, created_at) VALUES (?,?,?,?,?)').run(name, name.toLowerCase(), sec.hashPassword(pass), role, Date.now());
    db.prepare('INSERT INTO audit_log (ts, user_name, action, target) VALUES (?,?,?,?)').run(Date.now(), 'CLI', 'admin.create', name + ':' + role);
    console.log(`Administrator yaratildi: ${name} (${role}). Kirish: /admin`);
  } else if (cmd === 'reset-password') {
    const u = db.prepare("SELECT id FROM users WHERE name_lc = ? AND role != 'user'").get((name || '').toLowerCase());
    if (!u) throw new Error('Administrator topilmadi');
    const pass = await askHidden('Yangi parol: '); const prob = sec.passwordProblem(pass); if (prob) throw new Error(prob);
    db.prepare('UPDATE users SET pass_hash = ? WHERE id = ?').run(sec.hashPassword(pass), u.id);
    db.prepare('DELETE FROM sessions WHERE user_id = ?').run(u.id);
    db.prepare('INSERT INTO audit_log (ts, user_name, action, target) VALUES (?,?,?,?)').run(Date.now(), 'CLI', 'admin.reset-password', name);
    console.log('Parol yangilandi, barcha sessiyalar yopildi.');
  } else if (cmd === 'list-admins') {
    db.prepare("SELECT name, role, status FROM users WHERE role != 'user' ORDER BY id").all().forEach((u) => console.log(u.name, u.role, u.status));
  } else { console.log('Buyruqlar: create-admin | reset-password | list-admins'); }
})().catch((e) => { console.error('Xato:', e.message.includes('UNIQUE') ? 'Bu ism band' : e.message); process.exit(1); });
