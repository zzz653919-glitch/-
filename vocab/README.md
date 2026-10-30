# Til Yo'li · Lug'at sessiyalari

Faqat lug'at yodlashga qaratilgan ilova: har bir **sessiya** o'zining so'zlari, progressi, xatolari va takrorlash jadvaliga ega.
**Asosiy kafolat:** faol sessiyadagi barcha mashqlar (yangi so'z ko'rsatish, test variantlari, yozma/imlo/harf mashqlari, juftlashtirish, takrorlash, xatolar mashqi, yakuniy test, statistika) **faqat shu sessiyaning so'zlaridan** tuziladi.

## Ishga tushirish
Server va o'rnatish kerak emas:
- `vocab/lugat.html` ni brauzerda oching (hammasi bitta faylda), yoki
- `vocab/index.html` (manba) — qayta yig'ish: `cd vocab && python3 build-single.py`.

## Imkoniyatlar
- Sessiyalar paneli: yaratish, qidirish, saralash, progress, faol sessiya belgisi (yuqorida va karta ustida, har sessiyaning o'z rangi).
- Sessiya: nomini o'zgartirish, to'xtatish/davom ettirish, qayta boshlash (so'zlar qoladi), o'chirish; so'z qo'shish/tahrirlash/o'chirish; ko'p so'z import (`en - tarjima`, `=`, `|`, `;`, `,`, TAB/Excel; ixtiyoriy misol gap va talaffuz ustunlari; takrorlar faqat shu sessiya ichida tekshiriladi va o'zi o'chirilmaydi: «ko'rsat / o'tkazib yubor / yangila / qo'sh»).
- O'rganish raundi: yangi so'z taqdimoti (tarjima, misol, talaffuz, yashirish/ko'rsatish) → mashqlar → xato so'zlar qaytarilishi → sessiyaga xos xulosa. To'xtatib, keyin shu joydan davom ettirish mumkin.
- Mashqlar: so'z va ma'no (ko'rsatish/yashirish), tarjimani yozish, inglizchasini yozish, test (variantlar faqat shu sessiyadan; so'z kam bo'lsa variantlar soni kamayadi), imlo, harflardan so'z tuzish, juftlashtirish, xatolarni takrorlash, yakuniy test (≥70% — topshirildi).
- Takrorlash: Leitner qutilari (0–5), intervallar 0/1/2/4/8/16 kun; xato so'z «xato» deb belgilanadi va ketma-ket 2 marta to'g'ri topilgach chiqadi. Hammasi sessiya ichida.
- Statistika (har sessiya alohida): jami, yangi, o'rganilmoqda, o'zlashtirilgan (quti ≥ 4), xato javoblar, aniqlik, tugallangan raundlar, oxirgi faollik, keyingi takrorlash.
- Yorug'/qorong'i mavzu, telefon uchun moslashuvchan dizayn, klaviatura (Enter, 1–5), ARIA, animatsiyalar `prefers-reduced-motion` ga bo'ysunadi.

## Javobni tekshirish
Bo'shliq, katta-kichik harf va barcha apostrof turlari (' ʻ ’ ‘ `) farq qilmaydi. Bir nechta tarjima `;` bilan: hammasi to'g'ri. Qavs ichidagi qism ixtiyoriy (`ta'mirlamoq (qilmoq)`). Inglizcha imloda -our/-or, -ise/-ize, -re/-er farqlari va qo'lda kiritilgan variantlar qabul qilinadi. Yaqin lekin noto'g'ri javob (masalan bitta harf xato) **noto'g'ri** hisoblanadi, faqat «imlo xatosi» maslahati beriladi. Xatoda to'g'ri javob va tushuntirish (so'z, tarjima, misol) ko'rsatiladi.

## Ma'lumotlar modeli (localStorage, kalit `vocab:v1`)
```
{ schema, activeId, settings, migrations[],
  sessions: { <sessionId>: { id, name, lang, status, createdAt, lastActivity, rounds,
      words:   { <wordId>: { id, en, tr[], example, exampleTr, pron, variants[] } },   // faqat shu sessiyaniki
      order:   [wordId...],
      progress:{ <wordId>: { box, seen, correct, wrong, streak, fix, due, last, mistake } },  // sessiyaga xos
      attempts:[ { ts, w, kind, ok, a } ], run: { queue[], i, ... } | null, lastSummary } } }
```
- Har bir so'z `wordId` ga ega, progress so'z ID si bo'yicha **sessiya ichida** saqlanadi: bir xil inglizcha so'z ikki sessiyada ikki xil ID va mustaqil progressga ega.
- Hamma funksiya aniq `sessionId` oladi (`V.startRun(sid, mode)`, `V.answer(sid, ...)`). Har bir savol ekranga chiqarilishidan oldin `V.assertQuestion(sid, q)` tekshiradi (savol, so'zlar va barcha variantlar shu sessiyaga tegishliligini); buzilsa mashq to'xtaydi — jimgina boshqa so'z aralashtirilmaydi.
- Har bir javobdan keyin saqlanadi (localStorage + IndexedDB nusxasi; ochilganda eng yangisi tanlanadi), shuning uchun yangilash yoki yopishdan keyin progress va to'xtatilgan raund qoladi. **Cheklov:** brauzerlar yozuvni diskka kechiktirib o'tkazadi — javobdan so'ng ~0,1–0,3 soniya ichida sahifani majburan yangilasangiz, eng oxirgi javob yo'qolishi mumkin (avtomatik testda shu holat kuzatilgan, 0,3 s kutish bilan barqaror).
- Sxema yangilanishidan va JSON importdan oldin avtomatik zaxira (`vocab:v1:backup-…`) yoziladi; buzilgan ma'lumot `:corrupt-…` kalitiga ko'chiriladi, o'chirilmaydi.
- Backend yo'q: ma'lumot faqat shu brauzerda. Backend qo'shish uchun `V.load/V.save` (store.js) almashtiriladi.

## Migratsiya
Birinchi ochilishda eski «Til Yo'li» kursi ma'lumoti (`tilyoli:data:<ism>`, shuningdek admin qo'shgan so'zlar) **faqat o'qiladi**: progress yozuvi bor so'zlar «Til Yo'li kursidan (<ism>)» nomli alohida sessiyaga ko'chiriladi (to'g'ri/xato hisoblari, xato belgisi saqlanadi), panelda hisobot ko'rsatiladi. Eski kalitlar o'zgartirilmaydi va o'chirilmaydi; ikkinchi marta bajarilganda takror sessiya yaratilmaydi. Sozlamalarda qayta qidirish tugmasi bor. Eslatma: bu ma'lumot faqat bir brauzer profilida ko'rinadi (Chrome'da ikki `file://` sahifa localStorage'ni bo'lishadi, Firefox/Safari'da bo'lishmasligi mumkin — u holda eski ilovadan JSON eksport olib, kerak bo'lsa so'zlarni import qiling).

## Testlar
```
node test.js                                         # mantiq: izolyatsiya, progress, import, migratsiya (13)
NODE_PATH=$(npm root -g) node e2e.js                 # brauzer (Playwright): kompyuter va telefon
```
Izolyatsiya testi A/B sessiyalarida barcha rejimlarni (o'rganish, takrorlash, xatolar, test) yuzlab marta tuzib, har bir savol JSON'ida boshqa sessiya so'zlari yo'qligini tekshiradi; brauzer testi esa butun raund davomida ekran matnini tekshiradi. (Tekshiruv sezgirligi: izolyatsiyani ataylab buzilganda test uni topishi sinab ko'rilgan.)

## Cheklovlar
- Ko'p foydalanuvchi/egalik: ilova bir foydalanuvchili (har brauzer profilida o'z ma'lumoti). Server va egalik tekshiruvlari yo'q.
- Talaffuz va «eshitish» brauzer TTS'iga bog'liq; audio fayllar yo'q. Talaffuz (IPA) avtomatik berilmaydi, qo'lda kiritiladi.
- Mashqlar tartibi tasodifiy, lekin bir raundda 11 tagacha so'z ishlatiladi (5 tagacha yangi).
- Eski kursning boshqa qismlari (darajalar xaritasi, XP/yurakchalar, admin panel, o'quvchilar hisoblari) bu ilovada yo'q — ular `web/` papkasida daxlsiz turibdi.

## Ko'p so'z import va rasmdan o'qish (OCR)
`#/import` (panel yoki sessiya sahifasidagi «Ko'p so'z import»). Tartib: **1) maqsad sessiyani tanlash yoki yangisini yaratish (majburiy)** → **2) matn yoki rasm** → **3) jadvalda oldindan ko'rish va tahrirlash** → **Import All Valid Words**. Tasdiqlanmaguncha hech narsa saqlanmaydi (yangi sessiya ham yaratilmaydi). Tugmalar: *Import All Valid Words*, *Edit Entries* (yozuvlarni matn sifatida tahrirlab qayta tahlil), *Cancel*.

### Tahlil qoidalari (`importer.js`)
1. Qator tozalanadi (NBSP/nol kenglikli belgilar, `1.`/`2)`/`•` raqamlash, ortiqcha bo'shliq). Apostroflar va `o‘ g‘ ʻ ’` aynan saqlanadi; tekshiruvda barcha variantlar teng.
2. **Talaffuz**: `/…/` va IPA belgili `[…]` olib tashlanib, alohida «Talaffuz» ustunida saqlanadi (`and/or` kabi so'z ichidagi `/` talaffuz emas). OCR yopuvchi `/` ni tushirib qoldirsa — «tekshirish».
3. **Ajratuvchi**: eng chapdagi tanlanadi: TAB, `—`, `–`, ` - `, `=`, `|`, `:`; keyin 2+ bo'shliq; keyin `;`/`,` (ishonchsiz → «tekshirish»).
4. **Ajratuvchisiz** («take a photo suratga olmoq»): har so'z inglizcha/o'zbekcha ballanadi (o'zbekcha: `moq`, `lik`, `siz`, `chi`, `q`, `o'/g'`, apostrofli so'zlar, ro'yxatdagi aniq ajratuvchili qatorlar va maqsad sessiyadagi so'zlar «ko'rsatma» bo'ladi; inglizcha: `w`, `th`, `ph`, `ing`, funksiya so'zlari). Eng yaxshi chegara tanlanadi; ishonch past bo'lsa «tekshirish». O'ng tomon ham inglizcha ko'rinsa («to give up») — butun qator inglizcha ibora, tarjima bo'sh.
5. **Tavsifni olib tashlash**: faqat ishonchli holatlarda — fe'l (`…moq`) dan keyingi so'zlar, birinchi gapdan keyingi gaplar (`. `), inglizcha tomondagi `(v)`, `n.` kabi belgilar. Olib tashlangan matn jadvalda «olib tashlandi: …» deb ko'rinadi va «qaytarish» tugmasi bor. Tarjima 4+ so'z bo'lib fe'l-anchor topilmasa, ikkinchi ajratuvchi bo'lsa yoki bir nechta variant orasida kesish bo'lsa — hech narsa o'chirilmaydi, qator «tekshirish»ga tushadi. Qavs ichidagi izoh (`ulashmoq (bo'lishmoq)`) va `;`/`,` bilan berilgan muqobil tarjimalar saqlanadi. Ko'p so'zli iboralar (`take a photo`, `look after`, `give up`, `to be or not to be`) to'liq saqlanadi.
6. **Holatlar**: *To'g'ri*, *Tekshirish* (✓ bilan tasdiqlang yoki tahrirlang), *Takror* (importda yoki maqsad sessiyada; «Baribir qo'shish» bilan qo'shiladi), *To'liq emas* (tarjima yo'q — to'qilmaydi, qo'lda kiritiladi), *Xato* (inglizcha yo'q/juda uzun). Hech qator jimgina tashlab yuborilmaydi.
7. Takrorlar faqat **maqsad sessiya** ichida tekshiriladi: bir xil inglizcha so'z boshqa sessiyaga erkin qo'shiladi; mavjud so'zlar va progress hech qachon o'zgarmaydi/qayta yozilmaydi.

### Rasm (OCR)
- **Tesseract.js 5.1.1 (WebAssembly)**: JPG, JPEG, PNG, WebP; bir nechta rasm ketma-ket, tartib saqlanadi. Matn **brauzerda** o'qiladi (rasm serverga yuborilmaydi), **lekin kutubxona, worker, wasm yadro va `eng` til ma'lumoti CDN'dan (jsDelivr) yuklanadi — birinchi marta INTERNET kerak**; oflayn ishlashi kafolatlanmaydi (interfeys buni aniq yozadi). Boshqa manzil uchun `window.OCR_CONFIG = { script, options: { workerPath, corePath, langPath, gzip } }`.
- Natija o'sha jadvalga tushadi (tahrirlanadigan), xom OCR matni ham ko'rinadi. Faqat inglizcha rasmda tarjima bo'sh qoladi.
- OCR sifati cheklangan: IPA belgilari odatda buziladi (talaffuz maydoni shunga qaramay ajratiladi), `o‘/g‘/q` kabi harflar adashishi mumkin (`g'amxa'rlik gilmoq`) — import qilishdan oldin jadvalda tuzating. Ustunlari aralashib ketgan yoki bir yozuv ikki qatorga bo'lingan rasmlar «To'liq emas/Tekshirish» bo'ladi. Faqat `eng` modeli ishlatiladi (o'zbekcha uchun alohida model yuklanmaydi).

### Katta ro'yxatlar
Tahlil 300 qatorlik bo'laklarda (UI qotmaydi, progress ko'rsatiladi), jadval 50 qatorlik sahifalarda, saqlash bo'laklab va bitta yozuv bilan (`V.addWords`): 2000 qator ≈ 0,1 s tahlil. Import tugmasi bosilgach o'chadi (ikki marta bosish himoyasi); qayta import qilinsa, so'zlar «Takror» bo'ladi.

### Testlar
```
node test-import.js                                   # parser, tavsif/talaffuz, o'zbek harflari, takrorlar, katta ro'yxat, OCR (mock), izolyatsiya, saqlanish (16)
OCR_ASSETS=<node_modules> node e2e-import.js          # brauzer + HAQIQIY Tesseract (Playwright); OCR_ASSETS: tesseract.js, tesseract.js-core, @tesseract.js-data/eng
```
