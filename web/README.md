# Til Yo'li — ingliz tilini o'rganish platformasi

Duolingo uslubidagi (lekin o'z vizual uslubidagi) gamifikatsiyalangan veb-platforma: A1 dan IELTS gacha 6 daraja,
24 ta mavzu darsi, takrorlash va sinovlar, XP, seriya (streak), yurakchalar, yutuqlar, kunlik topshiriqlar.

## Ishga tushirish
Build yoki `npm install` kerak emas (toza HTML/CSS/JS).
```
cd web
python3 -m http.server 8080      # yoki istalgan statik server
# brauzerda: http://localhost:8080/
```
`index.html` ni to'g'ridan-to'g'ri ochish (file://) ham ishlaydi, lekin ovozli talaffuz va ba'zi brauzer xususiyatlari uchun lokal server tavsiya etiladi.

## Tuzilma
| Fayl | Vazifa |
|---|---|
| `index.html` | Kirish nuqtasi |
| `css/app.css` | Dizayn (yorug'/qorong'i rejim, moslashuvchan) |
| `js/data.js` | Kurs: 6 daraja × 4 mavzu × 8 so'z = 192 so'z, tushuntirishlar, misol gaplar |
| `js/store.js` | Saqlash adapteri, hisoblar, migratsiya, XP/streak/yurak/yutuq/topshiriq mantig'i |
| `js/engine.js` | Javobni tekshirish, mashqlarni tuzish (tasodifiy), sessiya |
| `js/ui.js` | Marshrutlash, sahifalar, dars oynasi |
| `tests/logic.test.js` | Node mantiq testlari (`node tests/logic.test.js`) |
| `tests/e2e.js` | Playwright brauzer testi (desktop + mobil) |

## Ma'lumotlarni saqlash (muhim)
- Backend yo'q. Hamma narsa brauzerning **localStorage**'ida, `tilyoli:` prefiksi bilan:
  `tilyoli:users` (hisoblar ro'yxati), `tilyoli:data:<ism>` (XP, streak, yurak, darslar, so'z statistikasi, xatolar, yutuqlar, kunlik statistika), `tilyoli:session`.
- Backend qo'shish uchun faqat `TY.Storage` (js/store.js) va `TY.Auth` dagi `register/login/save` almashtiriladi — qolgan kod holat obyektiga tayanadi.
- **Migratsiya:** ma'lumotda `v` (sxema versiyasi) bor. Eski versiya ochilganda avval `tilyoli:data:<ism>:backup-v<N>` nusxa yoziladi, keyin yetishmagan maydonlar qo'shiladi; mavjud maydonlar o'chirilmaydi. Buzilgan JSON `:corrupt` kalitiga ko'chiriladi.
- Profil → Eksport/Import orqali JSON nusxa olish va boshqa qurilmaga ko'chirish mumkin.
- **So'z identifikatorlari** (`daraja.mavzu.indeks`) progressga bog'langan: `data.js` dagi so'zlar tartibini o'zgartirmang, yangilarini mavzu oxiriga qo'shing.

## Qoidalar
- **Qulf:** dars faqat oldingisi tugagach ochiladi; har daraja sinovi (≥75%) keyingi darajani ochadi.
- **XP:** to'g'ri javob +10 (xatodan keyingi qayta urinishda +5); dars +20, takrorlash +25, sinov +40, mukammal natija +10; kunlik topshiriqlar uchun alohida bonus.
- **Daraja:** `floor(sqrt(XP/50)) + 1`.
- **Streak:** haqiqiy kalendar kuni (qurilma vaqti) bo'yicha; kun hisoblanishi uchun dars/takrorlash/sinov/mashq tugatilishi shart. Bir kun o'tkazib yuborilsa 0 ga tushadi.
- **Yurakchalar:** maks. 5; darsda har xato savol −1 (bir savol uchun bir marta); har 20 daqiqada +1 (vaqt bo'yicha); dars/mashq tugasa +1. 0 bo'lsa dars boshlanmaydi — xato so'zlar yoki aralash mashq (yurak ketmaydi) taklif qilinadi.
- **Javob tekshiruvi:** katta-kichik harf, ortiqcha bo'shliq va barcha apostrof turlari (' ʻ ’ ` ʼ) farq qilmaydi; har so'zning bir nechta tarjimasi qabul qilinadi; boshqa javoblar noto'g'ri. Imlo xatosi (1 harf) «deyarli» deb ko'rsatiladi, lekin to'g'ri hisoblanmaydi.

## Mashq turlari
Tarjima tanlash (en→uz), yozish, o'zbekchadan inglizchani topish, harflardan so'z tuzish, juftlashtirish, bo'sh joyni to'ldirish, gap tuzish, eshitib yozish (brauzer TTS mavjud bo'lsa), rasm (emoji) bo'yicha topish, xato so'zlarni takrorlash.

## Cheklovlar (ochiq aytilgan)
- **Lug'at tizimi qo'shilmagan** (so'z qo'shish/jadvaldan import/«Lug'atlarim») — buyurtmaga ko'ra. Darslardagi so'zlar `data.js` ichida.
- Hisoblar **faqat lokal**: parol SHA-256 bilan saqlanadi, lekin serversiz bu haqiqiy xavfsizlik emas. Bir qurilmadagi boshqa odam ma'lumotlarni brauzer orqali ko'ra oladi. Qurilmalar orasida sinxronizatsiya yo'q.
- Dars o'rtasida sahifa yangilansa, shu dars boshidan boshlanadi (lekin olingan XP, ketgan yurakchalar va xatolar saqlanadi).
- «Rasm» mashqlari emoji bilan (faqat konkret otlar uchun, ~50% so'zlarda).
- Eshitish mashqi va talaffuz brauzerning `speechSynthesis`iga bog'liq; ovozlar yo'q bo'lsa mashq tuzilmaydi. Audio fayllar yo'q.
- IELTS bo'limi — lug'at + strategiya maslahatlari; to'liq Listening/Reading/Writing mock-test emas.
- Tarjimalar va misol gaplar sinchiklab yozilgan, lekin o'qituvchi/filolog tekshiruvidan o'tmagan; xato topsangiz `data.js` da tuzating.
- Placement (daraja aniqlash) testi yo'q; hamma A1 dan boshlaydi.
- PWA/oflayn rejim (service worker) qo'shilmagan; push-eslatmalar yo'q.
- Ekran o'quvchilar bilan faqat avtomatik/qo'lda mantiqiy tekshirilgan (ARIA, fokus, klaviatura), real NVDA/VoiceOver sinovi o'tkazilmagan.
