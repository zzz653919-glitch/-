# ПЯТНИЦА — o'zbek tilidagi xavfsiz ovozli kompyuter yordamchisi

Windows uchun Python + PySide6 ilovasi. **Buyruqlar faqat ilova oynasi ochiq va faol bo'lgandagina qabul qilinadi va bajariladi.** Kiberpank uslubidagi interfeys (animatsiyali AI Core), ovozli buyruq (Space), matnli chat, buyruq terminali, diagnostika va jonli **PC monitoring** —
bitta dasturda. Dastur faqat siz buyruq berganingizda ishlaydi va faqat oldindan belgilangan xavfsiz amallarni bajaradi.

## Ishga tushirish (Windows)
1. **Python 3.10–3.13** o'rnating (3.14 hali sinalmagan; `run.bat` o'zi 3.13 → 3.10 ni tanlaydi, 3.14 yonida turishi mumkin): https://www.python.org/downloads/ (o'rnatishda «Add python.exe to PATH» ni belgilang).
2. Loyiha papkasida **`run.bat`** ni ikki marta bosing. Birinchi marta virtual muhit yaratiladi va `requirements.txt`
   o'rnatiladi (internet kerak), keyin oyna ochiladi.
3. Mikrofon uchun: Windows → Sozlamalar → Maxfiylik → Mikrofon → «Ilovalarga ruxsat berish» yoqilgan bo'lsin.
4. Qo'lda: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python main.py`
5. Xatolar jurnali: `%APPDATA%\Pyatnitsa\pyatnitsa.log`; sozlamalar: `%APPDATA%\Pyatnitsa\settings.json`.

