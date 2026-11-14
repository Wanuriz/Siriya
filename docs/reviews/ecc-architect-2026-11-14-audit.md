# ecc:architect | 2026-11-14 | архитектурный аудит всего проекта (task: FULL PROJECT AUDIT)

агент: ecc:architect | дата: 2026-11-14 | scope: вся архитектура (scripts, scenes, data, project.godot, docs-контракты). Вывод дословно ниже, без правок. Примечание приёмщика: находка P1-1 (нет выхода из главы 0) перекликается с Д-31 (намеренное решение "ожидает [у]"), см. сверку в аудите.

---

# Архитектурный аудит — SIRIYA (только чтение, без изменений файлов)

## Итог

Ядро архитектуры работоспособно и точно соответствует своей документации там, где это важно: GameState соответствует точно указанному контракту из 5 методов (headless-тест блокирует его структуру и сущность), контракт переключения локаций (константа SCENES, неактивные состояния F-key, литеральные строки путей сцены, отсутствие связи location→GameState) реализован как задокументировано, а подсистема глав соблюдает собственное правило "данные, а не код" для текста, src/ref и gas. Направления зависимостей чистые: GameState — тупиковой (leaf), только chapter0.gd использует его (задокументированное исключение).

Дрейф контракта (contract drift) между ARCHITECTURE.md и кодом минимален (одна сигнатура метода, один путь к данным). Реальные риски сосредоточены в трех областях: **глава 0 — односторонняя сцена без выхода**, **глухо закодированное (hardcoded) количество кадров**, нарушающее принцип "без атрибутов кадров в коде", задокументированный в собственной документации проекта, и **вводная документация, описывающая дерево проекта, которое еще не существует** (data/chapters/, data/dialogue/, data/endings/, scenes/ui/).

Оценка: **architecture is sound for the current slice; three P1 items must be resolved before chapter 1 or the dialogue runner starts**.

## Findings

### P1

**1. В главе 0 нет пути выхода — переход через F3 является односторонним.**
- `C:\Users\user\Desktop\Siriya\scenes\chapters\chapter0.tscn:5-6` — корневой узел несет только `chapter0.gd`; `location.gd` (единственный обработчик F1/F2/F3) присоединен только к корням базара/оазиса (`C:\Users\user\Desktop\Siriya\scenes\locations\bazaar.tscn:8`, `oasis.tscn:8`).
- `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:108-110` — `_unhandled_input` обрабатывает только `ui_accept`; ни одной клавиши выхода (F1/F2/F3/Esc) нет.
- Свидетельство: `C:\Users\user\Desktop\Siriya\scripts\location.gd:9-13` определяет маршрутизацию; в главе 0 это единственный достижимый узел, который ее не имеет.
- Следствие: вход в главу 0 (F3 из любой локации) можно покинуть только перезапуском процесса. ARCHITECTURE.md раздел 7 (`C:\Users\user\Desktop\Siriya\docs\ARCHITECTURE.md:60-63`) не описывает выход главы; этот тупик не задокументирован как намеренный где-либо, что я смог найти.

**2. LAST_FRAME=7 дублирует атрибут данных в коде, а установка флага упорядочена после boundary guard.**
- `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:18` (`LAST_FRAME := 7`), используется на `:114` (advance stop) и `:148-149` (`GameState.set_flag("chapter0_done", true)`).
- `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:122-124` — `_apply_frame` возвращается при `n > frames.size()` **до** установки флага, поэтому корректность `chapter0_done` молча зависит от `frames.size() >= 7`.
- ARCHITECTURE.md:62 явно запрещает это: "код не содержит сюжетных строк и не дублирует атрибуты кадров константами" (gas — это единственный атрибут, управляемый данными, и он корректно считывается из данных на `:143`).
- Количество кадров "7" теперь закодировано в трех местах: `C:\Users\user\Desktop\Siriya\data\chapter0.json` (7 записей), `chapter0.gd:18` и `C:\Users\user\Desktop\Siriya\tests\test_chapter0.gd:46,59` (блокировка `size()==7`, ids 1..7). Тест сегодня отслеживает дрейф, но с главами 1-9 этот триплет должен быть повторно синхронизирован для каждой главы — первое место, где система глав сломается.

