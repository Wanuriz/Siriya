# ecc:code-reviewer | 2026-11-14 | полный аудит репозитория (task: FULL PROJECT AUDIT)

агент: ecc:code-reviewer | дата: 2026-11-14 | scope: весь репозиторий (scripts, scenes, data, tests, tools, project.godot, INSTALL.md). Вывод дословно ниже, без правок.

---

The review is complete. All requested files were read fully; integration claims were verified with grep and read-only command runs. No files were modified.

---

# Full-Repository Code Review — SIRIYA (read-only)

## Verdict summary

The codebase is in good shape for a vertical slice: the Godot side is small, data-driven, contract-pinned by tests, and the test/marker discipline in `tools/check.py` is sound (verified statically and by a live `--canon-only` run: `RESULT: OK`, 0 errors, 1 expected `R-zlat` warn). No P0 issues — nothing breaks today. One P1: the canon-rules regression test `tools/test_canon_rules.py` is never executed by `tools/check.py`, so the only safety net for the linter itself is a manual command. The rest are P2 observations, several of which are already honestly tracked in the project's own registries (П-34/П-35/П-36, Д-31) and are listed here only as confirmed-still-present.

Evidence of live runs during this review:
- `python -I tools/test_canon_rules.py` → `CANON_RULES_TEST_OK (5 cases)`, exit 0
- `python -I tools/check.py --canon-only` → `scanned 9 files in data, scenes, scripts`, `[warn ] R-zlat data/chapter0.json:28`, `canon: 0 errors, 1 warnings`, `RESULT: OK`, exit 0
- OKLab cross-check: `rgb_to_oklab` in both tools produces bit-identical output on 1000 random RGB values; `oklab_to_rgb(rgb_to_oklab(x))` round-trips with max diff 0; `palette_v3.hex` = 48 colors, min quantized pair dE 4.17.

## Findings

**P1**

1. **`tools/test_canon_rules.py` is not invoked by `tools/check.py` — the linter has no automated regression net.** Confirmed by grep: the only references to `test_canon_rules` in the repo are its own docstring (`tools/test_canon_rules.py:11`) and a history note (`docs/DECISIONS.md:32`); `tools/check.py` has no reference. Failure scenario: a future edit to `tools/canon_rules.json` (renamed rule id, mistyped regex, dropped `R-zhebi-case`) leaves `check.py` printing `RESULT: OK` while the «Жебь» case gate silently disappears, and the test explicitly ordered in Д-16 never runs. The test passes standalone (verified above), so wiring is the only missing piece — `canon_lint()` in `tools/check.py` could run it in ~5 lines (it is stdlib-only, so the "Needs only the Python standard library" contract of check.py is preserved).

**P2**

2. **OKLab math duplication between the two art tools — cost quantified, drift currently zero, but unguarded.** Verbatim duplicates: `_srgb_to_linear` (`tools/art/import_bg.py:83-85` vs `tools/art/import_icon.py:71-73`), `rgb_to_oklab` (`import_bg.py:93-103` vs `import_icon.py:76-86`), `hex_to_rgb` (`import_bg.py:131-132` vs `import_icon.py:89-90`); near-duplicate k-means (`import_bg.py:148-168` vs `import_icon.py:136-165`, already diverged: one subsamples `KMEANS_SAMPLE=40000`, the other does not); `DE_SCALE = 100.0` and the chunk size `50000` magic constant duplicated in both. Two different palette loaders over two different encodings of the same palette: `read_palette()` reads the `.png` swatch (`import_bg.py:389-391`), `load_palette()` reads the `.hex` list (`import_icon.py:93-99`). I verified the duplicated formulas are currently bit-identical, but nothing enforces that: a coefficient fix in one file silently leaves the other behind. A shared `tools/art/oklab.py` (~60 lines moved) would close the drift risk cheaply.

3. **`import_bg.py` has no bad-input handling (П-35/П-36 cover only `import_icon.py`).** Evidence, all uncaught tracebacks on operator error:
   - missing/corrupt image → `FileNotFoundError`/`PIL.UnidentifiedImageError` from `load_small` (`import_bg.py:77`), used by all three subcommands (`:183`, `:421-423`, `:539`);
   - `palette-add` hardcodes the v2 base slots and does `cur_hexes.index("9CD1EA")` / `cur_hexes.index("3FA9D9")` (`import_bg.py:554-555`) — uncaught `ValueError` with any other base palette; the tool is documented as a one-off v2→v3 migration (П-33), nothing prevents reuse against a future base;
   - malformed `new_hex` (wrong length) → `ValueError`/`IndexError` inside `hex_to_rgb` (`import_bg.py:131-132`); argparse does not validate the format (`import_bg.py:750`).

4. **`build_palette` internal duplication and length.** The MIN_PAIR_DE repair loop exists twice nearly verbatim (`import_bg.py:243-258` and `:281-293`), and a third variant of the same merge logic lives in `palette_add` (`:669-686`). `build_palette` spans ~180 lines and `palette_add` ~230 with nested while-loops — functional, but this is the highest-cost debt in the repo for future palette work. (The reuse of the `changed` flag across the outer and inner loop at `:280-293` is correct but easy to misread.)

