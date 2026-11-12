#!/usr/bin/env python3
"""Turn AI-generated location art into game-ready pixel art.

Two commands:

  1) Build the shared palette once, from the master images of all locations:
       python tools/art/import_bg.py palette art/palette.png art/src/bazaar.png art/src/oasis.png

  2) Convert any image with that palette:
       python tools/art/import_bg.py convert art/src/oasis.png assets/backgrounds/oasis.png --palette art/palette.png

Why a shared palette: every location then uses the same colors, so the game looks like one world.
Why reserved accents: plain quantization eats small but important colors (the glowing green spring,
grass, turquoise). Pixels that are clearly green/cyan and saturated get their own palette slots.
"""
import argparse
import colorsys
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 480, 270          # base game resolution (16:9)
BASE_COLORS = 40         # general palette size
ACCENT_COLORS = 8        # slots reserved for saturated green/cyan accents
ACCENT_HUE = (70, 200)   # degrees: yellow-green .. cyan
ACCENT_MIN_SAT = 0.28
ACCENT_MIN_VAL = 0.35


def load_small(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return img.resize((W, H), Image.LANCZOS)


def accent_mask(arr: np.ndarray) -> np.ndarray:
    """True where a pixel is a saturated green/cyan accent."""
    flat = arr.reshape(-1, 3) / 255.0
    mask = np.zeros(len(flat), dtype=bool)
    for i, (r, g, b) in enumerate(flat):
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        deg = h * 360
        if ACCENT_HUE[0] <= deg <= ACCENT_HUE[1] and s >= ACCENT_MIN_SAT and v >= ACCENT_MIN_VAL:
            mask[i] = True
    return mask


def quantize_pixels(pixels: np.ndarray, n: int) -> list:
    """Median-cut a list of RGB pixels down to n colors."""
    if len(pixels) == 0:
        return []
    side = int(np.ceil(np.sqrt(len(pixels))))
    padded = np.zeros((side * side, 3), dtype=np.uint8)
    padded[: len(pixels)] = pixels
    padded[len(pixels):] = pixels[-1]
    img = Image.fromarray(padded.reshape(side, side, 3), "RGB")
    q = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[: n * 3]
    return [tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)]


def build_palette(sources, out_path: Path):
    arrs = [np.asarray(load_small(Path(s))).reshape(-1, 3) for s in sources]
    pixels = np.concatenate(arrs)
    mask = accent_mask(pixels)
    base = quantize_pixels(pixels[~mask], BASE_COLORS)
    accents = quantize_pixels(pixels[mask], ACCENT_COLORS) if mask.any() else []
    colors = list(dict.fromkeys(base + accents))
    # palette as a swatch image (one pixel per color) + hex list for humans/Godot tooling
    swatch = Image.new("RGB", (len(colors), 1))
    swatch.putdata(colors)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    swatch.save(out_path)
    hex_path = out_path.with_suffix(".hex")
    hex_path.write_text("\n".join("%02x%02x%02x" % c for c in colors) + "\n")
    print(f"palette: {len(colors)} colors ({len(accents)} accents) -> {out_path}, {hex_path}")


def read_palette(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    return np.asarray(img).reshape(-1, 3).astype(np.int32)


def convert(src: Path, dst: Path, palette_path: Path, preview: bool):
    pal = read_palette(palette_path)
    small = np.asarray(load_small(src)).reshape(-1, 3).astype(np.int32)
    # nearest palette color for every pixel
    out = np.empty_like(small)
    chunk = 20000
    for i in range(0, len(small), chunk):
        part = small[i:i + chunk]
        d = ((part[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        out[i:i + chunk] = pal[d.argmin(axis=1)]
    result = Image.fromarray(out.reshape(H, W, 3).astype(np.uint8), "RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(dst)
    print(f"{src.name} -> {dst} ({W}x{H}, palette of {len(pal)})")
    if preview:
        big = dst.with_name(dst.stem + "_preview_x3.png")
        result.resize((W * 3, H * 3), Image.NEAREST).save(big)
        print(f"preview -> {big}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("palette", help="build shared palette from master images")
    p.add_argument("out")
    p.add_argument("sources", nargs="+")
    c = sub.add_parser("convert", help="convert one image with the shared palette")
    c.add_argument("src")
    c.add_argument("dst")
    c.add_argument("--palette", required=True)
    c.add_argument("--preview", action="store_true", help="also save a 3x nearest-neighbor preview")
    a = ap.parse_args()
    if a.cmd == "palette":
        build_palette(a.sources, Path(a.out))
    else:
        convert(Path(a.src), Path(a.dst), Path(a.palette), a.preview)


if __name__ == "__main__":
    sys.exit(main())
