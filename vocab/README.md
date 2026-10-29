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