### Alohida ilova (.exe) yig'ish
`build.bat` ni ishga tushiring (PyInstaller o'rnatiladi) — natija `dist\Pyatnitsa\Pyatnitsa.exe`. Butun `dist\Pyatnitsa` papkasini istalgan joyga ko'chirib, yorliq yaratish mumkin. (Bu skript Windows'da hali sinalmagan.)

## AI suhbat (haqiqiy til modeli bilan)
ПЯТНИЦА oddiy savollarga javob beradi, tushuntiradi, oldingi gapni davom ettiradi (uz / ru / en va aralash) — javoblar **qoliplardan emas, haqiqiy AI modeli** (Anthropic Claude, rasmiy `anthropic` SDK) tomonidan yaratiladi. Modul: `pyatnitsa/ai_chat.py` (GUI'ga bog'liq emas, qayta ishlatiladi).

**Yo'naltirish** (`pyatnitsa/router.py`, mahalliy qoidalar; AI'ga yuborishdan oldin):
| Kategoriya | Misol | Qayerga boradi |
|---|---|---|
| `COMPUTER_COMMAND` | «Google Chrome och», «Faylni o'chir» | mavjud tasdiqlangan buyruq tizimi (rad etish qoidalari bilan); **AI'ga bormaydi** |
| `CURRENT_INFORMATION` | «Dollar kursi qancha?», «Soat necha?», «RAM holati» | ilovaning o'z manbalari (cbu.uz, Open-Meteo, psutil). Manbasi yo'q jonli savol («bugungi yangiliklar», «evro kursi») — AI'ga «jonli ma'lumotingiz yo'q, o'ylab topmang» ko'rsatmasi bilan |
| `QUESTION_ANSWERING` | «Python nima?», «Nega osmon ko'k?», «Nega Chrome ochilmayapti?» | AI |
| `GENERAL_CONVERSATION` | «Salom, yaxshimisan?», «Oldingi gapimizni davom ettir» | AI (kontekst bilan) |
| `CLARIFICATION_REQUIRED` | «Chrome» | aniqlashtiruvchi savol |
«Nega/qanday qilib/how to/почему…» savollar — hatto buyruq so'zi bo'lsa ham (yoki xavfli so'z bo'lsa ham) — **tushuntirish** sifatida AI'ga boradi, hech narsa bajarilmaydi.

**Xavfsizlik:** AI javobi faqat MATN sifatida ko'rsatiladi/o'qiladi; undan buyruq ajratilmaydi va bajarilmaydi. Barcha kompyuter amallari faqat oldingi tekshirilgan yo'ldan (NLU → ruxsat → tasdiq → ijro) o'tadi. Testlar: AI javobida «rm -rf /», «Open Chrome» yozilsa ham hech narsa bajarilmaydi.

**Kontekst:** joriy sessiya tarixi (xotirada, sozlanadigan hajm: standart 16 xabar va ~12 000 belgi); har so'rovda oxirgi xabarlar yuboriladi. «Clear» tugmasi chat va AI kontekstini tozalaydi. Diskka **saqlanmaydi** (doimiy tarix amalga oshirilmagan). Model faqat shu suhbatda bor narsani biladi; «eslab qolish» da'vo qilinmaydi.

**Oqim:** javob so'z-ma'noli bo'laklar bilan chatga oqib keladi (`THINKING` → `RESPONDING`), fon oqimida; GUI qotmaydi. «Stop» darhol to'xtatadi (qisman javob saqlanadi); xatoda «Retry». Space bosilsa — javob to'xtatilib, tinglash boshlanadi. Yangi xabar AI band paytida rad etiladi.

**Ovozli suhbat:** Space → gapirish → matn chatda ko'rinadi → AI javobi → (ixtiyoriy) ovozda o'qiladi. Mikrofon faqat Space bilan; nutq tanish muvaffaqiyatsiz bo'lsa — xabar yo'qolmaydi, «Retry» o'sha yozuvni qayta taniydi. Ovozli va matnli kiritish bir suhbatda aralash ishlaydi.

**Ovozli javob (TTS):** AI javobi tilida o'qiladi (uz/ru/en; erkak/ayol), tezlik va ovoz balandligi sozlanadi, «Stop voice» tugmasi bor; kod bloklari, havolalar va markdown o'qilmaydi. Tizim ovozlari ro'yxatidan **tekshirilgan** til topilmasa, javob jim qoladi va sabab ko'rsatiladi (noto'g'ri tilda o'qilmaydi).

**Holatlar (AI Core):** STANDBY · LISTENING · PROCESSING · INTERPRETING · **THINKING** (so'rov ketdi, birinchi token kutilmoqda) · **RESPONDING** (javob oqib kelmoqda) · **SPEAKING** (ovoz haqiqatan chalinmoqda) · EXECUTING · ERROR.

### AI provayderni sozlash
1. Kalit oling: https://console.anthropic.com → API Keys.
2. **Eng oson:** ilovada **Settings → AI Chat → API key** ga qo'ying → *Save key* → *Test AI connection*. Kalit faqat sizning `%APPDATA%\Pyatnitsa\secrets.env` faylingizda (foydalanuvchiga xos) saqlanadi; ekranda, jurnalda va `settings.json` da **ko'rsatilmaydi**.
3. **Yoki muhit o'zgaruvchisi** (afzal): `setx ANTHROPIC_API_KEY "kalitingiz"` (so'ng dasturni qayta ishga tushiring). Muhit o'zgaruvchisi fayldan ustun.
4. Kalit yo'q bo'lsa: AI savollarga dasturning o'zi sozlash ko'rsatmasini beradi; kompyuter buyruqlari kalitsiz ishlayveradi.
- **Model:** standart `claude-opus-5-5` (Settings'da o'zgartiriladi: masalan `claude-sonnet-5-5` — arzonroq, `claude-haiku-5-5` — eng tez va arzon). **Narx/tezlik sizning qaroringiz:** Opus eng sifatli, lekin qimmatroq. Suhbat uchun «Thinking effort» standart *Low* (tez javob).
- Opus modellarda serverdagi *refusal fallback* yoqilgan (rad etilganda server avtomatik zaxira modelga o'tadi); xizmat uni qabul qilmasa — avtomatik o'chirilib, qayta uriniladi. Settings'dan o'chirish mumkin.
- Xatolar (kalit, ruxsat, model, limit/`Retry-After`, hisob mablag'i, vaqt, tarmoq, server band, uzun suhbat) — har biri aniq, 3 tilli xabar bilan.

> **Maxfiylik:** AI chat yoqilganda suhbat **matni** (va oxirgi xabarlar) Anthropic'ga yuboriladi — birinchi so'rovdan oldin dastur buni bir marta eslatadi. **Mikrofon audiosi AI'ga yuborilmaydi** (nutqni tanish alohida: Google yoki oflayn Whisper). **Kompyuter buyruqlari AI'ga yuborilmaydi.** AI chatni Settings'da o'chirish mumkin.

## Interfeys (kiberpank, PySide6)
Chap: **AI Assistant · Command History · System Monitoring · Diagnostics · Settings · About** (hammasi ishlaydigan sahifalar). Markaz: animatsiyali **AI Core**, ПЯТНИЦА, holat yorlig'i, mikrofon ko'rsatkichi va ovoz vizualizatsiyasi, suhbat (pufakchalar, vaqt belgisi), kiritish maydoni, tasdiq paneli, ijro holati, **Command Terminal**. O'ng: jonli PC holati (CPU, RAM, disk, GPU, harorat, batareya, tarmoq, uptime).
- **AI Core holatlari faqat haqiqiy holatni ko'rsatadi:** STANDBY · LISTENING (mikrofon haqiqatan ochilgandan keyin; to'lqin real mikrofon darajasiga bog'liq) · PROCESSING (audio → matn) · INTERPRETING (matn → amal) · AWAITING CONFIRMATION · EXECUTING · RESPONDING (javob aytilayotganda) · ERROR (haqiqiy mikrofon/tanish/ijro xatosi).
- **Terminal** faqat haqiqiy hodisalarni yozadi (`[VOICE] Listening activated`, `[AI] Intent identified: OPEN_APPLICATION`, `[EXECUTION] …`, `[SUCCESS]/[ERROR] …`).
- Monitoring qiymatlari `psutil`/tizim vositalaridan olinadi, fon oqimida, GUI qotmaydi. Datchik yo'q bo'lsa — **Unavailable** (yoki **Not supported**); soxta/tasodifiy qiymat ko'rsatilmaydi. Monitoring faqat oyna ochiq (kichraytirilmagan) paytda o'qiydi; hech narsa yuborilmaydi.
- **Animatsiyalar:** yengil taymer (~30 FPS, oyna yashirilganda to'xtaydi); Sozlamalarda «Reduce motion» yoki Windows'ning «animatsiyalarni o'chirish» tanlovi hisobga olinadi.
- Oyna o'lchamiga moslashadi: <1240 px da chap panel ikonkalarga siqiladi, <1100 px da o'ng panel yashiriladi, past oynada terminal yashiriladi.
- Interfeys yorliqlari inglizcha (HUD uslubi); yordamchining **javoblari** esa buyruq tilida (uz/ru/en).

## Boshqaruv
| Amal | Usul |
|---|---|
| Tinglash | **Space'ni bosib turing — gapiring — qo'yib yuboring** (hold-to-talk: qo'yib yuborilganda yozuv to'xtaydi va gap qayta ishlanadi). 0,35 s dan qisqa bosish — avvalgidek yoqish/o'chirish (ikkinchi Space to'xtatadi). Oyna faolligini yo'qotsa yozuv to'xtaydi. Matn yozayotganda emas, lekin **bo'sh** kiritish maydonida ham ishlaydi; «Start listening» tugmasi — bosib yoqish/o'chirish |
| Matnli buyruq | Pastdagi chat: Enter — yuborish, Shift+Enter — yangi qator |
| Tasdiqlash / bekor qilish | Enter yoki «Ha, bajar» / Esc yoki «Bekor qilish» |
| Ovoz balandligi | Slayder; Sozlamalar (⚙) — til, mikrofon, ovoz, tarix, ruxsat etilgan dasturlar |

Oqim: **buyruq (ovoz yoki matn) → ekranda matn → tahlil → tasdiq → bajarish → natija ekranda va ovozda**.
Ovozli va matnli buyruqlar *aynan bir xil* kod yo'lidan va bir xil xavfsizlik qoidalaridan o'tadi.

## Fayl ruxsati, fayl qidirish va ochish (File Access)
Пятница **faqat siz aynan ruxsat bergan papka/disklarda** fayl qidiradi va ochadi. Bitta papkaga ruxsat — butun kompyuterga ruxsat emas.

**Ruxsat berish:** chap menyu → **File Access** → **Add Folder…** (Windows papka tanlash oynasi; butun diskni ham tanlash mumkin — qo'shimcha ogohlantirish chiqadi) yoki **Add standard folder** (Desktop, Documents, Downloads, Pictures, Music, Videos). Birinchi marta fayl buyrug'ini aytsangiz ham (masalan «Downloads papkasidan videoni top») ilova ruxsat so'raydi: aniq papka nomi ko'rsatilgan dialog chiqadi; «Yes» desangiz ruxsat beriladi va buyruq qayta bajariladi. **Ruxsat faqat tugma bosish orqali beriladi — ovozli buyruq o'zi ruxsat bera olmaydi.** Ro'yxat sessiyalar orasida eslab qolinadi (`settings.json` → `file_roots`), Sozlamalarda ham ko'rinadi.

**Ruxsatni bekor qilish:** File Access → ro'yxatdan joyni tanlang → **Remove Access**. Ta'sir darhol: o'sha joydagi eski natijalar ham ochilmaydi. Hech narsa o'chirilmaydi, faqat ilovaning kirish huquqi olinadi.

**Ovozli/matnli buyruqlar (uz · ru · en):**
| Misol | Natija |
|---|---|
| «Downloads papkasidan videoni top» · «Find the video named example.mp4» · «Найди видео в папке Загрузки» | topilgan fayllar: nom, to'liq yo'l, tur, hajm, sana |
| «Videolar papkasidagi eng yangi videoni ko'rsat» · «Покажи самое новое видео» · «find the latest video in Downloads» | eng yangi fayl (o'zgargan vaqt bo'yicha) |
| «Rus tilidagi videolarni top» · «Покажи русские видео» | fayl/papka **nomi**ga qarab taxmin (media metama'lumoti o'qilmaydi — xabarda aytiladi) |
| «Show me the available files in my authorized folders» | ruxsat etilgan papkalarning ichidagilar |
| «Open the video named example.mp4» · «Открой видео example.mp4» · «Videoni och» | aniq nom bitta faylga mos kelsa — **tasdiq** so'raladi, so'ng ochiladi; bir nechta mos kelsa — ro'yxat chiqadi va **qaysi biri** deb so'raladi |
| «2» · «birinchisini och» · «open the third one» · «открой второй» · «bekor» | ro'yxatdan tanlash; tanlangan **fayl nomi ovoz bilan o'qib beriladi** va (sozlamada tasdiq o'chiq bo'lsa ham) tasdiqlanadi |
| «Open the video I requested» · «shu faylni qidir» | oxirgi ro'yxatga ishora; ro'yxat yo'q bo'lsa — fayl nomi so'raladi |
| «Open that person's video» · «o'sha odamning videosini och» | «Qaysi odam/fayl?» deb so'raydi — taxmin qilib ochmaydi |

Qidirish faqat **o'qiydi** va tasdiq so'ramaydi; **ochish** har doim tasdiqlanadi (aniq nom bitta faylga mos kelganda — sozlamaga ko'ra; ro'yxatdan tanlanganda — majburiy). Aniq nom topilmasa o'xshash nomlar ko'rsatiladi, lekin ular **hech qachon avtomatik ochilmaydi**.

**Ochish:** video (MP4, MKV, AVI, MOV, WebM, WMV, FLV, M4V, MPG, 3GP), rasm, audio, PDF/TXT/DOCX/XLSX/PPTX/CSV kabi hujjatlar Windows'ning standart ilovasida ochiladi; xohlasangiz videolar uchun o'z pleyeringizni tanlang (File Access → Video player → Choose…, `.exe`, shell'siz ishga tushadi). Xabar «**ochish so'rovi Windows'ga yuborildi**» deydi — ilova haqiqatan ochilganini Python tekshira olmaydi, shuning uchun «ochildi/ijro etilmoqda» deb **aytilmaydi**. Fayl topilmasa, ruxsat bekor qilingan bo'lsa, o'qib bo'lmasa yoki ilova biriktirilmagan bo'lsa — aniq sabab ko'rsatiladi.

**Xavfsizlik:**
- Qidiruv matni hech qachon yo'l sifatida ishlatilmaydi (faqat fayl nomi bilan solishtiriladi); `..`, disk harflari va h.k. hech narsa ochmaydi. Ochish faqat **ko'rsatilgan natijalar** ichidan va ruxsat qayta tekshirilgach mumkin.
- Symlink/junction orqali ruxsat etilgan papkadan chiqib bo'lmaydi; Windows ruxsat bermagan papkalar o'tkazib yuboriladi va soni aytiladi. Himoyalangan joylar (Windows, Program Files, ProgramData, AppData, ilovaning o'z ma'lumotlari, Корзина) ildiz bo'la olmaydi va qidirilmaydi; `.env`, kalit/sertifikat va parol bazalari ko'rsatilmaydi.
- **Hech qachon ochilmaydigan turlar:** `.exe .bat .cmd .ps1 .vbs .js .msi .lnk .url .dll .jar`, makroli hujjatlar (`.docm .xlsm .pptm`), `.svg .html`, arxivlar va boshqa noma'lum turlar — ro'yxatda ko'rinishi mumkin, lekin ochilmaydi.
- Fayllar **o'chirilmaydi, ko'chirilmaydi, nusxalanmaydi, o'zgartirilmaydi, yuborilmaydi va yuklanmaydi**: bunday buyruqlar («o'chir», «ko'chir», «nusxala», «send», «upload», «share» ...) fayl nomining ichida bo'lmasa butunlay rad etiladi. Fayl nomi/papka nomi/metama'lumot — **ma'lumot**: buyruq sifatida talqin qilinmaydi, chatda oddiy matn sifatida (HTML emas) chiziladi, boshqaruv va bidi belgilar (kengaytmani yashiruvchi RLO) olib tashlanadi.
- Fayl ma'lumotlari AI'ga yuborilmaydi: fayl buyruqlari AI suhbat yo'liga umuman kirmaydi.
- Administrator huquqi so'ralmaydi.

## Mahsuldorlik moduli: eslatmalar, vazifalar, qaydlar, ingliz tili rejasi, Home paneli
Chap menyu: **Home · Assistant · File Finder · Reminders · Tasks · Notes · English Study · History · Monitor · Diagnostics · Settings & Permissions · About**. Hammasi lokal SQLite bazada (`pyatnitsa.db`, foydalanuvchi papkasida); yangi pip bog'liqlik yo'q (`sqlite3` — standart kutubxona).

**Imkoniyatlar**
- **Reminders:** sana/vaqt, takrorlanish (har N daqiqa/kun/hafta/oy, ish kunlari), tahrirlash, kechiktirish (1 soat/ertaga), bajarildi, o'chirish (tasdiq bilan), kutilayotgan/kechikkan/bajarilgan ko'rinishlar. Muddat kelganda ilova ichida banner (Done · Snooze 10 min · Dismiss), tizim tray bildirishnomasi (Settings'da o'chirish mumkin) va chatda xabar. Ilova yopiq paytda o'tgan eslatma keyingi ishga tushishda **bir marta** ko'rsatiladi. Eslatmalar faqat ilova ishlab turganda chiqadi (fon xizmati yo'q).
- **Tasks:** sarlavha, tavsif, muddat, ustuvorlik (Low/Medium/High), holat (To Do/In Progress/Completed), kategoriya; qidiruv, filtrlar, Today/Week/Overdue ko'rinishlari, progress; o'chirish tasdiq bilan.
- **Notes:** sarlavha, kategoriya, teglar, qidiruv, avtomatik saqlash (holat ko'rsatiladi), oddiy formatlash (qalin/kursiv/sarlavha/ro'yxat), vaqt belgilari; bir xil nomli qayd ustiga **yozilmaydi** (ogohlantiradi).
- **English Study:** standart reja 60 daqiqa (lug'at 15 · grammatika 15 · tinglash 15 · o'qish 10 · yozish/takrorlash 5), o'zgartirish mumkin; kunlik ro'yxat — **faqat siz belgilagan** faoliyat yoziladi; streak va haftalik daraja faqat haqiqiy yozuvlardan; tarix; qiyin so'z/grammatika ro'yxati; ixtiyoriy kunlik/takrorlash eslatmalari. Bu reja IELTS bali yoki muddatini va'da qilmaydi.
- **Home:** sana, bugungi eslatma/vazifa, kechikkanlar, tezkor qayd, o'quv progressi, yaratish tugmalari; vazifa/eslatma/o'quv faoliyatini shu yerning o'zida bajarilgan deb belgilash mumkin.

**Buyruqlar (uz · ru · en; matn yoki Space ushlab turib ovoz):** «Ertaga soat 16:00 da vazifamni eslat» · «Remind me to study English at 7 PM» · «Har kuni soat 19:00 da ingliz tilini o'rganishni eslat» · «Add a task to finish my Python homework» · «Bugungi vazifalarimni ko'rsat» · «Show my overdue tasks» · «Mark my English homework as completed» · «Create a note called English Vocabulary» · «Start my English study plan» · «I finished English vocabulary». Vaqt noaniq bo'lsa («soat 9 da» — ertalabmi/kechqurunmi?) Пятница so'raydi va javobingiz bilan davom etadi; o'tmishdagi vaqtga jimgina eslatma qo'ymaydi. Yaratilgan ma'lumot to'g'ridan-to'g'ri sahifalarda ko'rinadi.

**Maxfiylik va ma'lumot:** hammasi faqat shu kompyuterda; AI'ga yoki internetga yuborilmaydi. Bazani yangilashdan oldin `*.bak-vN-vaqt` zaxira nusxasi olinadi; buzilgan baza `*.corrupt-…` deb saqlab qo'yilib yangisi ochiladi (foydalanuvchiga ko'rsatiladi). **Settings & Permissions → Local data:** soni, joylashuvi, bo'limlar bo'yicha tozalash (tasdiq bilan) va zaxira nusxani eksport qilish. Bir xil eslatma/vazifa tasodifan ikki marta qo'shilmaydi.

## File Finder (yangilangan)
**File Finder** sahifasi: qidiruv maydoni, tur filtri (Video · Images · Documents · Audio · Code · Other), o'zgargan sana va hajm filtri, «Exact name», ruxsat berilgan papkalarni boshqarish (qo'shish — Windows papka oynasi; olib tashlash — ta'sir darhol), natijalar (nom · tur · joy · sana · hajm), tanlangan faylning to'liq yo'li, **Open File**, **Cancel Search** va jarayon ko'rsatkichi. Qidiruv fon oqimida — interfeys qotmaydi. Bir nomli bir nechta fayl topilsa, hammasi joyi bilan ko'rsatiladi. Videolarni topish: «Eng yangi videoni topib och», «Find my latest video and open it», «Найди видео с названием example» — bir nechta moslik bo'lsa ro'yxat chiqadi va qaysi birini ochishni siz tanlaysiz (taxmin qilinmaydi).

## Mikrofon va ovozli buyruq quvuri (tuzatilgan)
**Aniqlangan asl sabablar** (kod tahlili bo'yicha; haqiqiy qurilmada tasdiqlash — «Test holati» bo'limiga qarang):
1. `transcribe()` ichidagi `except Exception` **har qanday ichki xatoni yutib**, «buyruqni tushunmadim» deb ko'rsatardi (FLAC konverteri bloklangan, HTTP 403/429, `audioop` yo'q ...). Endi xatolar turlarga ajratilib, aniq sabab bilan ko'rsatiladi.
2. Audio sifati tekshirilmasdi: jim / juda past / bo'sh yozuv ham yuborilardi, «ovoz past» va «ovoz yo'q» farqlanmasdi. Endi tahlil, kuchaytirish, chetdagi jimlikni kesish va 16 kHz ga o'tkazish bor.
3. Qurilma faqat nom bo'yicha (Windows'da bir nom bir necha host API'da takrorlanadi) tanlanar, ochilish xatolari bitta umumiy xabarga aylanardi. Endi MME > DirectSound > WASAPI tartibida tanlanadi; ruxsat yo'q / qurilma yo'q / chastota mos emas / PortAudio yo'q alohida xabarlar.
4. Space bosilishi bilan yozuv darhol kesilardi (oxirgi bo'g'in yo'qolardi) — endi 250 ms «post-roll». Daraja ko'rsatkichi chiziqli edi (past mikrofon ko'rinmasdi) — endi dBFS shkalasi.
5. Eski interfeysda matn maydoni fokusda bo'lsa Space bo'shliq yozardi, mikrofon yoqilmasdi — endi bo'sh maydonda Space mikrofonni yoqadi.
6. «Tushunmadim» javobi nima eshitilganini aytmasdi — endi: *«Eshitdim: «…». Mos amalni aniqlay olmadim»*.

**Quvur:** Space → qurilma tekshiruvi → yozish (LISTENING faqat oqim ochilgach) → Space/(ixtiyoriy) jimlikda to'xtash → mikrofon bo'shatiladi → PROCESSING (sifat tahlili → 16 kHz → dvigatel, fon oqimida) → INTERPRETING → tasdiq → EXECUTING → natija tekshirilib ko'rsatiladi. Bir vaqtda faqat bitta yozuv (qulf). Bo'sh/jim/past ishonchli (<0,40) natijada buyruq **bajarilmaydi**.

**Aniq xabarlar (uz/ru/en):** «Mikrofon topilmadi…», «Mikrofon hech qanday tovush yozmadi», «Nutq aniqlanmadi», «Mikrofon ishlayapti, lekin ovoz juda past», «Nutqni tanish xizmatiga ulanib bo'lmadi», «Nutqni tanish ishlamadi (sabab)», «Aniq eshitilmadi — takrorlang», «Eshitdim: «…»…».

### «Tashqaridagi ovozim tanilmaydi, kompyuter ichidagi tovush tanilyapti» — diagnostika
Bunday belgi odatda **noto'g'ri kirish qurilmasi** (Stereo Mix / «What U Hear» / Loopback / Monitor / «CABLE Output») bo'lishidan kelib chiqadi: u mikrofon emas, kompyuterning o'z chiqish ovozini «kirish» sifatida beradi. Endi:
- Bunday qurilmalar **hech qachon tanlanmaydi** va Sozlamalardagi ro'yxatda ko'rinmaydi. Windows'ning standart kirishi (yoki eski sozlamada saqlangan nom) shunday qurilma bo'lsa, ilova jismoniy mikrofonni ishlatadi va chatda aniq ogohlantiradi. Faqat loopback qurilmalar bo'lsa — alohida xato (`mic.loopback_only`).
- Ikki kanalli qurilmalar (mikrofon massivi) 2 kanalda ochiladi va mono'ga tushiriladi; kanallardan biri «o'lik» bo'lsa faqat jonlisi olinadi (aks holda daraja -6 dB ga tushadi).
- Nutq chegarasi (VAD): yozuvda nutq ritmi (bo'g'in/so'z) bo'lsa, jimlik chetlari bo'lmasa ham (Space bosib turib darrov gapirish) nutq topiladi; o'zgarmas shovqin (ventilyator) nutq hisoblanmaydi. VAD Google uchun **maslahat**: «nutq yo'q» desa ham ovoz kuchaytirilib Google'ga beriladi (Whisper'ga berilmaydi — u shovqinda gap to'qiydi).
- **Diagnostika** — Settings → MICROPHONE TEST: «List input devices» (indeks, nom, API, kanal, `LOOPBACK`, `Windows default`, `IN USE`), jonli holat **Idle / Recording / Processing** + «speech detected», daraja, hisobotda qurilma indeksi, oqim ochilish vaqti, nutq faolligi %, tanilgan matn, aniq xato. Konsolda: `python -m pyatnitsa.mic_check --list`, `python -m pyatnitsa.mic_check [--device 3] [--seconds 4] [--no-stt]`.
- Mikrofon oqimi **faqat Space bosilganda ochiladi** (doimiy tinglash yo'q: Windows'dagi «mikrofon ishlatilmoqda» belgisi faqat yozuv paytida). Oqim ochilishi uchun ketgan vaqt (odatda 50–300 ms) hisobotda ko'rsatiladi; LISTENING faqat oqim ochilgach chiqadi — shundan keyin gapiring.

**Mikrofon testi** (Settings → Microphone test): 4 s yozadi, jonli daraja, qurilma/chastota/peak/shovqin/nutq davomiyligi, tanigan matn (+ muqobillar), **qanday amal sifatida tushunilgani** — hech narsa bajarilmaydi. Hali saqlanmagan tanlovlar (qurilma, til, dvigatel) bilan sinaydi.

**Dvigatellar:** Google Web Speech (standart; uz/ru/en parallel) yoki **Whisper** (oflayn, ixtiyoriy: `pip install -r requirements-optional.txt`; Settings → Speech engine; o'zbekcha uchun «small» tavsiya). Whisper tilni faqat uz/ru/en orasidan tanlaydi va buyruq so'zlari (Chrome, Downloads, RAM …) bilan yo'naltiriladi. **Jurnal** (`%APPDATA%\Pyatnitsa\pyatnitsa.log`): qurilma, chastota, yozuv davomiyligi, peak/shovqin, dvigatel va til, tanigan matn, intent, ijro natijasi, istisnolar. Audio yozuv va kalitlar **hech qachon** yozilmaydi.

## Ko'p tilli tushunish (o'zbekcha · ruscha · inglizcha · aralash)
Buyruq faqat aniq iboraga solishtirilmaydi — `pyatnitsa/nlu.py` ma'nosini aniqlaydi:
1. **Normallashtirish:** kichik harf, kirill → lotin (`Хром` = `xrom`), apostroflar (`o'`, `o‘`, `oʻ`) birlashtiriladi; asl matn chatda o'zgartirilmasdan ko'rsatiladi (`Chrome`, `RAM`, `Telegram` kabi nomlar buzilmaydi).
2. **Til aniqlash:** har so'z lug'at va qo'shimchalar (`-ni`, `-da`, `-ов`...) bo'yicha uz/ru/en dalil beradi. Javob tili: faqat ruscha → ruscha, faqat inglizcha → inglizcha, o'zbekcha belgi bor yoki aralash → o'zbekcha.
3. **Maqsad:** gap bo'laklarga bo'linadi (`va`, `и`, `and`, vergul), har bo'lak uchun nomzod amallar ball oladi (fe'l + ob'ekt + so'roq so'zlari). Imlo xatolari (`Chorme`, `Notpad`) yaqinlik bo'yicha tuzatiladi (xavfli so'zlar uchun yaqinlik qo'llanmaydi).
4. **Parametrlar:** qidiruv matni, dollar miqdori (raqam yoki so'z bilan: «yuz», «сто», «hundred»), ob'ektlar ro'yxati.
5. **Xavfsizlik:** xavfli so'z (o'chir/удали/delete, o'chirish/выключи/shutdown, yubor/отправь/send, o'rnat/установи/install, parol, yop/закрой/close, `cmd`/`powershell`...) har qanday tilda butun gapni rad etadi. Istisno: Google qidiruvi matni ichidagi so'z (u faqat qidiruv so'rovi). Natija faqat `ALLOWED_ACTIONS` ichidagi amallardan iborat; ruxsat Sozlamalardan ham tekshiriladi.
6. **Ishonch:** ≥ 0,70 — bajarishga tayyor (baribir tasdiq so'raladi), 0,40–0,70 — aniqlashtiruvchi savol, undan past — «tushunmadim». Ikki xil ma'no teng bo'lsa («A yoki B?») so'raladi. Bir gapda 2–4 ta amal bo'lsa, bitta reja sifatida bir marta tasdiqlanadi va tartib bilan bajariladi.

Intent turlari: `open_app`, `open_folder`, `web_search`, `get_exchange_rate`, `get_pc_health`, `get_system_info` (+ `get_weather`). Har biri faqat oldindan yozilgan funksiyani chaqiradi.

**Javob tili:** tasdiq savollari, jarayon xabarlari («Dollar kursini tekshiryapman…»), natijalar va xatolar uz/ru/en da. Natija xabari amal haqiqatan boshlangandan keyin beriladi (`ochilmoqda` — jarayon ishga tushgani tekshirilgach); xato bo'lsa muvaffaqiyat deyilmaydi. Ovoz: o'zbekcha `uz-UZ-SardorNeural`, ruscha `ru-RU-DmitryNeural`, inglizcha `en-US-GuyNeural` (standart: erkak ovozi; Sozlamalarda ayol ovoziga o‘tkazish mumkin) (internet); oflayn zaxira — Windows tizim ovozi.

**Nutqni tanish (STT):** Google Web Speech bir so'rovda *bitta* til qabul qiladi va bitta gap ichidagi uz+ru aralashmasini ishonchli tanimaydi (bu texnologiya cheklovi). Shuning uchun standart «Avto» rejimi: Space bilan olingan yozuv **uz-UZ, ru-RU, en-US** da parallel taniladi (har til 3 tagacha variant), so'ng nomzodlardan buyruq sifatida eng mazmunlisi NLU ballari bo'yicha tanlanadi. Sozlamalarda bitta tilni majburlash mumkin. Haqiqiy bir gapda aralash til uchun yaxshiroq yechim — to'liq ko'p tilli model (masalan, Whisper/Azure Speech); u hozir ulanmagan.
> Maxfiylik: «Avto» rejimida yozuv Google'ga **uch marta** (har til uchun) yuboriladi, faqat Space bosilgan paytda.

### Tushunish sifati — o'lchangan natijalar
`python -m pytest tests/test_nlu.py -s` — buyruq → kutilgan amal (+ javob tili) solishtiriladi. Uch alohida to'plam (jami 451 ibora: uz/ru/en, aralash, lotin+kirill, imlo xatolari, ko'p amalli, noaniq, xavfli):

| To'plam | Qanday ishlatilgan | Natija |
|---|---|---|
| DEV (164) | foydalanuvchi misollari + variantlar; tizim shunga qarab sozlangan | 100 % (sozlangan, baho emas) |
| HELDOUT (146) | sozlashdan keyin yozilgan; **birinchi ishga tushirishda 133/146 = 91,1 %**, xatolari tuzatilgandan so'ng 99,3–100 % | birinchi natija — halol baho |
| FRESH (141) | yana yangi; **birinchi ishga tushirishda 135/141 = 95,7 %**, til aniqlash 86/87 | yakuniy halol baho |

Eslatma: bu to'plamlarni tizim muallifi yozgan (haqiqiy foydalanuvchi emas), shuning uchun real hayotda natija pastroq bo'lishi mumkin; «100 % tushunadi» deb da'vo **qilinmaydi**. FRESH dagi 6 nomuvofiqlikdan 3 tasi mening yorliqlash xatolarim, 3 tasi haqiqiy kamchilik edi (tuzatilgan). Xavfsizlik o'lchovi: barcha 3 to'plamda xavfli deb belgilangan iboralarning 100 % i rad etilgan va «bajarilmasin» deb belgilangan hech bir ibora buyruqqa aylanmagan (bu xavfsizlik isboti emas, faqat shu to'plamlardagi natija).

**Ma'lum cheklovlar:** faqat ruscha fe'l + lotincha nomlar («Покажи dollar kursi») ruscha javob oladi (o'zbekcha belgi yo'q); juda uzun yoki qo'shma gaplarda bo'laklar noto'g'ri bog'lanishi mumkin; lug'atdan tashqari sinonimlar tushunilmaydi (so'raladi); `ru` dagi o'zbek-kirill (`ўқғҳ`) so'zlari faqat lug'atdagi ko'rinishda; tilni faqat 3 til bo'yicha aniqlaydi.

## Qo'llab-quvvatlanadigan buyruqlar
(AI suhbat — alohida; yuqoriga qarang.)
- **Ochish:** Google Chrome, brauzer, yangi brauzer oynasi, Downloads / Desktop / Documents, Kalkulyator, Notepad, Fayl menejeri, YouTube.
- **Qidiruv:** «Google'da Python darslarini qidir».
- **Ma'lumot:** «Dollar kursini ko'rsat», «100 dollar necha so'm?» (O'zbekiston Markaziy banki, sana ko'rsatiladi), «Bugungi ob-havoni ko'rsat» (Open-Meteo, shahar — Sozlamalarda), «Hozirgi vaqtni ayt».
- **Kompyuter holati (faqat o'qish):** «Kompyuterim holati qanday?», «To'liq diagnostika qil», «Protsessorni tekshir», «RAM holatini ko'rsat», «Diskimda qancha joy qoldi?», «Haroratlarni ko'rsat», «Qaysi dastur ko'p RAM ishlatyapti?», «Kompyuterimda qaysi dasturlar ko'p resurs ishlatyapti?», «Kompyuter holati hisobotini yarat» (hisobot faqat `%APPDATA%\Pyatnitsa\reports\` ga yoziladi), «Kompyuterni tezlashtir» (faqat tahlil va tavsiya, hech narsa o'zgarmaydi).
- **Fayllar:** ruxsat etilgan papkalarda qidirish, ro'yxat, «eng yangi», ochish — yuqoridagi «File Access» bo'limiga qarang.
- Tushunarsiz buyruq → hech narsa bajarilmaydi, aniqlashtiruvchi savol beriladi.

## Xavfsizlik modeli
- Mikrofon **faqat Space/tugma bosilganda** ochiladi (ko'pi bilan 30 soniya), yozuv xotirada qoladi, diskka yozilmaydi. Fon tinglash yo'q; oyna yopilsa jarayon tugaydi.
- Matn hech qachon shell, `eval`, `exec` yoki fayl yo'liga berilmaydi. `parse()` faqat ruxsat etilgan `action` nomlaridan birini tanlaydi; dasturlar `subprocess.Popen([yo'l])` (shell'siz, argumentsiz) bilan, papkalar `os.startfile` bilan, veb-manzillar faqat `https` bilan ochiladi. Topilmagan dastur o'rniga boshqa fayl ochilmaydi.
- **Xavfli buyruqlar** (fayl o'chirish/ko'chirish/nomini o'zgartirish, kompyuterni o'chirish yoki qayta yoqish, xabar yuborish, dastur o'rnatish, parol) taniladi va **butunlay rad etiladi** — ularni bajaradigan kod yo'q.
- Internetdan kelgan javoblardan faqat raqamlar o'qiladi; veb-sahifa, fayl yoki tashqi matn yangi ko'rsatma bera olmaydi.
- Monitoring faqat o'qiydi: sozlamalarni o'zgartirmaydi, fayl o'chirmaydi, dastur yopmaydi, shaxsiy fayllar mazmunini o'qimaydi (jarayonlar uchun faqat nomlari). Administrator talab qiladigan amallar (`sfc`, `chkdsk`, `DISM`) avtomatik bajarilmaydi.
- Yuqori harorat/yuklanish uchun «ehtimol» tilida tushuntiriladi, aniq tashxis qo'yilmaydi. O'lchab bo'lmagan ko'rsatkich «Ma'lumot mavjud emas» deb ko'rsatiladi.
- **Faqat ilovada:** oyna yopiq, kichraytirilgan yoki boshqa oynada bo'lsa, mikrofon ochilmaydi, matn qabul qilinmaydi va kutayotgan tasdiq bajarilmaydi. Global Space tugmasi olib tashlangan.
- Avtomatik ochilish — standart holatda **o'chiq**.

## Maxfiylik
- **Nutqni tanish** Google Web Speech xizmatidan foydalanadi: Space bilan olingan yozuv faqat shu paytda internet orqali yuboriladi.
- **O'zbekcha ovoz** `edge-tts` (Microsoft internet ovozi `uz-UZ-MadinaNeural`) orqali; javob matni yuboriladi. Internet bo'lmasa yoki «Faqat tizim ovozi» tanlansa, `pyttsx3` (Windows SAPI) ishlatiladi — Windows'da o'zbekcha tizim ovozi odatda yo'q, shuning uchun talaffuz yomon bo'lishi mumkin. Ovozni Sozlamalardan o'chirish mumkin.

## Kompyuter holati — qaysi ko'rsatkichlar qayerda ishlaydi
Dashboard «Kompyuter holati» bo'limida (faqat shu bo'lim ochiq bo'lganda 2/3/5 soniyada yangilanadi; «Hozir tekshirish» tugmasi bor).

| Ko'rsatkich | Manba | Holat |
|---|---|---|
| CPU yuklanishi, yadrolar, chastota | `psutil` | Har qanday Windows'da ishlashi kerak |
| RAM jami/band/bo'sh | `psutil` | Har qanday Windows'da |
| Disklar: hajm/band/bo'sh, o'qish-yozish tezligi, kam joy ogohlantirishi | `psutil` | Har qanday Windows'da (disk «band vaqti %» ko'rsatilmaydi) |
| Batareya %, quvvat holati | `psutil.sensors_battery` | Noutbukda; stol kompyuterida «Batareya mavjud emas» |
| OS versiyasi, ishlagan vaqt | `sys`, `psutil` | Har qanday Windows'da |
| **CPU harorati** | LibreHardwareMonitor/OpenHardwareMonitor (WMI) yoki ACPI `MSAcpi_ThermalZoneTemperature` | Windows standart holatda bermaydi. LibreHardwareMonitor ishlab tursa (yoki ba'zi qurilmalarda ACPI) o'qiladi, aks holda «Ma'lumot mavjud emas» |
| **GPU** nomi | PowerShell `Win32_VideoController` | Odatda ishlaydi |
| **GPU** yuklanish/harorat/xotira | `nvidia-smi` | Faqat NVIDIA + drayver. AMD/Intel uchun «Ma'lumot mavjud emas» |
| Oxirgi tizim xatolari | PowerShell `Get-WinEvent` (System, Critical/Error, 24 soat; faqat manba, ID, vaqt) | Odatda oddiy foydalanuvchida ishlaydi; ruxsat bo'lmasa «Ma'lumot mavjud emas» |

## Test holati
`pip install -r requirements-dev.txt && python -m pytest` — 776 ta avtomatik test (Linux, offscreen Qt).

**Haqiqatan sinovdan o'tgan (avtomatik):**
- Buyruq tahlili: barcha ro'yxatdagi buyruqlar (lotin/kirill/ruscha variantlar), noma'lum buyruq hech narsa qilmaydi, xavfli buyruqlar rad etiladi, ikki buyruq aralashsa rad etiladi.
- Boshqaruvchi: Space → tinglash boshlanishi, qayta Space → to'xtash; mikrofon Space'siz ochilmaydi; tasdiqsiz hech narsa bajarilmaydi; bekor qilish; xatodan keyin dastur ishlashda davom etadi; mikrofon/tanish xatolari tushunarli xabar beradi.
- Ijrochi (soxta Windows qatlami bilan): Chrome va Downloads to'g'ri chaqiriladi; topilmagan dastur o'rniga boshqasi ochilmaydi; o'chirilgan dastur ochilmaydi; Google URL to'g'ri kodlanadi; kurs/ob-havo formatlash va manba/sana ko'rsatilishi (soxta javob bilan); internet yo'qligida son o'ylab topilmaydi.
- Chat va tugmalar: Enter yuboradi, Shift+Enter yangi qator, matnli buyruq mikrofonsiz ishlaydi, matn yozayotganda Space — oddiy bo'shliq, bo'sh maydonda va boshqa joyda — mikrofon.
- **Audio quvuri** (soxta `sounddevice` bilan, haqiqiy kod): qurilma tanlash (MME > WASAPI), 16 kHz ochish va mahalliy chastotaga o'tish, hamma audio bloklari yozilishi, mikrofon bo'shatilishi va qayta ochilishi, ikkinchi yozuv rad etilishi, ruxsat/qurilma/PortAudio xatolari alohida kalitlar bilan; sifat tahlili (nutq/jim/shovqin/past/qisqa), kuchaytirish, chetlarni kesish (ichki pauzalar saqlanadi), resampling; jimlikni aniqlash.
- **Nutq dvigatellari:** Google 3 tilda parallel, xatolarning turlarga ajratilishi (tarmoq / xizmat rad etdi / FLAC) va yutilmasligi, qisman xatoda qolgan tillardan foydalanish; Whisper (soxta model bilan); jim/qisqa/past ovoz dvigatelga yuborilmasligi.
- **Boshqaruvchi:** holatlar tartibi (LISTENING → PROCESSING → INTERPRETING → CONFIRM → EXECUTING → RESPONDING), mikrofon matnga aylantirishdan oldin bo'shatilishi, past ishonchda bajarilmasligi, har bir xato turiga aniq xabar va to'g'ri holat (ERROR faqat haqiqiy xatolarda), terminal hodisalarining tartibi, tarix yozuvlari.
- **Interfeys:** 6 sahifa navigatsiyasi, tasdiq paneli, terminal va ijro holati, tarix (matnni kiritish maydoniga qo'yish bajarmaydi), diagnostika fon oqimida, sozlamalar saqlanishi, mikrofon testi (matn va tushunilgan amal ko'rsatiladi, bajarilmaydi), kichik/katta oyna, uzun xabarlar maketni buzmasligi, reduced-motion.
- Monitoring: haqiqiy `psutil` o'lchovlari (Linux'da), holat baholash va sabablar, mavjud bo'lmagan qiymatlar uchun «Ma'lumot mavjud emas».

**Fayl ruxsati va fayllarni ochish (haqiqiy fayl tizimida, vaqtinchalik papkalarda; Windows qatlami soxta):** ruxsatlarni eslab qolish va bekor qilish, himoyalangan/xavfli ildizlarni rad etish, ruxsat berilmagan joyga hech qanday yo'l bilan (nom matni, `..`, symlink, eski natija) kirib bo'lmasligi, Windows ruxsat xatolarini sanash, nom/kengaytma/tur/til/«eng yangi» qidiruvi, kirill-lotin moslashuvi, o'xshash nomlarni avtomatik ochmaslik, noaniq moslikda ro'yxat + tanlash + nomni o'qib berish + majburiy tasdiq, o'chirilgan/ruxsati bekor qilingan faylni ochmaslik, `.exe`/makro/skript ochilmasligi, xavfli fe'llar rad etilishi, fayl nomi buyruq bo'la olmasligi, AI'ga hech narsa bormasligi, ovozdagi past ishonch, File Access sahifasi (qo'shish/bekor qilish/qidirish/ochish/xatolar/maket), ruxsat dialogi va buyruqni qayta bajarish. Xavfsizlik mantig'ining 12 ta qismi mutatsiya bilan tekshirilgan (buzilganda testlar qulaydi). **Sinalmagan (Windows'da bajariladi):** `os.startfile` bilan haqiqiy ilova ochilishi, tanlangan pleyerning ishga tushishi, junction/reparse nuqtalari, Windows papka tanlash oynasi, Known Folder yo'llari (OneDrive ko'chirgan Desktop/Documents), real Windows ruxsat xatolari va Defender bilan tezlik (Linux'da 30 600 element ≈ 0,2–0,9 s).

**Mikrofon diagnostikasi (soxta qurilma bilan; haqiqiy mikrofon sinovi emas):** loopback/Stereo Mix nomlari, standart/tanlangan loopback'ni o'tkazib yuborish va ogohlantirish, faqat-loopback xatosi, kanal tushirish va o'lik kanal, 2→1 kanal zaxirasi, jonli faollik, VAD, hold-to-talk (bosish/qo'yib yuborish, qisqa bosish, oyna faolligini yo'qotish, endpoint to'xtatmasligi, haqiqiy Qt tugma hodisalari), holatlar ketma-ketligi, qurilmalar jadvali, konsol vositasi. Har bir asosiy mantiq mutatsiya bilan tekshirilgan (buzilganda testlar qulaydi).

**AI suhbat bo'yicha (haqiqatan sinalgan):**
- Rasmiy `anthropic` SDK **haqiqiy HTTP/SSE orqali lokal soxta server** bilan: oqimli matn, so'rov shakli (model, effort, tizim ko'rsatmasi, kontekst), `fallbacks` yuborilishi va rad etilsa tashlab qayta urinish, kalitni muhitdan o'qish, kalit yo'qligi, 401/403/404/429(+Retry-After)/529/500/400(kredit)/413 xaritalash, timeout, ulanib bo'lmasligi, refusal/bo'sh/`max_tokens` javoblari, **bekor qilish** (birinchi token kutilayotganda ham darhol; oqim o'rtasida — qisman matn saqlanadi).
- Boshqaruvchi (soxta mijoz bilan): holatlar tartibi (THINKING → STREAMING → …), kontekst va «uni/misol ber» davomi, har turn tilining ko'rsatmasi, kontekst hajmi chegarasi, **buyruq ↔ suhbat ajratish** (buyruq/xavfli so'z AI'ga bormaydi; «Nega Chrome ochilmayapti?» AI'ga boradi va hech narsa ochilmaydi), **AI javobidagi buyruqlar bajarilmasligi**, kalitsiz/o'chirilgan holatda tushuntirish, xatolarning 3 tilda ko'rsatilishi, Retry (savol takrorlanmaydi), Stop, Space bilan to'xtatib tinglash, tozalash, maxfiylik eslatmasi bir marta, tarix yozuvlari, nutq tanish muvaffaqiyatsiz bo'lsa yozuvni saqlab qayta urinish.
- Kalit xavfsizligi: fayl ruxsati 0600 (POSIX), muhit > fayl tartibi, kalit `settings.json`, jurnal va xato matnlarida yo'q (filtr), manba kodida qattiq kodlangan kalit yo'q.
- Ovoz (soxta `edge_tts`/`pyttsx3`): til+jins bo'yicha ovoz nomi, tezlik, markdown/kod o'qilmasligi, tekshirilmagan tilda jim qolib sabab ko'rsatish (bir marta), `pending`/`speaking` holatlari, to'xtatish.
- Interfeys: oqimli pufakcha, «Thinking…», Stop/Retry/Clear/Stop voice tugmalari, xato pufakchasi, Sozlamalarda kalit saqlash va **ulanish testi (lokal serverga, fon oqimida)**.

**Yo'naltiruvchi aniqligi (o'lchangan, `tests/router_corpus.py`):** DEV 95/95 (sozlangan); **YANGI to'plam (105 ibora), birinchi ishga tushirishda: aniq kategoriya 98/105 = 93,3%, buyruq↔AI chegarasi 101/105 = 96,2%**; to'rtta chegara xatosi (vaqt/«dastur» so'zi tasodifan buyruq bo'lib qolishi, savol shaklidagi «xavfli» so'zlar, jonli natija) tuzatilgandan keyin 104/105 va 105/105 — shu sababli bu to'plam endi mustaqil baho emas. To'plamni muallif yozgan; real foydalanishda pastroq bo'lishi mumkin.

**Windows'da qo'lda tekshirilishi kerak (bu muhitda sinab bo'lmadi):**
- **Haqiqiy Anthropic API** (bu muhitda kalit yo'q; `api.anthropic.com` ga tarmoq ulanishi bor — kalitsiz GET 404 qaytardi — lekin haqiqiy so'rov yuborilmagan): haqiqiy javob sifati va o'zbekcha/ruscha/inglizcha kalitlar bilan natijalar, haqiqiy kechikish, `fallbacks` beta sarlavhasining kalitingiz tomonidan qabul qilinishi (qabul qilinmasa avtomatik o'chiriladi), modelning mavjudligi (`claude-opus-5-5`).
- Haqiqiy ovozli javob: `edge-tts` o'zbekcha/ruscha/inglizcha erkak va ayol ovozlari, `QMediaPlayer` chalishi, to'xtatish, tezlik; Windows tizim ovozlarida til mavjudligi.
- Mikrofon → AI to'liq jonli suhbat (haqiqiy mikrofon va nutq tanish bilan).
- **Haqiqiy mikrofon** (bu muhitda audio qurilma va PortAudio yo'q): yozish, daraja ko'rsatkichi, Windows ruxsatlari, oqim ochilish kechikishi (birinchi bo'g'in kesilishi mumkinligi), haqiqiy shovqin sharoitida jimlikni aniqlash chegaralari — barchasi faqat sintetik signallar va soxta qurilma bilan sinalgan.
- **Haqiqiy tanish sifati:** Google va Whisper bilan o'zbekcha/ruscha/inglizcha jonli nutq, aralash gaplar (ular Google'da cheklangan), Whisper modelini yuklab olish va tezligi. Real tanish aniqligi o'lchanmagan.
- Ovozli javob: `edge-tts` + `QMediaPlayer` ovozi va `pyttsx3` fallback.
- Chrome/Kalkulyator/Notepad/Explorer ochilishi, Downloads/Desktop/Documents (OneDrive ko'chirilgan papkalar ham) — kodi tayyor, lekin Windows'da bajarilmagan.
- Haqiqiy internet: cbu.uz kursi va Open-Meteo ob-havosi (sinov muhitida tarmoq bloklangan edi; faqat «internet yo'q» yo'li tekshirildi).
- Avtomatik ochilish (reestr), `build.bat` bilan .exe yig'ish, Windows batareya/PowerShell/nvidia-smi sensorlari, tizim jurnali.
- Interfeysning Windows'dagi ko'rinishi (skrinshotlar Linux offscreen'da olingan).

**Mahsuldorlik moduli testlari (haqiqiy SQLite, offscreen Qt):** migratsiya/zaxira/buzilgan baza, barcha omborlar, vaqt tahlili (uz/ru/en, noaniqlik, takrorlanish), buyruq→amal→sahifa yangilanishi, tasdiq va aniqlashtirish davomi, eslatma banneri (Done/Snooze/Dismiss, 3 tadan ko'p emas, tray yo'q/o'chiq holat), dialog tekshiruvi, qaydlar avto-saqlash va nom to'qnashuvi, o'quv streak'i faqat yozuvdan, ma'lumotni tozalash/eksport. Testlar ikkita haqiqiy xatoni topdi va tuzatildi (reja dialogi yaratilishda qulashi; vazifa tahririda ustuvorlik rad etilishi) va dialog sana konstruktori xatosini. **Sinalmagan (Windows'da):** haqiqiy tray bildirishnomasi ko'rinishi, ilova yopiq paytda eslatma (qo'llab-quvvatlanmaydi), haqiqiy ovoz bilan buyruq aytish, papka tanlash oynasi.

## Loyiha tuzilishi
```
main.py                  ishga tushirish
run.bat                  Windows uchun avtomatik o'rnatish va ishga tushirish
build.bat                Pyatnitsa.exe yig'ish (PyInstaller)
pyatnitsa/ai_chat.py     AI suhbat: tarix, tizim ko'rsatmasi, oqimli so'rov, xatolar, bekor qilish
pyatnitsa/router.py      suhbat ↔ buyruq yo'naltirish (5 kategoriya)
pyatnitsa/credentials.py API kalit (muhit / shaxsiy fayl), jurnaldan yashirish
pyatnitsa/tts.py         ovozli javob (til/jins/tezlik, tekshirilgan ovozlar)
pyatnitsa/nlu.py         ko'p tilli tushunish (til, maqsad, parametr, noaniqlik)
pyatnitsa/i18n.py        uz/ru/en matnlar
pyatnitsa/commands.py    buyruq turlari, normallashtirish, ruxsat etilgan amallar
pyatnitsa/executor.py    ruxsat etilgan amallar ro'yxati va ijrosi
pyatnitsa/files.py       ruxsat etilgan papkalar, xavfsiz qidirish, ochishdan oldingi tekshiruv
pyatnitsa/fileintent.py  fayl buyruqlarini tushunish (uz/ru/en), ro'yxatdan tanlash
pyatnitsa/db.py          SQLite: migratsiya, zaxira, buzilgan bazani karantin, xotira zaxirasi
pyatnitsa/reminders.py, tasks.py, notes.py, study.py   mahsuldorlik omborlari
pyatnitsa/timeparse.py   sana/vaqt/takrorlanishni tushunish (uz/ru/en), noaniqlikda so'rash
pyatnitsa/taskintent.py, toolsintent.py   eslatma/vazifa/qayd/o'quv va media buyruqlarini tushunish
pyatnitsa/apps.py        ruxsat etilgan dasturlar, Windows qatlami
pyatnitsa/services.py    kurs va ob-havo (internet)
pyatnitsa/health.py      PC Health Monitor (faqat o'qish)
pyatnitsa/controller.py  holat mashinasi (ovoz + matn)
pyatnitsa/audio.py, tts.py, settings.py
pyatnitsa/audio.py       mikrofon, qurilma tanlash, sifat tahlili, tayyorlash, jimlikni aniqlash
pyatnitsa/stt.py         nutq dvigatellari (Google / Whisper), xato turlari
pyatnitsa/voice_test.py  mikrofon testi
pyatnitsa/diagnostics.py haqiqiy tizim tekshiruvlari
pyatnitsa/gui/           kiberpank interfeys (main_window, dashboard_page, reminders_page, tasks_page, notes_page, study_page, dialogs, common, core_widget, monitor_view, chat, terminal, pages, files_page, settings_page, theme, icons)
pyatnitsa/ui.py          moslik uchun qisqa import
tests/                   avtomatik testlar
```
