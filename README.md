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
| Tinglashni boshlash / to'xtatish | **Space** (oyna faol bo'lganda; matn yozayotganda emas, lekin **bo'sh** kiritish maydonida ham ishlaydi) yoki «Start listening» tugmasi |
| Matnli buyruq | Pastdagi chat: Enter — yuborish, Shift+Enter — yangi qator |
| Tasdiqlash / bekor qilish | Enter yoki «Ha, bajar» / Esc yoki «Bekor qilish» |
| Ovoz balandligi | Slayder; Sozlamalar (⚙) — til, mikrofon, ovoz, tarix, ruxsat etilgan dasturlar |

Oqim: **buyruq (ovoz yoki matn) → ekranda matn → tahlil → tasdiq → bajarish → natija ekranda va ovozda**.
Ovozli va matnli buyruqlar *aynan bir xil* kod yo'lidan va bir xil xavfsizlik qoidalaridan o'tadi.

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
`pip install -r requirements-dev.txt && python -m pytest` — 391 ta avtomatik test (Linux, offscreen Qt).

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
pyatnitsa/apps.py        ruxsat etilgan dasturlar, Windows qatlami
pyatnitsa/services.py    kurs va ob-havo (internet)
pyatnitsa/health.py      PC Health Monitor (faqat o'qish)
pyatnitsa/controller.py  holat mashinasi (ovoz + matn)
pyatnitsa/audio.py, tts.py, settings.py
pyatnitsa/audio.py       mikrofon, qurilma tanlash, sifat tahlili, tayyorlash, jimlikni aniqlash
pyatnitsa/stt.py         nutq dvigatellari (Google / Whisper), xato turlari
pyatnitsa/voice_test.py  mikrofon testi
pyatnitsa/diagnostics.py haqiqiy tizim tekshiruvlari
pyatnitsa/gui/           kiberpank interfeys (main_window, core_widget, monitor_view, chat, terminal, pages, settings_page, theme, icons)
pyatnitsa/ui.py          moslik uchun qisqa import
tests/                   avtomatik testlar
```
