// Node bilan: node web/tests/logic.test.js  (brauzersiz mantiq testlari)
var assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
var store = {}; var win = { localStorage: { getItem: function (k) { return k in store ? store[k] : null; }, setItem: function (k, v) { store[k] = String(v); }, removeItem: function (k) { delete store[k]; } }, crypto: require('crypto').webcrypto, TextEncoder: TextEncoder };
win.window = win; vm.createContext(win);
['data', 'store', 'engine'].forEach(function (f) { vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/' + f + '.js'), 'utf8'), win); });
var TY = win.TY, G = TY.Game, n = 0;
function t(name, fn) { return Promise.resolve().then(fn).then(function () { n++; console.log('ok  ' + name); }); }

(async function () {
  await t('ma\'lumot: 6 daraja, 192 so\'z, noyob id', function () {
    assert.equal(TY.LEVELS.length, 6); assert.equal(TY.allWords.length, 192);
    assert.equal(new Set(TY.allWords.map(function (w) { return w.id; })).size, 192);
    TY.allWords.forEach(function (w) { assert(w.en && w.uz.length && w.sent && w.sentUz, w.id); assert(!/[Ѐ-ӿ]/.test(w.uz.join('')), 'kirill: ' + w.id); });
  });
  await t('gap ichida so\'z bor (cloze/build uchun)', function () {
    var bad = TY.allWords.filter(function (w) { return !new RegExp('\\b' + w.en + '\\b', 'i').test(w.sent); });
    assert.deepEqual(bad.map(function (w) { return w.en + ' :: ' + w.sent; }), [], 'gapda topilmadi');
  });
  await t('normalizatsiya: harf/bo\'shliq/apostrof', function () {
    assert(TY.checkText("  O‘G‘IL   bola ", ["o'g'il bola"]).ok);
    assert(TY.checkText("Bogʼ", ["bog'"]).ok);
    assert(TY.checkText("TA'MIRLASH", ["ta’mirlamoq", "ta'mirlash"]).ok);
    assert(!TY.checkText("mushuk", ["it"]).ok);
    assert(!TY.checkText("", ["it"]).ok);
  });
  await t('muqobil tarjimalar qabul qilinadi, noto\'g\'ri rad etiladi', function () {
    var w = TY.allWords.find(function (x) { return x.en === 'boy'; });
    assert(TY.checkText('bola', w.uz).ok); assert(TY.checkText("o'g'il bola", w.uz).ok); assert(!TY.checkText('qiz', w.uz).ok);
  });
  await Auth();
  async function Auth() {
    await t('ro\'yxatdan o\'tish/kirish/parol', async function () {
      await TY.Auth.register('Ali', 'sir1234'); assert.equal(TY.Auth.current.name, 'Ali');
      TY.Auth.logout(); await assert.rejects(TY.Auth.login('ali', 'xato'));
      await TY.Auth.login('ALI', 'sir1234'); assert(TY.Auth.state);
      await assert.rejects(TY.Auth.register('ali', 'boshqa123'));
    });
    await t('qulf: keyingi dars oldingisini tugatmaguncha yopiq', function () {
      assert(G.isUnlocked('L0T0')); assert(!G.isUnlocked('L0T1')); assert(!G.isUnlocked('L1T0'));
      G.completeNode('L0T0', 100, 20, 0); assert(G.isUnlocked('L0T1'));
    });
    await t('savol generatsiyasi: barcha mashq turlari va tartib tasodifiy', function () {
      var kinds = {}, orders = {};
      for (var i = 0; i < 40; i++) {
        var s = new TY.Session('lesson', TY.nodeById.L0T2);
        s.queue.forEach(function (q) { kinds[q.kind] = 1; assert(q.type); if (q.options) { assert.equal(new Set(q.options).size, q.options.length); assert(q.options.length >= 3); } });
        orders[s.queue.map(function (q) { return q.w || 'm'; }).join(',')] = 1;
      }
      ['mc_en_uz', 'mc_uz_en', 'type_en_uz', 'type_uz_en', 'scramble', 'cloze', 'build', 'picture', 'match'].forEach(function (k) { assert(kinds[k], 'tur yo\'q: ' + k); });
      assert(Object.keys(orders).length > 20, 'tartib qotib qolgan');
    });
    await t('cloze/choice: to\'g\'ri javob variantlar ichida, noto\'g\'ri rad etiladi', function () {
      for (var i = 0; i < 300; i++) {
        var w = TY.allWords[i % TY.allWords.length], s = new TY.Session('practice', null);
        var qs = [TY.buildSession('lesson', TY.nodeById['L' + w.level + 'T' + w.topic]).queue].reduce(function (a, b) { return a.concat(b); }, []);
        qs.filter(function (q) { return q.type === 'choice'; }).forEach(function (q) {
          assert(q.options.some(function (o) { return TY.checkText(o, q.answer).ok; }));
          assert.equal(q.options.filter(function (o) { return TY.checkText(o, q.answer).ok; }).length, 1, 'bir nechta to\'g\'ri variant: ' + JSON.stringify(q));
        });
      }
    });
    await t('XP, yurak, xatolar ro\'yxati va xato qaytarilishi', function () {
      var s = new TY.Session('lesson', TY.nodeById.L0T1), q = s.current(), xp0 = TY.Auth.state.xp, h0 = TY.Auth.state.hearts, len = s.queue.length;
      var r = s.answer(q, true, [q.w]); assert.equal(r.xp, 10); assert.equal(TY.Auth.state.xp, xp0 + 10);
      s.next(); var q2 = s.current(); s.answer(q2, false, [q2.w]);
      assert.equal(TY.Auth.state.hearts, h0 - 1); assert(TY.Auth.state.mistakes[q2.w]); assert.equal(s.queue.length, len + 1);
      TY.Auth.state.hearts = 1; var s2 = new TY.Session('lesson', TY.nodeById.L0T1), qq = s2.current();
      assert(s2.answer(qq, false, [qq.w]).outOfHearts); assert(s2.over && s2.failed);
      TY.Auth.state.hearts = 5;
    });
    await t('xato so\'z 2 ta ketma-ket to\'g\'ri javobdan keyin chiqadi', function () {
      var id = Object.keys(TY.Auth.state.mistakes)[0]; G.recordAnswer(id, true); assert(TY.Auth.state.mistakes[id]); G.recordAnswer(id, true); assert(!TY.Auth.state.mistakes[id]);
    });
    await t('yurak tiklanishi vaqt bo\'yicha', function () {
      var s = TY.Auth.state; s.hearts = 2; s.heartTs = Date.now() - 45 * 60000; G.regen(); assert.equal(s.hearts, 4);
      s.hearts = 0; s.heartTs = Date.now() - 200 * 60000; G.regen(); assert.equal(s.hearts, 5);
    });
    await t('streak: kalendar kunlariga bog\'liq', function () {
      var s = TY.Auth.state; s.streak = 0; s.lastDay = null; G.markActiveDay(); assert.equal(s.streak, 1); G.markActiveDay(); assert.equal(s.streak, 1);
      s.lastDay = TY.addDays(TY.today(), -1); s.streak = 4; G.markActiveDay(); assert.equal(s.streak, 5);
      s.lastDay = TY.addDays(TY.today(), -2); s.streak = 5; assert.equal(G.streakNow(), 0); G.markActiveDay(); assert.equal(s.streak, 1);
    });
    await t('dars tugashi: XP saqlanadi, test 75% dan past bo\'lsa o\'tmaydi', function () {
      var s = new TY.Session('test', TY.nodeById.L0X); s.firstTry = 1; var r = s.finish(); assert(!r.passed); assert(!TY.Auth.state.done.L0X);
      TY.Auth.state.done.L0T3 = { best: 100 }; TY.Auth.state.done.L0R = { best: 100 };
      var s2 = new TY.Session('test', TY.nodeById.L0X); s2.firstTry = s2.total; var r2 = s2.finish(); assert(r2.passed); assert(TY.Auth.state.done.L0X); assert(G.isUnlocked('L1T0'));
    });
    await t('yangilashdan keyin ma\'lumot qoladi + migratsiya zaxirasi', function () {
      var xp = TY.Auth.state.xp; TY.Auth.state = null; assert(TY.Auth.restore()); assert.equal(TY.Auth.state.xp, xp);
      TY.Storage.set('data:ali', JSON.stringify({ v: 1, xp: 77, done: { L0T0: { best: 90, times: 1 } } })); TY.Auth.open('Ali');
      assert.equal(TY.Auth.state.xp, 77); assert(TY.Auth.state.done.L0T0); assert.equal(TY.Auth.state.v, 2); assert(TY.Storage.get('data:ali:backup-v1'));
    });
    await t('kunlik topshiriqlar real statistikadan', function () {
      TY.Auth.resetProgress(); var q = G.quests(); assert(q.every(function (x) { return x.cur === 0; }));
      G.recordAnswer('0.0.0', true); G.addXP(50); G.completePractice(0); var q2 = G.quests(); assert(q2[0].cur === 1 && q2[2].cur >= 40);
      var gain = G.claimQuests(); assert(gain >= 30); assert.equal(G.claimQuests(), 0);
    });
    console.log('\n' + n + ' ta test o\'tdi');
  }
})().catch(function (e) { console.error('XATO:', e); process.exit(1); });
