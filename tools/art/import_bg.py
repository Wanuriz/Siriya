#!/usr/bin/env python3
"""Turn AI-generated location art into game-ready pixel art.

Two commands:

  1) Build the shared palette (v2) from the master images of all locations:
       python tools/art/import_bg.py palette art/palette_v2.png art/src/bazaar.png art/src/oasis.png art/src/gangbang.png

  2) Convert any image with that palette:
       python tools/art/import_bg.py convert art/src/oasis.png art/preview_v2/oasis.png --palette art/palette_v2.png --preview

v2 palette (2026-11-12, by lead's order):
  - k-means in OKLab (deterministic, seed fixed) over ALL source images;
  - 12 mandatory anchors the algorithm may never drop (cream/lavender whites,
    light and saturated sky, two saturated greens, turquoise, terracotta,
    dusty rose, indigo, violet-instead-of-black, lamp orange);
  - at most WARM_MAX warm yellow-orange slots;
  - minimum pairwise distance MIN_PAIR_DE in the OKLab*100 scale
    (black-white ~= 100), anchors snap to real clusters within ANCHOR_SNAP_DE;
  - the palette has exactly PALETTE_SIZE colors.

Conversion maps every pixel to the nearest palette color in OKLab
(perceptual Euclidean, not RGB) and prints mean/max color error in the same
OKLab*100 scale. --measure-only prints the error table without writing files
(used to compare palettes with one and the same method).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 480, 270          # base game resolution (16:9)
PALETTE_SIZE = 48        # total palette slots
MIN_PAIR_DE = 4.0        # OKLab*100 scale: no two palette colors closer than this
ANCHOR_SNAP_DE = 6.0     # a GIVEN anchor snaps to a real cluster within this distance
SEED_SNAP_DE = 12.0      # seed anchors pick a cluster within this, else keep the seed hex
WARM_MAX = 10            # cap on warm yellow-orange slots (anchors included)
WARM_HUE = (40.0, 90.0)  # OKLCh hue degrees that count as warm yellow-orange
WARM_CHROMA = 0.05       # min OKLCh chroma to count as warm (excludes cream)
KMEANS_K = 52            # initial cluster count before anchors/merges
KMEANS_ITERS = 30
SEED = 0

GIVEN_ANCHORS = [        # lead-specified anchors ("about" these hexes)
    ("cream_white", "F4EAD8"),
    ("lavender_white", "D9D0EC"),
    ("sky_light", "8FD3E6"),
    ("sky_saturated", "3FA7D6"),
    ("green_dark", "3E7A3A"),
    ("green_light", "8AA84A"),
]
SEED_ANCHORS = [         # [s] fallback seeds; final value = nearest source cluster, reported
    ("turquoise", "3FB8AF"),
    ("terracotta", "C06A4D"),
    ("dusty_rose", "C98D8A"),
    ("indigo", "3A3F8F"),
    ("violet_black", "2B2440"),
    ("lamp_orange", "F08C3A"),
]

DE_SCALE = 100.0         # OKLab distances are multiplied by this (black-white ~= 100)

# --- ordered dithering (default OFF; enable with --dither bayer) -------------
DITHER_GAP_CAP = 6.0     # OKLab*100: pixel's two nearest slots farther apart than
                         # this still use this cap, so noise never exceeds
                         # 0.5 * strength * 6.0 per axis (2.6 vector at strength 1.0)
GRAD_THRESHOLD = 2.0     # OKLab*100: dither only where the 3x3 max neighbor
                         # difference on the LANCZOS source is below this
DITHER_STRENGTH_DEFAULT = 0.4  # chosen by metrics on the gangbang sky: series mean
                               # 19.04 -> 6.02 rows with only +0.04 mean dE cost;
                               # 0.5-0.7 add visible grain without further benefit


def load_small(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return img.resize((W, H), Image.LANCZOS)


# --- OKLab (Bjorn Ottosson) -------------------------------------------------

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


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


def oklab_to_rgb(lab: np.ndarray) -> np.ndarray:
    L, a, b2 = lab[..., 0], lab[..., 1], lab[..., 2]
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b2) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b2) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b2) ** 3
    r = +4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    b = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return (_linear_to_srgb(np.stack([r, g, b], axis=-1)) * 255.0).round().astype(np.uint8)


def oklch(lab: np.ndarray) -> tuple:
    """Return (hue_degrees, chroma). Works on (..., 3) arrays or a single color."""
    a, b2 = lab[..., 1], lab[..., 2]
    chroma = np.sqrt(a * a + b2 * b2)
    hue = np.degrees(np.arctan2(b2, a)) % 360.0
    return hue, chroma


def de_oklab(lab_a: np.ndarray, lab_b: np.ndarray) -> float:
    """Pairwise OKLab distance in the OKLab*100 scale (black-white ~= 100)."""
    return float(np.linalg.norm(np.asarray(lab_a, dtype=np.float64)
                                - np.asarray(lab_b, dtype=np.float64)) * DE_SCALE)


def hex_to_rgb(h: str) -> np.ndarray:
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)


def rgb_hex(rgb) -> str:
    return "%02X%02X%02X" % tuple(int(v) for v in rgb)


def is_warm(lab: np.ndarray) -> bool:
    hue, chroma = oklch(lab)
    if WARM_HUE[0] <= hue <= WARM_HUE[1] and chroma >= WARM_CHROMA:
        return True
    return False


# --- k-means -----------------------------------------------------------------

def kmeans(lab_pixels: np.ndarray, k: int, iters: int = KMEANS_ITERS, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centroids = lab_pixels[rng.choice(len(lab_pixels), size=k, replace=False)].copy()
    for _ in range(iters):
        # assign in chunks
        idx = np.empty(len(lab_pixels), dtype=np.int32)
        chunk = 50000
        for i in range(0, len(lab_pixels), chunk):
            part = lab_pixels[i:i + chunk]
            d = ((part[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
            idx[i:i + chunk] = d.argmin(axis=1)
        new = centroids.copy()
        for c in range(k):
            members = lab_pixels[idx == c]
            if len(members):
                new[c] = members.mean(axis=0)
        shift = np.abs(new - centroids).max()
        centroids = new
        if shift < 1e-4:
            break
    return centroids


def pair_table(colors: np.ndarray) -> np.ndarray:
    """Symmetric pairwise OKLab*100 distance matrix."""
    d = np.linalg.norm(colors[:, None, :] - colors[None, :, :], axis=2) * DE_SCALE
    np.fill_diagonal(d, np.inf)
    return d


# --- palette build -----------------------------------------------------------

def build_palette(sources, out_path: Path):
    print("scale: OKLab*100 (black-white ~= 100); MIN_PAIR_DE=%.1f, ANCHOR_SNAP_DE=%.1f, WARM_MAX=%d"
          % (MIN_PAIR_DE, ANCHOR_SNAP_DE, WARM_MAX))
    arrs = [np.asarray(load_small(Path(s))).reshape(-1, 3) for s in sources]
    pixels = np.concatenate(arrs)
    labs = rgb_to_oklab(pixels)

    centroids = kmeans(labs, KMEANS_K)

    # resolve anchors: given ones snap to the nearest cluster within ANCHOR_SNAP_DE,
    # seed ones pick the nearest cluster within SEED_SNAP_DE (else keep the seed hex)
    anchors = []       # list of (name, lab, provenance string, is_given)
    used_clusters = set()
    for name, hexval in GIVEN_ANCHORS:
        seed_lab = rgb_to_oklab(hex_to_rgb(hexval).reshape(1, 3))[0]
        d = np.linalg.norm(centroids - seed_lab, axis=1) * DE_SCALE
        best = int(d.argmin())
        if d[best] <= ANCHOR_SNAP_DE:
            anchors.append((name, centroids[best].copy(),
                            "%s -> cluster %s (dE %.1f)" % (hexval, rgb_hex(oklab_to_rgb(centroids[best].reshape(1, 3))[0]), d[best]),
                            True))
            used_clusters.add(best)
        else:
            anchors.append((name, seed_lab, "%s (kept as given, nearest cluster dE %.1f)" % (hexval, d[best]), True))
    for name, hexval in SEED_ANCHORS:
        seed_lab = rgb_to_oklab(hex_to_rgb(hexval).reshape(1, 3))[0]
        d = np.linalg.norm(centroids - seed_lab, axis=1) * DE_SCALE
        best = int(d.argmin())
        if d[best] <= SEED_SNAP_DE and best not in used_clusters:
            anchors.append((name, centroids[best].copy(),
                            "seed %s -> cluster %s (dE %.1f)" % (hexval, rgb_hex(oklab_to_rgb(centroids[best].reshape(1, 3))[0]), d[best]),
                            False))
            used_clusters.add(best)
        else:
            anchors.append((name, seed_lab, "seed %s (kept as given)" % hexval, False))

    anchor_labs = np.stack([a[1] for a in anchors])

    # anchors must be mutually >= MIN_PAIR_DE apart; nudge the later one if not
    for i in range(len(anchors)):
        for j in range(i + 1, len(anchors)):
            d = de_oklab(anchors[i][1], anchors[j][1])
            if d < MIN_PAIR_DE:
                # push anchors[j] away from anchors[i] along the connecting axis
                direction = anchors[j][1] - anchors[i][1]
                n = np.linalg.norm(direction)
                if n < 1e-9:
                    direction = np.array([0.0, 1.0, 0.0])
                    n = 1.0
                target = MIN_PAIR_DE + 0.5
                anchors[j] = (anchors[j][0], anchors[i][1] + direction / n * (target / DE_SCALE),
                              anchors[j][2] + " | NUDGED away from %s (was dE %.1f)" % (anchors[i][0], d), anchors[j][3])
                anchor_labs[j] = anchors[j][1]
                print("WARN: anchors %s/%s were dE %.1f apart; %s nudged to %s"
                      % (anchors[i][0], anchors[j][0], d, anchors[j][0], rgb_hex(oklab_to_rgb(anchors[j][1].reshape(1, 3))[0])))

    # pool: k-means centroids not absorbed by anchors
    pool = [c for i, c in enumerate(centroids) if i not in used_clusters]

    # drop/merge pool colors too close to anchors or each other
    def all_colors():
        return np.concatenate([anchor_labs, np.stack(pool)]) if pool else anchor_labs

    changed = True
    while changed and pool:
        changed = False
        colors = all_colors()
        dmat = pair_table(colors)
        i, j = np.unravel_index(dmat.argmin(), dmat.shape)
        if dmat[i, j] < MIN_PAIR_DE:
            if i >= len(anchors) and j >= len(anchors):
                # merge two pool colors
                a, b = min(i, j) - len(anchors), max(i, j) - len(anchors)
                pool[a] = (pool[a] + pool[b]) / 2.0
                del pool[b]
            else:
                # too close to an anchor: remove the pool color
                del pool[max(i, j) - len(anchors)]
            changed = True

    # warm cap: merge warm pool colors until the cap holds (anchors are frozen)
    def warm_count():
        return sum(1 for a in anchors if is_warm(a[1])) + sum(1 for c in pool if is_warm(c))

    while warm_count() > WARM_MAX and pool:
        warm_idx = [i for i, c in enumerate(pool) if is_warm(c)]
        best_pair, best_d = None, None
        for x in warm_idx:
            colors = all_colors()
            d = np.linalg.norm(colors - pool[x], axis=1) * DE_SCALE
            d[len(anchors) + x] = np.inf
            if best_d is None or d.min() < best_d:
                best_d, best_pair = d.min(), (x, int(d.argmin()))
        x, y = best_pair
        y -= len(anchors) if y >= len(anchors) else 0
        if 0 <= y < len(pool) and y != x:
            pool[x] = (pool[x] + pool[y]) / 2.0
            del pool[y]
        else:
            del pool[x]  # nearest neighbor was an anchor: drop the warm color
        changed = True
        while changed and pool:  # keep MIN_PAIR_DE valid after cap merges
            changed = False
            colors = all_colors()
            dmat = pair_table(colors)
            i, j = np.unravel_index(dmat.argmin(), dmat.shape)
            if dmat[i, j] < MIN_PAIR_DE:
                if i >= len(anchors) and j >= len(anchors):
                    a, b = min(i, j) - len(anchors), max(i, j) - len(anchors)
                    pool[a] = (pool[a] + pool[b]) / 2.0
                    del pool[b]
                else:
                    del pool[max(i, j) - len(anchors)]
                changed = True

    colors = all_colors()

    # split the largest clusters until exactly PALETTE_SIZE colors
    # (warm-cap aware: a split that would exceed WARM_MAX is rejected)
    while len(colors) < PALETTE_SIZE:
        counts = []
        chunk = 50000
        idx = np.empty(len(labs), dtype=np.int32)
        for i in range(0, len(labs), chunk):
            part = labs[i:i + chunk]
            d = ((part[:, None, :] - colors[None, :, :]) ** 2).sum(axis=2)
            idx[i:i + chunk] = d.argmin(axis=1)
        for c in range(len(colors)):
            counts.append(int((idx == c).sum()))
        order = np.argsort(counts)[::-1]
        warm_before = sum(1 for lab in colors if is_warm(lab))
        placed = False
        for cand in order:
            if cand < len(anchors):
                continue
            base = colors[cand]
            delta = 2.5 / DE_SCALE
            for axis in (1, 2, 0):
                trial_a = base.copy()
                trial_b = base.copy()
                trial_a[axis] += delta
                trial_b[axis] -= delta
                da = np.linalg.norm(colors - trial_a, axis=1) * DE_SCALE
                db = np.linalg.norm(colors - trial_b, axis=1) * DE_SCALE
                da[cand], db[cand] = np.inf, np.inf
                if da.min() >= MIN_PAIR_DE and db.min() >= MIN_PAIR_DE:
                    warm_after = warm_before - (1 if is_warm(base) else 0) \
                        + (1 if is_warm(trial_a) else 0) + (1 if is_warm(trial_b) else 0)
                    if warm_after > WARM_MAX:
                        continue  # this split would break the warm cap
                    pool.append(trial_a)
                    pool[cand - len(anchors)] = trial_b
                    placed = True
                    break
            if placed:
                break
        if not placed:
            print("WARN: cannot split further while keeping MIN_PAIR_DE and WARM_MAX")
            break
        colors = all_colors()

    # final pass: merge again if any pair drifted under the threshold
    pool_changed = True
    while pool_changed and len(colors) > PALETTE_SIZE:
        pool_changed = False
        colors = all_colors()
        if len(colors) <= PALETTE_SIZE:
            break
        dmat = pair_table(colors)
        i, j = np.unravel_index(dmat.argmin(), dmat.shape)
        if i >= len(anchors) and j >= len(anchors):
            a, b = min(i, j) - len(anchors), max(i, j) - len(anchors)
            pool[a] = (pool[a] + pool[b]) / 2.0
            del pool[b]
            pool_changed = True
        else:
            print("WARN: over %d colors and the closest pair touches an anchor; stopping merges" % PALETTE_SIZE)
            break

    colors = all_colors()
    if len(colors) != PALETTE_SIZE:
        print("WARN: palette has %d colors, expected %d" % (len(colors), PALETTE_SIZE))

    # deterministic output order: anchors first (given, then seeds), pool by lightness
    pool_sorted = sorted(pool, key=lambda c: c[0])
    final_labs = np.concatenate([anchor_labs, np.stack(pool_sorted)]) if pool_sorted else anchor_labs
    final_rgb = oklab_to_rgb(final_labs)

    # report
    print("anchors (%d):" % len(anchors))
    for (name, _, prov, _), rgb in zip(anchors, final_rgb[:len(anchors)]):
        print("  %-14s #%s  %s" % (name, rgb_hex(rgb), prov))
    warm_idx = [i for i, lab in enumerate(final_labs) if is_warm(lab)]
    dmat = pair_table(final_labs)
    i, j = np.unravel_index(dmat.argmin(), dmat.shape)
    print("palette: %d colors | warm yellow-orange slots: %d (cap %d) | min pair dE %.2f (%s/%s)"
          % (len(final_rgb), len(warm_idx), WARM_MAX, dmat[i, j], rgb_hex(final_rgb[i]), rgb_hex(final_rgb[j])))
    print("hex list:")
    print("\n".join("  %s" % rgb_hex(c) for c in final_rgb))

    swatch = Image.new("RGB", (len(final_rgb), 1))
    swatch.putdata([tuple(int(v) for v in c) for c in final_rgb])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    swatch.save(out_path)
    hex_path = out_path.with_suffix(".hex")
    hex_path.write_text("\n".join(rgb_hex(c) for c in final_rgb) + "\n")
    print("palette -> %s, %s" % (out_path, hex_path))


def read_palette(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    return np.asarray(img).reshape(-1, 3).astype(np.uint8)


def bayer4() -> np.ndarray:
    """Bayer 4x4 threshold matrix normalized to [-0.5, +0.5)."""
    m = np.array([[0, 8, 2, 10],
                  [12, 4, 14, 6],
                  [3, 11, 9, 15],
                  [15, 7, 13, 5]], dtype=np.float64)
    return (m + 0.5) / 16.0 - 0.5


def smooth_mask(labs: np.ndarray) -> np.ndarray:
    """True where the 3x3 max neighbor OKLab*100 difference on the LANCZOS
    source (BEFORE palette matching) is below GRAD_THRESHOLD: smooth gradients
    get dithering, edges/architecture/windows/text keep their crisp pixels."""
    lab_img = labs.reshape(H, W, 3)
    padded = np.pad(lab_img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    grad = np.zeros((H, W), dtype=np.float64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            neigh = padded[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx, :]
            grad = np.maximum(grad, np.linalg.norm(neigh - lab_img, axis=2) * DE_SCALE)
    return (grad < GRAD_THRESHOLD).reshape(-1)


def convert(src: Path, dst: Path, palette_path: Path, preview: bool, measure_only: bool,
            dither: str = None, dither_strength: float = DITHER_STRENGTH_DEFAULT):
    pal = read_palette(palette_path)
    pal_lab = rgb_to_oklab(pal)
    small = np.asarray(load_small(src)).reshape(-1, 3).astype(np.uint8)
    labs = rgb_to_oklab(small)

    use_dither = dither == "bayer"
    if use_dither:
        mask = smooth_mask(labs)
        bay = bayer4()
        bayer_vals = bay[np.arange(H)[:, None] % 4, np.arange(W)[None, :] % 4].reshape(-1)
        print("dither: bayer 4x4 in OKLab; strength %.2f (default %.2f); amplitude = bayer * strength *"
              " min(gap to 2nd nearest slot, cap %.1f), equal per-axis offset; mask: 3x3 max neighbor"
              " dE < %.1f on the LANCZOS source, before palette matching"
              % (dither_strength, DITHER_STRENGTH_DEFAULT, DITHER_GAP_CAP, GRAD_THRESHOLD))

    out_idx = np.empty(len(small), dtype=np.int32)
    chunk = 20000
    err_sum = 0.0
    err_max = 0.0
    if use_dither:
        err_after_sum = 0.0
        err_after_max = 0.0
        dithered_pixels = 0
    for i in range(0, len(small), chunk):
        part = labs[i:i + chunk]
        d = np.linalg.norm(part[:, None, :] - pal_lab[None, :, :], axis=2) * DE_SCALE
        best = d.argmin(axis=1)
        if use_dither:
            # amplitude from the palette: distance between the two nearest slots,
            # capped (see DITHER_GAP_CAP); at strength 1.0 the noise reaches the
            # midpoint between the two slots
            d2 = d.copy()
            d2[np.arange(len(part)), best] = np.inf
            second = d2.argmin(axis=1)
            gap = np.linalg.norm(pal_lab[best] - pal_lab[second], axis=1) * DE_SCALE
            amp = dither_strength * np.minimum(gap, DITHER_GAP_CAP)
            offset = (bayer_vals[i:i + len(part)] * amp)[:, None] / DE_SCALE
            d_d = np.linalg.norm((part + offset)[:, None, :] - pal_lab[None, :, :], axis=2) * DE_SCALE
            best_d = d_d.argmin(axis=1)
            m = mask[i:i + len(part)]
            out_idx[i:i + len(part)] = np.where(m, best_d, best)
            sel = d[np.arange(len(part)), best]                      # error before dithering
            err_after = np.linalg.norm(part - pal_lab[out_idx[i:i + len(part)]], axis=1) * DE_SCALE
            err_after_sum += float(err_after.sum())
            err_after_max = max(err_after_max, float(err_after.max()))
            dithered_pixels += int(m.sum())
        else:
            out_idx[i:i + len(part)] = best
            sel = d[np.arange(len(part)), best]
        err_sum += float(sel.sum())
        err_max = max(err_max, float(sel.max()))
    mean_de = err_sum / len(small)
    print("%s: mean dE %.2f, max dE %.2f (OKLab*100, palette %s: %d colors)"
          % (src.name, mean_de, err_max, palette_path.name, len(pal)))
    if use_dither:
        print("  dither: %d/%d pixels (%.1f%%) dithered by the smooth-area mask; "
              "error vs source BEFORE dither mean %.2f / max %.2f, AFTER dither mean %.2f / max %.2f"
              % (dithered_pixels, len(small), 100.0 * dithered_pixels / len(small),
                 mean_de, err_max, err_after_sum / len(small), err_after_max))
    # anchor coverage: how many pixels map to each palette color (top slots + anchors)
    counts = np.bincount(out_idx, minlength=len(pal))
    order = counts.argsort()[::-1]
    print("  slot coverage (top 8): %s"
          % ", ".join("#%s: %d" % (rgb_hex(pal[i]), counts[i]) for i in order[:8]))
    anchor_names = [n for n, _ in GIVEN_ANCHORS] + [n for n, _ in SEED_ANCHORS]
    anchor_hexes = [h for _, h in GIVEN_ANCHORS] + [h for _, h in SEED_ANCHORS]
    anchor_labs_const = rgb_to_oklab(np.stack([hex_to_rgb(h) for h in anchor_hexes]))
    slot_anchor = []
    for c in pal:
        lab = rgb_to_oklab(c.reshape(1, 3))[0]
        d = np.linalg.norm(anchor_labs_const - lab, axis=1) * DE_SCALE
        k = int(d.argmin())
        slot_anchor.append(anchor_names[k] if d[k] <= ANCHOR_SNAP_DE else None)
    agg = {}
    for i, name in enumerate(slot_anchor):
        if name and counts[i] > 0:
            agg[name] = agg.get(name, 0) + int(counts[i])
    print("  anchor coverage (dE<=%.0f neighborhoods): %s"
          % (ANCHOR_SNAP_DE, ", ".join("%s: %d" % kv for kv in sorted(agg.items())) or "NONE"))
    if measure_only:
        return
    result = Image.fromarray(pal[out_idx].reshape(H, W, 3), "RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(dst)
    print("%s -> %s (%dx%d)" % (src.name, dst, W, H))
    if preview:
        big = dst.with_name(dst.stem + "_preview_x3.png")
        result.resize((W * 3, H * 3), Image.NEAREST).save(big)
        print("preview -> %s" % big)


def palette_add(out_path: Path, base_path: Path, new_hex: str, sources):
    """П-33: surgically add one slot to a palette (v2 -> v3).

    ALL constraint checks run on QUANTIZED colors (uint8 round trip), because
    uint8 quantization can erode float-time pair distances below the threshold
    (this is exactly how palette v2 on disk ended up with a 2.27 pair while its
    build printed 4.14)."""
    print("scale: OKLab*100 (black-white ~= 100); pair threshold %.1f checked on QUANTIZED colors; snap tolerance %.1f"
          % (MIN_PAIR_DE, ANCHOR_SNAP_DE))
    base = read_palette(base_path)
    if len(base) != PALETTE_SIZE:
        print("FAIL: base palette %s has %d colors, expected %d" % (base_path, len(base), PALETTE_SIZE))
        return
    # first 12 entries of a build_palette output are the anchors
    cur_rgb = [c for c in base]                 # exact uint8 colors, byte-preserving
    cur = [rgb_to_oklab(c) for c in base]
    cur_hexes = [rgb_hex(c) for c in base]
    anchor_hexes = set(cur_hexes[:12])

    def q(lab):
        """Quantize float OKLab: -> uint8 RGB -> back to OKLab."""
        return rgb_to_oklab(oklab_to_rgb(lab.reshape(1, 3)).reshape(1, 3))[0]

    def qhex(lab):
        return rgb_hex(oklab_to_rgb(lab.reshape(1, 3))[0])

    # snap the given hex to a real k-means cluster of the sources
    labs_all = rgb_to_oklab(np.concatenate([np.asarray(load_small(Path(s))).reshape(-1, 3) for s in sources]))
    centroids = kmeans(labs_all, KMEANS_K)
    given_lab = rgb_to_oklab(hex_to_rgb(new_hex).reshape(1, 3))[0]
    d = np.linalg.norm(centroids - given_lab, axis=1) * DE_SCALE
    best = int(d.argmin())
    if d[best] <= ANCHOR_SNAP_DE:
        snap_lab = centroids[best]
        print("new slot: given %s -> cluster %s (dE %.1f)" % (new_hex, qhex(snap_lab), d[best]))
    else:
        snap_lab = given_lab
        print("new slot: given %s kept as is (nearest cluster dE %.1f)" % (new_hex, d[best]))

    # insert the new slot; if it violates the pair threshold (quantized), shift it
    # ONLY along the line between the two REAL v2 sky slots (9CD1EA -> 3FA9D9)
    ia = cur_hexes.index("9CD1EA")
    ib = cur_hexes.index("3FA9D9")
    lab_a, lab_b = cur[ia], cur[ib]
    new_lab_q = None
    snap_hex = qhex(snap_lab)
    if snap_hex not in cur_hexes:
        dmin_snap = min(float(np.linalg.norm(q(snap_lab) - l) * DE_SCALE) for l in cur)
        if dmin_snap >= MIN_PAIR_DE:
            new_lab_q = q(snap_lab)
            print("new slot: %s (snapped cluster; quantized min pair %.1f - no shift needed)"
                  % (snap_hex, dmin_snap))
    if new_lab_q is None:
        best_t, best_gap = None, None
        for t in np.linspace(0.0, 1.0, 2001):
            trial = q(lab_a + t * (lab_b - lab_a))
            if qhex(trial) in cur_hexes:
                continue
            dmin = min(float(np.linalg.norm(trial - l) * DE_SCALE) for l in cur)
            if dmin >= MIN_PAIR_DE:
                dist = float(np.linalg.norm(trial - snap_lab) * DE_SCALE)
                if best_gap is None or dist < best_gap:
                    best_gap, best_t = dist, t
        if best_t is None:
            print("FAIL: no position on the 9CD1EA -> 3FA9D9 line satisfies dE >= %.1f (quantized)" % MIN_PAIR_DE)
            return
        new_lab_q = q(lab_a + best_t * (lab_b - lab_a))
        print("new slot: %s (t=%.3f on the 9CD1EA -> 3FA9D9 line, dE %.1f from the snapped cluster %s)"
              % (qhex(new_lab_q), best_t, best_gap, snap_hex))
    cur.append(new_lab_q)
    cur_rgb.append(oklab_to_rgb(new_lab_q.reshape(1, 3))[0])
    cur_hexes.append(qhex(new_lab_q))
    new_pos = len(cur) - 1

    # per-background no-dither mapping for usage/regression stats (rebuilt after
    # every removal, because indices shift)
    src_labs = [rgb_to_oklab(np.asarray(load_small(Path(s))).reshape(-1, 3).astype(np.uint8)) for s in sources]

    def map_indices(pal_labs):
        pal_arr = np.stack(pal_labs)
        out = []
        for labs in src_labs:
            idx = np.empty(len(labs), dtype=np.int32)
            chunk = 50000
            for i in range(0, len(labs), chunk):
                part = labs[i:i + chunk]
                dd = np.linalg.norm(part[:, None, :] - pal_arr[None, :, :], axis=2) * DE_SCALE
                idx[i:i + chunk] = dd.argmin(axis=1)
            out.append(idx)
        return out

    per_bg = map_indices(cur)

    def rebuild_usage():
        nonlocal per_bg, usage
        per_bg = map_indices(cur)
        usage = np.zeros(len(cur), dtype=np.int64)
        for idx in per_bg:
            usage += np.bincount(idx, minlength=len(cur))

    usage = np.zeros(len(cur), dtype=np.int64)
    for idx in per_bg:
        usage += np.bincount(idx, minlength=len(cur))

    def removal_stats(cand):
        """Per-background regression stats for removing slot cand."""
        keep = [k for k in range(len(cur)) if k != cand]
        reduced = np.stack(cur)[keep]
        reduced_rgb = oklab_to_rgb(reduced)
        cur_rgb_arr = np.stack([np.asarray(c) for c in cur_rgb])
        stats = []
        for s_i, idx_cur in enumerate(per_bg):
            labs = src_labs[s_i]
            idx_new = np.empty(len(labs), dtype=np.int32)
            chunk = 50000
            for i in range(0, len(labs), chunk):
                part = labs[i:i + chunk]
                dd = np.linalg.norm(part[:, None, :] - reduced[None, :, :], axis=2) * DE_SCALE
                idx_new[i:i + chunk] = dd.argmin(axis=1)
            old_rgb = cur_rgb_arr[idx_cur]
            new_rgb = reduced_rgb[idx_new]
            changed_de = np.linalg.norm(
                rgb_to_oklab(old_rgb.reshape(-1, 3)) - rgb_to_oklab(new_rgb.reshape(-1, 3)), axis=1) * DE_SCALE
            gt6 = int((changed_de > 6.0).sum())
            stats.append((gt6, gt6 / len(labs), idx_new, reduced_rgb))
        return stats

    def remove_slot(cand, reason):
        nonlocal per_bg, usage, new_pos
        stats = removal_stats(cand)
        print("removed slot: #%s (%s), usage per background: %s, total %d"
              % (cur_hexes[cand], reason,
                 ", ".join("%s: %d" % (Path(s).stem, int((idx == cand).sum())) for s, idx in zip(sources, per_bg)),
                 int(usage[cand])))
        for s, (gt6, frac, _, _) in zip(sources, stats):
            print("  regression check %s: %d pixels (%.3f%%) changed color by more than dE 6.0"
                  % (Path(s).stem, gt6, 100.0 * frac))
        reduced_rgb = stats[0][3]
        for s_i, (_, _, idx_new, _) in enumerate(stats):
            moved = per_bg[s_i] == cand
            if moved.any():
                pairs = {}
                for new_k in idx_new[moved]:
                    h = rgb_hex(reduced_rgb[new_k])
                    pairs[h] = pairs.get(h, 0) + 1
                top = sorted(pairs.items(), key=lambda kv: -kv[1])[:4]
                print("  remap %s: #%s -> %s" % (Path(sources[s_i]).stem, cur_hexes[cand],
                      ", ".join("#%s: %d" % (dst, cnt) for dst, cnt in top)))
        del cur[cand]
        del cur_rgb[cand]
        del cur_hexes[cand]
        if cand < new_pos:
            new_pos -= 1
        rebuild_usage()

    # step 1: repair any pair violations (including ones inherited from the base
    # palette): remove the non-anchor slot involved in the most violating pairs
    while True:
        labs_arr = np.stack(cur)
        dm = pair_table(labs_arr)
        viol = [(a, b) for a in range(len(cur)) for b in range(a + 1, len(cur)) if dm[a, b] < MIN_PAIR_DE]
        if not viol:
            break
        for a, b in viol:
            print("violating pair: #%s <-> #%s (dE %.2f)" % (cur_hexes[a], cur_hexes[b], dm[a, b]))
        cnt = {}
        for a, b in viol:
            for k in (a, b):
                if k != new_pos and cur_hexes[k] not in anchor_hexes:
                    cnt[k] = cnt.get(k, 0) + 1
        if not cnt:
            print("FAIL: every violating pair consists of anchors/new slot only")
            return
        victim = max(cnt, key=lambda k: (cnt[k], -usage[k]))
        remove_slot(victim, "repair: member of %d violating pair(s)" % cnt[victim])

    # step 2: still too many slots? remove the least-used non-anchor slots
    # (0.5% >dE 6.0 regression budget per the lead's rule)
    while len(cur) > PALETTE_SIZE:
        candidates = sorted((k for k in range(len(cur))
                             if k != new_pos and cur_hexes[k] not in anchor_hexes),
                            key=lambda k: usage[k])
        chosen = None
        for cand in candidates:
            stats = removal_stats(cand)
            worst_i = max(range(len(stats)), key=lambda s: stats[s][1])
            worst = stats[worst_i][1]
            if worst <= 0.005:
                chosen = cand
                break
            print("candidate #%s rejected: %.2f%% pixels change color by more than dE 6.0 in %s (budget 0.5%%)"
                  % (cur_hexes[cand], 100.0 * worst, Path(sources[worst_i]).stem))
        if chosen is None:
            print("FAIL: no removal fits the 0.5%% dE>6.0 budget")
            return
        remove_slot(chosen, "least-used non-anchor (regression within 0.5%% budget)")

    if len(cur) < PALETTE_SIZE:
        print("FAIL: palette has %d colors, expected %d; no slots invented" % (len(cur), PALETTE_SIZE))
        return

    # verification on the exact quantized palette that gets written
    final_rgb = np.stack([np.asarray(c) for c in cur_rgb])
    final_labs = np.stack(cur)
    dm = pair_table(final_labs)
    i, j = np.unravel_index(dm.argmin(), dm.shape)
    warm_n = sum(1 for lab in final_labs if is_warm(lab))
    final_hexes = [rgb_hex(c) for c in final_rgb]
    anchors_present = sum(1 for h in anchor_hexes if h in final_hexes)
    new_rgb_final = np.asarray(cur_rgb[new_pos])
    final_idx = map_indices(final_labs)
    new_total = int(sum(np.all(final_rgb[k] == new_rgb_final, axis=1).sum() for k in final_idx))
    sky_idx = final_idx[2].reshape(H, W)[: int(H * 0.35), :].reshape(-1)
    new_in_sky = int(np.all(final_rgb[sky_idx] == new_rgb_final, axis=1).sum())
    print("verify: %d colors | min pair dE %.2f (%s/%s) | warm slots %d (cap %d) | anchors %d/12 present"
          % (len(final_rgb), dm[i, j], final_hexes[i], final_hexes[j], warm_n, WARM_MAX, anchors_present))
    print("new slot #%s usage: %d pixels total, gangbang sky (top 35%%): %d"
          % (cur_hexes[new_pos], new_total, new_in_sky))
    hex_order = "\n".join(final_hexes)
    print("hex list:\n%s" % hex_order)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    swatch = Image.new("RGB", (len(final_rgb), 1))
    swatch.putdata([tuple(int(v) for v in c) for c in final_rgb])
    swatch.save(out_path)
    hex_path = out_path.with_suffix(".hex")
    hex_path.write_text(hex_order + "\n")
    print("palette -> %s, %s" % (out_path, hex_path))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("palette", help="build shared palette from master images")
    p.add_argument("out")
    p.add_argument("sources", nargs="+")
    p3 = sub.add_parser("palette-add", help="surgically add one slot to an existing palette (P-33)")
    p3.add_argument("out")
    p3.add_argument("--base", required=True)
    p3.add_argument("new_hex")
    p3.add_argument("sources", nargs="+")
    c = sub.add_parser("convert", help="convert one image with the shared palette")
    c.add_argument("src")
    c.add_argument("dst")
    c.add_argument("--palette", required=True)
    c.add_argument("--preview", action="store_true", help="also save a 3x nearest-neighbor preview")
    c.add_argument("--measure-only", action="store_true",
                   help="print error metrics only, write nothing (palette comparison)")
    c.add_argument("--dither", choices=["bayer"], default=None,
                   help="ordered dithering for smooth gradients (default: off)")
    c.add_argument("--dither-strength", type=float, default=DITHER_STRENGTH_DEFAULT,
                   help="dither strength (default %.2f)" % DITHER_STRENGTH_DEFAULT)
    a = ap.parse_args()
    if a.cmd == "palette":
        build_palette(a.sources, Path(a.out))
    elif a.cmd == "palette-add":
        palette_add(Path(a.out), Path(a.base), a.new_hex.upper(), a.sources)
    else:
        convert(Path(a.src), Path(a.dst), Path(a.palette), a.preview, a.measure_only,
                a.dither, a.dither_strength)


if __name__ == "__main__":
    sys.exit(main())
