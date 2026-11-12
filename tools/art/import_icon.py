#!/usr/bin/env python3
"""Turn the AI-generated chronicler portrait into a 48x48 palette icon.

Pipeline (lead's task, 2026-11-12):
  1) background key: the background color is taken from the frame corners;
     pixels close to it become transparent ONLY if connected to the frame
     edges (flood fill from the edges), so light parts inside the figure are
     never cut out;
  2) crop to the figure bounding box, fit the longest side into 44 px,
     center in a 48x48 canvas (2 px margin);
  3) downscale by averaging (LANCZOS), then every opaque pixel is mapped to
     the nearest color of art/palette_v3.hex by OKLab Euclidean distance
     (the Д-18 scale, OKLab*100); alpha is binary (threshold 0.5);
     no dithering. If quantization yields more than 16 unique opaque colors,
     the rarest color is repeatedly remapped to its nearest remaining color
     (script adjustment, thresholds unchanged) until <= 16 remain;
  4) write assets/ui/scribe_icon.png (48x48 RGBA);
  5) --preview also writes art/preview_icon/scribe_icon_x8.png
     (nearest x8 upscale, at most one current version).

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
ALPHA_THRESHOLD = 0.5    # binary alpha after the averaging downscale
UNIQUE_COLORS_MAX = 16   # test threshold; enforced by merging, never loosened
BG_KEY_DE = 6.0          # [с] corner-key threshold, OKLab*100 scale (Д-18)
SHIFT_REPORT_DE = 6.0    # report share of pixels moved by more than this

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


def bg_key_alpha(rgb: np.ndarray) -> np.ndarray:
    """Return binary alpha (0 = background, 255 = figure) via edge flood fill."""
    h, w, _ = rgb.shape
    corners = np.stack([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(rgb_to_oklab(rgb) - rgb_to_oklab(bg.reshape(1, 1, 3)),
                          axis=-1) * DE_SCALE
    close = dist <= BG_KEY_DE
    # geodesic reconstruction: keep only "close" pixels connected to the border
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true",
                    help="also write art/preview_icon/scribe_icon_x8.png")
    args = ap.parse_args()

    src = Image.open(SRC_PATH).convert("RGB")
    rgb = np.asarray(src)
    alpha = bg_key_alpha(rgb)

    # crop to the figure bounding box
    ys, xs = np.nonzero(alpha)
    if len(ys) == 0:
        print("ERROR: background key removed everything; lower BG_KEY_DE")
        return 1
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    print("figure bbox: %s" % (box,))
    fig_alpha = Image.fromarray(alpha[box[1]:box[3], box[0]:box[2]], "L")
    fig_rgb = src.crop(box)

    # fit the longest side into FIGURE_MAX, centered in ICON_SIZE (2 px margin)
    fw, fh = fig_alpha.size
    scale = FIGURE_MAX / max(fw, fh)
    nw, nh = max(1, round(fw * scale)), max(1, round(fh * scale))
    ox, oy = (ICON_SIZE - nw) // 2, (ICON_SIZE - nh) // 2
    if ox < 2 or oy < 2:
        print("ERROR: figure does not fit with a 2 px margin (%dx%d -> %dx%d)"
              % (fw, fh, nw, nh))
        return 1

    fig_rgba = fig_rgb.resize((nw, nh), Image.LANCZOS).convert("RGBA")
    fig_rgba.putalpha(fig_alpha.resize((nw, nh), Image.LANCZOS))
    rgba = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    rgba.paste(fig_rgba, (ox, oy))

    # binary alpha (threshold 0.5), then palette quantization in OKLab
    arr = np.asarray(rgba).copy()
    arr[..., 3] = np.where(arr[..., 3] / 255.0 >= ALPHA_THRESHOLD, 255, 0)
    opaque = arr[..., 3] == 255
    palette = load_palette(PALETTE_PATH)
    pal_lab = rgb_to_oklab(palette)                       # (N, 3)
    px_lab = rgb_to_oklab(arr[..., :3])                   # (48, 48, 3)
    d = np.linalg.norm(px_lab[..., None, :] - pal_lab[None, None, :, :], axis=-1) \
        * DE_SCALE
    idx = d.argmin(axis=-1)
    print("quantized, unique before merge: %d" % len(np.unique(idx[opaque])))

    # enforce UNIQUE_COLORS_MAX by merging the rarest ACTIVE color into its
    # nearest other ACTIVE color (script adjustment; the threshold never moves;
    # targeting only active slots prevents ping-pong through absent slots)
    active = set(int(v) for v in np.unique(idx[opaque]))
    guard = 0
    while len(active) > UNIQUE_COLORS_MAX:
        guard += 1
        if guard > 100:
            print("ERROR: merge loop did not converge (active=%d)" % len(active))
            return 1
        vals, counts = np.unique(idx[opaque], return_counts=True)
        rare = int(vals[counts.argmin()])
        others = sorted(active - {rare})
        sub = np.linalg.norm(pal_lab[rare] - pal_lab[others], axis=-1) * DE_SCALE
        target = others[int(sub.argmin())]
        idx[idx == rare] = target
        active.discard(rare)
        active.add(target)
        print("merge: active=%d, slot %d -> %d" % (len(active), rare, target))

    # apply the palette colors and measure the final quantization shift
    pal_u8 = np.zeros_like(arr[..., :3])
    for i, c in enumerate(palette):
        pal_u8[idx == i] = c
    arr[..., :3][opaque] = pal_u8[opaque]
    shift = np.linalg.norm(px_lab - rgb_to_oklab(arr[..., :3]), axis=-1) * DE_SCALE

    Image.fromarray(arr, "RGBA").save(OUT_PATH)
    if args.preview:
        PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        Image.open(OUT_PATH).resize((ICON_SIZE * 8, ICON_SIZE * 8), Image.NEAREST) \
            .save(PREVIEW_PATH)

    final = np.unique(arr[opaque][:, :3], axis=0)
    hexes = sorted("%02X%02X%02X" % (int(p[0]), int(p[1]), int(p[2])) for p in final)
    moved = float((shift[opaque] > SHIFT_REPORT_DE).mean()) * 100.0
    print("opaque pixels: %d" % int(opaque.sum()))
    print("unique colors: %d -> %s" % (len(hexes), ", ".join(hexes)))
    print("pixels shifted >%.1f dE by quantization: %.1f%%" % (SHIFT_REPORT_DE, moved))
    print("written: %s%s" % (OUT_PATH.relative_to(ROOT),
                             " + %s" % PREVIEW_PATH.relative_to(ROOT) if args.preview else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
