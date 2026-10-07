# Lime Gen3 — Complete Detachment from IoT/Aux Controllers

**patch_for_60sec_unlock**

> A solution for owners of Lime Gen3 scooters (STM32F103) who want to **completely abandon the IoT module, emulators, and any external auxiliary controllers**.  
> The goal is not beauty or a speed display, but **simplicity, reliability, and minimal hardware**.

---

## ⚠️ Disclaimer

The author is **not a professional developer** (weak in code, assembly, and programming in general). Everything was done by trial and error and with the help of AI.  
Already **burned 2 × ESP32**.  
I fundamentally **do not want to spend any more money** on this scooter.  
Released "as is". If you have experience — pull requests are welcome.

Many thanks to [Pikokosan/Lime_Gen3_IoT_Replacement](https://github.com/Pikokosan/Lime_Gen3_IoT_Replacement) — half a year of riding on this solution, the only fully working one.

---

## 🎯 What Has Been Achieved

- **Unlock on wake** without IoT and without an emulator.
- Uses the `lockctrl` signal (an input that must be **pulled up to HIGH**).
- HIGH is supplied through a **large resistor** (if not using a 12 V step-down converter).

---

## 🕒 Behavior (Clarified)

### Main Work Cycle

| Step | Action | Result |
|---|---|---|
| 1 | Briefly apply **+2 sec** (HIGH) to `lockctrl` while in `sleep` & `lock` state | Scooter starts, rides |
| 2 | Remove + from `lockctrl` pin (LOW) | Starts the **60-second timer** (independent of anything) for the transition to sleep |
| 3 | After **60 sec** | Throttle stops responding (lock) regardless of `lockctrl` pin HIGH or LOW; the light stays on for ~2 sec if `lockctrl` was LOW immediately after the work cycle started |
| 4 | After another **2–3 sec** | **Sleep & lock** occur — the light goes off |
| 5 | Only after **sleep & lock** | Re-applying + (HIGH) to `lockctrl` pin for >=2 sec starts a **new work cycle** — you can ride again |

### Key Nuance

> **While the controller has not yet gone to sleep (the light is on), re-applying + to `lockctrl` only resets the 60-second timeout. The light stays on, but there is no motion.**  
> A full work cycle and riding are only possible **after the scooter has gone to sleep and turned the light off**.

### What Resets the Timer

- **Full power removal from the controller.**
- **Reset via 7 pin STM32F103** (short to GND).

> Current logic: the 60-second timeout starts **after removing +** from the `lockctrl` pin (it gets the `LOW` flag) and **does not depend** on the lock/unlock state. **Sleep** occurs **after the 60-second cycle ends while the `lockctrl` pin is LOW**. Until sleep occurs, a new work cycle cannot be started — only the controller can be reset.

---

## 🔧 Current Implementation (Temporary but Working)

- HIGH is **permanently** held on the `lockctrl` pin (HIGH).
- The RST **7 pin STM32F103** is wired to a button → short to GND = **reset the controller**.
- On lock → button → restart → **unlock faster** than waiting 3 sec after the work cycle until it goes to sleep.

This is faster than waiting for sleep after the 60-second cycle.  
You can also use:
- an automotive relay,
- a 12 V converter,
- other methods of resetting the controller.

Previously tried a variant with a button + capacitor + resistor — touch less than 0.2 sec, HIGH <=3 sec for unlock. But if you don't hold HIGH >2 sec — you get a 60-second timeout with **light but no throttle response**.  
**The 7 pin responds faster.**

---

## 🧠 Under the Hood

- MCU: **STM32F103**
- `lockctrl` input — control lock signal.
- The algorithm is then expanded into RAM, so as I understand, finding it by dump reverse engineering is not so easy.

---

## 🎯 Wishes (TODO / Roadmap)

- [ ] Find and disable the logic waiting for HB and other conditions to prevent LOCK
- [ ] Dig into the **speed** and **current** limit tables.
- [ ] Move **start** from 3 km/h to 0 km/h (zero-start)
- [ ] Settings close to custom firmware.

---

## 🛠️ Tools

- **ST-Link V2**
- Flashing via **Android app** — convenient for testing patched firmware.

---

## 🤝 Help

Any help is welcome:
- find the places in the firmware responsible for timeouts,
- understand where the RAM algorithm expands,
- speed/current limit tables,
- zero-start.

---

## 📜 License

As is. Use at your own risk.

---

## See Also

- [Pikokosan/Lime_Gen3_IoT_Replacement](https://github.com/Pikokosan/Lime_Gen3_IoT_Replacement) — a fully working solution with IoT emulation.
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
- (https://github.com/lcannabinol/lime-scooter-reversing)
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
