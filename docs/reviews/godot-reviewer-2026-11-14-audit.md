# godot-reviewer | 2026-11-14 | статическое ревью всего Godot-кода (task: FULL PROJECT AUDIT)

агент: godot-reviewer | дата: 2026-11-14 | scope: scripts, scenes, data, tests, project.godot. Вывод дословно ниже, без правок. Прочитанные SKILL.md: godot, godot-gdscript-patterns, godot-best-practices.

---

Skills прочитаны: `godot`, `godot-gdscript-patterns`, `godot-best-practices` (SKILL.md все трёх). Ревью статическое, файлы не менял.

# Вердикт

P0 нет. Каркас корректен: autoload зарегистрирован, `ExtResource`/`load_steps` во всех .tscn верны, пути узлов в `chapter0.gd` совпадают с `chapter0.tscn`, контракты GameState/локаций соответствуют `docs/ARCHITECTURE.md`, tests имеют fail-safe exit(1) и реальные маркеры. Одно реальное дефектное место (P1) — дублирование числа кадров из данных в коде главы.

# Находки

**P1**

1. `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:18` — `const LAST_FRAME := 7` дублирует число кадров из `C:\Users\user\Desktop\Siriya\data\chapter0.json` (7 элементов). `docs/ARCHITECTURE.md` §7 прямо запрещает: «код не дублирует атрибуты кадров константами». При добавлении кадра 8 в JSON он недостижим (`_advance`, строка 114), а флаг `chapter0_done` выставится на 7-м; при удалении кадра — `current_frame` дорастёт до 7 по «пустым» кадрам (строка 122 присваивает до валидации) и флаг выставится без показа контента. Всё молча. Исправление: в `_load_frames()` после `frames = data` добавить `_last_frame = frames.size()` (при ошибке загрузки — 0), заменить оба использования `LAST_FRAME` (строки 114, 148) на `_last_frame`; тест `test_chapter0.gd:46` уже пиннит размер данных и останется сторожем.

**P2**

2. `scripts\chapter0.gd:122` — `current_frame = n` присваивается до проверки `n < 1 or n > frames.size()` (строка 123). При невалидном n состояние портится до выхода по guard. Перенести присваивание после guard (это же механизм дефекта №1 при рассинхроне данных).

3. `scripts\chapter0.gd` (весь скрипт) — из главы 0 нет выхода: обработка F1/F2 живёт в `scripts/location.gd:16-25`, который на корне `scenes/chapters/chapter0.tscn` отсутствует. После 7-го кадра игрок заперт до перезапуска игры. В `docs/ARCHITECTURE.md` §3 выход главы не определён — подтвердить у руководителя (вернуться в F1/F2 или отдельная клавиша).

4. `scripts\chapter0.gd:61-67` — `_load_frames()` молча выходит при невозможности открыть файл или при не-Array JSON: сцена показывает пустое окно без текста и без ошибки в консоли. Добавить `push_error("chapter0: cannot load %s" % DATA_PATH)` в обе ветки отказа.

5. `scripts\chapter0.gd:125` — `var frame: Dictionary = frames[n - 1]` жёсткий каст: элемент JSON не-Dictionary уронит `_apply_frame` посреди fade, `busy` останется true навсегда (софт-лок ввода). Страхуется тестом `test_chapter0.gd:51`, но в рантайме лучше: `var frame_v = frames[n - 1]; if frame_v is Dictionary: ... else: push_error(...)`.

6. `scripts\chapter0.gd:137-140` против `scenes\chapters\chapter0.tscn:83` — логика плейсхолдера общая для любого отсутствующего bg, а текст метки захардкожен «igloo (placeholder)». Для другого отсутствующего файла подпись соврёт. Исправление: в `_apply_frame` ставить `placeholder_label.text = bg + " (placeholder)"`.

