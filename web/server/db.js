'use strict';
// SQLite (Node o'rnatilgan `node:sqlite`) + versiyalangan migratsiyalar. Qo'shimcha paket kerak emas.
const path = require('path');
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');

const MIGRATIONS = [
  // v1: asosiy jadvallar
  `CREATE TABLE users (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     name TEXT NOT NULL, name_lc TEXT NOT NULL UNIQUE, pass_hash TEXT NOT NULL,
     role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','editor','admin','super_admin')),
     status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
     created_at INTEGER NOT NULL, last_seen INTEGER, xp INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
     lessons INTEGER NOT NULL DEFAULT 0, words_learned INTEGER NOT NULL DEFAULT 0, state TEXT
   );
   CREATE TABLE sessions (
     id_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
     kind TEXT NOT NULL CHECK (kind IN ('learner','admin')), csrf TEXT NOT NULL, created INTEGER NOT NULL, expires INTEGER NOT NULL
   );
   CREATE TABLE login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, ip TEXT, ts INTEGER NOT NULL, ok INTEGER NOT NULL, kind TEXT);
   CREATE INDEX idx_attempts ON login_attempts(key, ts);
   CREATE TABLE events (
     id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
     ts INTEGER NOT NULL, mode TEXT NOT NULL, node TEXT, pct INTEGER NOT NULL, xp INTEGER NOT NULL, ok INTEGER NOT NULL
   );
   CREATE INDEX idx_events_ts ON events(ts);
   CREATE TABLE content_levels (idx INTEGER PRIMARY KEY, title TEXT, sub TEXT);
   CREATE TABLE content_topics (level INTEGER NOT NULL, idx INTEGER NOT NULL, title TEXT NOT NULL, icon TEXT, tip TEXT, PRIMARY KEY (level, idx));
   CREATE TABLE content_words (
     id TEXT PRIMARY KEY, level INTEGER NOT NULL, topic INTEGER NOT NULL, en TEXT NOT NULL, uz TEXT NOT NULL,
     emoji TEXT, sent TEXT, sentUz TEXT, hidden INTEGER NOT NULL DEFAULT 0, base INTEGER NOT NULL DEFAULT 0, pos INTEGER NOT NULL DEFAULT 0
   );
   CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
   CREATE TABLE announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created INTEGER NOT NULL, author TEXT);
   CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, user_id INTEGER, user_name TEXT, action TEXT NOT NULL, target TEXT, ok INTEGER NOT NULL DEFAULT 1, detail TEXT);
   CREATE INDEX idx_audit_ts ON audit_log(ts);`
];

function open(file) {
  if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000;');
  let v = db.prepare('PRAGMA user_version').get().user_version;
  while (v < MIGRATIONS.length) {
    db.exec('BEGIN');
    try { db.exec(MIGRATIONS[v]); v++; db.exec('PRAGMA user_version = ' + v); db.exec('COMMIT'); }
    catch (e) { db.exec('ROLLBACK'); throw e; }
  }
  db.tx = function (fn) { db.exec('BEGIN IMMEDIATE'); try { const r = fn(); db.exec('COMMIT'); return r; } catch (e) { db.exec('ROLLBACK'); throw e; } };
  return db;
}
module.exports = { open };
