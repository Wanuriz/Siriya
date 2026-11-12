# ecc:code-reviewer | 2026-11-12 | дельта вехи chapter0 (повтор после таймаута, суженный scope)

агент: ecc:code-reviewer | дата: 2026-11-12 | scope: дельта вехи — location.gd (F3), tests/test_locations.gd (пин F3), tests/walk_chapter0.gd, tests/test_chapter0.gd, кросс-файловая согласованность data/chapter0.json ↔ chapter0.gd. Первая попытка агента прервалась по таймауту 600 с (частичный вывод без находок), это повтор по п.6.5 с суженным scope. Вывод дословно ниже, без правок.

---

## Code Review — веха Chapter 0 (narrowed scope)

**1. scripts/location.gd:12 (F3 line) — clean.** Dictionary addition only; the F1/F2 lookup path and the `target == scene_file_path` no-op guard (location.gd:23) are untouched, and the no-op is enforced by the scene-root script instance (location.gd is *not* an autoload — only GameState is, project.godot:19), so its `scene_file_path` is set. Target scene exists (scenes/chapters/chapter0.tscn confirmed on disk). No F1/F2 regression.

**2. tests/test_locations.gd:58-59 — correct.** F3 pin matches location.gd:12 exactly, same pattern as F1/F2 pins. No issue.

**3. tests/walk_chapter0.gd — marker discipline is sound; 2 P2s.**
- WALK_CH0_OK (walk_chapter0.gd:144) prints only at the end, gated on `_failures == 0`; `_done` guard keeps the 45 s fail-safe from suppressing a real result, and a runtime error aborting the coroutine still exits 1 with no marker. Checks are real predicates (spare-press, gas on/off per frame, flag, pixel count) — no tautologies.
- [P2] walk_chapter0.gd:107 — the reset-guard dereferences `current_scene` *before* `_check(loaded, ...)` at line 113. If the scene fails to load, `current_scene.get(...)` on null aborts `_run`, and the only diagnostic is the 45 s timeout FAIL instead of a clear load failure. No false OK, no hang; fix is reordering (check `loaded` first).
- [P2] walk_chapter0.gd:121-124 — the spare-press window is frame-counted (`await _frames(5)`) while the guard it probes (`busy`) is time-based (0.3 s fade). Under a severe FPS drop in the windowed run, 5 frames can outlast the fade and the spare press legitimately advances to frame 3, failing `reached`. Flaky only under extreme conditions.
- [P2] Coverage gap: the F3 keypress path is pinned as a mapping (test_locations.gd:58) but never exercised with real input; walk_chapter0 loads the scene directly via `change_scene_to_file`. One `_press_key(KEY_F3)` assertion in walk_locations would close it.

**4. tests/test_chapter0.gd — marker discipline sound; white-box safe.** CHAPTER0_OK (line 97) gated at the end on `_failures == 0`; `_exit_code` defaults to 1 if `_run` aborts. White-box order is correct: `_cache_nodes()` before `_setup_gas()` (lines 111-112), `$`-lookup works outside the tree, Image/ImageTexture work headless, and `_apply_frame(1)` avoids the `GameState.set_flag` branch (only n==7 touches it, chapter0.gd:149) — which matters since autoloads are absent in `--script` mode. No hidden hazards.

**5. Cross-file consistency — consistent.** chapter0.gd reads `bg`/`tint`/`gas`/`text`/`speaker`; all present in all 7 entries; `id` 1..7 in order matches index-based `frames[n-1]` access and `LAST_FRAME = 7`; `gas: true` on ids 2 and 7 matches `GAS_FRAMES = [2, 7]` in walk_chapter0.gd:15; `speaker` non-empty only on frame 1 matches test_chapter0.gd:133; `gangbang.png` exists, `igloo.png` missing is whitelisted (test_chapter0.gd:13) and handled by the runtime placeholder; `tint: "indigo"` on id 6 matches chapter0.gd:141-142; `src`/`ref` present per AGENTS provenance rule.

No P0, no P1. Three P2s as above; everything else in scope is clean.
