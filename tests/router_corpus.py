"""Yo'naltiruvchi baholash to'plamlari: (matn, kutilgan kategoriya). G=GENERAL_CONVERSATION Q=QUESTION_ANSWERING C=COMPUTER_COMMAND I=CURRENT_INFORMATION L=CLARIFICATION_REQUIRED
   «I+» — jonli manbasi bor (ilova o'zi javob beradi); «I-» — jonli ma'lumot kerak, manba yo'q (AI'ga «jonli ma'lumot yo'q» ko'rsatmasi bilan boradi)."""
from pyatnitsa import router

SHORT = {"G": router.GENERAL_CONVERSATION, "Q": router.QUESTION_ANSWERING, "C": router.COMPUTER_COMMAND, "I+": router.CURRENT_INFORMATION,
         "I-": router.CURRENT_INFORMATION, "L": router.CLARIFICATION_REQUIRED}


def classify(text: str) -> str:
    r = router.route(text)
    if r.category == router.CURRENT_INFORMATION:
        return "I-" if r.live_unsupported else "I+"
    return {v: k for k, v in SHORT.items() if k not in ("I+", "I-")}[r.category]


def evaluate(corpus):
    ok, bad, safe_ok = 0, [], 0
    for text, want in corpus:
        got = classify(text)
        ok += got == want
        if got != want:
            bad.append((text, want, got))
        # asosiy xavfsizlik chegarasi: buyruq/ma'lumot <-> AI
        to_ai = lambda k: k in ("G", "Q", "I-")  # noqa: E731
        safe_ok += to_ai(got) == to_ai(want)
    return ok, len(corpus), bad, safe_ok


DEV = [
    # ---- foydalanuvchi misollari
    ("Salom, yaxshimisan?", "G"), ("Bugun nima bilan shug'ullansam bo'ladi?", "Q"), ("Python nima?", "Q"), ("Nega osmon ko'k?", "Q"),
    ("Menga ingliz tilini o'rganishda yordam ber.", "Q"), ("Oldingi gapimizni davom ettir.", "G"), ("Uni kim yaratgan?", "Q"), ("Misol ham ber.", "G"),
    ("Google Chrome och", "C"), ("Kalkulyatorni och", "C"), ("Dollar kursi qancha?", "I+"), ("Nega Chrome ochilmayapti?", "Q"), ("Salom", "G"),
    # ---- uz
    ("Hozirgi vaqtni ayt", "I+"), ("Kompyuterim holati qanday?", "I+"), ("RAM qancha band?", "I+"), ("Bugungi ob-havo qanday?", "I+"),
    ("Brauzer nima?", "Q"), ("Internet nima?", "Q"), ("Kompyuter qanday ishlaydi?", "Q"), ("Menga Python haqida gapirib ber", "Q"),
    ("Qanday qilib fayl ochaman?", "Q"), ("Chrome ni qanday ochaman?", "Q"), ("Faylni qanday o'chiraman?", "Q"), ("Kompyuter sekin ishlayapti", "Q"),
    ("Rahmat", "G"), ("Yaxshi, tushunarli", "G"), ("Hayr", "G"), ("Assalomu alaykum", "G"), ("Nima gap?", "G"), ("Chrome", "L"), ("Notepad", "L"),
    ("Bugungi yangiliklar", "I-"), ("Evro kursi qancha?", "I-"), ("Hozirgi prezident kim?", "I-"), ("Bitcoin narxi qancha?", "I-"),
    ("Faylni o'chir", "C"), ("Kompyuterni o'chir", "C"), ("Chrome'ni och va Notepad'ni och", "C"), ("Google'da Python darslarini qidir", "C"), ("Downloads papkasini och", "C"),
    ("Yana bir misol ber", "G"), ("Buni sodda qilib tushuntir", "Q"), ("Ingliz tilida gaplashamizmi?", "Q"),
    # ---- ru
    ("Привет", "G"), ("Привет, как дела?", "G"), ("Спасибо", "G"), ("Что такое Python?", "Q"), ("Почему небо голубое?", "Q"), ("Расскажи про космос", "Q"),
    ("Помоги мне выучить английский", "Q"), ("Почему не открывается Chrome?", "Q"), ("Как открыть Chrome?", "Q"), ("Продолжи", "G"), ("Приведи пример", "G"),
    ("Открой калькулятор", "C"), ("Открой Chrome", "C"), ("Открой папку Загрузки", "C"), ("Покажи курс доллара", "I+"), ("Какая погода?", "I+"),
    ("Покажи новости", "I-"), ("Курс евро сегодня", "I-"), ("Удали файл", "C"), ("Выключи компьютер", "C"), ("Сколько RAM занято?", "I+"), ("Блокнот", "L"),
    # ---- en
    ("Hello", "G"), ("Hi there", "G"), ("Thanks", "G"), ("How are you?", "G"), ("What is Python?", "Q"), ("Why is the sky blue?", "Q"), ("Explain how the internet works", "Q"),
    ("Help me learn English", "Q"), ("Why won't Chrome open?", "Q"), ("How do I open Chrome?", "Q"), ("How do I delete a file?", "Q"), ("Tell me a joke", "Q"),
    ("Continue", "G"), ("Give me an example", "G"), ("Open Chrome", "C"), ("Open calculator", "C"), ("Delete all files", "C"), ("Shut down the computer", "C"),
    ("What time is it?", "I+"), ("Show the dollar rate", "I+"), ("What's the weather?", "I+"), ("Latest news", "I-"), ("Bitcoin price today", "I-"), ("Chrome", "L"),
    # ---- aralash
    ("Salom, как дела?", "G"), ("Python nima, объясни", "Q"), ("Chrome ni открой", "C"), ("Dollar kursini покажи", "I+"), ("Nega Chrome не открывается?", "Q"),
]


