# LimeRE_Helper.py — Ghidra Interactive Helper

## Установка

1. Открой Ghidra → **Window → Script Manager**
2. Нажми зелёный **+** (Script Directories) и добавь папку:
   ```
   <путь-к-репо>/lime-scooter-reversing/ghidra_scripts
   ```
3. В Script Manager найди `LimeRE_Helper.py` (категория **Lime.RE**)
4. Дважды кликни или нажми **Run**

## Возможности меню

| # | Действие | Что делает |
|---|----------|------------|
| 1 | **Apply ALL known names** | Переименовывает все известные функции + ставит labels на RAM + ключевые точки патча |
| 2 | Trace CALLERS | Показывает все места, откуда вызывается функция |
| 3 | Trace CALLEES | Показывает все функции, которые вызывает данная |
| 4 | XREFs to address | Все ссылки на конкретный адрес |
| 5 | XREFs into RANGE | Все ссылки, попадающие в диапазон адресов |
| 6 | Find constant | Ищет инструкции, использующие 0x258 / 0x3C / другие пороги |
| 7 | Rename | Переименовать функцию или создать label |
| 8 | Add comment | Plate-комментарий (над блоком) или EOL |
| 9 | Function info | Полная информация + callers + callees |
| 10 | Bookmark key sites | Закладки на все критические точки (IoT-gate, timer cmp, patch site) |
| 11 | Go to known | Быстрая навигация по всем известным символам |

## Известные символы (зашиты в скрипт)

### Функции
- `main_state_machine` @ `0x080073fc`
- `motor_control_main` @ `0x08005ed0` ← **настоящий гейт тяги**
- `timer_handler_CMP_0x3C` @ `0x08003b32`
- `timer_struct_init` @ `0x08003706`
- и другие…

### RAM
- `iot_active_flag` @ `0x20000477`
- `traction_lock_flag` @ `0x20000158`
- `unlock_elapsed_counter` @ `0x200003C8`
- `sec_counter_or_lock_timer` @ `0x20000035`
- …

### Ключевые точки патча
- `0x0800609e` — `IOT_FLAG_bne_GATE` (радикальный патч)
- `0x08007922` — `TIMER_cmp_#0x258` (безопасный патч)
- `0x080010A0` — место подмены указателя

## Как расширять

Все таблицы находятся в начале файла:

```python
KNOWN_FUNCTIONS = { 0x0800xxxx : "nice_name", ... }
KNOWN_RAM       = { 0x2000xxxx : "nice_name", ... }
KEY_LOCATIONS   = { 0x0800xxxx : "description", ... }
```

Просто добавляй новые адреса — при следующем запуске пункта 1 они будут применены.

## Примечания

- Скрипт использует только стандартный Ghidra Python API (`askChoice`, `askAddress`, `createLabel`, `setName` и т.д.).
- Работает как в GUI, так и в headless (через `.properties` файлы для ask-методов).
- После массового переименования рекомендуется **Window → Functions** обновить / пересортировать.