**3. Дрейф структуры: вводная документация описывает дерево, которое не существует.**
- `C:\Users\user\Desktop\Siriya\docs\PROJECT_CONTEXT.md:22-33` показывает `data/dialogue/`, `data/chapters/`, `data/endings/` и `scenes/ui/`. Фактические перечисления: `data/` содержит ровно один файл, `chapter0.json` в корне данных; `scenes/` содержит только `chapters/`, `characters/`, `locations/`; `scenes/ui/` отсутствует.
- `C:\Users\user\Desktop\Siriya\docs\ARCHITECTURE.md:62` требует `data/chapters/<имя>.json`, но соглашается с "(фактически: data/chapter0.json)"; код подтверждает это: `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:10` (`DATA_PATH := "res://data/chapter0.json"`).
- Следствие: каждый агент, загрузившийся через PROJECT_CONTEXT, будет ожидать подкаталоги, которые не существуют; главы 1-9 накапливаются в корне данных; `data/chapter0.json` уже конфликтует с его собственной задокументированной схемой расположения.

### P2

**4. GameState get_flag сигнатура дрейфует от документированного контракта.**
- Документ: `C:\Users\user\Desktop\Siriya\docs\ARCHITECTURE.md:25-30` — `get_flag(flag_name: String) -> bool`, "Только эти пять методов. Ничего не добавлять без смены контракта".
- Код: `C:\Users\user\Desktop\Siriya\scripts\game_state.gd:19` — `get_flag(flag_name: String, default: bool = false)`. Необязательный параметр не добавляет метод (структурный тест на `C:\Users\user\Desktop\Siriya\tests\test_game_state.gd:47-57` все еще проходит) и тест блокирует расширенное поведение на `:76` и `:81`. Безвредно, но документ контракта больше не является дословно точным.

**5. Тихая ошибка загрузки данных в главе 0.**
- `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:61-67` — `_load_frames` возвращается молча при отсутствующем файле или сбое парсинга; без `push_error`. Сцена затем отображает устаревший/пустой UI. Уже отложено как вынесенное на рассмотрение P2 замечание в `C:\Users\user\Desktop\Siriya\docs\STATUS.md:23` ("push_error").

**6. current_frame присваивается перед validation guard.**
- `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:122-124` (`current_frame = n` до проверки границ). Также в списке отложенных STATUS.md:23.

**7. Отсутствующий производственный ресурс igloo.png с жестко закодированным видимым плейсхолдером.**
- `C:\Users\user\Desktop\Siriya\data\chapter0.json:14` ссылается на `"bg": "igloo.png"`; `assets/backgrounds/` содержит только bazaar.png, oasis.png, gangbang.png (перечисление).
- Обрабатывается во время выполнения (`C:\Users\user\Desktop\Siriya\scripts\chapter0.gd:136-140`, плейсхолдер-ветка) и в списке разрешенных тестом (`C:\Users\user\Desktop\Siriya\tests\test_chapter0.gd:13`), но строка плейсхолдера `"igloo (placeholder")` жестко закодирована на английском в `C:\Users\user\Desktop\Siriya\scenes\chapters\chapter0.tscn:83` и будет видна игроку, если выйдет в этот путь.