# ============================================================================ YANGI TO'PLAM (DEV sozlab bo'lingandan keyin yozilgan; birinchi ishga tushirish — yakuniy baho)
FRESH = [
    # ---- uz: suhbat, maslahat, o'rganish
    ("Kayfiyatim yomon", "G"), ("Sen kimsan?", "Q"), ("Menga maslahat ber", "Q"), ("Bugun nima qilsam ekan?", "Q"), ("Qanday yordam bera olasan?", "Q"),
    ("Rus tilini o'rganmoqchiman", "G"), ("Menga bir she'r o'qib ber", "Q"), ("Kecha film ko'rdim, juda yaxshi ekan", "G"), ("Ha, to'g'ri aytasan", "G"),
    ("Yaxshi tong", "G"), ("Ertaga imtihonim bor", "G"), ("Fotosintez nima?", "Q"), ("Yer Quyosh atrofida qancha vaqtda aylanadi?", "Q"), ("Java va Python farqi nima?", "Q"),
    ("Qaysi dasturlash tilini o'rgansam yaxshi?", "Q"), ("Buni qisqaroq qilib ayt", "G"), ("Davom et", "G"), ("Yana bir bor tushuntirib ber", "Q"),
    # ---- uz: buyruq so'zlari ishtirok etgan savollar (AI'ga borishi kerak)
    ("Chrome nima?", "Q"), ("Kalkulyator qanday ishlaydi?", "Q"), ("Brauzer ochilmasa nima qilaman?", "Q"), ("Notepad bilan Word farqi nima?", "Q"),
    ("Kompyuterni qayta ishga tushirish nima uchun kerak?", "Q"), ("Parolni qanday saqlash kerak?", "Q"), ("O'chirish tugmasi nima?", "Q"), ("Dollar nima?", "Q"),
    ("Dollar kursi nega o'sadi?", "Q"), ("Fayllarni qanday qilib zaxiralash mumkin?", "Q"), ("Google qanday ishlaydi?", "Q"),
    # ---- uz: buyruqlar
    ("Chrome'ni oching, iltimos", "C"), ("Notepadni ochib ber", "C"), ("Documents papkasini och", "C"), ("Google'da ob-havo haqida qidir", "C"), ("Yangi brauzer oynasini och", "C"),
    ("Chrome va kalkulyatorni och", "C"), ("Fayllarimni o'chirib tashla", "C"), ("Kompyuterni qayta yoq", "C"), ("Menga kalkulyator kerak", "L"),
    ("Soat necha?", "I+"), ("Bugun havo qanday?", "I+"), ("Diskda joy qancha?", "I+"), ("Protsessor haroratini ko'rsat", "I+"), ("Dollar necha so'm?", "I+"), ("Kompyuter holatini tekshir", "I+"),
    ("Bugun nima yangilik?", "I-"), ("Dollar kursi", "I+"),
    # ---- ru
    ("Я устал", "G"), ("Спасибо большое", "G"), ("Давай поговорим", "G"), ("Как тебя зовут?", "Q"), ("Расскажи анекдот", "Q"), ("Объясни, как работает интернет", "Q"),
    ("Что делать, если Chrome не открывается?", "Q"), ("Как работает калькулятор?", "Q"), ("В чём разница между Python и Java?", "Q"), ("Зачем нужен антивирус?", "Q"),
    ("Что такое браузер?", "Q"), ("Как удалить файл?", "Q"), ("Продолжай", "G"), ("Ещё пример", "G"),
    ("Запусти Chrome", "C"), ("Открой блокнот", "C"), ("Открой Chrome и калькулятор", "C"), ("Удали историю", "C"), ("Перезагрузи компьютер", "C"),
    ("Сколько времени?", "I+"), ("Проверь процессор", "I+"), ("Покажи состояние компьютера", "I+"), ("Какие программы грузят процессор?", "I+"),
    ("Матч счёт сегодня", "I-"), ("Курс биткоина", "I-"), ("Последние новости", "I-"),
    # ---- en
    ("I'm bored", "G"), ("Thank you so much", "G"), ("Let's practice English", "G"), ("Good morning", "G"), ("Who are you?", "Q"), ("Can you help me with my homework?", "Q"),
    ("What is the capital of France?", "Q"), ("How does a calculator work?", "Q"), ("What's the difference between RAM and a hard drive?", "Q"), ("Why does my computer get slow?", "Q"),
    ("How can I delete files safely?", "Q"), ("Why is Chrome not opening?", "Q"), ("Tell me about the moon", "Q"), ("Explain recursion with an example", "Q"),
    ("Can you open Chrome?", "C"), ("Please open the calculator", "C"), ("Delete my files", "C"), ("Restart my computer", "C"), ("Open notepad and chrome", "C"),
    ("Check my CPU usage", "I+"), ("What's the dollar rate?", "I+"), ("Tell me the time", "I+"), ("Show disk space", "I+"),
    ("Latest iPhone price", "I-"), ("Who won the match yesterday?", "I-"), ("Today's news", "I-"),
    # ---- aralash
    ("Salom, помоги мне", "G"), ("Python nima, explain please", "Q"), ("Chrome ni запусти", "C"), ("Kompyuterimni проверь", "I+"), ("Почему Chrome ochilmayapti?", "Q"),
    ("Thanks, rahmat", "G"), ("Menga help kerak", "G"),
]
