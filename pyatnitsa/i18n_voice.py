"""Ovozli boshqaruv, kompyuter/oyna/skrinshot/clipboard/veb va ingliz tili mashqlari matnlari (uz · ru · en). `i18n._S` ga qo'shiladi."""
from __future__ import annotations

S: dict[str, tuple[str, str, str]] = {
    # ---- faqat ovozli rejim
    "voice_only": ("Faqat ovozli rejim yoqilgan: buyruqni yozib bo'lmaydi. Space tugmasini bosib turing, gapiring va qo'yib yuboring. (Sozlamalarda o'chirish mumkin.)",
                   "Включён режим «только голос»: команды нельзя вводить текстом. Удерживайте Пробел, говорите и отпустите. (Отключается в настройках.)",
                   "Voice-only mode is on: commands cannot be typed. Hold SPACE, speak, then release. (You can turn this off in Settings.)"),
    "confirm.voice_hint": ("Tasdiqlash uchun Space bosib turing va «ha», bekor qilish uchun «yo'q» deng.",
                           "Чтобы подтвердить, удерживайте Пробел и скажите «да»; чтобы отменить — «нет».",
                           "To confirm, hold SPACE and say “yes”; to cancel say “no”."),
    "confirm.voice_yes": ("Ovozli tasdiq qabul qilindi.", "Голосовое подтверждение принято.", "Voice confirmation accepted."),
    # ---- oyna boshqaruvi
    "win.minimize": ("oynani kichraytirish", "свернуть окно", "minimize window"), "win.maximize": ("oynani kattalashtirish", "развернуть окно", "maximize window"),
    "win.next": ("keyingi oynaga o'tish", "переключиться на следующее окно", "switch to the next window"),
    "win.prev": ("oldingi oynaga o'tish", "переключиться на предыдущее окно", "switch to the previous window"),
    "ask.window": ("Oyna: {what}", "Окно: {what}", "Window: {what}"),
    "win.sent": ("«{what}» buyrug'i Windows'ga yuborildi. Qaysi oyna o'zgarganini tekshira olmayman. («Bu oyna» — hozir faol oyna, ya'ni Пятница'ning o'zi.)",
                 "Команда «{what}» отправлена в Windows. Проверить, какое окно изменилось, я не могу. («Это окно» — активное окно, то есть сама Пятница.)",
                 "The “{what}” command was sent to Windows. I cannot verify which window changed. (“This window” means the active window — Пятница itself.)"),
    "win.failed": ("Oyna buyrug'i yuborilmadi: {err}", "Команда окну не отправлена: {err}", "The window command could not be sent: {err}"),
    # ---- skrinshot
    "ask.screenshot": ("Ekran rasmini olib, Pictures papkasidagi Pyatnitsa bo'limiga saqlash", "Сделать снимок экрана и сохранить в Pictures\\Pyatnitsa", "Take a screenshot and save it to Pictures\\Pyatnitsa"),
    "shot.ok": ("Skrinshot saqlandi: {path}", "Снимок экрана сохранён: {path}", "Screenshot saved: {path}"),
    "shot.ok_say": ("Skrinshot saqlandi.", "Снимок экрана сохранён.", "Screenshot saved."),
    "shot.fail": ("Skrinshot olinmadi: {err}", "Снимок экрана не получен: {err}", "The screenshot could not be taken: {err}"),
    "shot.pending": ("Skrinshot olinmoqda…", "Делаю снимок экрана…", "Taking the screenshot…"),
    # ---- clipboard
    "ask.clip.read": ("Clipboard (nusxa buferi) matnini shu yerda ko'rsatish (hech qayerga yuborilmaydi)", "Показать текст из буфера обмена здесь (никуда не отправляется)",
                      "Show the clipboard text here (nothing is sent anywhere)"),
    "ask.clip.explain": ("Nusxalangan matnni tushuntirish uchun AI xizmatiga YUBORISH", "ОТПРАВИТЬ скопированный текст в ИИ-сервис, чтобы объяснить его",
                         "SEND the copied text to the AI service to explain it"),
    "ask.clip.summarize": ("Nusxalangan matnni qisqartirish uchun AI xizmatiga YUBORISH", "ОТПРАВИТЬ скопированный текст в ИИ-сервис для краткого пересказа",
                           "SEND the copied text to the AI service to summarize it"),
    "clip.empty": ("Clipboard bo'sh yoki unda matn yo'q. Avval kerakli matnni nusxalang (Ctrl+C), keyin qayta ayting.",
                   "Буфер обмена пуст или в нём нет текста. Сначала скопируйте нужный текст (Ctrl+C), затем повторите.",
                   "The clipboard is empty or has no text. Copy the text first (Ctrl+C), then ask again."),
    "clip.secret": ("Clipboard'dagi matn parol yoki kalitga o'xshaydi, shuning uchun uni ko'rsatmayman va hech qayerga yubormayman.",
                    "Текст в буфере похож на пароль или ключ, поэтому я не показываю его и никуда не отправляю.",
                    "The clipboard text looks like a password or key, so I will not show it or send it anywhere."),
    "clip.show": ("Clipboard ({n} belgi):\n{text}", "Буфер обмена ({n} симв.):\n{text}", "Clipboard ({n} characters):\n{text}"),
    "clip.cut": ("… (qolgani ko'rsatilmadi)", "… (остальное не показано)", "… (the rest is not shown)"),
    "clip.say": ("Clipboard matni ekranda. Maxfiylik uchun o'qib bermayman.", "Текст буфера на экране. Из соображений приватности вслух не читаю.",
                 "The clipboard text is on screen. I do not read it aloud for privacy."),
    "clip.sending": ("Nusxalangan matn ({n} belgi) AI xizmatiga yuborilmoqda — siz tasdiqlaganingiz uchun.", "Скопированный текст ({n} симв.) отправляется в ИИ-сервис — вы это подтвердили.",
                     "Sending the copied text ({n} characters) to the AI service — you confirmed this."),
    "clip.too_long": ("Nusxalangan matn juda uzun ({n} belgi; ko'pi bilan {max}). Qisqaroq qismini nusxalang.", "Скопированный текст слишком длинный ({n} симв.; максимум {max}). Скопируйте часть покороче.",
                      "The copied text is too long ({n} characters; the limit is {max}). Copy a shorter part."),
    "clip.p.explain": ("Quyidagi nusxalangan matnni (kod, xato yoki oddiy matn) sodda tilda tushuntiring. Javobni {language} tilida bering.\n\n{text}",
                       "Объясните простыми словами следующий скопированный текст (код, ошибку или обычный текст). Ответьте на языке: {language}.\n\n{text}",
                       "Explain the following copied text (code, an error or plain text) in simple terms. Answer in {language}.\n\n{text}"),
    "clip.p.summarize": ("Quyidagi nusxalangan matnni qisqacha xulosa qiling. Javobni {language} tilida bering.\n\n{text}",
                         "Кратко перескажите следующий скопированный текст. Ответьте на языке: {language}.\n\n{text}",
                         "Summarize the following copied text briefly. Answer in {language}.\n\n{text}"),
    "lang.name": ("o'zbek", "русский", "English"),
    # ---- veb
    "ask.yt": ("YouTube'da «{q}» ni qidirish", "Искать «{q}» на YouTube", "Search YouTube for “{q}”"),
    "yt.ok": ("YouTube'da «{q}» qidiruvi brauzerda ochildi.", "Поиск «{q}» на YouTube открыт в браузере.", "The YouTube search for “{q}” was opened in the browser."),
    "cl.yt": ("YouTube'da nimani qidiray?", "Что искать на YouTube?", "What should I search for on YouTube?"),
    "ask.site": ("Saytni ochish: {url}", "Открыть сайт: {url}", "Open the website: {url}"),
    "site.ok": ("{host} brauzerda ochildi.", "{host} открыт в браузере.", "{host} was opened in the browser."),
    "site.bad": ("«{what}» xavfsiz veb-manzilga o'xshamaydi, shuning uchun ochmayman.", "«{what}» не похоже на безопасный веб-адрес, поэтому я его не открою.",
                 "“{what}” does not look like a safe web address, so I will not open it."),
    "cl.site": ("Qaysi saytni ochay? Manzilni ayting (masalan, kun.uz).", "Какой сайт открыть? Назовите адрес (например, kun.uz).", "Which website? Say the address (for example kun.uz)."),
    # ---- internet va kompyuter xususiyatlari
    "ask.net": ("Internet ulanishini tekshirish", "Проверить подключение к интернету", "Check the internet connection"),
    "net.ok": ("Internet ishlayapti: {host} bilan ulanish {ms} ms ichida o'rnatildi.", "Интернет работает: соединение с {host} установлено за {ms} мс.",
               "The internet is working: connected to {host} in {ms} ms."),
    "net.fail": ("Internetga chiqib bo'lmadi ({err}). Wi-Fi yoki kabelni tekshiring.", "Выйти в интернет не удалось ({err}). Проверьте Wi-Fi или кабель.",
                 "Could not reach the internet ({err}). Check the Wi-Fi or cable."),
    "ask.specs": ("Kompyuter xususiyatlarini ko'rsatish", "Показать характеристики компьютера", "Show the computer specifications"),
    "specs.title": ("Kompyuter xususiyatlari", "Характеристики компьютера", "Computer specifications"),
    "specs.os": ("Tizim", "Система", "System"), "specs.cpu": ("Protsessor", "Процессор", "Processor"), "specs.cores": ("yadro/oqim", "ядер/потоков", "cores/threads"),
    "specs.ram": ("Operativ xotira", "Оперативная память", "Memory"), "specs.disk": ("Disk", "Диск", "Disk"), "specs.gpu": ("Videokarta", "Видеокарта", "Graphics"),
    "specs.na": ("aniqlanmadi", "не определено", "not detected"),
    # ---- interfeys buyruqlari
    "ask.ui.settings": ("Пятница sozlamalarini ochish", "Открыть настройки Пятницы", "Open the Пятница settings"),
    "ask.ui.close": ("Sozlamalar panelini yopish (asosiy oynaga qaytish)", "Закрыть панель настроек (вернуться к ассистенту)", "Close the settings panel (return to the assistant)"),
    "ask.ui.dark": ("Qorong'i mavzuni yoqish", "Включить тёмную тему", "Switch to dark mode"),
    "ask.ui.commands": ("Mavjud buyruqlar ro'yxatini ko'rsatish", "Показать список доступных команд", "Show the list of available commands"),
    "ask.ui.mic": ("Mikrofon holatini ko'rsatish", "Показать состояние микрофона", "Show the microphone status"),
    "ui.settings": ("Пятница sozlamalari ochildi.", "Настройки Пятницы открыты.", "The Пятница settings are open."),
    "ui.closed": ("Sozlamalar paneli yopildi.", "Панель настроек закрыта.", "The settings panel was closed."),
    "ui.dark": ("Interfeys allaqachon qorong'i mavzuda. Yorug' mavzu yo'q.", "Интерфейс уже в тёмной теме. Светлой темы нет.", "The interface is already in dark mode. There is no light theme."),
    "ui.light": ("Yorug' mavzu hozircha mavjud emas: interfeys faqat qorong'i mavzuda ishlaydi.", "Светлой темы пока нет: интерфейс работает только в тёмной теме.",
                 "A light theme is not available: the interface only has the dark theme."),
    "ui.mic": ("Mikrofon holati: {state}.\nQurilma: {dev}.\nMikrofon faqat Space tugmasini bosib turganingizda yoqiladi; boshqa paytda eshitmaydi.",
               "Состояние микрофона: {state}.\nУстройство: {dev}.\nМикрофон включается только пока вы удерживаете Пробел; в остальное время он не слушает.",
               "Microphone status: {state}.\nDevice: {dev}.\nThe microphone only listens while you hold SPACE; it does not listen at any other time."),
    "mic.state.idle": ("Tayyor (Ready)", "Готов (Ready)", "Ready"), "mic.state.listening": ("Tinglayapti (Listening)", "Слушаю (Listening)", "Listening"),
    "mic.state.processing": ("Qayta ishlanmoqda (Processing)", "Обработка (Processing)", "Processing"), "mic.state.executing": ("Bajarilmoqda (Executing)", "Выполняется (Executing)", "Executing"),
    "mic.state.error": ("Xato (Error)", "Ошибка (Error)", "Error"),
    "mic.default": ("tizim standarti", "по умолчанию", "system default"),
    "cl.settings": ("Qaysi sozlamalar: Windows sozlamalarimi yoki Пятница sozlamalarimi? («Windows» yoki «ilova» deng.)",
                    "Какие настройки открыть: Windows или Пятницы? (Скажите «Windows» или «приложение».)",
                    "Which settings: Windows or the Пятница app? (Say “Windows” or “app”.)"),
    "ui.commands": ("Mavjud ovozli buyruqlar (Space ni bosib turib ayting):\n"
                    "• Ilovalar: «Chrome'ni och», «VS Code ni och», «Downloads papkasini och», «YouTube'ni och»\n"
                    "• Oyna/ovoz: «oynani kichraytir», «keyingi oynaga o't», «ovozni oshir», «ovozni o'chir»\n"
                    "• Fayllar: «eng yangi videoni top», «Downloads'dan PDF fayllarni top», «tanlangan faylni och»\n"
                    "• Veb: «internetda Python darslarini qidir», «YouTube'da English lessons ni qidir», «kun.uz saytini och»\n"
                    "• Eslatma/vazifa/qayd: «ertaga 16:00 da eslat», «vazifa qo'sh …», «qayd yarat: …», «bugungi vazifalarim»\n"
                    "• Ingliz tili: «ingliz tili darsini boshla», «10 ta A1 lug'at savoli ber», «talaffuzimni tekshir», «tinglash mashqi ber», «'improve' so'zini tarjima qil», «darajani A2 qil», «o'quv progressim»\n"
                    "• Kompyuter: «CPU yuklamasi», «RAM», «disk joyi», «batareya», «internetni tekshir», «kompyuter xususiyatlari»\n"
                    "• Skrinshot/clipboard: «skrinshot ol», «clipboard'ni o'qi», «nusxalangan kodni tushuntir», «nusxalangan matnni qisqartir»\n"
                    "• Media: «pauza», «keyingi qo'shiq», «musiqa papkasini och»\n"
                    "• Interfeys: «sozlamalarni och (ilova)», «sozlamalar panelini yop», «mikrofon holati», «buyruqlarni ko'rsat»\n"
                    "• Suhbat: «Python xatosini tushuntir», «bu gapni o'zbekchaga tarjima qil», «Claude uchun prompt yozishga yordam ber»",
                    "Доступные голосовые команды (говорите, удерживая Пробел):\n"
                    "• Программы: «открой Chrome», «открой VS Code», «открой папку Загрузки», «открой YouTube»\n"
                    "• Окна и звук: «сверни окно», «следующее окно», «громче», «выключи звук»\n"
                    "• Файлы: «найди самое новое видео», «найди PDF в Загрузках», «открой выбранный файл»\n"
                    "• Интернет: «найди в интернете уроки Python», «найди на YouTube English lessons», «открой сайт kun.uz»\n"
                    "• Напоминания, задачи, заметки: «напомни завтра в 16:00», «добавь задачу …», «создай заметку: …», «мои задачи на сегодня»\n"
                    "• Английский: «начни урок английского», «10 вопросов по лексике A1», «проверь произношение», «упражнение на аудирование», «переведи слово “improve”», «уровень A2», «мой прогресс»\n"
                    "• Компьютер: «загрузка процессора», «оперативная память», «место на диске», «батарея», «проверь интернет», «характеристики компьютера»\n"
                    "• Скриншот и буфер: «сделай скриншот», «прочитай буфер обмена», «объясни скопированный код», «перескажи скопированный текст»\n"
                    "• Медиа: «пауза», «следующий трек», «открой папку музыки»\n"
                    "• Интерфейс: «открой настройки приложения», «закрой панель настроек», «состояние микрофона», «покажи команды»\n"
                    "• Разговор: «объясни ошибку Python», «переведи предложение на узбекский», «помоги написать промпт для Claude»",
                    "Available voice commands (hold SPACE and speak):\n"
                    "• Apps: “open Chrome”, “open VS Code”, “open Downloads”, “open YouTube”\n"
                    "• Windows and sound: “minimize this window”, “switch to the next window”, “volume up”, “mute the sound”\n"
                    "• Files: “find my latest video”, “find PDF files in Downloads”, “open the selected file”\n"
                    "• Web: “search the web for Python tutorials”, “open YouTube and search for English lessons”, “open the website kun.uz”\n"
                    "• Reminders, tasks, notes: “remind me tomorrow at 4 PM”, “add a task to …”, “create a note: …”, “what tasks do I have today?”\n"
                    "• English: “start my English lesson”, “ask me ten A1 vocabulary questions”, “test my pronunciation”, “give me a short listening exercise”, “translate the word ‘improve’”, “set my English level to A2”, “show my English progress”\n"
                    "• Computer: “show my CPU usage”, “check available RAM”, “how much disk space is free?”, “battery status”, “check my internet connection”, “show my computer specifications”\n"
                    "• Screenshot and clipboard: “take a screenshot”, “read my clipboard”, “explain the copied Python code”, “summarize the copied text”\n"
                    "• Media: “pause”, “next track”, “open my music folder”\n"
                    "• Interface: “open the app settings”, “close the settings panel”, “show microphone status”, “show available commands”\n"
                    "• Conversation: “explain this Python error”, “translate this sentence into Uzbek”, “help me write a prompt for Claude”"),
    # ---- ingliz tili mashqlari
    "ask.eng.lesson": ("Ingliz tili darsini boshlash (reja va mashqlar)", "Начать урок английского (план и упражнения)", "Start the English lesson (plan and exercises)"),
    "ask.eng.quiz": ("{n} ta {level} lug'at savolini boshlash", "Начать {n} вопросов по лексике ({level})", "Start {n} {level} vocabulary questions"),
    "ask.eng.pron": ("Talaffuz mashqini boshlash", "Начать упражнение на произношение", "Start the pronunciation exercise"),
    "ask.eng.listen": ("Tinglash mashqini boshlash", "Начать упражнение на аудирование", "Start the listening exercise"),
    "ask.eng.tr": ("«{word}» so'zini tarjima qilish", "Перевести слово «{word}»", "Translate the word “{word}”"),
    "ask.eng.level": ("Ingliz tili darajasini {level} ga o'zgartirish", "Изменить уровень английского на {level}", "Change the English level to {level}"),
    "eng.lesson": ("Ingliz tili darsi. Darajangiz: {level}. Bugungi reja: {plan}.\nNimani boshlaymiz? Ayting:\n• «{level} lug'at savollarini ber» — viktorina\n• «talaffuzimni tekshir»\n• «tinglash mashqini ber»\n• «'improve' so'zini tarjima qil»\n• «darajani A2 qil» — qiyinlikni o'zgartirish",
                   "Урок английского. Ваш уровень: {level}. План на сегодня: {plan}.\nС чего начнём? Скажите:\n• «вопросы по лексике {level}» — викторина\n• «проверь произношение»\n• «упражнение на аудирование»\n• «переведи слово “improve”»\n• «уровень A2» — изменить сложность",
                   "English lesson. Your level: {level}. Today's plan: {plan}.\nWhat shall we start? Say:\n• “ask me {level} vocabulary questions” — quiz\n• “test my pronunciation”\n• “give me a listening exercise”\n• “translate the word ‘improve’”\n• “set my level to A2” — change the difficulty"),
    "eng.translate": ("«{w}» — {uz} (o'zbekcha), {ru} (ruscha). Daraja: {lvl}.", "«{w}» — {uz} (узб.), {ru} (рус.). Уровень: {lvl}.", "“{w}” — {uz} (Uzbek), {ru} (Russian). Level: {lvl}."),
    "eng.notfound": ("«{w}» so'zi mening kichik lug'atimda yo'q; AI'dan so'rayman.", "Слова «{w}» нет в моём небольшом словаре; спрошу у ИИ.", "“{w}” is not in my small word list; I will ask the AI."),
    "eng.p.translate": ("Ingliz tilidagi «{w}» so'zini o'zbek va rus tillariga tarjima qiling, qisqa ta'rif va bitta oddiy misol gap bering. Javobni {language} tilida yozing.",
                        "Переведите английское слово «{w}» на узбекский и русский, дайте краткое определение и один простой пример. Ответьте на языке: {language}.",
                        "Translate the English word “{w}” into Uzbek and Russian, give a short definition and one simple example sentence. Answer in {language}."),
    "eng.level.set": ("Daraja {level} ga o'zgartirildi. Keyingi mashqlar shu darajada bo'ladi.", "Уровень изменён на {level}. Следующие упражнения будут этого уровня.",
                      "Level changed to {level}. The next exercises will use it."),
    "eng.level.same": ("Daraja allaqachon {level}.", "Уровень уже {level}.", "The level is already {level}."),
    "eng.level.limit": ("Daraja {level} — bu mening mashqlarimdagi chegara.", "Уровень {level} — это предел моих упражнений.", "{level} is the limit of my exercises."),
    "eng.quiz.start": ("{n} ta savol, daraja {level}. Javob uchun variant raqamini ayting (masalan, «ikki») yoki tarjimaning o'zini. «Bekor» desangiz to'xtayman.",
                       "{n} вопросов, уровень {level}. Назовите номер варианта (например, «два») или сам перевод. Скажите «отмена», чтобы остановиться.",
                       "{n} questions, level {level}. Say the option number (for example “two”) or the translation itself. Say “stop” to end."),
    "eng.q": ("Savol {i}/{n}: «{word}» so'zi nimani anglatadi?", "Вопрос {i}/{n}: что означает слово «{word}»?", "Question {i}/{n}: what does “{word}” mean?"),
    "eng.right": ("To'g'ri!", "Верно!", "Correct!"),
    "eng.wrong": ("Noto'g'ri. «{word}» — {tr}.", "Неверно. «{word}» — {tr}.", "Not quite. “{word}” means {tr}."),
    "eng.unclear": ("Javobni tushunmadim. Variant raqamini ayting (1, 2 yoki 3).", "Не понял ответ. Назовите номер варианта (1, 2 или 3).", "I did not catch that. Say the option number (1, 2 or 3)."),
    "eng.stopped": ("Mashq to'xtatildi.", "Упражнение остановлено.", "The exercise was stopped."),
    "eng.result": ("Natija: {n} tadan {c} ta to'g'ri.", "Результат: {c} из {n}.", "Result: {c} out of {n} correct."),
    "eng.review": ("Takrorlash uchun: {words}.", "Для повторения: {words}.", "To review: {words}."),
    "eng.saved": ("Natija mahalliy tarixga yozildi.", "Результат записан в локальную историю.", "The result was saved to your local history."),
    "eng.added": ("{n} ta so'z «qiyin so'zlar» ro'yxatiga qo'shildi (English Study sahifasida ko'rinadi).", "Слов добавлено в «сложные слова»: {n} (видно на странице English Study).",
                  "{n} word(s) were added to your difficult-words list (visible on the English Study page)."),
    "eng.pron.start": ("Quyidagi gapni ingliz tilida ayting (Space ni bosib turing):\n«{text}»", "Скажите по-английски (удерживая Пробел):\n«{text}»", "Say this sentence in English (hold SPACE):\n“{text}”"),
    "eng.pron.good": ("Yaxshi! Moslik: {pct}%. Men eshitdim: «{heard}».", "Хорошо! Совпадение: {pct}%. Я услышал: «{heard}».", "Good! Match: {pct}%. I heard: “{heard}”."),
    "eng.pron.retry": ("Moslik: {pct}%. Men eshitdim: «{heard}». Tushib qolgan yoki boshqacha so'zlar: {missed}. Yana urinib ko'ring (yoki «bekor»).",
                       "Совпадение: {pct}%. Я услышал: «{heard}». Пропущенные или другие слова: {missed}. Попробуйте ещё раз (или «отмена»).",
                       "Match: {pct}%. I heard: “{heard}”. Missing or different words: {missed}. Try again (or say “stop”)."),
    "eng.pron.end": ("Bugungi urinishlar tugadi. Bu baho nutqni tanish dvigatelining natijasiga asoslangan, shuning uchun taxminiy.",
                     "Попытки закончились. Оценка основана на результате распознавания речи и потому приблизительна.", "No more attempts for now. This score relies on the speech recognizer, so it is only approximate."),
    "eng.pron.note": ("Eslatma: baho nutqni tanish dvigatelining natijasiga asoslangan, shuning uchun taxminiy.", "Примечание: оценка основана на распознавании речи и потому приблизительна.",
                      "Note: the score relies on the speech recognizer, so it is only approximate."),
    "eng.listen.start": ("Qisqa tinglash mashqi. Men gapni bir marta ingliz tilida aytaman; keyin savolga javob bering. «Qaytar» desangiz yana aytaman.",
                         "Короткое упражнение на аудирование. Я произнесу фразу по-английски; затем ответьте на вопрос. Скажите «повтори», чтобы услышать ещё раз.",
                         "A short listening exercise. I will say a sentence in English; then answer the question. Say “repeat” to hear it again."),
    "eng.listen.q": ("Savol: {q}", "Вопрос: {q}", "Question: {q}"),
    "eng.listen.wrong": ("Noto'g'ri. To'g'ri javob: {ans}.", "Неверно. Правильный ответ: {ans}.", "Not quite. The correct answer: {ans}."),
    "eng.listen.said": ("Aytilgan gap: «{text}»", "Прозвучала фраза: «{text}»", "The sentence was: “{text}”"),
    "eng.listen.silent": ("(Ovozli javob o'chirilgan, shuning uchun gap matni:) «{text}»", "(Голосовой вывод выключен, поэтому вот текст фразы:) «{text}»",
                          "(Voice output is off, so here is the sentence as text:) “{text}”"),
    "eng.progress": ("Mashq sessiyalari: {s} ta, savollar: {q}, to'g'ri: {c}.", "Упражнений: {s}, вопросов: {q}, верно: {c}.", "Exercise sessions: {s}, questions: {q}, correct: {c}."),
}
