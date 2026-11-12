#!/usr/bin/env python3
"""Turn the AI-generated chronicler portrait into a 48x48 palette icon.

Second-round pipeline (lead's task, 2026-11-12; replaces the LANCZOS-average
version whose per-pixel nearest-palette mapping produced speckle):
  1) background key (unchanged, Д-34): corners median, flood fill from edges;
  2) crop to the figure bounding box, fit the longest side into 44 px,
     center in a 48x48 canvas (2 px margin);
  3) cell alpha = BOX average of the source alpha, binary threshold 0.4
     (single lead-approved correction from 0.5 to keep the quill alive; Д-36);
     k-means (k=9, deterministic seed, numpy) over the SOURCE figure pixels
     in OKLab; the cell color is the DOMINANT cluster label among the cell's
     source pixels (area-weighted vote, NOT an average - averaging mixes
     ornament and base colors, which caused the speckle); centroids then snap
     to the nearest art/palette_v3.hex color (OKLab*100 scale, Д-18) and
     duplicate snaps merge -> at most 9 form colors;
  4) de-speckle: majority label filter (3x3, tie -> own label), then remove
     8-connected same-label components smaller than 4 px by repainting to the
     neighbor label with the longest shared border;
  5) connectivity: the largest 8-connected opaque component must be >= 95%
     of opaque; otherwise morphological closing (dilate 1 -> erode 1) and,
     if still short, re-attach by adding a 1 px path to the main component.
     ADDED pixels are printed; more than 3% of opaque added is drawing,
     not import -> exit 1 (BLOCKERS per the task);
  6) contour: every opaque pixel with a transparent 4-neighbor or a neighbor
     outside the icon becomes #3B3251 -> at most 10 unique colors;
  7) --preview also writes art/preview_icon/scribe_icon_x8.png
     (NEAREST x8 upscale, at most one current version).

Fail-secure: if any final gate fails (unique > 10, opaque outside
[350..1500], largest component < 95%, added > 3%), print the numbers and
exit 1 WITHOUT writing the icon. Only numpy and PIL are used.

Reads ONLY: assets/ui/scribe_source.png, art/palette_v3.hex.
Writes ONLY: assets/ui/scribe_icon.png, art/preview_icon/scribe_icon_x8.png.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = ROOT / "assets" / "ui" / "scribe_source.png"
PALETTE_PATH = ROOT / "art" / "palette_v3.hex"
OUT_PATH = ROOT / "assets" / "ui" / "scribe_icon.png"
PREVIEW_PATH = ROOT / "art" / "preview_icon" / "scribe_icon_x8.png"

ICON_SIZE = 48
FIGURE_MAX = 44          # longest figure side inside the icon
ALPHA_THRESHOLD = 0.4    # binary cell alpha after the BOX downscale (one lead-allowed
                         # correction from 0.5: keeps the thin quill stroke alive)
BG_KEY_DE = 6.0          # [с] corner-key threshold, OKLab*100 scale (Д-34)

KMEANS_K = 9             # form colors before contour; + contour <= 10
KMEANS_ITERS = 30
KMEANS_SAMPLE = 40000    # subsample of source figure pixels for the fit
SEED = 0

UNIQUE_COLORS_MAX = 10   # final gate (test threshold, never loosened)
TINY_COMPONENT_PX = 4    # same-label components smaller than this are removed
CONNECT_MIN_PCT = 95.0   # largest 8-connected opaque component
ADDED_MAX_PCT = 3.0      # more than this = drawing, not import
CONTOUR_HEX = "3B3251"

DE_SCALE = 100.0         # OKLab distances are multiplied by this (Д-18)


# --- OKLab (Bjorn Ottosson), same math as tools/art/import_bg.py -------------

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    c = _srgb_to_linear(rgb.astype(np.float64))
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return np.stack([L, a, b2], axis=-1)


def hex_to_rgb(h: str) -> np.ndarray:
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)


def load_palette(path: Path) -> np.ndarray:
    colors = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().upper()
        if len(line) == 6:
            colors.append(hex_to_rgb(line))
    return np.stack(colors)  # (N, 3) uint8


# --- background key (unchanged from the first round) -------------------------

def bg_key_alpha(rgb: np.ndarray) -> np.ndarray:
    """Return binary alpha (0 = background, 255 = figure) via edge flood fill."""
    h, w, _ = rgb.shape
    corners = np.stack([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(rgb_to_oklab(rgb) - rgb_to_oklab(bg.reshape(1, 1, 3)),
                          axis=-1) * DE_SCALE
    close = dist <= BG_KEY_DE
    reach = np.zeros((h, w), dtype=bool)
    reach[0, :] = close[0, :]
    reach[-1, :] = close[-1, :]
    reach[:, 0] |= close[:, 0]
    reach[:, -1] |= close[:, -1]
    while True:
        grown = reach.copy()
        grown[1:, :] |= reach[:-1, :]
        grown[:-1, :] |= reach[1:, :]
        grown[:, 1:] |= reach[:, :-1]
        grown[:, :-1] |= reach[:, 1:]
        grown &= close
        if (grown == reach).all():
            break
        reach = grown
    alpha = np.where(reach, 0, 255).astype(np.uint8)
    print("bg key: corners median %s, dE<=%.1f, cleared %d px (%.1f%%), kept %d px"
          % ("%02X%02X%02X" % tuple(int(v) for v in bg), BG_KEY_DE,
             int(reach.sum()), 100.0 * reach.sum() / (h * w), int((alpha == 255).sum())))
    return alpha


# --- k-means over source figure pixels (pattern from import_bg.py) -----------

def kmeans_fit(lab_pixels: np.ndarray, k: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    if len(lab_pixels) > KMEANS_SAMPLE:
        pick = rng.choice(len(lab_pixels), size=KMEANS_SAMPLE, replace=False)
        sample = lab_pixels[pick]
    else:
        sample = lab_pixels
    centroids = sample[rng.choice(len(sample), size=k, replace=False)].copy()
    for _ in range(KMEANS_ITERS):
        assign = nearest_lab(sample, centroids)
        new = centroids.copy()
        for c in range(k):
            members = sample[assign == c]
            if len(members):
                new[c] = members.mean(axis=0)
        shift = np.abs(new - centroids).max()
        centroids = new
        if shift < 1e-4:
            break
    return centroids


def nearest_lab(points: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    assign = np.empty(len(points), dtype=np.int32)
    chunk = 50000
    for i in range(0, len(points), chunk):
        part = points[i:i + chunk]
        d = ((part[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        assign[i:i + chunk] = d.argmin(axis=1)
    return assign


# --- grid helpers (48x48, plain python BFS is plenty) ------------------------

OFFS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
OFFS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def label_components(mask: np.ndarray):
    """8-connected components of a boolean grid -> (lab, sizes)."""
    h, w = mask.shape
    lab = np.full((h, w), -1, dtype=np.int32)
    sizes = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or lab[sy, sx] != -1:
                continue
            cid = len(sizes)
            stack = [(sy, sx)]
            lab[sy, sx] = cid
            size = 0
            while stack:
                y, x = stack.pop()
                size += 1
                for dy, dx in OFFS8:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and lab[ny, nx] == -1:
                        lab[ny, nx] = cid
                        stack.append((ny, nx))
            sizes.append(size)
    return lab, sizes


def majority_pass(lab: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """3x3 majority of labels among opaque cells; ties keep the own label."""
    h, w = lab.shape
    out = lab.copy()
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            counts = {}
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                        counts[lab[ny, nx]] = counts.get(lab[ny, nx], 0) + 1
            best = max(counts.values())
            if counts[lab[y, x]] == best:
                continue  # tie or own majority -> keep own label
            tops = [c for c, n in counts.items() if n == best]
            out[y, x] = min(tops)
    return out


def remove_tiny(lab: np.ndarray, mask: np.ndarray) -> int:
    """Repaint same-label 8-connected components < TINY_COMPONENT_PX to the
    neighbor label with the longest shared 4-border. Returns count repainted."""
    changed = 0
    for pass_i in range(3):  # a repaint can expose new tiny components
        comp, sizes = label_components_from_labels(lab, mask)
        done = True
        for cid, size in enumerate(sizes):
            if size >= TINY_COMPONENT_PX:
                continue
            cells = list(zip(*np.nonzero(comp == cid)))
            contact = {}
            for y, x in cells:
                for dy, dx in OFFS4:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < lab.shape[0] and 0 <= nx < lab.shape[1] \
                            and mask[ny, nx] and lab[ny, nx] != lab[y, x]:
                        contact[lab[ny, nx]] = contact.get(lab[ny, nx], 0) + 1
            if not contact:
                continue  # isolated speck: left for the connectivity step
            done = False
            target = max(contact, key=lambda c: contact[c])
            for y, x in cells:
                lab[y, x] = target
            changed += size
        if done:
            break
    return changed


def label_components_from_labels(lab: np.ndarray, mask: np.ndarray):
    """8-connected components of equal labels within the opaque mask."""
    h, w = lab.shape
    comp = np.full((h, w), -1, dtype=np.int32)
    sizes = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or comp[sy, sx] != -1:
                continue
            cid = len(sizes)
            stack = [(sy, sx)]
            comp[sy, sx] = cid
            size = 0
            while stack:
                y, x = stack.pop()
                size += 1
                for dy, dx in OFFS8:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] \
                            and comp[ny, nx] == -1 and lab[ny, nx] == lab[sy, sx]:
                        comp[ny, nx] = cid
                        stack.append((ny, nx))
            sizes.append(size)
    return comp, sizes


def shift(m: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    ys0, ys1 = max(dy, 0), h + min(dy, 0)
    xs0, xs1 = max(dx, 0), w + min(dx, 0)
    out[ys0:ys1, xs0:xs1] = m[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def dilate8(m: np.ndarray) -> np.ndarray:
    out = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= shift(m, dy, dx)
    return out


def erode8(m: np.ndarray) -> np.ndarray:
    out = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            out &= shift(m, -dy, -dx)
    return out


def connect_and_report(mask: np.ndarray, lab: np.ndarray):
    """Ensure the largest 8-connected component >= CONNECT_MIN_PCT.
    Returns (mask, lab, added_px). Closing fills 1 px gaps; if still short,
    a 1 px path is added to re-attach each leftover component (counted)."""
    added = np.zeros_like(mask)
    work = mask.copy()
    for _ in range(2):  # up to two closing rounds
        lab_c, sizes = label_components(work)
        main = int(np.argmax(sizes))
        if 100.0 * sizes[main] / work.sum() >= CONNECT_MIN_PCT:
            break
        closed = erode8(dilate8(work))
        grown = closed & ~work & ~added
        if grown.any():
            added |= grown
            work |= grown
            # fill added gap cells with the label of an adjacent opaque cell
            for y, x in zip(*np.nonzero(grown)):
                for dy, dx in OFFS8:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < work.shape[0] and 0 <= nx < work.shape[1] \
                            and mask[ny, nx]:
                        lab[y, x] = lab[ny, nx]
                        break
    # if still short: re-attach leftover components with a 1 px path
    lab_c, sizes = label_components(work)
    main = int(np.argmax(sizes))
    if 100.0 * sizes[main] / work.sum() < CONNECT_MIN_PCT:
        main_mask = lab_c == main
        for cid, size in enumerate(sizes):
            if cid == main or 100.0 * size / work.sum() >= 100.0 - CONNECT_MIN_PCT:
                continue
            comp_mask = lab_c == cid
            # BFS from the component through transparent cells to the main one
            dist = np.full(work.shape, -1, dtype=np.int32)
            prev = {}
            queue = []
            for y, x in zip(*np.nonzero(comp_mask)):
                dist[y, x] = 0
                queue.append((y, x))
            target = None
            head = 0
            while head < len(queue) and target is None:
                y, x = queue[head]
                head += 1
                for dy, dx in OFFS8:
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < work.shape[0] and 0 <= nx < work.shape[1]):
                        continue
                    if main_mask[ny, nx]:
                        target = (y, x)
                        break
                    if dist[ny, nx] == -1 and not work[ny, nx]:
                        dist[ny, nx] = dist[y, x] + 1
                        prev[(ny, nx)] = (y, x)
                        queue.append((ny, nx))
            if target is None:
                continue
            # walk the path back and mark the transparent cells as added
            cur = target
            while dist[cur] > 0:
                work[cur] = True
                added[cur] = True
                cur = prev[cur]
            # give every added cell a label from an adjacent original cell
            for y, x in zip(*np.nonzero(added)):
                for dy, dx in OFFS8:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < work.shape[0] and 0 <= nx < work.shape[1] \
                            and mask[ny, nx] and not added[ny, nx]:
                        lab[y, x] = lab[ny, nx]
                        break
    return work, lab, added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true",
                    help="also write art/preview_icon/scribe_icon_x8.png")
    args = ap.parse_args()

    src = Image.open(SRC_PATH).convert("RGB")
    rgb = np.asarray(src)
    alpha = bg_key_alpha(rgb)
    pal = load_palette(PALETTE_PATH)

    ys, xs = np.nonzero(alpha)
    if len(ys) == 0:
        print("ERROR: background key removed everything; lower BG_KEY_DE")
        return 1
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    alpha_f = alpha[box[1]:box[3], box[0]:box[2]]
    rgb_f = rgb[box[1]:box[3], box[0]:box[2]]
    fh, fw = alpha_f.shape
    print("figure bbox: %s (%dx%d)" % (box, fw, fh))

    scale = FIGURE_MAX / max(fw, fh)
    nw, nh = max(1, round(fw * scale)), max(1, round(fh * scale))
    ox, oy = (ICON_SIZE - nw) // 2, (ICON_SIZE - nh) // 2
    if ox < 2 or oy < 2:
        print("ERROR: figure does not fit with a 2 px margin (%dx%d -> %dx%d)"
              % (fw, fh, nw, nh))
        return 1

    # --- k-means over the SOURCE figure pixels, dominant label per cell -----
    fig_mask = alpha_f == 255
    fig_lab = rgb_to_oklab(rgb_f[fig_mask])            # (N, 3)
    centroids = kmeans_fit(fig_lab, KMEANS_K)
    all_lab = np.empty((fh, fw), dtype=np.int32)
    all_lab[fig_mask] = nearest_lab(fig_lab, centroids)
    snap_d = np.linalg.norm(centroids[:, None, :] - rgb_to_oklab(pal)[None, :, :], axis=-1) * DE_SCALE
    slot_of_centroid = snap_d.argmin(axis=1)
    print("centroid snap dE: %s" % ", ".join("%.1f" % v for v in snap_d.min(axis=1)))

    # duplicate snaps merge (labels -> slot ids)
    lab_grid = np.full((ICON_SIZE, ICON_SIZE), -1, dtype=np.int32)
    mask = np.zeros((ICON_SIZE, ICON_SIZE), dtype=bool)
    ci = (np.arange(fw) * nw) // fw
    cj = (np.arange(fh) * nh) // fh
    cell_idx = cj[:, None] * nw + ci[None, :]
    cell_area = np.bincount(cell_idx.ravel(), minlength=nw * nh).reshape(nh, nw)
    fig_cells = cell_idx[fig_mask]
    fig_count = np.bincount(fig_cells, minlength=nw * nh).reshape(nh, nw)
    frac = fig_count / np.maximum(cell_area, 1)
    mask[oy:oy + nh, ox:ox + nw] = frac >= ALPHA_THRESHOLD
    dominant = np.zeros(nw * nh, dtype=np.int32)
    pair = fig_cells * len(pal) + slot_of_centroid[all_lab[fig_mask]]
    counts = np.bincount(pair, minlength=nw * nh * len(pal)).reshape(nw * nh, len(pal))
    dominant = counts.argmax(axis=1)
    lab_grid[oy:oy + nh, ox:ox + nw][mask[oy:oy + nh, ox:ox + nw]] = \
        dominant.reshape(nh, nw)[mask[oy:oy + nh, ox:ox + nw]]
    if not mask.any():
        print("ERROR: no 48x48 cell reached ALPHA_THRESHOLD; nothing to import")
        return 1

    active = sorted(int(v) for v in np.unique(lab_grid[mask]))
    print("form colors after snap: %d (%s)" % (
        len(active), ", ".join("%02X%02X%02X" % tuple(pal[s]) for s in active)))

    # --- de-speckle ----------------------------------------------------------
    repainted = remove_tiny(lab_grid, mask)
    for _ in range(2):
        new_lab = majority_pass(lab_grid, mask)
        if (new_lab == lab_grid).all():
            break
        lab_grid = new_lab
    repainted += remove_tiny(lab_grid, mask)
    print("de-speckle: %d px repainted" % repainted)

    # --- connectivity --------------------------------------------------------
    mask, lab_grid, added = connect_and_report(mask, lab_grid)
    added_n = int(added.sum())
    added_pct = 100.0 * added_n / float(mask.sum())
    print("connectivity: added %d px (%.1f%% of opaque)" % (added_n, added_pct))

    # --- contour -------------------------------------------------------------
    pal_hex = ["%02X%02X%02X" % (int(p[0]), int(p[1]), int(p[2])) for p in pal]
    contour_slot = pal_hex.index(CONTOUR_HEX)
    h, w = mask.shape
    contour = np.zeros_like(mask)
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            for dy, dx in OFFS4:
                ny, nx = y + dy, x + dx
                if not (0 <= ny < h and 0 <= nx < w) or not mask[ny, nx]:
                    contour[y, x] = True
                    break
    lab_grid[contour] = contour_slot

    # --- final metrics and gates (fail-secure: no write on failure) ----------
    out = np.zeros((ICON_SIZE, ICON_SIZE, 4), dtype=np.uint8)
    out[mask, :3] = pal[lab_grid[mask]]
    out[mask, 3] = 255
    opaque_hex = sorted({"%02X%02X%02X" % tuple(int(v) for v in out[y, x, :3])
                         for y in range(ICON_SIZE) for x in range(ICON_SIZE) if mask[y, x]})

    comp, sizes = label_components(mask)
    comp_pct = 100.0 * max(sizes) / float(mask.sum())
    orphans = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            same = False
            for dy, dx in OFFS4:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] \
                        and lab_grid[ny, nx] == lab_grid[y, x]:
                    same = True
                    break
            if not same:
                orphans += 1
    orphan_pct = 100.0 * orphans / float(mask.sum())

    print("opaque pixels: %d" % int(mask.sum()))
    print("unique colors: %d -> %s" % (len(opaque_hex), ", ".join(opaque_hex)))
    print("pixels without same-color 4-neighbor: %.1f%% (%d of %d)"
          % (orphan_pct, orphans, int(mask.sum())))
    print("largest 8-connected component: %.1f%% (%d of %d)"
          % (comp_pct, max(sizes), int(mask.sum())))

    # non-contour color forms (color, area, center) - for the lead's eye:
    inner = mask & ~contour
    form_comp, form_sizes = label_components_from_labels(lab_grid, inner)
    forms = []
    for cid, size in enumerate(form_sizes):
        if size < 3:
            continue
        fy, fx = np.nonzero(form_comp == cid)
        forms.append("%s x%d @(%d,%d)" % (pal_hex[lab_grid[fy[0], fx[0]]], size, fx[0], fy[0]))
    print("color forms (non-contour): %s" % ", ".join(forms))

    gates = [
        (len(opaque_hex) <= UNIQUE_COLORS_MAX,
         "unique colors %d > %d" % (len(opaque_hex), UNIQUE_COLORS_MAX)),
        (350 <= int(mask.sum()) <= 1500,
         "opaque %d outside [350..1500]" % int(mask.sum())),
        (comp_pct >= CONNECT_MIN_PCT,
         "largest component %.1f%% < %.0f%%" % (comp_pct, CONNECT_MIN_PCT)),
        (added_pct <= ADDED_MAX_PCT,
         "added %.1f%% > %.0f%% (drawing, not import)" % (added_pct, ADDED_MAX_PCT)),
    ]
    failed = [msg for ok, msg in gates if not ok]
    if failed:
        print("GATES FAILED: %s" % "; ".join(failed))
        return 1

    Image.fromarray(out, "RGBA").save(OUT_PATH)
    if args.preview:
        PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        Image.open(OUT_PATH).resize((ICON_SIZE * 8, ICON_SIZE * 8), Image.NEAREST) \
            .save(PREVIEW_PATH)
    print("written: %s%s" % (OUT_PATH.relative_to(ROOT),
                             " + %s" % PREVIEW_PATH.relative_to(ROOT) if args.preview else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
