# Как поставить правила в новый проект

1. Папка проекта: путь только латиницей и без пробелов (например `C:\\dev\\jak`). Старый путь с кириллицей и пробелом ломал хуки, поэтому новый проект лучше сразу поставить в чистое место.
2. Распакуй этот архив в корень папки проекта. Получится `AGENTS.md`, `docs/`, `tools/`, `.gitignore`.
3. Положи рядом четыре документа канона в `docs/` (имена: `lore_bible_part_A.md`, `game_bible_part_B.md`, `story_scenario_part_C.md`, `source_texts.txt`).
4. Распакуй туда же `jak_art_kit.zip` (скрипт импорта фонов и готовые фоны).
5. Установи Python-зависимости. Два ОКРУЖЕНИЯ, не смешивать в одном venv:

   А) Арт-инструменты (`tools/art/import_bg.py`, `tools/art/import_icon.py`) - из `requirements.txt`. Проверенный базовый интерпретатор для арт-инструментов - Python 3.12:
   - Windows: `py -3.12 -m pip install -r requirements.txt`
   - macOS/Linux: `python3.12 -m pip install -r requirements.txt`
   Арт-скрипты нужно запускать тем же интерпретатором, в который установлены пакеты.

   Б) Проверочное окружение для `tools/check.py` (этап E-6A): правила канона из `tools/canon_rules.json` исполняются ТОЛЬКО движком Google RE2 (линейное время). Отдельный venv на Python 3.12 из `requirements-check.txt`:
   - Windows: `py -3.12 -m venv "%TEMP%\re2-check-312"` затем `"%TEMP%\re2-check-312\Scripts\python.exe" -m pip install -r requirements-check.txt`; запуск проверки: `"%TEMP%\re2-check-312\Scripts\python.exe" tools/check.py`
   - macOS/Linux: `python3.12 -m venv "$TMPDIR/re2-check-312"` затем `"$TMPDIR/re2-check-312/bin/python" -m pip install -r requirements-check.txt`; запуск проверки: `"$TMPDIR/re2-check-312/bin/python" tools/check.py`
   Любой каталог venv допустим; зафиксированное рабочее окружение проекта - `%TEMP%\re2-test-312` с `google-re2==1.1.20251105` (см. `requirements-check.txt`). Не устанавливать RE2 в окружения арт-инструментов и не объединять списки зависимостей.

   Fail-secure: если RE2 недоступен тому интерпретатору, которым запущен `check.py`, канон-линт печатает `[ERROR] R-setup ... RE2 binding not available` и завершается `RESULT: FAIL`. Fallback на Python `re` отсутствует: `check.py` не импортирует `re` вовсе. `tools/test_canon_rules.py` - самостоятельный legacy-тест на Python `re`, автоматическим путём E-6A не запускается (запуск вручную: `python tools/test_canon_rules.py`).
6. Скажи ZCode путь к Godot: создай файл `tools/godot_path.txt` с одной строкой, путь к консольной версии, например `C:\\Users\\user\\Desktop\\Godot\\Godot_v4.7.2-stable_win64_console.exe`. Или задай переменную окружения `GODOT_BIN`.
7. `git init`, первый коммит с префиксом `process:`.
8. Проверка: запускай `tools/check.py` интерпретатором проверочного venv из пункта 5Б (Windows: `"%TEMP%\re2-check-312\Scripts\python.exe" tools/check.py`). Ожидаемо `RESULT: OK` (пока тестов нет) или `INCOMPLETE`, если Godot не найден; при отсутствии RE2 - `[ERROR] R-setup` и `RESULT: FAIL` (fail-secure).
9. Определения субагентов (`game-designer`, `pixel-art-tiles`, `godot-reviewer`, `playtester`) лежат вне проекта, в настройках ZCode. Старые определения могут ссылаться на старые пути и хуки. Отправь ZCode такое задание:

```
Найди определения моих субагентов и скилов (папки .zcode/agents, ~/.zcode/agents, ~/.zcode/skills и любые другие, где лежат game-designer, pixel-art-tiles, godot-reviewer, playtester). Ничего не меняй. Составь таблицу: файл, строки, где упоминаются game/docs, .enforcement, ledger, gates.json, hooks, hash-отчёты, docs/reviews, docs/qa, game/ как корень проекта, AGENTS.md старого образца. Покажи мне таблицу и жди решения, что править.
```
