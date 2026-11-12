# Как поставить правила в новый проект

1. Папка проекта: путь только латиницей и без пробелов (например `C:\\dev\\jak`). Старый путь с кириллицей и пробелом ломал хуки, поэтому новый проект лучше сразу поставить в чистое место.
2. Распакуй этот архив в корень папки проекта. Получится `AGENTS.md`, `docs/`, `tools/`, `.gitignore`.
3. Положи рядом четыре документа канона в `docs/` (имена: `lore_bible_part_A.md`, `game_bible_part_B.md`, `story_scenario_part_C.md`, `source_texts.txt`).
4. Распакуй туда же `jak_art_kit.zip` (скрипт импорта фонов и готовые фоны).
5. Установи Python-пакеты для арт-скрипта: `pip install pillow numpy`.
6. Скажи ZCode путь к Godot: создай файл `tools/godot_path.txt` с одной строкой, путь к консольной версии, например `C:\\Users\\user\\Desktop\\Godot\\Godot_v4.7.2-stable_win64_console.exe`. Или задай переменную окружения `GODOT_BIN`.
7. `git init`, первый коммит с префиксом `process:`.
8. Проверка: `python tools/check.py` должен показать `RESULT: OK` (пока тестов нет) или `INCOMPLETE`, если Godot не найден.
9. Определения субагентов (`game-designer`, `pixel-art-tiles`, `godot-reviewer`, `playtester`) лежат вне проекта, в настройках ZCode. Старые определения могут ссылаться на старые пути и хуки. Отправь ZCode такое задание:

```
Найди определения моих субагентов и скилов (папки .zcode/agents, ~/.zcode/agents, ~/.zcode/skills и любые другие, где лежат game-designer, pixel-art-tiles, godot-reviewer, playtester). Ничего не меняй. Составь таблицу: файл, строки, где упоминаются game/docs, .enforcement, ledger, gates.json, hooks, hash-отчёты, docs/reviews, docs/qa, game/ как корень проекта, AGENTS.md старого образца. Покажи мне таблицу и жди решения, что править.
```
