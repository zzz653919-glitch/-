/* Rasmdan matn o'qish (OCR): Tesseract.js (WebAssembly) — hisoblash BRAUZERDA bajariladi, rasm hech qayerga yuborilmaydi.
   LEKIN kutubxona, worker, wasm yadro va til ma'lumoti (eng.traineddata) CDN'dan yuklanadi → birinchi marta INTERNET kerak.
   (Yuklangandan keyin brauzer keshi tufayli keyingi safar tezroq bo'lishi mumkin, lekin oflayn ishlashi kafolatlanmaydi.) */
(function (V) {
  'use strict';
  var O = V.ocr = {};
  O.TYPES = ['image/jpeg', 'image/png', 'image/webp'];
  // Sozlash: sinov yoki o'z serveringizdagi nusxa uchun window.OCR_CONFIG orqali almashtirish mumkin
  O.cfg = Object.assign({
    script: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js',
    lang: 'eng',
    options: {}     // workerPath, corePath, langPath, gzip ... (Tesseract.js createWorker sozlamalari)
  }, (typeof window !== 'undefined' && window.OCR_CONFIG) || {});
  O.engine = null;  // (file, onProgress) => Promise<string> — sinov uchun almashtiriladi
  O.needsInternet = function () { return !O.engine && !/^(\/|\.|file:|blob:)/.test(O.cfg.script) ? true : false; };
  O.accepted = function (file) { return O.TYPES.indexOf(file.type) >= 0 || /\.(jpe?g|png|webp)$/i.test(file.name || ''); };

  function loadScript(src) {
    return new Promise(function (res, rej) {
      if (window.Tesseract) return res();
      var s = document.createElement('script'); s.src = src; s.async = true; s.crossOrigin = 'anonymous';
      s.onload = function () { res(); }; s.onerror = function () { rej(new Error("OCR kutubxonasini yuklab bo'lmadi. Internet aloqasini tekshiring.")); };
      document.head.appendChild(s);
    });
  }
  var worker = null, workerLang = null;
  function getWorker(onProgress) {
    if (worker && workerLang === O.cfg.lang) return Promise.resolve(worker);
    return loadScript(O.cfg.script).then(function () {
      var cur = { fn: null }; O._cur = cur;
      return window.Tesseract.createWorker(O.cfg.lang, 1, Object.assign({ logger: function (m) { if (O._cur.fn) O._cur.fn(m); } }, O.cfg.options));
    }).then(function (w) { worker = w; workerLang = O.cfg.lang; return w; });
  }
  // Natija: { text, confidence }. Qatorlar tartibi rasmdagi tartibni saqlaydi.
  O.recognize = function (file, onProgress) {
    if (O.engine) return Promise.resolve(O.engine(file, onProgress)).then(function (t) { return { text: typeof t === 'string' ? t : t.text, confidence: t && t.confidence != null ? t.confidence : null }; });
    if (!O.accepted(file)) return Promise.reject(new Error('Faqat JPG, PNG va WebP rasmlar qabul qilinadi: ' + file.name));
    if (file.size > 15 * 1024 * 1024) return Promise.reject(new Error('Rasm juda katta (15 MB dan oshmasin): ' + file.name));
    return getWorker().then(function (w) {
      O._cur.fn = function (m) { if (onProgress && m.status) onProgress(m.status, m.progress || 0); };
      return w.recognize(file);
    }).then(function (r) { if (O._cur) O._cur.fn = null; return { text: r.data.text, confidence: r.data.confidence }; });
  };
  O.terminate = function () { if (worker) { try { worker.terminate(); } catch (e) {} worker = null; } };
})(typeof window !== 'undefined' ? (window.V = window.V || {}) : (globalThis.V = globalThis.V || {}));
