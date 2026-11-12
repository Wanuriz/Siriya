# ecc:architect | 2026-11-12 | структура scripts/chapter0.gd (система глав)

агент: ecc:architect | дата: 2026-11-12 | scope: scripts/chapter0.gd (state machine, разбиение на методы), scripts/location.gd, data/chapter0.json, docs/ARCHITECTURE.md, docs/PROJECT_CONTEXT.md §4, tests/test_chapter0.gd. Вывод дословно ниже, без правок.

---

## Ревью scripts/chapter0.gd (без правок файлов)

**1. Декомпозиция — здравая.** `_ready / _cache_nodes / _setup_gas / _load_frames / _apply_frame / _advance / _process`: по одной ответственности, явный кэш узлов вместо `@onready` осознанно — тест `C:\Users\user\Desktop\Siriya\tests\test_chapter0.gd` вызывает `_cache_nodes/_setup_gas/_load_frames/_apply_frame` вне дерева (headless, без ожидания кадров). Это ровно паттерн «критичная логика под тестом» из AGENTS.md п.3. Два мелких замечания: `_process` смешивает мигалку и фейд (на этом размере терпимо); `_load_frames` молча глотает ошибку открытия/парсинга JSON (нет `push_warning`) — сцена просто пустая без следа в консоли.

**2. Фейд-машина — приемлема.** Целая фаза 0/1/2 + накопление delta: детерминировано, тестируемо вне дерева, не требует `create_tween()` (которому нужно быть в дереве — ломает текущий headless-паттерн). Для линейного 0.3s-фейда это проще и честнее Tween. При появлении `scenes/chapters/` с несколькими главами: вынести скрипт в базовый `scripts/chapter_viewer.gd`, параметризованный `DATA_PATH` (константы `GAS_FRAMES`/`LAST_FRAME` должны переехать в JSON или в экспорт сцены); сама машина 0/1/2 масштабируется (расширять только при нелинейных таймингах кадра — тогда длительность брать из данных).

**3. Нарушения принципов — два, оба уровня warn, не P0:**
- **Данные/код:** в `C:\Users\user\Desktop\Siriya\data\chapter0.json` у каждого кадра есть поле `"gas"` (тест требует его как bool), но `_apply_frame` его игнорирует: `gas.emitting = n in GAS_FRAMES` с захардкоженным `const GAS_FRAMES := [2, 7]`. Поле данных мёртвое, правило живёт в коде — сейчас совпадает (2 и 7), при правке JSON рассинхронизируется молча. Правильно: `gas.emitting = frame.get("gas", false)`. Аналогично `LAST_FRAME := 7` дублирует размер массива.
- **Дрейф контракта ARCHITECTURE.md:** раздел 1 («локации не ссылаются на GameState, связь появится у диалогового рана») и раздел 3 («только эти два пути») фактически расширены: `chapter0.gd` зовёт `GameState.set_flag`, а `location.gd` несёт третий путь F3. Само по себе это не зло (глава — не локация, GameState остаётся тупым хранилищем: строковый флаг через существующий 5-методный API, новые методы не добавлены, выдуманных фактов в коде нет — все видимые тексты только из JSON с `src/ref`), но документ этого не знает — расхождение надо записать, а не оставить молча.

**4. Предложение абзаца для `docs/ARCHITECTURE.md` (не вношу):**
> **Система глав (первый срез: глава 0).** Просмотрщик главы — сцена `scenes/chapters/<имя>.tscn` без игрока; кадры, тексты и признаки кадров (включая газ) — только в `data/chapters/<имя>.json` с полями `src`/`ref`, код не содержит сюжетных строк и не дублирует атрибуты кадров константами. Завершение глава фиксирует единственным разрешённым вызовом `GameState.set_flag("<флаг>", true)` — это первый не-диалоговый потребитель GameState; новых методов GameState не добавлять. Открытие главы — F-клавишей через константу `SCENES` в `scripts/location.gd` (расширение п.3, третий путь). При второй главе общий код просмотра (фейд, кэш узлов, чтение JSON) выносится в базовый скрипт; до этого дублировать не запрещено.

Файлы: `C:\Users\user\Desktop\Siriya\scripts\chapter0.gd`, `C:\Users\user\Desktop\Siriya\scripts\location.gd`, `C:\Users\user\Desktop\Siriya\data\chapter0.json`, `C:\Users\user\Desktop\Siriya\docs\ARCHITECTURE.md`, `C:\Users\user\Desktop\Siriya\docs\PROJECT_CONTEXT.md` (раздел 4), `C:\Users\user\Desktop\Siriya\tests\test_chapter0.gd`.
