"""Builds assets/images/comparison-xetafit.webp for section 08 (Comparison).

The right-hand comparison image needs the XETAFIT tube beside a prepared drink,
shot in the same cream studio light as the liquid-vinegar photograph on the left.
This script places the existing tube render (tube-angle.webp, built from the real
packshot) into the finished-drink frame of preparation-sequence.webp:

  * the background is upscaled to 1024 px to match comparison-vinegar.webp
  * the tube is sized to a real tube/tumbler ratio (about 1.1 x the glass height)
  * it is graded to the photo's warm light and softened to the photo's sharpness
  * a contact shadow and a soft cast shadow to the right follow the scene light

The label is never altered: only scale, a warm grade and edge softening.

    python tools/compose_comparison.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "assets" / "images"
OUT = IMG / "comparison-xetafit.webp"

SIZE = 1024                       # output square, matches the vinegar photo height
PANEL = (1448, 0, 2172, 724)      # the third ("sip") frame of the preparation sheet


def main() -> None:
    bg = Image.open(IMG / "preparation-sequence.webp").convert("RGB").crop(PANEL)
    bg = bg.resize((SIZE, SIZE), Image.LANCZOS)
    k = SIZE / 724

    tube = Image.open(IMG / "tube-angle.webp").convert("RGBA")
    th = int(500 * k)                                   # ~1.1 x the tumbler height, leaves headroom in a 5:4 crop
    tw = round(th * tube.width / tube.height)
    tube = tube.resize((tw, th), Image.LANCZOS)

    # warm grade towards the photo's daylight, slightly lower contrast
    a = np.asarray(tube).astype(np.float32)
    rgb = a[..., :3] / 255.0
    rgb = 0.06 + rgb * 0.92                             # lift blacks, soften whites
    rgb *= np.array([1.0, 0.975, 0.93], dtype=np.float32)
    # gentle fall-off to the right (light comes from the left of the scene)
    x = np.linspace(0, 1, tw, dtype=np.float32)[None, :, None]
    rgb *= 1.0 - 0.08 * x ** 1.6
    a[..., :3] = np.clip(rgb * 255, 0, 255)
    tube = Image.fromarray(a.astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(0.55))

    base_y = int(668 * k)                               # a little in front of the glass base (~655)
    left = int(44 * k)
    top = base_y - th

    # shadows: a tight contact line and a soft cast shadow falling to the right
    sh = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(sh)
    d.ellipse((left - 6 * k, base_y - 12 * k, left + tw + 6 * k, base_y + 9 * k), fill=150)
    sh_contact = sh.filter(ImageFilter.GaussianBlur(5 * k))
    cast = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(cast)
    d.polygon([(left + tw * 0.15, base_y - 4 * k), (left + tw * 0.95, base_y - 6 * k),
               (left + tw * 2.4, base_y - 40 * k), (left + tw * 1.3, base_y - 34 * k)], fill=70)
    cast = cast.filter(ImageFilter.GaussianBlur(16 * k))
    shadow = np.maximum(np.asarray(sh_contact), np.asarray(cast)).astype(np.float32) / 255.0
    shade = np.array([0.36, 0.27, 0.2], dtype=np.float32)        # warm, not grey
    b = np.asarray(bg).astype(np.float32) / 255.0
    b = b * (1 - shadow[..., None]) + b * shade * shadow[..., None]
    out = Image.fromarray(np.clip(b * 255, 0, 255).astype(np.uint8), "RGB")

    out.paste(tube, (left, top), tube)
    out.save(OUT, "WEBP", quality=86, method=6)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
