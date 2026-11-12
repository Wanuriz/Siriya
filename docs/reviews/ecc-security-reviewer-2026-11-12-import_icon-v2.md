# ecc:security-reviewer | 2026-11-12 | tools/art/import_icon.py (круг 1 после переписывания пайплайна)

агент: ecc:security-reviewer | дата: 2026-11-12 | scope: tools/art/import_icon.py после переписывания на k-means пайплайн (второе задание иконки). Вывод дословно ниже, без правок.

---

Review complete. All the script's inputs, outputs, and its callers were inspected; nothing imports it, and the current data on disk does not trigger any of the crash paths noted below.

# Security review: C:\Users\user\Desktop\Siriya\tools\art\import_icon.py

## Verdict

**No P0 findings — safe to commit from a security standpoint.** The script has no injection surface (no `eval`/`exec`/`subprocess`/`os.system`, no dynamic imports, no network, no deserialization, no secrets, no env-derived paths). All four filesystem paths are absolute constants derived from `Path(__file__).resolve()` (line 42), the only CLI input is the boolean `--preview` flag, and all output writes happen strictly after the four fail-secure gates (lines 514-527) exit 1 on failure without writing — the fail-secure claim in the docstring is accurate. The findings below are hardening items for unvalidated input sizes and unguarded parse failures, rated against the stated threat model (local single-developer tool whose input PNG is an externally AI-generated asset that gets replaced over time).

## Findings

**1. P1 — No size guard on the source PNG before full float64 decode (resource exhaustion / decompression bomb).**
`import_icon.py:384-386` (`Image.open(SRC_PATH).convert("RGB")`, `np.asarray(src)`), `import_icon.py:70-85` (`rgb_to_oklab`), `import_icon.py:116-125` (flood fill `while True`).
The source asset is externally AI-generated (project workflow: art comes from external generators, imported into `assets/ui/`) and is re-processed whenever replaced. Nothing bounds its dimensions. PIL's default bomb protection only warns above ~89 MP and errors above ~179 MP, so a large-but-legal file passes with a warning and then `rgb.astype(np.float64)` plus the OKLab intermediates allocate multiple GB (at 89 MP, one float64 HxWx3 array alone is ~2.1 GB). The edge flood fill copies the full boolean grid once per growth iteration; a large image whose background grows slowly (spiral / 1 px corridors) is O(iterations x h*w) — minutes of churn and near-hang on a legitimate-looking file. Secondary instance of the same class: `import_icon.py:430` `np.bincount(pair, minlength=nw * nh * len(pal))` allocates proportionally to the palette line count, so a bloated hand-edited `palette_v3.hex` also drives memory.
Current file is fine (1254x1254 = 1.57 MP, palette 48 lines), so this is a guard for future replacements, not a live bug.
Fix: after `Image.open`, before `.convert("RGB")`, check `src.width * src.height <= MAX_SRC_PIXELS` (e.g. 4096x4096, 10x the current source) and `min(src.size) >= 2` (corner indexing at line 106 needs at least 2x2), `print` a clean `ERROR:` and `return 1`; cap the palette line count in `load_palette` (line 92) as well.

**2. P1 — Unguarded parse failures crash with raw tracebacks instead of clean fail-closed errors.**
`import_icon.py:88-98` (`hex_to_rgb` / `load_palette`): a palette line of exactly 6 chars that is not hex (e.g. `XYZ123`) raises `ValueError: invalid literal for int()`; an empty palette makes `np.stack(colors)` raise. `import_icon.py:457` `contour_slot = pal_hex.index(CONTOUR_HEX)` raises `ValueError` with a traceback if `3B3251` is ever absent from a future palette revision. `import_icon.py:142` `rng.choice(len(sample), size=k, replace=False)` raises if the surviving figure has fewer than 9 pixels. All crash before any write (save is at line 529), so this is robustness, not exploitability — the current palette contains the contour color and only well-formed lines.
Fix: wrap palette parsing in explicit validation (`print("ERROR: palette line N not hex: ..."); return 1`), check `"3B3251" in pal_hex` before use, and guard `kmeans_fit` with `if len(sample) < k: print("ERROR: ..."); return 1`.

**3. P2 — Degenerate empty icon grid crashes inside `connect_and_report` instead of reaching the fail-secure gate.**
`import_icon.py:310-311` and `import_icon.py:452`.
The early guard at lines 389-392 only ensures the source figure is non-empty; if every 48x48 cell's figure coverage is below `ALPHA_THRESHOLD` (thin/sparse figure), `mask` ends up all-False. Then `label_components(work)` returns an empty `sizes` list and `int(np.argmax(sizes))` at line 311 raises `ValueError: attempt to get argmax of an empty sequence` with a confusing traceback. The intended gate at line 517 (`350 <= int(mask.sum()) <= 1500`) never gets to explain the problem. Fail-closed (crash precedes the write at line 529), but it defeats the script's own "print the numbers and exit 1" contract.
Fix: after the mask is built (after line 433 or 447), `if not mask.any(): print("ERROR: no cell reached alpha threshold"); return 1`.

**4. P2 — Preview re-opens the just-written output file from disk (theoretical swap window, needless I/O).**
`import_icon.py:529-533`. The script writes `OUT_PATH`, then does `Image.open(OUT_PATH)` to build the preview, re-reading a file it just wrote. On a single-user dev machine there is no real attacker, but re-reading from disk after writing is both a (theoretical) TOCTOU window and wasteful.
Fix: build the preview from the in-memory array: `Image.fromarray(out, "RGBA").resize((ICON_SIZE * 8, ICON_SIZE * 8), Image.NEAREST).save(PREVIEW_PATH)`.

**5. P2 — Palette parser silently skips non-conforming lines.**
`import_icon.py:96` `if len(line) == 6:`. Lines with trailing comments (`AABBCC # note`) or any non-6-char content are dropped without a message. Combined with finding 2, a hand-edited palette can lose colors silently and shift behavior. Fix: count and report skipped lines, or reject non-empty lines that are not exactly 6 hex characters.

**6. P2 (observation) — Docstring contradicts the constant.**
`import_icon.py:9` says "binary threshold 0.5" while `ALPHA_THRESHOLD = 0.4` at `import_icon.py:50` (the inline comment marks the change as lead-approved; only the docstring is stale). The docstring is also passed as the argparse description (line 379), so `--help` advertises the wrong threshold. Fix: update line 9 to 0.4.

## Not checked (out of scope for a read-only review)

- Did not execute the script or run its pipeline (no files modified, no execution requested).
- Installed versions of numpy/PIL on the project's actual interpreter were not verified for CVEs (the default shell python lacks PIL, so the project evidently runs another interpreter that I did not locate).
- `tools/art/import_bg.py` was inspected only at the header level: it is not imported by `import_icon.py` (shared math is by comment reference only), so its internals were not reviewed.
- Filesystem ACLs and symlink hardening on `assets/ui/` were not assessed (irrelevant under the stated single-user local threat model; exploiting output overwrites would already require local write access).
