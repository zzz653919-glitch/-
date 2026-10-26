/* Admin tahrirlarini asosiy kursga qo'llash (brauzer va serverda bir xil ishlaydi).
   rows = { levels:[{idx,title,sub}], topics:[{level,idx,title,icon,tip}], words:[{id,level,topic,en,uz,emoji,sent,sentUz,hidden,pos}], disabled:[tur] }
   keepHidden=true bo'lsa yashirin so'zlar `hidden` belgisi bilan qoladi (admin ko'rinishi). */
(function (TY) {
  TY.disabledKinds = {};
  TY.applyContent = function (rows, keepHidden) {
    rows = rows || {};
    var L = JSON.parse(JSON.stringify(TY.baseLevels));
    (rows.levels || []).forEach(function (r) { var lv = L[r.idx]; if (lv) { if (r.title) lv.title = r.title; if (r.sub) lv.sub = r.sub; } });
    (rows.topics || []).slice().sort(function (a, b) { return a.idx - b.idx; }).forEach(function (r) {
      var lv = L[r.level]; if (!lv) return;
      if (lv.topics[r.idx]) { var t = lv.topics[r.idx]; if (r.title) t.title = r.title; if (r.icon) t.icon = r.icon; if (r.tip != null) t.tip = r.tip; }
      else if (r.idx === lv.topics.length) lv.topics.push({ title: r.title, icon: r.icon || '📘', tip: r.tip || '', words: [] });
    });
    (rows.words || []).slice().sort(function (a, b) { return (a.pos || 0) - (b.pos || 0); }).forEach(function (r) {
      var lv = L[r.level], tp = lv && lv.topics[r.topic]; if (!tp) return;
      var w = tp.words.filter(function (x) { return x.id === r.id; })[0];
      if (w) { w.en = r.en; w.uz = r.uz; w.emoji = r.emoji || ''; w.sent = r.sent || ''; w.sentUz = r.sentUz || ''; w.hidden = !!r.hidden; }
      else tp.words.push({ id: r.id, en: r.en, uz: r.uz, emoji: r.emoji || '', sent: r.sent || '', sentUz: r.sentUz || '', hidden: !!r.hidden });
    });
    if (!keepHidden) L.forEach(function (lv) { lv.topics.forEach(function (tp) { tp.words = tp.words.filter(function (w) { return !w.hidden; }); }); });
    TY.LEVELS = L; TY.reindex();
    TY.disabledKinds = {}; (rows.disabled || []).forEach(function (k) { TY.disabledKinds[k] = 1; });
  };
})(typeof window !== 'undefined' ? (window.TY = window.TY || {}) : (globalThis.TY = globalThis.TY || {}));
