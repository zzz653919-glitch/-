# ПЯТНИЦА — o'zbek tilidagi xavfsiz ovozli kompyuter yordamchisi

Windows uchun Python + PySide6 ilovasi. **Buyruqlar faqat ilova oynasi ochiq va faol bo'lgandagina qabul qilinadi va bajariladi.** Ovozli buyruq (Space), matnli chat va **PC Health Monitor** —
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

## Boshqaruv
| Amal | Usul |
|---|---|
| Tinglashni boshlash / to'xtatish | **Space** (oyna faol bo'lganda) yoki «Mikrofonni yoqish» tugmasi |
| Matnli buyruq | Pastdagi chat: Enter — yuborish, Shift+Enter — yangi qator |
| Tasdiqlash / bekor qilish | Enter yoki «Ha, bajar» / Esc yoki «Bekor qilish» |
| Ovoz balandligi | Slayder; Sozlamalar (⚙) — til, mikrofon, ovoz, tarix, ruxsat etilgan dasturlar |

Oqim: **buyruq (ovoz yoki matn) → ekranda matn → tahlil → tasdiq → bajarish → natija ekranda va ovozda**.
Ovozli va matnli buyruqlar *aynan bir xil* kod yo'lidan va bir xil xavfsizlik qoidalaridan o'tadi.

## Ko'p tilli tushunish (o'zbekcha · ruscha · inglizcha · aralash)
Buyruq faqat aniq iboraga solishtirilmaydi — `pyatnitsa/nlu.py` ma'nosini aniqlaydi:
1. **Normallashtirish:** kichik harf, kirill → lotin (`Хром` = `xrom`), apostroflar (`o'`, `o‘`, `oʻ`) birlashtiriladi; asl matn chatda o'zgartirilmasdan ko'rsatiladi (`Chrome`, `RAM`, `Telegram` kabi nomlar buzilmaydi).
2. **Til aniqlash:** har so'z lug'at va qo'shimchalar (`-ni`, `-da`, `-ов`...) bo'yicha uz/ru/en dalil beradi. Javob tili: faqat ruscha → ruscha, faqat inglizcha → inglizcha, o'zbekcha belgi bor yoki aralash → o'zbekcha.
3. **Maqsad:** gap bo'laklarga bo'linadi (`va`, `и`, `and`, vergul), har bo'lak uchun nomzod amallar ball oladi (fe'l + ob'ekt + so'roq so'zlari). Imlo xatolari (`Chorme`, `Notpad`) yaqinlik bo'yicha tuzatiladi (xavfli so'zlar uchun yaqinlik qo'llanmaydi).
4. **Parametrlar:** qidiruv matni, dollar miqdori (raqam yoki so'z bilan: «yuz», «сто», «hundred»), ob'ektlar ro'yxati.
5. **Xavfsizlik:** xavfli so'z (o'chir/удали/delete, o'chirish/выключи/shutdown, yubor/отправь/send, o'rnat/установи/install, parol, yop/закрой/close, `cmd`/`powershell`...) har qanday tilda butun gapni rad etadi. Istisno: Google qidiruvi matni ichidagi so'z (u faqat qidiruv so'rovi). Natija faqat `ALLOWED_ACTIONS` ichidagi amallardan iborat; ruxsat Sozlamalardan ham tekshiriladi.
6. **Ishonch:** ≥ 0,70 — bajarishga tayyor (baribir tasdiq so'raladi), 0,40–0,70 — aniqlashtiruvchi savol, undan past — «tushunmadim». Ikki xil ma'no teng bo'lsa («A yoki B?») so'raladi. Bir gapda 2–4 ta amal bo'lsa, bitta reja sifatida bir marta tasdiqlanadi va tartib bilan bajariladi.

Intent turlari: `open_app`, `open_folder`, `web_search`, `get_exchange_rate`, `get_pc_health`, `get_system_info` (+ `get_weather`). Har biri faqat oldindan yozilgan funksiyani chaqiradi.

**Javob tili:** tasdiq savollari, jarayon xabarlari («Dollar kursini tekshiryapman…»), natijalar va xatolar uz/ru/en da. Natija xabari amal haqiqatan boshlangandan keyin beriladi (`ochilmoqda` — jarayon ishga tushgani tekshirilgach); xato bo'lsa muvaffaqiyat deyilmaydi. Ovoz: o'zbekcha `uz-UZ-MadinaNeural`, ruscha `ru-RU-SvetlanaNeural`, inglizcha `en-US-JennyNeural` (internet); oflayn zaxira — Windows tizim ovozi.

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
`pip install -r requirements-dev.txt && python -m pytest` — 194 ta avtomatik test (Linux, offscreen Qt).

**Haqiqatan sinovdan o'tgan (avtomatik):**
- Buyruq tahlili: barcha ro'yxatdagi buyruqlar (lotin/kirill/ruscha variantlar), noma'lum buyruq hech narsa qilmaydi, xavfli buyruqlar rad etiladi, ikki buyruq aralashsa rad etiladi.
- Boshqaruvchi: Space → tinglash boshlanishi, qayta Space → to'xtash; mikrofon Space'siz ochilmaydi; tasdiqsiz hech narsa bajarilmaydi; bekor qilish; xatodan keyin dastur ishlashda davom etadi; mikrofon/tanish xatolari tushunarli xabar beradi.
- Ijrochi (soxta Windows qatlami bilan): Chrome va Downloads to'g'ri chaqiriladi; topilmagan dastur o'rniga boshqasi ochilmaydi; o'chirilgan dastur ochilmaydi; Google URL to'g'ri kodlanadi; kurs/ob-havo formatlash va manba/sana ko'rsatilishi (soxta javob bilan); internet yo'qligida son o'ylab topilmaydi.
- Chat: Enter yuboradi, Shift+Enter yangi qator, matnli buyruq mikrofonsiz ishlaydi, matn yozayotganda Space mikrofonni yoqmaydi.
- Monitoring: haqiqiy `psutil` o'lchovlari (Linux'da), holat baholash va sabablar, mavjud bo'lmagan qiymatlar uchun «Ma'lumot mavjud emas».

**Windows'da qo'lda tekshirilishi kerak (bu muhitda sinab bo'lmadi):**
- Haqiqiy mikrofondan yozish (`sounddevice`) va Google nutq tanishi, o'zbekcha tanish sifati.
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
pyatnitsa/nlu.py         ko'p tilli tushunish (til, maqsad, parametr, noaniqlik)
pyatnitsa/i18n.py        uz/ru/en matnlar
pyatnitsa/commands.py    buyruq turlari, normallashtirish, ruxsat etilgan amallar
pyatnitsa/executor.py    ruxsat etilgan amallar ro'yxati va ijrosi
pyatnitsa/apps.py        ruxsat etilgan dasturlar, Windows qatlami
pyatnitsa/services.py    kurs va ob-havo (internet)
pyatnitsa/health.py      PC Health Monitor (faqat o'qish)
pyatnitsa/controller.py  holat mashinasi (ovoz + matn)
pyatnitsa/audio.py, tts.py, settings.py
pyatnitsa/ui.py, widgets.py  interfeys
tests/                   avtomatik testlar
```