**8. Цепочка иконок писца не имеет внутриигрового потребителя.**
- `C:\Users\user\Desktop\Siriya\assets\ui\scribe_icon.png` имеет генератор (`C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:44-47`) и headless-тест (`C:\Users\user\Desktop\Siriya\tests\test_scribe_icon.gd:7`, маркер `SCRIBE_ICON_OK`), но ноль ссылок в любых сценах/скриптах (grep по *.gd/*.tscn/*.godot/*.py: совпадения только в tools/ и tests/). Это подготовленный ресурс для UI диалога, который еще не существует.
- `C:\Users\user\Desktop\Siriya\assets\ui\scribe_source_v2.png` не упоминается нигде — неиспользуемый ресурс.

**9. Нет настроенной иконки проекта.**
- `C:\Users\user\Desktop\Siriya\project.godot:11-35` не имеет `config/icon`; `icon.svg` не существует нигде в проекте (grep). Сборка/export будет использовать путь к иконке Godot по умолчанию с предупреждением.

**10. art/ рабочая область накапливается внутри сканируемого Godot проекта.**
- `C:\Users\user\Desktop\Siriya\art\` содержит backup_v1/, preview_v2/, preview_v2_dither/, preview_v3/, preview_icon/, screens/ (9 png), плюс три поколения палитры (palette.png+hex, palette_v1/v2/v3.png+hex). Все имеют .import сайдкары, т.е. Godot импортирует их как ресурсы. Это рабочие файлы инструментов, а не контент игры, они конфликтуют с лимитом "максимум две последние версии" AGENTS.md п.10 и правилами ограничения дискового пространства.
- Дрейф палитры: `C:\Users\user\Desktop\Siriya\docs\PROJECT_CONTEXT.md:39` называет `art/palette.png` инструментом импорта фона, в то время как `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:34` читает `art/palette_v3.hex` — два активных инструмента, два разных источника палитры.

**11. Тест закрепляет неявное значение по умолчанию движка, а не настройку проекта.**
- `C:\Users\user\Desktop\Siriya\tests\test_locations.gd:38` подтверждает `display/window/stretch/aspect == "keep"`, но `project.godot:27-28` устанавливает только stretch mode и scale_mode. Утверждение выполняется через встроенное значение по умолчанию Godot — скрытая зависимость от настроек по умолчанию движка, а не от проекта.

**12. Потенциально неотслеживаемый шум в корне репозитория.**
- `C:\Users\user\Desktop\Siriya\.zcode\plans\*.md` и `.zcode\config.json` существуют; `.gitignore:1-8` не исключает `.zcode/`. Статус отслеживания не проверяем без доступа к git (см. список "не проверено").
- `tools/art/__pycache__/*.pyc` присутствует на диске, но правильно проигнорирован git (`*.pyc`, `__pycache__/`).

**13. Оставшиеся замечания по главе 0 уже зарегистрированы и отложены (перекрестная ссылка, не новизна).**
- `C:\Users\user\Desktop\Siriya\docs\STATUS.md:23` откладывает: мёртвые константы, push_error, current_frame до валидации, текст плейсхолдера, типизация, порядок guard-а walk-теста, F3 реальным вводом. Пункты 5, 6, 7 выше перекрываются с этим списком — они являются подтвержденным техническим долгом, а не новыми открытиями.

## Контрактная проверка (документ vs код)

| Документированный контракт | Реализация | Вердикт |
|---|---|---|
| GameState: ровно 5 методов, clamp 0..3, unset flag = false, dumb store (ARCHITECTURE.md §2) | `C:\Users\user\Desktop\Siriya\scripts\game_state.gd:15-32`; заблокировано `tests/test_game_state.gd:47-57,60-72` | MATCH (за исключением дополнительного параметра `default` — P2 #4) |
| Переключение локаций: SCENES const, F-key direct compare, no-op on current, literal paths, no GameState refs (§3 incl. Д-22 F3) | `C:\Users\user\Desktop\Siriya\scripts\location.gd:9-25` | MATCH |
| Система глав: только данные для текстов/src/ref/gas, no story strings in code, завершение через единственный set_flag (§7) | `chapter0.gd:143,148-149`; src/ref на каждой рамке `data\chapter0.json` | MATCH, кроме закодированного количества кадров (P1 #2) |
| "Связь локация -> GameState появится только у диалогового рана" (§1) | grep: ни один скрипт локаций не упоминает GameState | MATCH |
| Позиция игрока не переносится; инстанс на локацию (§3) | player.tscn инстанс в обеих локациях на y=240 | MATCH |

## Карта фактических зависимостей

```
project.godot
  ├─ application/run/main_scene ────► scenes/locations/bazaar.tscn
  └─ autoload "GameState" ──────────► scripts/game_state.gd   [тупиковой: нет исходящих ссылок]

scenes/locations/bazaar.tscn ──┬──► scripts/location.gd  (корневой скрипт)
                               ├──► assets/backgrounds/bazaar.png  (Sprite2D)
                               └──► scenes/characters/player.tscn (инстанс)
scenes/locations/oasis.tscn ───┬──► scripts/location.gd
                               ├──► assets/backgrounds/oasis.png
                               └──► scenes/characters/player.tscn
scenes/characters/player.tscn ───► scripts/player.gd  (→ только синглтон Input: ui_left/ui_right)
scenes/chapters/chapter0.tscn ───► scripts/chapter0.gd

scripts/location.gd ── change_scene_to_file (константные строки) ──►
      scenes/locations/bazaar.tscn | scenes/locations/oasis.tscn | scenes/chapters/chapter0.tscn
      [нет ссылки на GameState — согласно документации]

scripts/chapter0.gd ──┬──► data/chapter0.json            (FileAccess во время выполнения)
                      ├──► assets/backgrounds/*.png      (имена из данных: gangbang.png ок,
                      │                                    igloo.png ОТСУТСТВУЕТ → плейсхолдер)
                      └──► GameState.set_flag("chapter0_done")  (глобальный autoload)

tests/test_game_state.gd  ──► scripts/game_state.gd          (блокировка контракта, headless)
tests/test_locations.gd   ──► location.gd consts + настройки project.godot + пути сцен
tests/test_chapter0.gd    ──► data/chapter0.json + chapter0.tscn (white-box: _cache_nodes/_setup_gas/_load_frames/_apply_frame)
tests/test_scribe_icon.gd ──► assets/ui/scribe_icon.png      (только ресурс; нет игрового потребителя)
tests/walk_*.gd           ──► windowed runs (не headless)

tools/check.py ──► tools/canon_rules.json, data/**/*.json (src/ref lint),
                   tests/test_*.gd через godot --headless; Godot bin из tools/godot_path.txt
tools/art/import_bg.py    ──► art/src/*.png → assets/backgrounds/*.png (art/palette.png)
tools/art/import_icon.py  ──► assets/ui/scribe_source.png → assets/ui/scribe_icon.png (art/palette_v3.hex)

absent (документировано как отсутствующее): dialog runner, save/load, сигналы GameState, scenes/ui/, data/dialogue|chapters|endings/
```

## Что сломается первым при добавлении глав 1-9 / диалогов / сохранения-загрузки

1. **Глава 1** — chapter0.gd специфична для одной главы (DATA_PATH, LAST_FRAME, имя флага, трио блокировки теста). Раздел 7 ARCHITECTURE.md обещает извлечение базового скрипта "при второй главе" — это будет первая принудительная реорганизация. P1 #2 должен быть исправлен одновременно с этим, иначе каждая глава унаследует дрейф количества кадров.
2. **Роутер F-key** — SCENES в location.gd уже маршрутизирует главы (3 маршрута). Документированное условие перехода к менеджеру переходов — "4+ локации", но оно не учитывает главы; с 10 главами + 10 локациями клавиши F заканчиваются задолго до того, как условие сработает. Порог неоднозначен и должен быть переписан.
3. **Раннер диалогов** — нет точки монтирования (scenes/ui/ отсутствует), нет сигналов GameState (задокументированное будущее изменение контракта, требующее запуска ecc:architect), ui_accept в настоящее время используется исключительно chapter0.gd и будет конфликтовать с любым UI диалога, если оба активны, data/dialogue/ должен быть создан с нуля; scribe_icon.png готов, но некуда его монтировать. P1 #1 также блокирует здесь: модель выхода главы (viewer → return to location) должна существовать до того, как главы и диалоги соединятся.
4. **Сохранение/загрузка** — наименьший риск. GameState чист, типизирован (`Dictionary[String, bool]` + int), тупиковой; только to_dict/from_dict является задокументированным изменением контракта (раздел 6.2). Флаг chapter0_done уже живет в хранилище флагов, так что сериализация покрывает его автоматически.

## Не проверено

- Исполнение во время выполнения: check.py, Godot tests и walk tests не были запущены — это статический, доступный только для чтения аудит без инструментов исполнения. Все поведенческие утверждения взяты из чтения кода; STATUS.md:9 сообщает о них как о "зеленых" на последней сессии, что здесь принято на веру.
- Статус git-отслеживания любого файла (незавершенные .zcode/, art/, .pyc) — доступ к shell отсутствовал.
- Содержимое tests/test_player.gd, tests/walk_locations.gd, tests/walk_chapter0.gd, tools/canon_rules.json, tools/art/import_bg.py, tools/test_canon_rules.py и полные тексты STATUS.md/DECISIONS.md/BLOCKERS.md (только STATUS.md проходил grep).
- Фактические пиксельные размеры фоновых PNG (480x270 взяты из документации и .import сайдкаров, размер не проверен).
- Какая клавиша физически связана с ui_accept в сборке 4.7.2 (предположение стандартных настроек движка по умолчанию).
