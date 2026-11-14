# playtester | 2026-11-14 | запуск игры и оконных walk-тестов (task: FULL PROJECT AUDIT)

агент: playtester | дата: 2026-11-14 | scope: Godot MCP запуск, walk_locations, walk_chapter0. Вывод дословно ниже, без правок.

---

## 1. Состояние проекта

- Рабочая папка: `C:\Users\user\Desktop\Siriya` (корень проекта, `project.godot` на месте).
- Ветка: main (detached не обнаружено), commit `3b3bcba` — «docs: проектная конфигурация ZCode…».
- `git status --short` (дословно, до и после тестирования — одинаково, только untracked):
  ```
  ?? .zcode/plans/plan-sess_4b9ef712-3843-4f90-8f2e-482964ef5ad4.md
  ?? .zcode/plans/plan-sess_b93e7e8b-7910-4819-9240-db1f7471ed8a.md
  ?? art/backup_v1/bazaar.png
  ?? art/backup_v1/bazaar.png.import
  ?? art/backup_v1/gangbang.png.import
  ?? art/backup_v1/gangbang_preview_x3.png
  ?? art/backup_v1/gangbang_preview_x3.png.import
  ?? art/backup_v1/oasis.png
  ?? art/backup_v1/oasis.png.import
  ?? art/palette_v1.hex
  ?? art/palette_v1.png
  ?? art/palette_v1.png.import
  ?? art/palette_v2.hex
  ?? art/palette_v2.png
  ?? art/palette_v2.png.import
  ?? art/preview_icon/
  ?? art/screens/
  ```
- Локальные изменения до тестирования: изменённых tracked-файлов нет (`git diff --stat` пуст); перечисленные untracked-файлы уже существовали до начала сессии.

## 2. Godot MCP

- Версия движка: `4.7.2.stable.official.ed1daf0bf` — соответствует требуемой.
- `get_project_info`: `{"name": "Siriya", "path": "C:/Users/user/Desktop/Siriya", "godotVersion": "4.7.2.stable.official.ed1daf0bf", "structure": {"scenes": 4, "scripts": 11, "assets": 45, "other": 87}}`.
- Запуск (`run_project`): стартовал в debug-режиме, стартовая сцена — базар (main scene в project.godot).
- Консоль (дословно, единственный вывод за ~10 с работы):
  ```
  Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org
  OpenGL API 3.3.0 - Build 32.0.101.7084 - Compatibility - Using Device: Intel - Intel(R) UHD Graphics 730
  ```
  `errors: []` — ни SCRIPT ERROR, ни Parse Error, ни ошибок загрузки ресурсов. Предупреждений нет.
- Процесс остановлен через `stop_project` (finalErrors: []).

## 3. Автоматические проверки

Команда: `python -I tools/check.py` — exit code **0**, итог **`RESULT: OK`** (дословно):

```
== Canon lint ==
scanned 9 files in data, scenes, scripts
[warn ] R-zlat data/chapter0.json:28: Злат чертог не отождествлять с чертогом Гэнг-Бэнга и не связывать с Жебью.
canon: 0 errors, 1 warnings
== Godot tests ==
PASS test_chapter0.gd: CHAPTER0_OK
PASS test_game_state.gd: STATE_TESTS_OK
PASS test_locations.gd: LOCATION_TESTS_OK
PASS test_player.gd: PLAYER_TESTS_OK
PASS test_scribe_icon.gd: SCRIBE_ICON_OK
tests: 5 passed, 0 failed
RESULT: OK
```

- Маркеры: CHAPTER0_OK, STATE_TESTS_OK, LOCATION_TESTS_OK, PLAYER_TESTS_OK, SCRIBE_ICON_OK.
- Предупреждение `R-zlat` — единственное. Фактически упоминание «злат чертогу» находится в `data/chapter0.json`, строка 9: `«Место то подобно злат чертогу»` (текст [п], `ref: "руководитель, задание главы 0, 2026-11-12"`). Линтер формулирует сравнение («подобно»), а не отождествление; ошибка не фиксируется. Отдельная странность: линт указывает строку 28, а файл содержит 23 строки — номер строки в warn не совпадает с реальным положением текста (вероятно, внутренний счётчик линтера). Не исправлял, только зафиксировал.

## 4. Оконные тесты

- `tests/walk_locations.gd` — запущен окном (без `--headless`), exit code **0**, вывод дословный:

```
Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org
OpenGL API 3.3.0 - Build 32.0.101.7084 - Compatibility - Using Device: Intel - Intel(R) UHD Graphics 730

  ok: game starts at bazaar
  ok: F2 opens oasis
  ok: flag survives F2 switch
  ok: fruits survive F2 switch
  ok: F1 opens bazaar again
  ok: flag survives F1 switch
  ok: fruits survive F1 switch
  ok: F1 in bazaar does not reload the scene (no-op)
  ok: player exists in the scene
  ok: player reaches the left wall
  ok: player never passes the left bound (x=10.000000)
  ok: player stops at the left bound (x=10.000000)
  ok: player stays on the ground band (y=240)
  ok: player reaches the right wall
  ok: player never passes the right bound (x=470.000000)
  ok: player stops at the right bound (x=470.000000)
WALK_TESTS_OK (16 checks)
```

