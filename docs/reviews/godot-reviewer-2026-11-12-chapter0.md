# godot-reviewer | 2026-11-12 | глава 0 «Плёнка» MVP

агент: godot-reviewer | дата: 2026-11-12 | scope: scripts/chapter0.gd, scenes/chapters/chapter0.tscn, data/chapter0.json, tests/test_chapter0.gd, tests/walk_chapter0.gd, дельта scripts/location.gd (F3), дельта tests/test_locations.gd (пин F3). Вызов после WALK_CH0_OK (26 checks). Вывод дословно ниже, без правок.

---

Ревью завершено. Все файлы прочитаны, диффы location.gd и test_locations.gd проверены по содержимому (глубже диффа по F3 изменений нет), контекст сверен: project.godot:14 main scene = bazaar, autoload только GameState, палитра совпадает с art/palette_v3.hex (3B3251 — строка 11, 363A8C — строка 10, 8D7DA8 — 32, F5CBA9 — 46, FDE073 — 47).

## Итог: P0 — нет. Блокеров и нарушений ограничений не найдено

Ограничения соблюдены: GameState не расширялся (использован существующий `set_flag`, в game_state.gd ровно 5 методов), main scene не тронут, тексты только в data/chapter0.json с `"src": "п"` и `"ref"`, шрифты дефолтные (size 10 во всех Label), звука/сейва/NPC нет, .tscn корректен (ExtResource для скрипта, load_steps=2 сходится, путей-сирот нет), headless-тест без единого await, walk-тест с задержками — по дизайну, тайлмапов нет, в `_process` только мигалка и фейд.

### P1 (одна)

1. **Поле `"gas"` из данных игнорируется рантаймом — тройное дублирование константы.**
   `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:144` — `gas.emitting = n in GAS_FRAMES` (константа `GAS_FRAMES := [2, 7]`, строка 18). Тот же массив продублирован в `C:\Users\user\Desktop\Siriya\tests\walk_chapter0.gd:15`, и третий источник — поле `"gas": true/false` в `C:\Users\user\Desktop\Siriya\data\chapter0.json` (кадры 2 и 7), которое тест `test_chapter0.gd:66` строго валидирует (`gas is bool`), но код ни разу не читает. Сегодня значения совпадают, но при правке данных сцена не последует — нарушение data-driven контракта, который сам тест закрепил.
   Исправление (поведение идентично): в `_apply_frame` заменить строку 144 на `gas.emitting = bool(frame.get("gas", false))`. В walk-тесте можно оставить пин [2, 7] как независимую проверку или читать из данных.

### P2

2. **Мёртвые константы цветов.** `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:13` (`FRAME_BORDER_COLOR`) и `:15` (`LABEL_COLOR`) нигде не используются — цвета продублированы литералами в `C:\Users\user\Desktop\Siriya\scenes\chapters\chapter0.tscn:26` (рамка 8D7DA8) и `:54`, `:72` (FDE073). Дрейф при правке палитры. Либо убрать константы, либо задавать цвета из них в `_apply_frame`/`_ready`.

3. **`current_frame` мутируется до валидации.** `chapter0.gd:123` — `current_frame = n` выполняется до проверки `n < 1 or n > frames.size()` на строке 124: при невалидном n состояние меняется, а кадр не применяется. Перенести присваивание после guard-а.

4. **Тихий отказ при кривых данных.** `chapter0.gd:64-65` — при не открывшемся файле или не-Array JSON сцена молча становится инертной. Добавить `push_error("chapter0: cannot load " + DATA_PATH)` в оба ранних return.

5. **Хардкод текста плейсхолдера.** `chapter0.tscn:83` — `"igloo (placeholder)"`, а код (`chapter0.gd:137-141`) обрабатывает отсутствие любого bg. Сейчас тест разрешает отсутствовать только igloo.png, но при другом пропуске надпись соврёт. Фикс: `placeholder_label.text = bg + " (placeholder)"` рядом с `placeholder_label.visible = true`.

6. **Устаревший доккомментарий.** `C:\Users\user\Desktop\Siriya\scripts\location.gd:2` — «F1 opens the bazaar, F2 opens the oasis», F3 после диффа не упомянут. Строка 11 (KEY_F3 → chapter0) сама корректна, пин в `test_locations.gd:58-59` корректен.

7. **Нет пути назад из chapter0.** Переключение F1/F2 живёт в location.gd, который в chapter0.tscn отсутствует, а ui_accept на кадре 7 инертен — из главы нельзя вернуться на базар. Для MVP, судя по ТЗ, допустимо, но это стоит записать как [с]-решение в docs/DECISIONS.md или STATUS.md.

8. **Типизация/UX, опционально.** `chapter0.gd:21` — `frames: Array` можно усилить до `Array[Dictionary]` через `frames.assign(data)`; `chapter0.gd:66` — `var data` без типа; `walk_chapter0.gd:95` — `var gs` без типа. Мигалка «▼» (`chapter0.gd:89-91`) продолжает мигать на кадре 7, где продвижение отключено — мелкая вводящая в заблуждение подсказка.

## Не проверено

запуск и вывод `check.py`/walk-теста мной не повторялись — взяты заявленные результаты (CHAPTER0_OK, STATE_TESTS_OK, LOCATION_TESTS_OK, PLAYER_TESTS_OK, WALK_CH0_OK / 26 проверок); git diff не выполнялся, диффы проверены чтением текущего содержимого обоих файлов.
