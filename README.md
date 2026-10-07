## 📜 Лицензия

Как получится. Используйте на свой страх и риск.

patch_for_60sec_unlock 

# Lime Gen3 — полное отвязывание от IoT/доп-контроллеров

> Решение для владельцев самокатов Lime Gen3 (STM32F103), желающих **полностью отказаться от IoT-модуля, эмуляторов и любых внешних доп-контроллеров**.  
> Цель — не красота и не «дисплей со скоростью», а **простота, безотказность и минимум железа**.

---

## ⚠️ Дисклеймер

Автор **не является профессиональным разработчиком** (слабо в коде, ассемблере, программировании). Всё делалось методом проб, ошибок и с помощью ИИ.  
Уже **спалено 2 × ESP32**.  
Принципиально **не хочется тратить деньги** на этот самокат.  
Релиз «как есть» (as-is). Если у вас есть опыт — pull request'ы приветствуются.

Огромное спасибо [Pikokosan/Lime_Gen3_IoT_Replacement](https://github.com/Pikokosan/Lime_Gen3_IoT_Replacement) — полгода езды на этом решении, единственное полностью рабочее.

---

## 🎯 Что уже достигнуто

- **Unlock при пробуждении** без IoT и без эмулятора.
- Используется сигнал `lockctrl` (вход, который нужно **подтянуть на HIGH**).
- Подача HIGH через **большое сопротивление** (если не использовать понижающий преобразователь на 12 В).

---

## 🕒 Поведение (уточнённое)

### Основной рабочий цикл

| Шаг | Действие | Результат |
|---|---|---|
| 1 | Кратковременно **+2 сек** на (HIGH) `lockctrl` при условии состояния `sleep` и `lock` | Самокат заводится, едет |
| 2 | Снятие + с `lockctrl` pin (LOW) | Запускается **60-секундный таймер** (ни от чего не зависящий) переход в `sleep` |
| 3 | По истечении **60 сек** | Газ перестаёт реагировать (lock) независимо от `lockctrl` pin HIGH или LOW на нем, свет ещё горит 2сек если `lockctrl` был low сразу после начала рабочего цикла |
| 4 | Ещё через **2–3 сек** | Наступает **sleep** & **lock** — свет гаснет |
| 5 | Только после **sleep** & **lock** | Повторная подача + (HIGH) `lockctrl` pin >=2сек запускает **новый рабочий цикл** — снова можно ехать |

### Ключевой нюанс

> **Пока контроллер не уснул (свет горит) — повторная подача + на `lockctrl` только сбрасывает 60-секундный таймаут. Свет остаётся, но движения нет.**  
> Полноценно запустить рабочий цикл и поехать можно **только после того, как самокат уснул и потушил свет**.

### Что сбрасывает таймер

- **Полное обесточивание контроллера.**
- **Reset по 7 pin STM32F103** (замыкание на GND).

> Актуальная логика: 60-секундный таймаут стартует **после снятия +** с `lockctrl` pin (он получает флаг `LOW`) и **не зависит** от состояния lock/unlock. **Sleep** наступает  **после окончания 60-секундного цикла при статусе **LOW** `lockctrl` pin  .** Пока sleep не наступил — новый рабочий цикл не запустить, только сбросить контроллер.

---

## 🔧 Текущая реализация (временная но рабочая)

- HIGH **постоянно** висит на `lockctrl` pin (HIGH).
- На кнопку выведен RST **7 pin STM32F103** → замыкание на GND = **reset** контроллера.
- При блокировке → кнопка → перезапуск → **unlock быстрее**, чем ждать 3сек после рабочего цикла пока не уйдёт в sleep.

Это быстрее, чем ждать sleep после 60-секундного цикла.  
Можно также использовать:
- автомобильное реле,
- преобразователь на 12 В,
- иные способы ресета контроллера.

Раньше пробовал вариант с кнопкой + конденсатором + резистором — касание менее 0.2 сек HIGH <=3сек для unlock. Но если не выждать HIGH >2сек — получаешь 60-секундный таймаут со **светом, но без реакции на газ**.  
**Вывод 7 pin — отзывается быстрее.**

---

## 🧠 Что под капотом

- MCU: **STM32F103**
- Вход `lockctrl` — управляющий сигнал блокировки.
- Далее алгоритм **разворачивается в RAM**, и как я понимаю по реверсу дампа найти его не так просто.

---

## 🎯 Хотелки (TODO / Roadmap)

- [ ] Найти и отключить логику ожидания HB b других условий для предотвращения LOCK
- [ ] Расковырять таблицы лимитов по **скорости** и **токам**.
- [ ] подвинуть **start** с 3 км/ч на 0 км/ч
- [ ] Настройки, приближенные к кастомным прошивкам.

---

## 🛠️ Инструменты

- **ST-Link V2**
- Прошивка через **Android-приложение** — удобно для тестов патченных прошивок.

---

## 🤝 Помощь

Любая помощь приветствуется:
- найти места в прошивке, отвечающие за таймауты,
- понять, где разворачивается RAM-алгоритм,
- таблицы лимитов скорости/тока,
- zero-start.

---

## См. также

- [Pikokosan/Lime_Gen3_IoT_Replacement](https://github.com/Pikokosan/Lime_Gen3_IoT_Replacement) — полностью рабочее решение с IoT-эмуляцией.
Lime Scooter Reversing 
=======================
[![irc badge](https://img.shields.io/badge/irc-freenode/%23lime-brightgreen.png)](
http://webchat.freenode.net?channels=%23lime&uio=d4)



## Description

The purpose of this repository is to create a source/central point of truth for all things Lime. 

Please collaborate and share any information you may have, all pull requests are highly encouraged, let's build a database thats informative, helpful and most of all semi-legal.

--------

### Scooters
| Photo                                         | Manufacturer  | Model           | Manual     | Notes     |  
|  --                                           | ---           | ---             | ---        | --        | 
|  ![noidea](https://i.imgur.com/ZlH30AJ.jpg)   | ?             | ?               | N/A        | Without display, flat rear fender/brake; No longer deployed(?); Gen 1
|  ![okai](https://i.imgur.com/NzvMlJd.png)     | Okai          | Custom(?)       | N/A        | "Lime recalled all the scooters made by Okai in its fleet worldwide."; Flat read fender/brake; Gen 2  
|  ![ES2](https://i.imgur.com/73wa8GJ.jpg)      | Segway        | Kickscooter ES2 | http://www.segway.com/media/2272/25612-00001_aa-kickscooter-user-manual-en.pdf            | Scooter has it's own BT; Gen 2 (?)
|  ![SJ25](https://i.imgur.com/7Mno79i.png) ![okai](https://i.imgur.com/n8F8iaf.jpg)![okai](https://i.imgur.com/PyMBqDM.jpg)![okai](https://i.imgur.com/nChRz0X.jpg)![okai](https://i.imgur.com/VdqvsBN.jpg)![okai](https://i.imgur.com/IYYR47g.jpg)![okai](https://i.imgur.com/GndnBEB.jpg)      | Lime          | LimeS SJ2.5			| N/A        | Gen 2.5; Manufactured by `Dong Guan Honglin Industrial Co. Ltd`
|  ![SJ3](https://i.imgur.com/ZOKGUAc.jpg) ![SJ3](https://i.imgur.com/8qz5Shr.jpg)     | Lime          | LimeS SJ3(?)    | N/A        | [Linux (?); Gen 3](https://www.li.me/blog/lime-s-gen-3-electric-scooter-transform-micro-mobility)

--------

### Trackers  
Spotted in the wild:

| Model         | Spotted on  |  
| ------------- | ----------- | 
| LBCAT-S-EU    | SJ2.5       |
| LBCATSL-EU_V02|             |
| LBCATSL-EU_V03| ES2         |


Seems to share same internals as the `LBCAT-(H|B)`, minus keypad daughterboard.


MEIGLink SLM750
It seems to be running [EC25 Linux](https://osmocom.org/projects/quectel-modems/wiki/EC25_Linux)
```
SoC/Modem: Qualcomm MDM9607
BLE: TI CC2540
GPS: uBlox G7020 
SIM: Twillio
```

Misc:
```
Accelerometer: Bosch Sensortec BMI160
```


UART: 
```
idVendor=05c6
idProduct=f601
Product=Android
Manufacturer=Android
```

Shows up as BLE device, with naming format `lime-XXXXXXXX` and OUI `18:62:E4 - Texas Instruments`.

![lbcat_uart](https://i.imgur.com/bKcM6Wa.png)
![lbcat](https://i.imgur.com/B6msfgl.png)
![lbcat_closeup](https://i.imgur.com/WkkuX6L.png)



##### Docs 
- [FCC ID](https://fccid.io/2APB2)
- [User Manual](https://fccid.io/2APB2LBCAT/Users-Manual/Users-Manual-3863957)
- [External Photos](https://fccid.io/2APB2LBCAT/External-Photos/External-Photos-3863955)
- [Internal Photos](https://fccid.io/2APB2LBCAT/Internal-Photos/Internal-Photos-3863956)
----------
#### Misc

- [Tech Stack](https://stackshare.io/lime/lime)
- [Mathew Garrett - Reversing Article](https://www.nzherald.co.nz/business/news/article.cfm?c_id=3&objectid=12163221) 
