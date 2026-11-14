# STATUS - SIRIYA

Обновлять после каждого блока работы. Только факты с доказательствами (вывод команд).

## Состояние

- Дата: 2026-11-14
- Репозиторий: ветка main, HEAD 3b3bcba; main опережает origin/main на 11 коммитов, push не выполнялся. Неотслеживаемые пути: 24 прежних (до создания LICENSES.md), группами: 2 плана сессий ZCode (.zcode/plans/plan-sess_*.md); art/backup_v1/ — bazaar.png, bazaar.png.import, gangbang.png.import, gangbang_preview_x3.png, gangbang_preview_x3.png.import, oasis.png, oasis.png.import (art/backup_v1/gangbang.png отслеживается Git (коммит "260fb50") и не входит в число неотслеживаемых файлов); палитры v1/v2 (art/palette_v1.*, art/palette_v2.*); art/preview_icon/, art/screens/; 7 отчётов аудита (docs/reviews/*-2026-11-14-audit.md); плюс дополнительный новый файл docs/LICENSES.md. Общее количество теперь 25 (сверено с git status --short). Не удаляются и не коммитятся.
- Коммиты 2026-11-13 (не были отражены в этом файле до актуализации): cb93ca2 — норма «Жебь» [у] + R-zhebi-ins + тест правил линта + регламент v2 (AGENTS.md); 71525b1 — палитра v3 + фоны bazaar/oasis с дизерингом + import_bg.py v2 + превью; 260fb50 — v1-оригинал gangbang; 97458d9 — исходник иконки летописца v2; 97877a6 — канонизация project.godot + default_texture_filter=0 (Nearest); 3b3bcba — конфигурация ZCode + исторические планы вех.
- Проверки (три отдельные команды, не один запуск; прогоны 2026-11-14): `python tools/check.py` -> `RESULT: OK` (canon: 0 ошибок, 1 предупреждение R-zlat data/chapter0.json:28; 5 PASS: CHAPTER0_OK, STATE_TESTS_OK, LOCATION_TESTS_OK, PLAYER_TESTS_OK, SCRIBE_ICON_OK); оконный `tests/walk_locations.gd` -> `WALK_TESTS_OK` (16 проверок), exit 0 — отдельный прогон, в check.py не входит; `python tools/test_canon_rules.py` -> `CANON_RULES_TEST_OK` (5 случаев) — отдельный прогон, в check.py не входит; запуск через Godot MCP -> консоль без ошибок (`errors: []`).
- Известные нерешённые проблемы главы 0 (визуальное исправление НЕ выполнено): газ невидим на кадрах 2 и 7 (цвет газа совпадает с фоном); хвосты частиц газа остаются на кадрах 3-5; диалоговое окно наезжает на верх рамки кадра 2; окно плоское (без границы, серое на светлом, высота одна). Принятые в переписке решения: кадр 3 остаётся, кадр 7 правится, окно — вариант Б [у], Д-30 меняется; план исправления не исполнен.
- Прочее нерешённое: перо иконки летописца не читается полностью (плюмаж не различим — решение за владельцем; исходник v2 закоммичен 97458d9, третий круг не выполнялся); П-34/П-35/П-36 — отложенные P2-хвосты ревью; LICENSES.md отсутствовал до 2026-11-14 (создан актуализацией документации, см. журнал).
- В работе: актуализация документации по аудиту 2026-11-14 (без коммита).

## Что сделано (первый срез)

- Godot-проект создан: project.godot (480x270, Nearest, viewport/keep/integer, окно 960x540, gl_compatibility, autoload GameState, main scene bazaar, name "SIRIYA").
- scripts/game_state.gd (флаги + счётчик плодов 0-3, ровно 5 методов по контракту), scripts/player.gd (заглушка-прямоугольник, ходьба влево-вправо, полоса y 225-258, границы x 10-470), scripts/location.gd (F1/F2, no-op для текущей локации).
- scenes/locations/bazaar.tscn, oasis.tscn (фоны из assets/backgrounds/, debug-метка), scenes/characters/player.tscn.
- Тесты: tests/test_game_state.gd, test_player.gd, test_locations.gd (headless, без кадров), tests/walk_locations.gd (оконный, реальный ввод через Input.parse_input_event).
- docs/ARCHITECTURE.md (контракт первого среза, автор текста ecc:architect).

## Следующий шаг

Приоритеты определяет владелец проекта; перечень ниже — кандидаты из аудита 2026-11-14, не утверждённая дорожная карта.
- Кандидаты: актуализация документации (исполняется 2026-11-14, без коммита); визуальное исправление главы 0 (решения приняты в переписке, не исполнено); третий круг иконки на scribe_source_v2.png; wiring tools/test_canon_rules.py в tools/check.py (находка аудита); LAST_FRAME из данных вместо константы (chapter0.gd:18, находка аудита); утверждение Д-01...Д-36 пачкой; push 11 коммитов (по [у]).
- Отложено ([п] П-34): замечания godot-reviewer/ecc:code-reviewer уровня P2 (мёртвые константы, push_error, current_frame до валидации, текст плейсхолдера, типизация, порядок guard-а walk-теста, F3 реальным вводом) — не вносились по правилу «исправлять только нарушения». Абзац «Система глав» в ARCHITECTURE.md — внесён (ecc:doc-updater).

## Нужны тексты (от руководителя)

- (пусто)

## Открытые вопросы к руководителю

- Раздел 5 в `docs/PROJECT_CONTEXT.md`.
- BLOCKERS 2026-11-12 (хвост): playtester повторён 2026-11-14 (полный аудит); повтор godot-reviewer по файлам первого среза (project.godot, game_state.gd, player.tscn, test_game_state.gd) не выполнялся — хвост остаётся открытым до фактического повторного ревью этих файлов.
- Утверждение пачкой Д-01...Д-36 и П-33/П-35/П-36.
- Модель выхода из главы 0 (Д-31) перед главой 1; перо иконки летописца (третий круг на scribe_source_v2.png или приём текущего вида).

## Журнал (одна строка на блок работы: дата | что | результат проверки)

- 2026-11-12 | Godot-ядро первого среза: project.godot, GameState, игрок-заглушка, bazaar/oasis, F1/F2; тесты headless + оконный walk | check.py RESULT: OK; STATE_TESTS_OK 15; PLAYER_TESTS_OK 11; LOCATION_TESTS_OK 33; WALK_TESTS_OK 16 (число исправлено 15→16: те прогоны шли до добавления 16-й проверки, см. ниже); MCP-консоль без ошибок
- 2026-11-12 | Ревью godot-reviewer круг 1 (P0/P1 нет, 7xP2; исправлены P2-3/4/5/7), повторный полный прогон всех тестов после правок | STATE_TESTS_OK 15; PLAYER_TESTS_OK 11; LOCATION_TESTS_OK 33; WALK_TESTS_OK 16 (см. выше); check.py RESULT: OK; MCP errors: []
- 2026-11-12 | Круг 2 ревью и playtester упали по квоте субагентов | запись в BLOCKERS.md; замена своими прогонами не делалась молча, доказательства — выводы команд выше
- 2026-11-12 | Палитра v2: import_bg.py переведён на OKLab (k-means, 12 якорей, ΔE×100: пары ≥4.0, снэп якоря 6.0, тёплых ≤10), convert — OKLab-подбор, --measure-only; palette_v2 48 цветов, min pair dE 4.14; фоны перегнаны в art/preview_v2/ (gangbang mean dE 10.71→2.16); v1 сохранена | вывод скрипта; assets/backgrounds не тронут
- 2026-11-12 | Норма «Жебь» [у]: часть С 2 места (Жебь/с Жебью), новое правило линта R-zhebi-ins, тест 5/5, чек-лист/памятка/П-23 обновлены | CANON_RULES_TEST_OK; grep до/после в отчёте сессии
- 2026-11-12 | Дизеринг: Bayer 4x4 в OKLab с маской плавности (3x3 < 2.0, по LANCZOS-исходнику), амплитуда от палитры (кап 6.0), дефолт strength 0.4, флаг off по умолчанию; sha256 без флага == preview_v2 (3/3); превью в art/preview_v2_dither/; предложение П-33 (промежуточный голубой) | таблица метрик и счётчики неба в отчёте; assets/backgrounds и preview_v2 не тронуты; check.py RESULT: OK; MCP errors: []
- 2026-11-12 | П-33 реализован: palette_v3 (48; новый #79C1E3 по линии 9CD1EA→3FA9D9; убран #FFBA53 — ремонт унаследованных нарушений пар v2, отклонение от правила «наименее используемый» записано в Д-21); проверки переведены на квантованные цвета; превью art/preview_v3/ | небо: ступени 882→545, прыжок 6.73→5.39; базар/оазис: 0 px >ΔE 6.0; вода/купол не ухудшены; sha256 12 файлов v2 совпали до/после; check.py RESULT: OK; MCP errors: []
- 2026-11-12 | 16-я проверка walk-теста «player stops at the right bound» добавлена правкой руководителя перед коммитом cf056fb (git show cf056fb:tests/walk_locations.gd = 16 `_check(` вызовов); записи журнала ниже в тот день делались до этой правки, отсюда «15» | реальный прогон: WALK_TESTS_OK (16 checks), EXIT=0
- 2026-11-12 | Фоны v3 перенесены в assets/backgrounds/: bazaar+gangbang с дизером, oasis без; бэкап старых в art/backup_v1/ (3 фона + gangbang_preview_x3); sha256 до/после; godot --import без ошибок; скриншоты art/screens/{bazaar,oasis}.png (игрок верифицирован в пикселях, 11/11) | bazaar mean 2.62/2.65, oasis 2.54, gangbang 2.13/2.18; check.py RESULT: OK; MCP errors: []
- 2026-11-12 | Веха глава 0 закрыта: агент-петля завершена (planner задним числом, code-reviewer дельты, game-designer текстов, doc-updater), ecc:verification-loop применён; ARCHITECTURE.md дополнен разделом 7 «Система глав» | check.py RESULT: OK; WALK_CH0_OK (26 checks)
- 2026-11-12 | Иконка летописца для окна диалога: tools/art/import_icon.py (ключ фона по углам с заливкой от краёв, обрезка/вписывание 44 px в 48x48, LANCZOS, квантизация в palette_v3 по OKLab Д-18, слияние редких цветов до 16) + tests/test_scribe_icon.gd (8 проверок) + assets/ui/scribe_icon.png; вид иконки [п], 48x48 [у] руководителя; ecc:security-reviewer: PASS, 0 P0/P1, 5xP2 ([п] П-35) | тест падал до ассета (EXIT=1), после: SCRIBE_ICON_OK (8 checks) EXIT=0; check.py RESULT: OK (5 PASS); MCP errors: []
- 2026-11-12 | Иконка переработана (второй круг, Д-36): к-means по пикселям фигуры -> доминантная метка ячейки (не среднее), majority-фильтр, удаление меток < 4 px, контур #3B3251, порог альфы 0.4 (одна коррекция); итог: 7 цветов, сироты 1.8%, связность 100%, добавлено 0 px, непрозрачных 733; тест расширен до 13 проверок (5 новых, старые 8 без изменений), сначала падал на 3/13; ecc:security-reviewer круг 1: 0 P0, 2 P1 + 4 P2 (не вносились, [п] П-36), после 2 правок круг 2 п.6.8: PASS 0 P0/P1, 7xP2 ([п] П-36); перо: плюмаж не различим (решение за руководителем) | SCRIBE_ICON_OK (13 checks); check.py RESULT: OK (5 PASS); MCP errors: []
- 2026-11-13 | 6 коммитов без записи в этот файл в момент работы: cb93ca2 (норма «Жебь» [у], R-zhebi-ins, тест правил линта, регламент v2), 71525b1 (палитра v3, фоны bazaar/oasis с дизерингом, import_bg.py v2, превью), 260fb50 (v1-оригинал gangbang), 97458d9 (исходник иконки v2), 97877a6 (канонизация project.godot, default_texture_filter=0), 3b3bcba (конфигурация ZCode, исторические планы) | сверка фактов — аудит 2026-11-14 (ecc:doc-updater)
- 2026-11-14 | полный аудит проекта: 7 агентов п.6.3 (ecc:code-reviewer, playtester, ecc:doc-updater, ecc:architect, godot-reviewer, ecc:security-reviewer, game-designer; отчёты docs/reviews/*-2026-11-14-audit.md); P0 нет; High: LAST_FRAME=7 дублирует данные (chapter0.gd:18), test_canon_rules.py не вызывается из check.py, документационный кластер (STATUS/CANON_CHECKLIST/PROJECT_CONTEXT/LICENSES), непинненные pillow/numpy; walk_chapter0 не перезапускался (отказ перезаписи существующих скриншотов) | check.py RESULT: OK; WALK_TESTS_OK (16 checks); CANON_RULES_TEST_OK (5 cases); MCP errors: []
- 2026-11-14 | актуализация документации по аудиту: этот файл, CANON_CHECKLIST.md (ссылки на разделы AGENTS), PROJECT_CONTEXT.md (дерево, палитра v3, сохранение как план), BLOCKERS.md (шаблон, счётчик 15->16, статус хвоста), DECISIONS.md (пометки реализации без смены статусов), LICENSES.md создан | правки без коммита; git diff --stat в отчёте этапа
