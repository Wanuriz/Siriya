# ecc:security-reviewer | 2026-11-12 | tools/art/import_icon.py

агент: ecc:security-reviewer | дата: 2026-11-12 | scope: tools/art/import_icon.py (новый скрипт импорта иконки, первый прогон после SCRIBE_ICON_OK). Вывод дословно ниже, без правок.

---

**Verdict: PASS — no P0 or P1 findings.** The script is a self-contained local asset tool: no `subprocess`/`eval`/`exec`, no network, no deserialization of untrusted formats, all paths are fixed constants derived from `__file__`, and it accepts no path arguments. The only interactive inputs are two project files (`scribe_source.png`, `palette_v3.hex`) which PIL/numpy parse safely (PIL's default decompression-bomb guard is active). This is consistent with the pattern in the sibling `tools/art/import_bg.py`.

**Findings**

1. **P2 — empty/garbage palette causes an opaque crash, no validation** — `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:70-76`. `load_palette` silently skips lines that aren't exactly 6 chars; a hex line with non-hex characters (e.g. `GGHHII`) raises an unhandled `ValueError` with a traceback, and a palette file with zero valid colors raises `ValueError: need at least one array to stack` at line 76. Fail-secure (no bad output is written), but the error message is unhelpful. Fix: validate with a `try: int(..., 16) except ValueError: raise SystemExit(f"bad palette line: {line!r}")` and error out on `len(colors) == 0`.

2. **P2 — duplicate/ambiguous palette entries** — line 70-76. Duplicate hexes in `palette_v3.hex` are kept, which inflates slot count and could interact with the merge logic (merging into a slot that duplicates another). Not exploitable, just robustness. Fix: `np.unique(palette, axis=0)` after loading, or assert uniqueness.

3. **P2 — PNG decompression bomb** — line 116. `Image.open(SRC_PATH)` on a huge PNG allocates memory, but PIL's default `MAX_IMAGE_PIXELS` guard (~178 Mpx) raises `DecompressionBombError` before OOM, and the input is a developer-controlled repo file. No action needed; noting for completeness.

4. **P2 — flood fill cost** — lines 93-102. The border-reconstruction loop is O(pixels × iterations) in numpy rather than a proper flood-fill; worst case for a pathological image (checkerboard at exactly the threshold) it could be slow, but bounded by the image dimensions (icon source, small). Acceptable for this tool.

5. **P2 — merge guard cap is arbitrary** — lines 164-166. The `guard > 100` bail-out is correct fail-secure behavior (exits with error, no output written); no issue, just noting the convergence bound is heuristic.

**Explicitly checked and clean:** no command/code injection (no `subprocess`, `os.system`, `eval`, `exec`, pickle/marshal/yaml); no path traversal (no user-supplied paths; `ROOT` from `__file__`, outputs under project dir; `mkdir(parents=True)` only for the declared preview dir); no secrets or credentials; no logging of sensitive data; exit codes used correctly (`return 1` on failure paths, `SystemExit` at entry); no mutable global state issues; temp files not created.

**Not checked:** runtime behavior (read-only review; the script was not executed); correctness of the OKLab math vs `import_bg.py` (out of security scope); `palette_v3.hex` and `scribe_source.png` contents were not read.
