# План вехи: Глава 0 «Плёнка» MVP (2026-11-12)

**СОСТАВЛЕН ЗАДНИМ ЧИСЛОМ после выполнения вехи (AGENTS.md п.6.3)** — восстановлен по факту: STATUS.md, DECISIONS.md (Д-22…Д-33), docs/reviews/, файлы вехи. Автор плана: ecc:planner (текст дословно).

**Цель:** просмотрщик главы 0 «Плёнка» — 7 кадров из data/chapter0.json, перелистывание по ui_accept, текстовое окно, газ на кадрах 2 и 7, флаг chapter0_done через существующий GameState.set_flag; открытие главы по F3.

**Объём:** входит — data/chapter0.json (тексты [п] с src/ref), scenes/chapters/chapter0.tscn, scripts/chapter0.gd, F3 в scripts/location.gd, tests/test_chapter0.gd + tests/walk_chapter0.gd. НЕ входит: главы 1-9, диалоговая система, выбор 0.6, сохранение/загрузка, звук, NPC, файл фона igloo.png (плейсхолдер, Д-24), возврат из главы (Д-31).

**Шаги (как фактически выполнялись):**
1. Данные + тест данных: 7 кадров с src/ref; headless-тест CHAPTER0_OK; усилен по Д-33 (ref непустой).
2. Сцена + логика + F3: chapter0.tscn + chapter0.gd (фейд-машина 0/1/2, busy, шрифт 10 по Д-23); F3 в SCENES location.gd с пином в test_locations (Д-22); set_flag("chapter0_done") на кадре 7 (Д-25).
3. Газ + рамка: CPUParticles2D (Д-27, палитра #3B3251, ImageTexture 4x4), рамка плёнки bg "solid_frame" (Д-28, Д-30); после ревью — P1: газ из данных (Д-32).
4. Оконный walk-тест: tests/walk_chapter0.gd — WALK_CH0_OK, 26 проверок, 7 скриншотов ch0_01..07.png; playtester прогнал главный запуск + walk.
5. Docs: Д-22…Д-33 в DECISIONS.md, журнал STATUS.md, три отчёта в docs/reviews/ (godot-reviewer, playtester, ecc:architect); абзац «Система глав» в ARCHITECTURE.md отложен.

**Критерии готовности (все выполнены):**
- [x] python tools/check.py -> RESULT: OK (canon 0 ошибок; CHAPTER0_OK, STATE/LOCATION/PLAYER_TESTS_OK; тест подхвачен глобом автоматически, Д-29)
- [x] Оконный walk: WALK_CH0_OK (26 проверок), exit 0; главный запуск без ошибок консоли
- [x] Скриншоты ch0_01..07.png — ровно 7 шт, все 480x270, текстовое окно нарисовано (пиксельная проверка >= 30 попаданий)
- [x] Ревью агентов: godot-reviewer (P0 нет; P1 исправлен Д-32; P2 — [п], не вносились), playtester, ecc:architect — отчёты в docs/reviews/
