'use strict';
const crypto = require('crypto');

// Parol xeshi: scrypt + tasodifiy tuz. Oddiy matn hech qayerda saqlanmaydi.
const N = 16384;
function hashPassword(pass) {
  const salt = crypto.randomBytes(16);
  const h = crypto.scryptSync(pass, salt, 64, { N, r: 8, p: 1 });
  return `scrypt$${N}$${salt.toString('hex')}$${h.toString('hex')}`;
}
const DUMMY = hashPassword('dummy-password-for-timing');
function verifyPassword(pass, stored) {
  try {
    const [alg, n, salt, hash] = String(stored || DUMMY).split('$');
    if (alg !== 'scrypt') return false;
    const h = crypto.scryptSync(pass, Buffer.from(salt, 'hex'), 64, { N: +n, r: 8, p: 1 });
    return crypto.timingSafeEqual(h, Buffer.from(hash, 'hex')) && !!stored;
  } catch (e) { return false; }
}
const sha = (s) => crypto.createHash('sha256').update(s).digest('hex');
const token = () => crypto.randomBytes(32).toString('base64url');
const safeEq = (a, b) => { a = Buffer.from(String(a || '')); b = Buffer.from(String(b || '')); return a.length === b.length && crypto.timingSafeEqual(a, b); };

// Admin paroli siyosati
function passwordProblem(p) {
  if (typeof p !== 'string' || p.length < 10) return "Parol kamida 10 belgidan iborat bo'lsin";
  if (p.length > 128) return 'Parol juda uzun';
  if (!/[A-Za-z]/.test(p) || !/[0-9]/.test(p)) return "Parolda harf va raqam bo'lsin";
  return null;
}
// CSV in'ektsiyasidan himoya (=, +, -, @ bilan boshlanuvchi katakchalar)
function csvCell(v) {
  let s = v == null ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
module.exports = { hashPassword, verifyPassword, sha, token, safeEq, passwordProblem, csvCell };
