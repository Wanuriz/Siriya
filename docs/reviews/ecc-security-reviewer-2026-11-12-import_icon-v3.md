# ecc:security-reviewer | 2026-11-12 | tools/art/import_icon.py (круг 2, п.6.8 после правок)

агент: ecc:security-reviewer | дата: 2026-11-12 | scope: tools/art/import_icon.py после двух правок по кругу 1 (guard пустой маски, docstring 0.4). Вывод дословно ниже, без правок.

---

Review complete. All checks below were read-only; no files were modified.

## Verdict

**PASS — no P0, no P1.** The current `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py` (545 lines, second-round k-means pipeline) is sound as a whole for its threat model (single developer, local run, trusted repo inputs): no command or code injection, no network, no deserialization of untrusted formats, all paths are fixed constants derived from `__file__` with no user-supplied paths, all four final gates run before any file write (fail-secure), and exit codes are correct. Verified at runtime environment level: numpy 2.5.4, Pillow 13.0.0 (decompression-bomb guard active), source image 1254x1254 RGB. One caveat on scope: the intermediate "previously reviewed" working-tree version was never committed or snapshotted, so the only diff I could reconstruct is vs HEAD (the first-round LANCZOS version, `8b87cfb`) — this re-review therefore covers the entire current file, not a delta. Note the file in the working tree is modified vs HEAD and uncommitted.

The two P2s from the previous review (`docs/reviews/ecc-security-reviewer-2026-11-12-import_icon.md`, finding 1 and 2) are still present in the current code — the palette parsing was not hardened. Everything else from that review either still applies as an observation or was superseded by the rewrite.

## Findings

1. **P2 — palette parsing still fails with a raw traceback (carried over, unchanged).** `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:89-99` (`hex_to_rgb`, `load_palette`): a 6-char non-hex line (e.g. `GGHHII`) raises unhandled `ValueError`; a palette with zero valid lines raises `ValueError: need at least one array to stack` at line 99. Fail-secure (crash happens before any write), but the message is unhelpful. Fix: wrap `int(..., 16)` in try/except and exit with `bad palette line: {line!r}`; error explicitly when the parsed list is empty.

2. **P2 — new hard dependency: palette must contain `#3B3251`.** `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:461` (`contour_slot = pal_hex.index(CONTOUR_HEX)`) raises an unhandled `ValueError` if the palette ever drops the contour color — a new failure mode introduced by the rewrite. Verified present today (`C:\Users\user\Desktop\Siriya\art\palette_v3.hex` line 11), so it works now. Fix: check membership first and print a clear error, or derive the contour slot from the palette at load time with validation.

3. **P2 — `kmeans_fit` crashes if the figure has fewer than `KMEANS_K` (9) opaque source pixels.** `C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:143` — `rng.choice(len(sample), size=k, replace=False)` raises `ValueError` when `len(sample) < k`. Practically unreachable (the `len(ys) == 0` check at line 391 and the 350-opaque gate bound this), and fail-secure. Optional fix: guard `len(sample) < k` with an explicit error.

4. **P2 — added connectivity pixels can silently get the wrong color (data integrity, not security).** In `connect_and_report` (`C:\Users\user\Desktop\Siriya\tools\art\import_icon.py:321-327` and `369-375`), a newly added cell is given a label only if it has an adjacent *original* opaque cell; otherwise its label stays `-1`. The contour pass (line 473) repaints most such cells, but one fully surrounded by opaque cells can survive to line 477, where `pal[lab_grid[mask]]` treats `-1` as a negative index and silently maps to the *last* palette color. Bounded by the unique-colors gate. Fix: before line 477, fail-secure check `(lab_grid[mask] < 0).any()` and exit 1, or assign such cells a neighbor label as well.

5. **P2 — decompression-bomb / memory ceiling (carried over, unchanged).** `import_icon.py:385` — `Image.open(SRC_PATH)` relies solely on Pillow's default `MAX_IMAGE_PIXELS` guard (warning ~89 Mpx, error ~178 Mpx); a near-limit file could push multi-GB float64 intermediates (full-image OKLab at lines 109 and 410) before any gate. Input is a developer-controlled repo file; no action needed, noted for completeness.

6. **P2 — flood-fill cost is slow-but-finite (carried over, unchanged).** `import_icon.py:117-126` — the border-reconstruction loop is O((h+w) x hw) numpy work in the worst case (near-threshold checkerboard). It provably terminates (`reach` grows monotonically, bounded by `close`, and the `grown == reach` break is correct); the actual 1254x1254 source converges quickly. Acceptable for a local tool.

7. **P2 — cosmetic dead code.** `import_icon.py:429` — `dominant = np.zeros(nw * nh, dtype=np.int32)` is immediately overwritten at line 432. No effect; remove or ignore.

**Explicitly checked and clean:** no `subprocess` / `os.system` / `eval` / `exec` / `pickle` / `marshal` / `yaml` / network / tempfile (grep over the file returned nothing); the only CLI input is the boolean `--preview` flag (`import_icon.py:381`), no path arguments; all four paths are fixed under `ROOT` from `__file__` (lines 43-47) and `mkdir(parents=True, exist_ok=True)` at line 535 touches only the declared `art/preview_icon`; all writes happen strictly after all four gates pass (lines 518-533 — fail-secure); no secrets, no sensitive logging (only pixel metrics); exit codes correct on every failure path (`return 1`, `SystemExit(main())`); index bounds on the 48x48 grid are guarded (`ox < 2 or oy < 2` check at line 403; all neighbor loops bounds-checked); `all_lab` is `np.empty` but only `fig_mask` cells are read (lines 413, 430 — no uninitialized read).

## Not checked

- The script was not executed (read-only review; no runtime run of `import_icon.py` itself).
- Visual correctness/quality of the produced icon (out of security scope).
- Consistency of the OKLab math with `tools/art/import_bg.py` (referenced in the docstring, not compared line by line).
- The Godot-side consumer `tests/test_scribe_icon.gd` and `tools/check.py` (not part of this file's review scope).
- Exact identity of the "two small fixes": no snapshot of the intermediate reviewed version exists in git or elsewhere, so they could not be diffed individually; the review above is a whole-file assessment of the current state, as requested.

Per the process, this output should be saved verbatim by the main session to `docs/reviews/` (AGENTS.md п.6.4); I have not written any files.
