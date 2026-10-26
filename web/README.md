# Til Yo'li — ingliz tilini o'rganish platformasi + Admin panel

Duolingo uslubidagi (o'z vizual uslubida) platforma: A1 → IELTS, 24 mavzu darsi, 192 so'z, 9 turdagi mashq + juftlashtirish,
XP, seriya, yurakchalar, yutuqlar, kunlik topshiriqlar. **Admin panel** va **server (SQLite)** bilan; serversiz (localStorage) rejimi ham saqlangan.

## Ishga tushirish
Talab: **Node.js 22+** (qo'shimcha paket va `npm install` kerak emas; SQLite Node ichida).
```
cd web
node server/cli.js create-admin <ism> super_admin     # parol so'raladi (ekranda ko'rinmaydi, kamida 10 belgi, harf+raqam)
node server/server.js                                 # http://localhost:8080  ·  admin: http://localhost:8080/admin
```
- Birinchi administratorni **faqat shu CLI** yaratadi — ochiq standart akkaunt yo'q. Boshqa adminlarni Super Admin panel orqali qo'shadi.
- Parolni unutsangiz: `node server/cli.js reset-password <ism>`; ro'yxat: `list-admins`.
- Sozlamalar (muhit o'zgaruvchilari): `PORT` (8080), `HOST` (127.0.0.1), `TILYOLI_DB` (baza fayli, standart `web/server/data/tilyoli.db`), `COOKIE_SECURE=1` (HTTPS ortida majburiy), `TRUST_PROXY=1` (reverse-proxy ortida haqiqiy IP uchun).
- **Bitta fayl (server kerak emas):** `tilyoli.html` ni brauzerda oching — sayt; `tilyoli.html?admin` (yoki Profil → «Admin panel») — **lokal admin panel**. Birinchi kirishda kiritgan ism va parolingiz (kamida 10 belgi, harf+raqam) administrator bo'ladi. Admin faqat **shu brauzerdagi** o'quvchilar, so'zlar va statistikani boshqaradi (boshqa qurilmadagilarni ko'ra olmaydi), bitta administrator, rollar yo'q. Himoya faqat brauzer darajasida, haqiqiy xavfsizlik emas. Qayta yig'ish: `python3 build-single.py`.
- **Serversiz rejim:** `index.html` yoki bitta faylli `tilyoli.html` (`python3 build-single.py`) ni ochsangiz ilova eskicha ishlaydi (hisoblar va progress faqat shu brauzerda); admin panel bunda ishlamaydi. Server rejimida brauzerdagi eski lokal progress, o'sha ism bilan birinchi kirishda serverga ko'chiriladi.

## Admin panel (`/admin`)
| Bo'lim | Nima qiladi | Kim |
|---|---|---|
| Bosh panel | Foydalanuvchilar, faollik (7/30 kun), darslar, so'zlar, o'rtacha progress, mashhur/qiyin darslar, qiyin so'zlar, o'sish va faollik grafiklari, so'nggi ro'yxatlar/faollik | Editor: faqat kurs raqamlari |
| Foydalanuvchilar | Qidirish, filtr, saralash, sahifalash, profil (progress, qiyin so'zlar, kunlik faollik), bloklash, progressni tozalash, CSV eksport; hisobni o'chirish — faqat Super Admin | Admin+ |
| Kurs mazmuni | Daraja/mavzu nomi va tushuntirishi, yangi mavzu, so'z qo'shish/tahrirlash/yashirish/qaytarish/o'chirish, jadvaldan import (oldindan ko'rish, takrorlarni ko'rsatish/o'tkazib yuborish/qo'shish), qidirish | Editor+ |
| Mashqlar | Mashq turlarini yoqish/o'chirish | Editor+ |
| Yutuqlar, Statistika | Yutuqlarning ochilish ulushi; batafsil statistika | Admin+ |
| E'lonlar | O'quvchilar bosh sahifasida ko'rinadigan e'lonlar | Admin+ |
| Audit jurnali | Kim, nima, qachon, muvaffaqiyat/xato (parollar yozilmaydi) | Admin+ |
| Sozlamalar | Ro'yxatdan o'tishni ochish/yopish; administratorlar va rollar | Super Admin |

Rollar: **Super Admin** (hammasi) · **Admin** (mazmun, foydalanuvchilar, statistika, e'lonlar, audit) · **Editor** (faqat kurs mazmuni va mashqlar). Ruxsat **serverda** har so'rovda tekshiriladi (menyuni yashirish yetarli deb hisoblanmaydi).

## Xavfsizlik
- Parollar `scrypt` + tasodifiy tuz bilan xeshlanadi; xesh hech qanday API javobida qaytmaydi.
- Sessiya: tasodifiy token (bazada faqat SHA-256 xeshi), `HttpOnly` + `SameSite=Strict` cookie; admin sessiyasi 8 soat, o'quvchi 30 kun. Bloklash/rol o'zgartirish/parol almashtirish sessiyalarni darhol yopadi.
- CSRF: har bir o'zgartiruvchi so'rovda sessiyaga bog'liq token (`X-CSRF-Token`) + `Origin` tekshiruvi.
- Kirish cheklovi: 15 daqiqada 5 ta xato (ism+IP) yoki 30 ta (IP) → 429.
- Barcha kirishlar serverda validatsiya qilinadi (uzunlik, tur, format); SQL — faqat parametrli so'rovlar; foydalanuvchi matni brauzerda har doim `esc()` bilan qochiriladi, qo'shimcha ravishda CSP (`script-src 'self'`) bor.
- CSV eksportda formula in'ektsiyasidan himoya; statik fayllar ruxsat ro'yxati bilan beriladi (`server/`, baza, testlar yuklab olinmaydi).
- Oxirgi faol Super Admin'ni o'chirib/pasaytirib bo'lmaydi; admin o'z rolini o'zgartira olmaydi.

## Ma'lumotlar
SQLite (`PRAGMA user_version` bilan versiyalangan migratsiyalar, `server/db.js`). Jadvallar: `users`, `sessions`, `events`, `content_levels/topics/words`, `settings`, `announcements`, `audit_log`, `login_attempts`.
Asosiy kurs `data.js` da; admin o'zgartirishlari bazada **ustiga qo'llanadi** (`content.js`, brauzer va serverda bir xil kod). Shuning uchun:
- asosiy so'zni «o'chirish» uni **yashiradi** (foydalanuvchilar progressi buzilmaydi, qaytarish mumkin); admin qo'shgan so'zlar to'liq o'chiriladi;
- so'z identifikatorlari barqaror (`daraja.mavzu.indeks`, yangilari `...aN`); mavzuda kamida 4 ta ko'rinadigan so'z qolishi shart, aks holda mavzu darsi yashiriladi.
- O'quvchi progressi JSON holatda `users.state` da, statistika uchun asosiy ko'rsatkichlar (`xp`, `streak`, `lessons`, `words_learned`) alohida ustunlarda.

## Testlar
```
node logic.test.js          # o'yin mantig'i (15)
node --no-warnings server.test.js   # API, rollar, xavfsizlik (19)
node admin-e2e.js           # brauzer: o'quvchi + admin, desktop va mobil (Playwright kerak)
node single-e2e.js          # bitta fayl (tilyoli.html) + lokal admin, file:// orqali
node e2e.js                 # serversiz rejim brauzer testi (python3 -m http.server 8080 bilan)
```

## Cheklovlar (ochiq)
- **O'quvchi progressi mijoz tomonidan yuboriladi** (XP, darslar). Serverda faqat shakl/hajm tekshiriladi; texnik foydalanuvchi o'z XP'sini soxtalashtirishi mumkin. Statistikalar shu ma'lumotga tayanadi. Jiddiy reyting/mukofot kerak bo'lsa, javoblarni serverda tekshirish kerak.
- Statistika (qiyin so'zlar, yutuqlar) hozir barcha foydalanuvchi holatlarini o'qib hisoblaydi — yuzlab/minglab foydalanuvchigacha yaxshi, undan katta tizimda alohida jadvallar kerak.
- Parolni tiklash (email orqali) yo'q; o'quvchi parolini admin o'zgartira olmaydi (faqat bloklash/progressni tozalash). Adminlar parolini Super Admin yoki CLI o'zgartiradi.
- HTTPS serverning o'zida yo'q: ishlab chiqarishda reverse-proxy (nginx/Caddy) ortida `COOKIE_SECURE=1` bilan ishga tushiring. Ikki faktorli autentifikatsiya yo'q.
- «Mahsulot/buyurtma» kabi e-commerce bo'limlari yo'q (bu til o'rganish platformasi); admin panel kurs, so'z, foydalanuvchi, progress va statistikani boshqaradi.
- Admin paneldagi eski demo/mock ma'lumotlar yo'q: bo'sh bazada hamma raqamlar 0 va «ma'lumot yo'q» holati ko'rinadi.
- Real telefon va ekran o'quvchi (NVDA/VoiceOver) bilan sinalmagan; faqat Chromium emulyatsiyasi (390px).
- Tarjimalar filolog tomonidan tekshirilmagan.
