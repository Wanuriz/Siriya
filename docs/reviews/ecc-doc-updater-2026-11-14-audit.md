# ecc:doc-updater | 2026-11-14 | аудит состояния документации (task: FULL PROJECT AUDIT)

агент: ecc:doc-updater | дата: 2026-11-14 | scope: docs/* против фактического состояния репозитория, без правок. Вывод дословно ниже, без правок.

---

Аудит завершён. Файлы не изменялись; все команды были только читающими (git log/status/ls/grep, запуск `python tools/check.py`).

# Аудит документации SIRIYA (2026-11-14)

## Сверка с репозиторием (фактическое состояние)

- `git log --oneline -20`: 20 коммитов, последние — 2026-11-13 03:58 (`3b3bcba`, `97877a6`, `97458d9`, `260fb50`, `71525b1`, `cb93ca2`), предыдущие 2026-11-12 (последний `4408163` 23:55 — последний коммит, трогавший `docs/STATUS.md`).
- `git status --short`: 17 неотслеженных путей — `.zcode/plans/plan-sess_4b9ef712….md`, `plan-sess_b93e7e8b….md`, `art/backup_v1/` (кроме `gangbang.png`), `art/palette_v1.*`, `art/palette_v2.*`, `art/preview_icon/`, `art/screens/`.
- Свежий прогон проверки: `python tools/check.py` → `canon: 0 errors, 1 warnings` (warn `R-zlat data/chapter0.json:28`), `tests: 5 passed, 0 failed`, `RESULT: OK` (маркеры CHAPTER0_OK, STATE_TESTS_OK, LOCATION_TESTS_OK, PLAYER_TESTS_OK, SCRIBE_ICON_OK).

---

## (1) Устаревшие / противоречащие репозиторию утверждения по документам

### P1

1. **`C:\Users\user\Desktop\Siriya\docs\STATUS.md:9`** — «Тесты: … 3 PASS: STATE_TESTS_OK, LOCATION_TESTS_OK, PLAYER_TESTS_OK». Факт: тестовых наборов уже 5 (добавлены `tests/test_chapter0.gd` → CHAPTER0_OK и `tests/test_scribe_icon.gd` → SCRIBE_ICON_OK); свежий прогон check.py даёт «5 passed». Противоречие зафиксировано внутри самого файла: строки 46–47 журнала пишут «check.py RESULT: OK (5 PASS)». Блок «Состояние» — первое, что читает сессия по AGENTS.md п.2.
2. **`C:\Users\user\Desktop\Siriya\docs\CANON_CHECKLIST.md:3` и строки 9, 39, 41, 42, 43** — ссылки на «AGENTS.md (раздел 2)», «AGENTS §2», «AGENTS §20», «AGENTS §21, 3.12», «AGENTS §22», «AGENTS §23». Факт: действующий `AGENTS.md` (v2, переписан коммитом `cb93ca2` 2026-11-13, diff 186 строк) содержит 14 разделов; раздела 2 «правила канона» нет (правила канона — п.4), §20–§23 и п.3.12 не существуют. Приёмочный чек-лист ссылается на несуществующие разделы — источник правил не находится по ссылке.
3. **`C:\Users\user\Desktop\Siriya\docs\PROJECT_CONTEXT.md:22-33` (дерево «Структура проекта»)** — описывает `scenes/ locations/, ui/, characters/` (факт: `scenes/ui/` не существует, есть `scenes/chapters/chapter0.tscn`, не упомянут), `data/ dialogue/, chapters/, endings/` (факт: ни одного из этих подкаталогов нет; `data/` содержит плоский `data/chapter0.json`), `assets/ backgrounds/, characters/, ui/, audio/` (факт: `assets/characters/` и `assets/audio/` не существуют, есть не упомянутый `assets/ui/scribe_icon.png`). Не упомянуты `scripts/chapter0.gd`, `tools/art/import_icon.py`, `tools/test_canon_rules.py`. Агент, планирующий размещение файлов по этому дереву, будет создавать пути, которых схема проекта не использует.
4. **`LICENSES.md` не существует** — на него ссылаются `PROJECT_CONTEXT.md:41` («записывать в LICENSES.md») и `AGENTS.md:110` (п.8). Проверка: `ls LICENSES.md` → «No such file or directory». Требование п.8 AGENTS «ассеты … с записью в LICENSES.md» неисполнимо в текущем виде (ассеты уже добавлены — `assets/ui/scribe_icon.png`, `scribe_source*.png` — и записи некуда).

### P2

5. **`docs/STATUS.md:7-8`** — «Дата: 2026-11-12», «Закоммичено: ничего (коммиты не заказаны руководителем)». Факт: репозиторий содержит 20 коммитов; 6 из них (2026-11-13 03:58) сделаны после последней правки STATUS и не отражены в журнале (см. п.5 отчёта). Строка 43 журнала сама ссылается на «коммит cf056fb», т.е. «ничего» читается только как «в той сессии».
6. **`docs/STATUS.md:9`** — «canon: 0 ошибок» без упоминания постоянного предупреждения `R-zlat` на `data/chapter0.json` (текст кадра 3 «Место то подобно злат чертогу» — канон И2). Предупреждение воспроизводится в каждом прогоне и нигде в STATUS не расшифровано (AGENTS п.9 требует отвечать на каждый warn).
7. **`docs/ARCHITECTURE.md:26`** — контракт `func get_flag(flag_name: String) -> bool`. Факт: `scripts/game_state.gd:19` — `func get_flag(flag_name: String, default: bool = false) -> bool`. Сигнатура документирована уже после кода (параметр был в `cf056fb`), но в контрактном документе не отражена.
8. **`docs/DECISIONS.md:12` (Д-04)** — «без хуков и журнала вызовов | AGENTS.md | ожидает [у]». Факт: действующий `AGENTS.md:109` (п.8) предписывает «ECC и его хуки (GateGuard) не менять. GateGuard перед первой правкой просит фактов». Запись Д-04 противоречит файлу, на который она указывает.
9. **`docs/BLOCKERS.md:11`** — «(пока пусто)» перед фактической записью 2026-11-12 (шаблонная строка не убрана). **`docs/BLOCKERS.md:18`** — «walk_locations оконно (WALK_TESTS_OK, 15)»: фактическое число проверок 16 (исправление задокументировано только в `STATUS.md:43`).
10. **`docs/CANON_CHEATSHEET.md:4`** — «Не прочитано: сцены глав 2-9 в части С (строки 124-585)». Факт: `docs/story_scenario_part_C.md` сейчас 707 строк; диапазон «124-585» не соответствует текущей разметке файла (правки Д-17/коммит `cb93ca2`). Читать-статус по этим строкам не подтверждаем.
11. **`docs/PROJECT_CONTEXT.md:18`** — «Фоны готовы: `assets/backgrounds/bazaar.png`, `oasis.png`». Факт: там же лежит и используется главой 0 `gangbang.png` (коммит `8ecdc4b`).
12. **`docs/PROJECT_CONTEXT.md:37`** — «…сохранение и загрузка в JSON» читается как имеющаяся возможность; `ARCHITECTURE.md:45` прямо называет сохранение/загрузку «намеренно отсутствующей». Требуется явная пометка «план».

---

## (2) Решения DECISIONS.md vs фактический код

Проверено попарно «запись → код»:

- **Д-04 — единственное реальное расхождение** (см. п.8 выше): запись «без хуков» при действующем GateGuard-пункте в AGENTS.md v2.
- **Д-02 (тайл 16)** — в коде/арте тайлов нет вообще; предмет решения не реализован и не опровергнут (проверить нечем).
- Остальные «ожидает [у]» подтверждены кодом дословно (выборка доказательств):
  - Д-01/05/06/07/13/15 → `project.godot:13-14,23-28,32-35`;
  - Д-09/12 → `scripts/player.gd:7-16,24` + `scenes/characters/player.tscn:8-13` (цвет 0.85/0.25/0.2, 20x24);
  - Д-10/22 → `scripts/location.gd:9-13,16-25` (F1/F2/F3, no-op);
  - Д-11 → `scripts/game_state.gd:15-32` (пять методов, `flag_name`, no-op в location.gd:23);
  - Д-14 → `scenes/locations/bazaar.tscn:22` (text = "bazaar");
  - Д-19/20/21 → `tools/art/import_bg.py:55-60` (шесть сидов дословно), `:759` (--dither, default None = off), `art/palette_v3.hex:48` (79C1E3; FFBA53 отсутствует);
  - Д-16 → `tools/canon_rules.json:14` (R-zhebi-ins);
  - Д-23/30/31 → `scenes/chapters/chapter0.tscn:41-74` (font_size 10, окно 8..472/6..80, рамка 155..325/75..195, кайма 10 px, цвета #F5CBA9/#FDE073), отсутствие location.gd (tscn:3 — только chapter0.gd);
  - Д-24 → `scripts/chapter0.gd:133-140` + отсутствие `assets/backgrounds/igloo.png` (проверено: файла нет);
  - Д-25/27/32 → `chapter0.gd:143,149,70-85` (gas.emitting из данных; set_flag("chapter0_done"); параметры газа дословно);
  - Д-28 → `data/chapter0.json` (bg: "solid"/"solid_frame"/файл);
  - Д-29 → `tools/check.py:172` (glob `tests/test_*.gd`);
  - Д-33 → `tests/test_chapter0.gd:11,73-74` (REQUIRED_FIELDS с ref, проверка непустого ref);
  - Д-34/35/36 → `tools/art/import_icon.py:53` (BG_KEY_DE = 6.0), `:55` (KMEANS_K = 9); `tests/test_scribe_icon.gd:10-20` (OPAQUE 350..1500, UNIQUE_MAX 16, STRICT 10, ORPHAN 8%, COMPONENT 95%, MAJOR 3x4%, контур 3B3251);
  - Д-03/08/13/26 — подтверждены (нет платформинга; name "SIRIYA"; main_scene bazaar; `scenes/chapters/chapter0.tscn` существует).
- Статусы «утверждено [у]» (Д-08, Д-16, Д-17, Д-18, Д-35-частично) против кода не противоречят.

---

## (3) Предложения PROPOSALS.md, чей предмет уже есть в коде

- **П-33** — предмет реализован (`art/palette_v3.png/.hex`, фон перенесён в `assets/backgrounds/`), но статус-колонка (`PROPOSALS.md:60`) уже честно отражает это («утверждено [у] … Перенесено») — расхождения нет, фиксирую как «реализовано и помечено».
- **П-16** — частично: форма присутствия Летописца де-факто начата в коде — метка «Летописец» в окне текста главы 0 (`scenes/chapters/chapter0.tscn:56`, `scripts/chapter0.gd:145-147`) и спикер в `data/chapter0.json:2` при статусе «ожидает [у]» (`PROPOSALS.md:31`). Полный предмет П-16 (вступление/записи между главами/итоговые перечни) не реализован — пометка частичного пересечения, не нарушение.
- Остальные проверяемые предложения подтверждены как НЕ реализованные (статусы честные): П-32 (в `project.godot` нет секции [input]; player.gd:24 использует ui_left/ui_right), П-34 (мёртвые константы `chapter0.gd:13,15` на месте, push_error нет, `frames: Array` нетипизирован, плейсхолдер захардкожен в tscn:83, мигалка безусловна), П-35/П-36 (в `import_icon.py` нет guard'а размера исходника и чистых SystemExit-ошибок палитры), П-24 (`atlas.json` отсутствует), П-30 (README.md и LICENSES.md отсутствуют).

---

## (4) PROJECT_CONTEXT и INSTALL.md: файлы/команды, которых нет в описанном виде

- **PROJECT_CONTEXT.md:22-33** — см. P1 №3 (структурное дерево): несуществующие `scenes/ui/`, `data/dialogue|chapters|endings/`, `assets/characters|audio/`.
- **PROJECT_CONTEXT.md:41** — `LICENSES.md` не существует (см. P1 №4).
- **PROJECT_CONTEXT.md:39** — команда `python tools/art/import_bg.py convert … --palette … --preview` проверена по CLI скрипта (`import_bg.py:752-757`: subcommand `convert`, обязательный `--palette`, `--preview`) — **существует как описано**; `tools/art/import_bg.py` существует. (примечание приёмщика: путь палитры в этой строке — `art/palette.png`, устаревший v0-файл; см. находку ecc:code-reviewer №5 - сама команда валидна, аргумент устарел)
- **INSTALL.md** — противоречий с репозиторием не найдено: `tools/godot_path.txt` существует и игнорируется (`.gitignore:4`, `check.py:162`); логика «RESULT: OK (пока тестов нет) / INCOMPLETE, если Godot не найден» подтверждена кодом `check.py:172-179,217`; зависимости `pillow numpy` подтверждены импортами (`import_bg.py:31-32`, `import_icon.py:40-41`); четыре канонических документа из шага 3 существуют в `docs/` с точными именами.
- Вне репозитория (проверить нельзя): `jak_art_kiz.zip` → `jak_art_kit.zip` (INSTALL.md:7), определения субагентов в `~/.zcode/agents` (INSTALL.md:11-15).

---

## (5) Что STATUS.md НЕ фиксирует о недавней работе

1. Шесть коммитов 2026-11-13 03:58 не имеют записей в журнале STATUS (последняя правка — 4408163, 2026-11-12 23:55):
   - `cb93ca2` — переработка `AGENTS.md` (регламент v2, 186 строк diff) — статусный файл об этом не знает, при этом Д-04 противоречит новому AGENTS;
   - `97877a6` — канонизация Godot + `default_texture_filter=0` (сейчас `project.godot:32`);
   - `97458d9` — `assets/ui/scribe_source_v2.png`;
   - `260fb50` — `art/backup_v1/gangbang.png`;
   - `71525b1` — коммит палитры v3/import_bg v2/превью (само событие в журнале есть, датировано 11-12, коммит — нет);
   - `3b3bcba` — `.zcode/config.json` и два закоммиченных плана сессий.
2. 17 неотслеженных путей в рабочем дереве (полный список в начале отчёта), включая `art/screens/` (скриншоты, на которые отправляет «Следующий шаг» STATUS:22) и `art/preview_icon/` — нигде не помечены как «не закоммичено»; `STATUS:8` «Закоммичено: ничего» этого состояния не описывает.
3. Два новых плана сессий `.zcode/plans/plan-sess_4b9ef712…` и `plan-sess_b93e7e8b…` (не закоммичены) — работа некой сессии после 23:55 11-12 не отражена в STATUS.
4. Постоянный warn `R-zlat` (check.py) не зафиксирован (см. P2 №6).
5. Хвост блокера (BLOCKERS.md:21 «повтор godot-reviewer/playtester перед следующим ревью»): для главы 0 `docs/reviews/godot-reviewer-2026-11-12-chapter0.md` и `playtester-2026-11-12-chapter0.md` существуют, но снятие хвоста для файлов первого среза (project.godot, game_state.gd, player.tscn, test_game_state.gd — предмет круга 2 из BLOCKERS.md:16) в STATUS/BLOCKERS не зафиксировано; `STATUS:32` всё ещё держит вопрос открытым.

---

## Итог по severity

- **P1 (4):** STATUS.md:9 «3 PASS»; CANON_CHECKLIST.md:3+9+39-43 ссылки на несуществующие разделы AGENTS.md; PROJECT_CONTEXT.md:22-33 структурное дерево с несуществующими каталогами; LICENSES.md отсутствует при обязательных ссылках (PROJECT_CONTEXT.md:41, AGENTS.md:110).
- **P2 (8):** STATUS.md:7-8 (дата/«ничего не закоммичено»), STATUS.md:9 (скрытый warn R-zlat), ARCHITECTURE.md:26 (сигнатура get_flag), DECISIONS.md Д-04 vs AGENTS.md:109, BLOCKERS.md:11 и :18, CANON_CHEATSHEET.md:4 (строки 124-585 vs 707), PROJECT_CONTEXT.md:18 (gangbang.png) и :37 (сохранение как факт), PROPOSALS.md П-16 (частичное пересечение).

## Не проверено

- Оконные walk-тесты (`walk_locations`, `walk_chapter0`) не запускал — требуют окна; актуальность «WALK_TESTS_OK (16)»/«WALK_CH0_OK (26)» подтверждена только статическим подсчётом мест `_check(` (26 для ch0 сходится) и PASS headless-тестов.
- Заявления STATUS о Godot MCP «errors: []» — MCP в этой сессии недоступен.
- Д-17 («часть С правлена ровно в 2 местах») — содержательный канон-аудит части С не проводился.
- Д-18 (пороги 4.0/6.0/≤10) — проверены сиды и шкала OKLab*100 в коде, сами пороги численно не перепроверены.
- Содержимое 8 файлов `docs/reviews/` (только наличие), runtime-счётчики 15/11/33 (проверены только маркеры PASS), факт «прочитаны ли сцены 2-9» из CANON_CHEATSHEET.md:4, `jak_art_kit.zip` и определения субагентов вне репозитория.
- Проверка не меняла файлов: после прогонов `git status --short` идентичен исходному.