- `tests/walk_chapter0.gd` — **NOT RUN**, причина: тест сохраняет `art/screens/ch0_01.png`…`ch0_07.png`, а все семь файлов уже существуют на диске (дата 2026-11-12, 21:11 — след предыдущего прогона). По правилам запускать нельзя, чтобы не перезаписать изображения. Маркер `WALK_CH0_OK` в этой сессии **не получен**; его прошлое получение (26 checks, 2026-11-12) зафиксировано только в `docs/STATUS.md`, а не воспроизведено здесь. Скриншоты тестом в этой сессии не создавались.
- F3: реального оконного теста нажатия F3 в проекте нет (это известное отложенное P2-замечание, `docs/STATUS.md` «Отложено П-34»); F3 подтверждается только таблицей SCENES в `scripts/location.gd` и headless-тестом CHAPTER0_OK. Не заявляю, что F3 проверен вводом.

## 5. Найденные проблемы

1. **Warning (не ошибка), известное/информационное** — `data/chapter0.json:9` (линт пишет строку 28): фраза «Место то подобно злат чертогу» упоминает злат чертог рядом с Гэнг-Бэнгом. Линтер пропускает как сравнение; канонический запрет отождествления не нарушен текстом. Текст [п] с ref на задание руководителя. Воспроизведение: `python -I tools/check.py`. Ничего не менял.
2. **Мелкая странность линтера (новая, low)** — номер строки в предупреждении `R-zlat` (28) не соответствует реальной строке файла (9, файл из 23 строк). Доказательство: `grep -n "чертог" data/chapter0.json` → строка 9; `wc -l` → 23.
3. Отложенные P2-замечания прошлых ревью (мёртвые константы, push_error, F3 реальным вводом и др.) — перечислены в `docs/STATUS.md` как [п] П-34, в этой сессии не воспроизводились и не проверялись, остались отложенными.

Критичных проблем не найдено: запуск чистый, все доступные тесты зелёные.

## 6. Ограничения проверки

- `walk_chapter0.gd` не запущен (перезапись существующих скриншотов) — 7-кадровое перелистывание, игнор ввода во время fade, газ на кадрах 2/7, `chapter0_done`, пиксельная проверка текстового окна в этой сессии НЕ проверены. Headless `CHAPTER0_OK` покрывает только логику без кадров.
- Ручной геймплей невозможен: у Godot MCP нет ввода; все наблюдения — из выводов скриптовых тестов.
- FPS не измерялся; визуальный вид фонов/шрифта глазами не оценивался (только тестовые пиксельные проверки прошлых сессий, здесь не повторялись).
- F3 реальным нажатием не проверен (такого теста нет в проекте).
- Сохранение/загрузка, диалоги, счётчик плодов по дверям — в проекте отсутствуют (намеренно, по ARCHITECTURE.md), не тестировались.

## 7. Изменения

- Исходники, сцены, данные, тесты, документы не изменялись: `git diff --stat` пуст, `git status --short` до и после идентичен (только ранее существовавшие untracked-файлы).
- Скриншоты тестом не создавались (walk_chapter0 не запускался; walk_locations скриншоты не пишет).
- Прочитанные документы: `AGENTS.md` (проектный), `docs/STATUS.md`, `docs/CANON_CHEATSHEET.md`, `docs/ARCHITECTURE.md`, `docs/BLOCKERS.md`. SKILL.md не читались (сессия только на запуск/прогон, код не писался).

## Игровое состояние (по выводам скриптовых прогонов)

- Старт игры: сцена базара, фон 480x270, игрок — прямоугольник-заглушка, движется только горизонтально по `ui_left`/`ui_right`, полоса y=240, границы x=10..470 (обе стены достигаются и блокируются — проверено 16-проверочным walk-тестом).
- Клавиши: F2 открывает оазис, F1 возвращает на базар; повторное F1 в базаре — no-op (сцена не перезагружается); флаги и счётчик плодов GameState переживают переключения (autoload). F3 должен открывать главу 0 — подтверждено только таблицей SCENES и headless-тестом, реальным вводом не проверено.
- Глава 0 (по коду и headless-тесту): просмотрщик из 7 кадров из `data/chapter0.json`, листание `ui_accept`, газ на кадрах 2 и 7, после 7-го кадра ставится флаг `chapter0_done`. В этой сессии это окно-поведение не проверялось.
- Незавершённость/бро: игрок — цветной прямоугольник без спрайта; на локациях есть debug-метка (отладочный артефакт в видимой сцене, `scenes/locations/*.tscn`); диалогов, NPC, сохранения нет — сознательно отсутствуют по ARCHITECTURE.md.
