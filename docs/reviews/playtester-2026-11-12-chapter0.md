# playtester | 2026-11-12 | оконный прогон главы 0 «Плёнка»

агент: playtester | дата: 2026-11-12 | scope: оконный запуск проекта (--quit-after 300, main scene bazaar) + оконный walk-тест главы 0. Вывод дословно ниже, без правок.

---

Отчёт по playtest главы 0 «Плёнка» (файлы не менялись, только запуск и чтение).

## 1. Запуск главного окна (bazaar), 300 кадров

Команда:
```
"C:\Users\user\Desktop\Godot\Godot_v4.7.2-stable_win64_console.exe" --path C:/Users/user/Desktop/Siriya --quit-after 300
```
Полный вывод:
```
Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org
OpenGL API 3.3.0 - Build 32.0.101.7084 - Using Device: Intel - Intel(R) UHD Graphics 730

EXIT=0
```
Ошибок, SCRIPT ERROR и предупреждений нет. Главный барнас-сценарий загрузился, 300 кадров отработали, выход 0.

## 2. Скриптовый walk-тест главы 0

Команда:
```
"C:\Users\user\Desktop\Godot\Godot_v4.7.2-stable_win64_console.exe" --path C:/Users/user/Desktop/Siriya --script res://tests/walk_chapter0.gd
```
Полный вывод (exit 0):
```
Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org
OpenGL API 3.3.0 - Build 32.0.101.7084 - Using Device: Intel - Intel(R) UHD Graphics 730

  ok: chapter0 loads and finishes its initial state
  ok: starts at frame 1
  ok: flag chapter0_done absent before frame 7
  ok: frame 1: gas off
  [shot 1] fade.a=0.0000 img=480x270
  ok: frame 1: text window drawn (text-color pixels 85 >= 30)
  ok: accept advances to frame 2 (exactly +1, spare presses ignored)
  ok: frame 2: gas emitting == true
  [shot 2] fade.a=0.0000 img=480x270
  ok: frame 2: text window drawn (text-color pixels 104 >= 30)
  ok: accept advances to frame 3 (exactly +1, spare presses ignored)
  ok: frame 3: gas emitting == false
  [shot 3] fade.a=0.0000 img=480x270
  ok: frame 3: text window drawn (text-color pixels 155 >= 30)
  ok: accept advances to frame 4 (exactly +1, spare presses ignored)
  ok: frame 4: gas emitting == false
  [shot 4] fade.a=0.0000 img=480x270
  ok: frame 4: text window drawn (text-color pixels 109 >= 30)
  ok: accept advances to frame 5 (exactly +1, spare presses ignored)
  ok: frame 5: gas emitting == false
  [shot 5] fade.a=0.0000 img=480x270
  ok: frame 5: text window drawn (text-color pixels 90 >= 30)
  ok: accept advances to frame 6 (exactly +1, spare presses ignored)
  ok: frame 6: gas emitting == false
  [shot 6] fade.a=0.0000 img=480x270
  ok: frame 6: text window drawn (text-color pixels 67 >= 30)
  ok: accept advances to frame 7 (exactly +1, spare presses ignored)
  ok: frame 7: gas emitting == true
  [shot 7] fade.a=0.0000 img=480x270
  ok: frame 7: text window drawn (text-color pixels 70 >= 30)
  ok: flag chapter0_done set after frame 7
  ok: extra ui_accept on frame 7 does nothing
  ok: no transition started after the last frame accept
  WALK_CH0_OK (26 checks)
  EXIT=0
```
26/26 проверок: старт с кадра 1, ui_accept двигает ровно на +1, газ только на кадрах 2 и 7, флаг `chapter0_done` ставится после кадра 7, лишний accept на последнем кадре ничего не делает и переход не начинается. Текстовое окно рисуется на всех кадрах (пиксели текста 67–155 >= 30).

## 3. Скриншоты

`C:\Users\user\Desktop\Siriya\art\screens\` — ровно 7 файлов, все 480x270 (проверено чтением PNG-заголовков через stdlib, PIL в системе нет):
```
ch0_01.png 480x270 8317 bytes
ch0_02.png 480x270 9637 bytes
ch0_03.png 480x270 77184 bytes
ch0_04.png 480x270 71539 bytes
ch0_05.png 480x270 8502 bytes
ch0_06.png 480x270 67418 bytes
ch0_07.png 480x270 6388 bytes
```

## 4. Аномалии

- Ни ошибок, ни SCRIPT ERROR, ни предупреждений в обоих прогонах.
- FPS в выводе не печатался — оценить производительность по этим запускам нельзя (не проверено).
- Наблюдение (не ошибка): размеры PNG заметно скачут между кадрами (6 КБ у кадра 7 против 77 КБ у кадра 3) — вероятно, разные фоны/степень сжатия кадров, визуально не оценивалось. `fade.a=0.0000` во всех снимках — затемнение не активно, что согласуется с логикой перехода.
- Примечание: тест ч.2 запускался как `--script`, он сам поднимал окно/сцену chapter0; открытие главы по F3 из локационных сцен в этот прогон не входило (не проверено).

Сценарий воспроизвёлся полностью, WALK_CH0_OK получен, exit 0 у обоих запусков.