7. `scripts\game_state.gd:19` — `get_flag(flag_name, default: bool = false)` расходится с контрактом в `docs/ARCHITECTURE.md` §2 (`get_flag(flag_name: String) -> bool`). Расширение совместимое и тест его использует (`tests\test_game_state.gd:76`), но контрактный документ не обновлён — либо откатить параметр, либо записать изменение контракта в ARCHITECTURE.

8. `scenes\chapters\chapter0.tscn:11,26,34,46,54,63,72,81,89` — литералы цветов сцены дублируют константы палитры `scripts/chapter0.gd:12-16` (3b3251, 8d7da8, f5cba9, fde073), и `chapter0.tscn:56` «Летописец» дублирует speaker кадра 1 из `data\chapter0.json:2-3` (в рантайме перезаписывается). Смена палитры требует правки в двух местах. Осознанный компромисс на первый срез — записать в DECISIONS или генерировать цвета из скрипта в `_ready`.

9. `scenes\chapters\chapter0.tscn:58-64` — TextLabel высотой 54 px (18..72) при font_size 10: кадр 3 (~190 знаков, `data\chapter0.json:8-10`) даёт 4-5 строк и может визуально перелиться за окно. Walk-тест считает пиксели текста, но не проверяет переполнение. Проверить визуально на скриншоте ch0_03.

10. `tests\test_player.gd:36-44` — проверка «прямоугольник в полосе земли» считает границы из констант скрипта, а не из живого узла: удаление `position.y = Y_CENTER` из `scripts\player.gd:26` или изменение HEIGHT без правки констант тест не поймает (это поймает только `tests\walk_locations.gd:81`). Мелкий white-box долг; при появлении настоящего спрайта заменить на поведенческую проверку.

11. `scripts\location.gd:9-13` — `SCENES: Dictionary` без типизации; ключи — `Key` (int). Можно `Dictionary[int, String]`. То же в `tests\test_locations.gd:55` (`consts.get("SCENES", {})`).

12. `scenes\locations\bazaar.tscn:17-22`, `scenes\locations\oasis.tscn:17-22` — отладочная метка `DebugSceneName` остаётся в сценах; перед выпуском убрать (архитектура её санкционирует как «debug-метка», но срок съёма не зафиксирован).

13. `tests\test_*.gd` (все 5 файлов) — дублируется каркас `_check`/`_initialize`/fail-safe `_exit_code`. Можно вынести в общий хелпер (preload .gd со static-функциями). Долг, не дефект.

14. `tests\walk_chapter0.gd:69-70` — `img.save_png(path)` без проверки кода ошибки: при пропаже `art/screens/` доказательства-скриншоты молча не сохранятся, тест останется зелёным. Директория сейчас существует, но проверка `err == OK` + `_check` её закрепит.

# Дублирование данных/кода (сводка по заданию)

- Число кадров: JSON ↔ `chapter0.gd:18` ↔ `test_chapter0.gd:46` — находка №1.
- Палитра: `chapter0.gd` ↔ литералы `chapter0.tscn` — находка №8.
- «Летописец»: `chapter0.tscn:56` ↔ JSON кадр 1 — находка №8.
- Сюжетных строк в коде нет (`chapter0.gd` чист, gas только из данных) — соответствует ARCHITECTURE §7.

# Не проверено

- Запуск: `check.py`, headless- и windowed-тесты не выполнялись (ревью строго статическое, запуск у главной сессии/playtester). Статусы маркеров взяты из истории `docs/reviews/`, не перепроверены.
- `script.call("clamp_x", ...)` на ресурсе GDScript (`test_player.gd:29-33`) — семантика вызова static-метода через `Script.call()` не исполнена здесь; опирается на зелёные прогоны текущей версии движка.
- Визуальная верстка: переполнение TextLabel (№9), плейсхолдер igloo, частицы газа — по скриншотам не сверял (просмотр изображений вне объёма).
- Производительность TileMapLayer/чанков — в проекте тайлов нет, неприменимо.
- Бюджеты времени walk-тестов (45 с / 30 с против максимум ~600 кадров ожидания) под медленной машиной не замерялись.
