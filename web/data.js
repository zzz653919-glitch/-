/* Kurs ma'lumotlari. So'z qatori: inglizcha|tarjimalar(;)|emoji|inglizcha gap|o'zbekcha gap
   MUHIM: so'zlarning tartibini o'zgartirmang — progress so'z identifikatoriga (daraja.mavzu.indeks) bog'langan. Yangi so'zlarni oxiriga qo'shing. */
(function (TY) {
  var L = [];
  function lvl(id, title, sub, color, topics) { L.push({ id: id, title: title, sub: sub, color: color, topics: topics }); }
  function t(title, icon, tip, words) { return { title: title, icon: icon, tip: tip, words: words }; }

  lvl('A1', 'Beginner', 'A1 · Boshlang\'ich', '#22c55e', [
    t('Salomlashish', '💬', "Inglizcha salomlashish: 'Hello' — kun bo'yi, 'Good morning' — ertalab, 'Good night' — uxlashdan oldin. 'Please' va 'sorry' — muloqotdagi eng muhim so'zlar.", `
hello|salom|👋|Hello, my name is Ali.|Salom, mening ismim Ali.
goodbye|xayr;xayr-xo'sh||Goodbye, see you tomorrow.|Xayr, ertagacha ko'rishamiz.
please|iltimos;marhamat||Please sit down.|Iltimos, o'tiring.
sorry|kechirasiz;uzr;afsus||I am sorry I am late.|Kechikkanim uchun uzr.
friend|do'st;o'rtoq||She is my best friend.|U mening eng yaxshi do'stim.
name|ism;nom|📛|What is your name?|Ismingiz nima?
morning|ertalab;tong|🌅|Good morning, teacher.|Xayrli tong, ustoz.
night|tun;kecha|🌙|Good night, mom.|Xayrli tun, onajon.`),
    t('Oila', '👪', "'My' — mening: my mother, my father. Ingliz tilida egalik olmoshi ot oldidan keladi. 'Boy' va 'girl' — bola, 'baby' — chaqaloq.", `
mother|ona;oyi|👩|My mother cooks every day.|Onam har kuni ovqat pishiradi.
father|ota;dada|👨|My father works in a bank.|Otam bankda ishlaydi.
brother|aka;uka;birodar||My brother plays football.|Akam futbol o'ynaydi.
sister|opa;singil||My sister likes music.|Opam musiqani yaxshi ko'radi.
family|oila|👪|I love my family.|Men oilamni yaxshi ko'raman.
baby|chaqaloq;go'dak|👶|The baby is sleeping.|Chaqaloq uxlayapti.
boy|o'g'il bola;bola|👦|The boy has a ball.|Bolaning to'pi bor.
girl|qiz bola;qiz|👧|The girl reads a book.|Qiz kitob o'qiyapti.`),
    t('Ovqat', '🍎', "Sanaladigan otlar oldidan 'a/an' ishlatiladi: an apple, an egg. Sanalmaydigan otlar (water, milk, bread, rice) oldidan ishlatilmaydi.", `
apple|olma|🍎|I eat an apple every day.|Men har kuni olma yeyman.
bread|non|🍞|We buy fresh bread.|Biz yangi non sotib olamiz.
water|suv|💧|Drink more water.|Ko'proq suv iching.
milk|sut|🥛|Milk is good for children.|Sut bolalar uchun foydali.
rice|guruch;osh|🍚|We cook rice for dinner.|Biz kechki ovqatga guruch pishiramiz.
egg|tuxum|🥚|I eat one egg for breakfast.|Men nonushtada bitta tuxum yeyman.
cheese|pishloq|🧀|She likes cheese.|U pishloqni yaxshi ko'radi.
meat|go'sht|🥩|He does not eat meat.|U go'sht yemaydi.`),
    t('Hayvonlar', '🐶', "Ko'plik: ko'p otlarga -s qo'shiladi: cat → cats. Hayvonlar haqida: 'I have a dog' — mening itim bor.", `
cat|mushuk|🐱|The cat sleeps on the sofa.|Mushuk divanda uxlaydi.
dog|it|🐶|My dog is very friendly.|Mening itim juda xushmuomala.
bird|qush|🐦|A bird is singing in the tree.|Daraxtda qush kuylayapti.
fish|baliq|🐟|The fish swims in the river.|Baliq daryoda suzadi.
horse|ot|🐴|He rides a horse.|U ot minadi.
cow|sigir|🐄|The cow gives us milk.|Sigir bizga sut beradi.
lion|sher|🦁|The lion is a strong animal.|Sher kuchli hayvon.
rabbit|quyon|🐰|The rabbit eats a carrot.|Quyon sabzi yeydi.`)
  ]);

  lvl('A2', 'Elementary', 'A2 · Boshlang\'ich+', '#06b6d4', [
    t('Uy', '🏠', "Joy predloglari: in (ichida), on (ustida), under (tagida). 'The book is on the table' — kitob stol ustida.", `
kitchen|oshxona|🍳|My mother is in the kitchen.|Onam oshxonada.
bed|karavot;to'shak|🛏️|The bed is very comfortable.|Karavot juda qulay.
window|deraza|🪟|Please open the window.|Iltimos, derazani oching.
door|eshik|🚪|Close the door, please.|Iltimos, eshikni yoping.
table|stol||The keys are on the table.|Kalitlar stol ustida.
chair|stul|🪑|There is a chair near the wall.|Devor yonida stul bor.
garden|bog';bog'cha|🌳|We have a small garden.|Bizning kichik bog'imiz bor.
room|xona||My room is on the second floor.|Mening xonam ikkinchi qavatda.`),
    t('Sayohat', '✈️', "Sayohatda foydali so'zlar. 'I want to buy a ticket' — chipta sotib olmoqchiman. 'Want to + fe'l' — xohlamoq.", `
ticket|chipta|🎫|I want to buy a ticket.|Men chipta sotib olmoqchiman.
airport|aeroport|✈️|The airport is far from the city.|Aeroport shahardan uzoqda.
train|poyezd|🚆|The train leaves at nine.|Poyezd soat to'qqizda jo'naydi.
hotel|mehmonxona|🏨|We stay at a cheap hotel.|Biz arzon mehmonxonada qolamiz.
passport|pasport|🛂|Do not forget your passport.|Pasportingizni unutmang.
luggage|yuk;bagaj|🧳|My luggage is very heavy.|Yukim juda og'ir.
map|xarita|🗺️|Look at the map, please.|Iltimos, xaritaga qarang.
journey|sayohat;safar|🧭|The journey took five hours.|Safar besh soat davom etdi.`),
    t('Kasblar', '💼', "'He is a doctor' — kasbni aytishda 'a/an' ishlatiladi. Unli tovush bilan boshlansa 'an': an engineer.", `
teacher|o'qituvchi;ustoz;muallim||Our teacher is kind.|Ustozimiz mehribon.
doctor|shifokor;doktor;vrach|👩‍⚕️|The doctor helps sick people.|Shifokor kasal odamlarga yordam beradi.
nurse|hamshira|🩺|The nurse works at night.|Hamshira kechasi ishlaydi.
driver|haydovchi||The driver is waiting outside.|Haydovchi tashqarida kutyapti.
farmer|fermer;dehqon|🧑‍🌾|The farmer grows wheat.|Dehqon bug'doy yetishtiradi.
engineer|muhandis||My uncle is an engineer.|Amakim muhandis.
office|ofis;idora|🏢|I go to the office by bus.|Men ofisga avtobusda boraman.
salary|maosh;oylik||His salary is good.|Uning maoshi yaxshi.`),
    t('Ob-havo', '⛅', "Ob-havo haqida: 'It is sunny' — havo quyoshli. 'It' bu yerda rasmiy ega, tarjima qilinmaydi.", `
sunny|quyoshli|☀️|It is sunny today.|Bugun havo quyoshli.
rainy|yomg'irli|🌧️|Tomorrow will be rainy.|Ertaga yomg'irli bo'ladi.
cloudy|bulutli|☁️|It is cloudy in the morning.|Ertalab havo bulutli.
windy|shamolli|💨|It is very windy today.|Bugun juda shamolli.
snow|qor|❄️|Children play in the snow.|Bolalar qorda o'ynaydi.
winter|qish|⛄|Winter is my favourite season.|Qish mening sevimli faslim.
summer|yoz|🏖️|We go to the sea in summer.|Biz yozda dengizga boramiz.
cold|sovuq|🥶|The water is too cold.|Suv juda sovuq.`)
  ]);

  lvl('B1', 'Intermediate', 'B1 · O\'rta', '#3b82f6', [
    t('Salomatlik', '🩺', "Maslahat berish: 'You should + fe'l' — siz ... qilishingiz kerak. 'You should take medicine' — dori ichishingiz kerak.", `
headache|bosh og'rig'i||I have a terrible headache.|Mening boshim qattiq og'riyapti.
medicine|dori;tibbiyot|💊|You should take this medicine twice a day.|Bu dorini kuniga ikki marta ichishingiz kerak.
healthy|sog'lom;foydali||Fruit is healthy food.|Mevalar foydali ovqat.
exercise|mashq;jismoniy mashq|🏃|Regular exercise keeps you fit.|Muntazam mashq sizni sog'lom saqlaydi.
injury|jarohat;shikast||He missed the match because of an injury.|U jarohat tufayli o'yinni o'tkazib yubordi.
patient|bemor||The patient needs rest.|Bemorga dam kerak.
symptom|alomat;belgi||Fever is a common symptom.|Isitma keng tarqalgan alomat.
recover|tuzalmoq;sog'ayib ketmoq||She will recover soon.|U tez orada tuzaladi.`),
    t('Texnologiya', '💻', "Present Perfect: 'I have downloaded the file' — faylni yuklab oldim (natija hozir muhim). have/has + fe'lning 3-shakli.", `
software|dasturiy ta'minot;dastur||This software is easy to use.|Bu dastur foydalanish uchun oson.
website|veb-sayt;sayt|🌐|I found it on the website.|Men buni veb-saytda topdim.
password|parol|🔑|Never share your password.|Parolingizni hech kimga bermang.
download|yuklab olmoq;yuklamoq|⬇️|I want to download this video.|Men bu videoni yuklab olmoqchiman.
battery|batareya|🔋|My phone battery is dead.|Telefonimning batareyasi tugagan.
screen|ekran||The screen is too bright.|Ekran juda yorqin.
device|qurilma||This device is very small.|Bu qurilma juda kichik.
internet|internet||The internet is slow today.|Bugun internet sekin.`),
    t('Shahar hayoti', '🏙️', "Qiyosiy daraja: 'bigger than', 'more crowded than'. Uzun sifatlar oldidan 'more' qo'yiladi.", `
traffic|tirbandlik;transport harakati|🚦|The traffic is terrible in the morning.|Ertalab tirbandlik dahshatli.
neighbourhood|mahalla;qo'shnilar||I like my neighbourhood.|Men mahallamni yaxshi ko'raman.
public|jamoat;ommaviy||Public transport is cheap here.|Bu yerda jamoat transporti arzon.
crowded|gavjum;odam ko'p||The market is crowded on Sundays.|Bozor yakshanba kunlari gavjum.
pavement|yo'lak;trotuar||Walk on the pavement.|Yo'lakdan yuring.
tourist|sayyoh;turist|📸|Every tourist visits the museum.|Har bir sayyoh muzeyga boradi.
museum|muzey|🏛️|The museum opens at ten.|Muzey soat o'nda ochiladi.
suburb|shahar atrofi;chekka||They live in a quiet suburb.|Ular tinch shahar chekkasida yashaydi.`),
    t('Ta\'lim', '🎓', "Maqsadni ifodalash: 'I study to pass the exam'. 'To + fe'l' maqsadni bildiradi.", `
knowledge|bilim||Knowledge is power.|Bilim — kuch.
subject|fan;mavzu||Math is my favourite subject.|Matematika mening sevimli fanim.
exam|imtihon|📝|The exam starts at nine.|Imtihon soat to'qqizda boshlanadi.
lecture|ma'ruza||The lecture was very interesting.|Ma'ruza juda qiziqarli edi.
degree|daraja;diplom||She has a degree in law.|Uning huquq bo'yicha diplomi bor.
homework|uy vazifasi|📚|Did you finish your homework?|Uy vazifangizni tugatdingizmi?
deadline|muddat;oxirgi muddat||The deadline is on Friday.|Oxirgi muddat juma kuni.
research|tadqiqot;izlanish||Scientists do research in the lab.|Olimlar laboratoriyada tadqiqot olib boradi.`)
  ]);

  lvl('B2', 'Upper-Intermediate', 'B2 · O\'rta+', '#8b5cf6', [
    t('Ish va karyera', '🧑‍💼', "Rasmiy yozishmada: 'I am writing to apply for the position'. Ish suhbatida 'experience' sanalmaydigan ot: much experience.", `
employee|xodim;ishchi||Every employee gets a bonus.|Har bir xodim mukofot oladi.
colleague|hamkasb||My colleague helped me.|Hamkasbim menga yordam berdi.
manager|menejer;boshliq||The manager called a meeting.|Menejer yig'ilish chaqirdi.
promotion|lavozim ko'tarilishi;ko'tarilish||She got a promotion last year.|U o'tgan yili lavozimga ko'tarildi.
resign|ishdan ketmoq;iste'foga chiqmoq||He decided to resign.|U iste'foga chiqishga qaror qildi.
experience|tajriba||We need someone with experience.|Bizga tajribali odam kerak.
application|ariza;ilova||I sent my application yesterday.|Men arizamni kecha yubordim.
interview|suhbat;intervyu||The interview went well.|Suhbat yaxshi o'tdi.`),
    t('Atrof-muhit', '🌍', "Passiv: 'Plastic is recycled' — plastik qayta ishlanadi. be + fe'lning 3-shakli.", `
pollution|ifloslanish||Air pollution is a serious problem.|Havo ifloslanishi jiddiy muammo.
climate|iqlim||The climate is getting warmer.|Iqlim isib bormoqda.
recycle|qayta ishlamoq|♻️|We should recycle paper and glass.|Biz qog'oz va shishani qayta ishlashimiz kerak.
environment|atrof-muhit;muhit||We must protect the environment.|Biz atrof-muhitni asrashimiz kerak.
extinct|yo'q bo'lib ketgan||Dinosaurs became extinct long ago.|Dinozavrlar uzoq vaqt oldin qirilib ketgan.
resource|resurs;boylik||Water is a valuable resource.|Suv qimmatli resurs.
wildlife|yovvoyi tabiat||The park protects local wildlife.|Park mahalliy yovvoyi tabiatni himoya qiladi.
landscape|manzara;landshaft||The landscape is beautiful here.|Bu yerda manzara go'zal.`),
    t('Fikr bildirish', '🗣️', "Fikr bildirish: 'In my opinion...', 'I agree with...', 'I prefer tea to coffee'. Kelishmaslik: 'I'm afraid I disagree'.", `
opinion|fikr;nuqtai nazar||In my opinion, he is right.|Mening fikrimcha, u haq.
argue|bahslashmoq;da'vo qilmoq||They argue about everything.|Ular hamma narsa haqida bahslashadi.
agree|rozi bo'lmoq;kelishmoq||I agree with you completely.|Men siz bilan to'liq roziman.
evidence|dalil;isbot||There is no evidence for this.|Buning dalili yo'q.
conclusion|xulosa||What is your conclusion?|Sizning xulosangiz qanday?
suggest|taklif qilmoq;maslahat bermoq||I suggest we start now.|Men hozir boshlashni taklif qilaman.
doubt|shubha;shubhalanmoq||I doubt that he will come.|Uning kelishiga shubhalanaman.
prefer|afzal ko'rmoq;ma'qul ko'rmoq||I prefer tea to coffee.|Men choyni qahvadan afzal ko'raman.`),
    t('Pul va moliya', '💰', "Shart gap: 'If I had more money, I would invest.' (2-tur shart). Pul so'zlari: income — kirim, expense — chiqim.", `
income|daromad;kirim||Her income is quite high.|Uning daromadi ancha yuqori.
budget|byudjet||We have a small budget.|Bizning byudjetimiz kichik.
expense|xarajat;chiqim||Rent is our biggest expense.|Ijara bizning eng katta xarajatimiz.
savings|jamg'arma;omonat||He spent all his savings.|U barcha jamg'armasini sarfladi.
debt|qarz||She is trying to pay off her debt.|U qarzini to'lashga harakat qilyapti.
invest|sarmoya kiritmoq;investitsiya qilmoq||It is wise to invest early.|Erta sarmoya kiritish aqllilik.
afford|qurbi yetmoq;imkoni bo'lmoq||I cannot afford a new car.|Yangi mashinaga qurbim yetmaydi.
profit|foyda;daromad||The company made a big profit.|Kompaniya katta foyda ko'rdi.`)
  ]);

  lvl('C1', 'Advanced', 'C1 · Ilg\'or', '#f97316', [
    t('Murakkab sifatlar', '🧠', "C1 darajasida aniq va nozik ma'noli sifatlar kerak: 'inevitable' — muqarrar, 'meticulous' — juda sinchkov.", `
ambiguous|noaniq;ikki ma'noli||The ending of the film is ambiguous.|Filmning yakuni noaniq.
inevitable|muqarrar;oldini olib bo'lmaydigan||Change is inevitable.|O'zgarish muqarrar.
reluctant|istamaydigan;ikkilanayotgan||He was reluctant to speak.|U gapirishni istamasdi.
comprehensive|keng qamrovli;to'liq||We need a comprehensive plan.|Bizga keng qamrovli reja kerak.
substantial|sezilarli;katta||There was a substantial increase in sales.|Sotuvda sezilarli o'sish bo'ldi.
controversial|munozarali;bahsli||It is a controversial decision.|Bu munozarali qaror.
meticulous|sinchkov;puxta||She is meticulous about details.|U tafsilotlarga juda sinchkov.
profound|chuqur;teran||The book had a profound effect on me.|Kitob menga chuqur ta'sir qildi.`),
    t('Kuchli fe\'llar', '⚡', "Rasmiy yozuvda oddiy fe'llar o'rniga aniqroq fe'llar ishlatiladi: make worse → undermine, improve → enhance.", `
undermine|susaytirmoq;zaiflashtirmoq||Constant criticism can undermine confidence.|Doimiy tanqid ishonchni susaytirishi mumkin.
enhance|yaxshilamoq;oshirmoq||Exercise can enhance your memory.|Mashq xotirangizni yaxshilashi mumkin.
advocate|yoqlab chiqmoq;targ'ib qilmoq||Many people advocate equal rights.|Ko'pchilik teng huquqlarni yoqlab chiqadi.
acknowledge|tan olmoq;e'tirof etmoq||I acknowledge my mistake.|Men xatomni tan olaman.
accomplish|erishmoq;bajarmoq||We want to accomplish our goal.|Biz maqsadimizga erishmoqchimiz.
hinder|to'sqinlik qilmoq||Bad weather can hinder the rescue.|Yomon ob-havo qutqaruvga to'sqinlik qilishi mumkin.
mitigate|yumshatmoq;kamaytirmoq||Trees mitigate the effects of heat.|Daraxtlar issiqlik ta'sirini yumshatadi.
scrutinize|sinchiklab o'rganmoq;tekshirmoq||Auditors scrutinize every report.|Auditorlar har bir hisobotni sinchiklab tekshiradi.`),
    t('Jamiyat', '🏛️', "Ijtimoiy mavzularda abstrakt otlar ko'p: inequality, justice, welfare. Ular odatda sanalmaydi.", `
inequality|tengsizlik||Income inequality is growing.|Daromad tengsizligi o'sib bormoqda.
justice|adolat;sudlov||Everyone deserves justice.|Har kim adolatga loyiq.
welfare|farovonlik;ijtimoiy ta'minot||The government supports public welfare.|Hukumat jamoat farovonligini qo'llab-quvvatlaydi.
immigrant|muhojir;ko'chib kelgan||Each immigrant works very hard.|Har bir muhojir juda qattiq ishlaydi.
legislation|qonunchilik;qonunlar||New legislation was introduced.|Yangi qonunchilik kiritildi.
diversity|xilma-xillik||Diversity makes teams stronger.|Xilma-xillik jamoalarni kuchliroq qiladi.
authority|hokimiyat;vakolat||The local authority fixed the road.|Mahalliy hokimiyat yo'lni tuzatdi.
privilege|imtiyoz||Education is a privilege for many.|Ko'pchilik uchun ta'lim — imtiyoz.`),
    t('Fan va innovatsiya', '🔬', "Ilmiy uslub: 'The results suggest that...' — natijalar shuni ko'rsatadiki... Ishonchsizlik: may, might, could.", `
breakthrough|katta yutuq;burilish||Scientists announced a major breakthrough.|Olimlar katta yutuq haqida e'lon qildi.
innovation|yangilik;innovatsiya||Innovation drives economic growth.|Innovatsiya iqtisodiy o'sishni harakatga keltiradi.
hypothesis|gipoteza;faraz||The experiment confirmed the hypothesis.|Tajriba gipotezani tasdiqladi.
phenomenon|hodisa||Lightning is a natural phenomenon.|Chaqmoq — tabiiy hodisa.
sophisticated|murakkab;takomillashgan||It is a sophisticated machine.|Bu murakkab mashina.
outcome|natija;oqibat||The outcome was surprising.|Natija ajablanarli bo'ldi.
implement|joriy qilmoq;amalga oshirmoq||They will implement the plan next month.|Ular rejani keyingi oy joriy qiladi.
strategy|strategiya||We need a new marketing strategy.|Bizga yangi marketing strategiyasi kerak.`)
  ]);

  lvl('IELTS', 'IELTS tayyorgarligi', 'IELTS · Akademik', '#e11d48', [
    t('Grafik tavsifi', '📈', "Writing Task 1: grafikdagi o'zgarishni tasvirlash. 'The figure rose sharply' / 'remained steady'. Aniq raqam bo'lmasa 'approximately' ishlating.", `
fluctuate|o'zgarib turmoq;tebranmoq||Prices fluctuate during the year.|Narxlar yil davomida o'zgarib turadi.
decline|kamaymoq;pasaymoq||Sales began to decline in May.|Sotuv may oyida kamaya boshladi.
steady|barqaror;bir maromdagi||The figure remained steady.|Ko'rsatkich barqaror qoldi.
peak|cho'qqi;eng yuqori nuqta||Sales reached a peak in July.|Sotuv iyul oyida cho'qqiga chiqdi.
significant|sezilarli;muhim||There was a significant rise in 2020.|2020-yilda sezilarli o'sish bo'ldi.
proportion|ulush;nisbat||A large proportion of students passed.|Talabalarning katta ulushi o'tdi.
approximately|taxminan||Approximately half of the people agreed.|Odamlarning taxminan yarmi rozi bo'ldi.
trend|tendensiya;yo'nalish||The overall trend is upward.|Umumiy tendensiya yuqoriga.`),
    t('Essay bog\'lovchilari', '🔗', "Writing Task 2'da fikrlarni bog'lash band (Coherence) uchun muhim. Qarama-qarshilik: however, nevertheless, whereas. Natija: therefore, consequently.", `
moreover|bundan tashqari;qolaversa||Moreover, it saves a lot of time.|Bundan tashqari, bu juda ko'p vaqtni tejaydi.
however|biroq;lekin||However, there are some disadvantages.|Biroq, ba'zi kamchiliklar bor.
therefore|shuning uchun;demak||Therefore, schools should change.|Shuning uchun maktablar o'zgarishi kerak.
furthermore|shuningdek;yana||Furthermore, it is cheap.|Shuningdek, bu arzon.
nevertheless|shunga qaramay||Nevertheless, many people disagree.|Shunga qaramay, ko'p odamlar rozi emas.
whereas|holbuki;aksincha||Cities are noisy, whereas villages are quiet.|Shaharlar shovqinli, holbuki qishloqlar tinch.
consequently|natijada||Consequently, prices went up.|Natijada narxlar oshdi.
although|garchi;-sa ham||Although it is expensive, many buy it.|Garchi qimmat bo'lsa ham, ko'pchilik sotib oladi.`),
    t('Ta\'lim va ish', '🎒', "Speaking Part 2 va Task 2 mavzulari: ta'lim va mehnat bozori. 'Vocational training' — kasbiy ta'lim.", `
curriculum|o'quv dasturi||The curriculum includes science and art.|O'quv dasturi fan va san'atni o'z ichiga oladi.
tuition|ta'lim to'lovi;dars||Tuition fees are rising every year.|Ta'lim to'lovlari har yili oshmoqda.
vocational|kasbiy;kasb-hunar||Vocational training prepares students for work.|Kasbiy ta'lim talabalarni ishga tayyorlaydi.
graduate|bitiruvchi;bitirmoq||She will graduate in June.|U iyun oyida bitiradi.
literacy|savodxonlik||Literacy rates have improved.|Savodxonlik darajasi yaxshilandi.
qualification|malaka;diplom||You need a teaching qualification.|Sizga o'qituvchilik malakasi kerak.
enrol|o'qishga yozilmoq;ro'yxatdan o'tmoq||He wants to enrol in a course.|U kursga yozilmoqchi.
workforce|ishchi kuchi||The workforce is getting older.|Ishchi kuchi qarib bormoqda.`),
    t('Sog\'liq va ekologiya', '🌱', "Reading va Listening'da ko'p uchraydi. 'Renewable energy' — qayta tiklanadigan energiya, 'carbon emissions' — uglerod chiqindilari.", `
sustainable|barqaror;davomli||We need sustainable energy.|Bizga barqaror energiya kerak.
emission|chiqindi gaz;emissiya||Factories reduce carbon emission.|Zavodlar uglerod chiqindisini kamaytiradi.
deforestation|o'rmonlarning kesilishi||Deforestation destroys habitats.|O'rmonlarning kesilishi yashash joylarini yo'q qiladi.
obesity|semizlik||Obesity is increasing among children.|Bolalar orasida semizlik ko'paymoqda.
epidemic|epidemiya||The epidemic spread quickly.|Epidemiya tez tarqaldi.
nutrition|ovqatlanish;oziqlanish||Good nutrition is important.|To'g'ri ovqatlanish muhim.
awareness|xabardorlik;anglash||Public awareness is growing.|Jamoatchilik xabardorligi oshmoqda.
renewable|qayta tiklanadigan||Solar power is renewable energy.|Quyosh quvvati — qayta tiklanadigan energiya.`)
  ]);

  // Matnni tuzilmaga aylantirish; id = daraja.mavzu.indeks (barqaror)
  L.forEach(function (lv, li) {
    lv.topics.forEach(function (tp, ti) {
      tp.words = tp.words.trim().split('\n').map(function (line, wi) {
        var p = line.split('|');
        return { id: li + '.' + ti + '.' + wi, en: p[0].trim(), uz: p[1].split(';').map(function (s) { return s.trim(); }),
                 emoji: (p[2] || '').trim(), sent: p[3].trim(), sentUz: p[4].trim() };
      });
    });
  });
  TY.baseLevels = JSON.parse(JSON.stringify(L));   // admin o'zgartirishlari shu asosga qo'llanadi
  TY.MIN_WORDS = 4;                                  // mavzu darsi bo'lishi uchun kamida shuncha ko'rinadigan so'z

  // Indekslar va tugunlar (LEVELS o'zgarganda qayta chaqiriladi)
  TY.reindex = function () {
    var LV = TY.LEVELS;
    TY.NODES = []; TY.nodeById = {}; TY.wordById = {}; TY.allWords = [];
    LV.forEach(function (lv, li) {
      lv.index = li; lv.nodes = [];
      lv.topics.forEach(function (tp, ti) {
        tp.id = 'L' + li + 'T' + ti;
        tp.words.forEach(function (w) { w.level = li; w.topic = ti; if (!w.hidden) { TY.wordById[w.id] = w; TY.allWords.push(w); } });
        if (tp.words.filter(function (w) { return !w.hidden; }).length >= TY.MIN_WORDS) lv.nodes.push({ id: tp.id, kind: 'lesson', level: li, topic: ti, title: tp.title, icon: tp.icon });
      });
      lv.nodes.push({ id: 'L' + li + 'R', kind: 'review', level: li, title: 'Takrorlash', icon: '🔁' });
      lv.nodes.push({ id: 'L' + li + 'X', kind: 'test', level: li, title: 'Sinov', icon: '🏆' });
      lv.nodes.forEach(function (n) { n.order = TY.NODES.length; TY.NODES.push(n); TY.nodeById[n.id] = n; });
    });
  };
  TY.LEVELS = JSON.parse(JSON.stringify(L));
  TY.reindex();
})(typeof window !== 'undefined' ? (window.TY = window.TY || {}) : (globalThis.TY = globalThis.TY || {}));