5. **Documentation drift — stale palette and stale install claims.**
   - `docs/PROJECT_CONTEXT.md:39` instructs `--palette art/palette.png` for every new background. `art/palette.png` is the superseded v0 palette; shipped backgrounds use v3 (STATUS journal, П-33). Following the doc today would quantize new backgrounds to a palette that still contains the removed `#FFBA53` and lacks the P-33 sky slot — visible inconsistency with existing assets. Same stale mention at `docs/PROJECT_CONTEXT.md:30`.
   - `docs/PROJECT_CONTEXT.md:28` lists `data/ dialogue/, chapters/, endings/`; reality is a top-level `data/chapter0.json` (no `data/chapters/`).
   - `INSTALL.md:10` (step 8) says `RESULT: OK (пока тестов нет)` — there are now 5 headless tests, so `RESULT: OK` also requires a working Godot and green tests. `INSTALL.md` never mentions `tools/art/import_icon.py`, `tools/test_canon_rules.py`, or the `tests/` suite; steps 1/4 still speak of the old project (`C:\\dev\\jak`, `jak_art_kit.zip`).
   - `LICENSES.md` is required by `AGENTS.md` п.8 and `docs/PROJECT_CONTEXT.md:41` but does not exist in the repo, while AI-generated art assets (backgrounds, icon source) are committed.

6. **Dead/orphaned committed files.**
   - `art/palette.hex` + `art/palette.png` (+ `.import`) are tracked and referenced only by the stale `PROJECT_CONTEXT.md:39` line; superseded by v1/v2/v3. Retire the files together with the doc line.
   - `assets/ui/scribe_source_v2.png` is tracked (commit 97458d9) but referenced by nothing: `import_icon.py:44` reads `assets/ui/scribe_source.png`, no doc or test mentions the v2 file. If it is the source for a future round, the tool's `SRC_PATH` still points at the older file — either way the current state is undocumented.
   - `assets/ui/scribe_icon.png` is tracked but used by no scene yet (planned dialog-window asset per Д-35); also none of the three `assets/ui/*.png` have `.png.import` files (never editor-imported — harmless while unreferenced, but they will materialize on the next editor scan).
   - Tracked-and-used confirmed for: `art/palette_v3.hex/.png`, `art/src/*`, `art/preview_v2*/v3/*` (metric provenance), `art/backup_v1/gangbang.png` (documented sole carrier, commit 260fb50).

7. **Untracked working artifacts are not git-ignored — recurring status noise.** `git status --short` carries `art/screens/` (7 walk-test screenshots + 2 location shots), `art/preview_icon/`, `art/palette_v1.*`, `art/palette_v2.*`, `art/backup_v1/*` (siblings of the one tracked backup file). `walk_chapter0.gd:69` writes to `res://art/screens/` on every run, and `.gitignore` covers `art/_tmp/` and `reports/` but not `art/screens/` or `art/preview_icon/`. This collides with the project's own rule that `git status --short` must be clean of foreign/temp files before every commit.

8. **Headless suite stays green if `scenes/chapters/chapter0.tscn` is deleted.** `tests/test_chapter0.gd:92` skips all scene checks when the scene file is absent (`if ResourceLoader.exists(...): _check_scene()`), and `tests/test_locations.gd:58-59` pins only the F3 path constant, never loading the chapter scene. So `check.py` would report `RESULT: OK` with the chapter broken at runtime; only the windowed walk test would catch it. The skip is commented as deliberate tolerance, but for a shipped scene it is a silent-weakening path.

9. **`check.py` marker discipline: sound, with one convention-level note.** Discovery (`tools/check.py:172`, glob `tests/test_*.gd`) correctly excludes the frame-awaiting `walk_*.gd` (which would hit the 90 s timeout with a clear message anyway) and auto-picks up new tests (Д-29). Marker gating requires exit 0 AND a `*_OK` marker AND no `SCRIPT ERROR`/`Parse Error` (`tools/check.py:187`); all five test files print their marker only after every check, with `_exit_code = 1` fail-safe defaults. Note: the marker regex (`tools/check.py:32`) matches any `*_OK` token anywhere in output, so the guarantee rests on the tests' own convention of printing the marker last — currently true in all five files, but not enforced centrally.

10. **Known-and-tracked items confirmed still present (no action expected now).** Dead `dominant = np.zeros(...)` (`import_icon.py:429`, overwritten at `:432`); dead constants `FRAME_BORDER_COLOR`/`LABEL_COLOR` with colors duplicated in `chapter0.tscn` (`scripts/chapter0.gd:13-15`); no `push_error` when `data/chapter0.json` fails to load (`scripts/chapter0.gd:61-67` — silent dark screen); `current_frame` mutated before validation (`scripts/chapter0.gd:122-124`); one-way chapter 0 with no exit (`scripts/chapter0.gd` has no F-key handling; documented as deliberate in Д-31). All registered in П-34/П-35/П-36 awaiting the lead's decision.

**P0:** none found.

## Not checked

- Full `python tools/check.py` (Godot stage) and the five headless tests were not executed: a headless Godot run writes into `.godot/` and this review was read-only; relied on the STATUS.md journal plus static reading. Only the stdlib-only stages (`--canon-only`, `test_canon_rules.py`) were run.
- `tests/walk_chapter0.gd` and `tests/walk_locations.gd` not executed (require a windowed session per AGENTS.md п.9).
- `import_bg.py` / `import_icon.py` not run against real assets (they write PNGs); verified only by import and pure-math cross-check.
- Binary content of `art/*.png` and `assets/**/*.png` (dimensions, palette adherence of backgrounds) not inspected — asset verification was out of scope; the icon is guarded by `tests/test_scribe_icon.gd` instead.
- OKLab constants were verified for mutual consistency and round-trip losslessness, not re-derived against Ottosson's publication line by line.
- Runtime behavior of the fade machine and particle setup in `scripts/chapter0.gd` was reviewed statically only (covered dynamically by the walk test per STATUS.md, not re-run here).
