"""
XETAFIT header logo: cut the official logo out of the client's campaign creative.

    python tools/extract_logo.py [creative.jpeg] [out.png]

The only official logo supplied so far is raster artwork on a flat near-black
backdrop (the 1080 px "Busy day?" creative; the small logo screenshot sent later
is a downscaled crop of the same artwork). This script removes ONLY that backdrop
by alpha-unmixing every pixel against the measured background colour. It does not
redraw, recolour, reshape or re-space anything. Re-composited on the original
backdrop, the result matches the source to within JPEG noise (printed below).

Replace assets/images/xetafit-logo.png with the official vector (SVG) as soon as
the brand supplies it; the CSS needs no change beyond the file name.
"""
import sys
import numpy as np
from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:/Users/ASUS/Downloads/Xetafit/WhatsApp Image 2026-11-02 at 12.06.48 PM.jpeg"
OUT = sys.argv[2] if len(sys.argv) > 2 else "assets/images/xetafit-logo.png"
src = Image.open(SRC).convert("RGB")
crop = np.asarray(src.crop((60, 60, 350, 160))).astype(np.float64)
border = np.concatenate([crop[:4].reshape(-1, 3), crop[-4:].reshape(-1, 3), crop[:, :4].reshape(-1, 3), crop[:, -4:].reshape(-1, 3)])
B = np.median(border, 0)
dist = np.linalg.norm(crop - B, axis=2)
ys, xs = np.nonzero(dist > 40)
y0, y1, x0, x1 = ys.min() - 3, ys.max() + 4, xs.min() - 3, xs.max() + 4
C = crop[y0:y1, x0:x1]
print("background", B.round(1), "logo box", (x0 + 60, y0 + 60, x1 + 60, y1 + 60), "size", C.shape[1], "x", C.shape[0])

# the two ink colours of the artwork, measured from its solid interiors
d = np.linalg.norm(C - B, axis=2)
warm_px = (C[..., 0] - C[..., 2] > 90) & (d > 120)
warm = warm_px & (d > np.percentile(d[warm_px], 60))          # solid orange interior
cool = (C.min(2) > 200) & (d > np.percentile(d, 99))           # solid white interior
F_or = np.median(C[warm], 0); F_wh = np.median(C[cool], 0)
print("orange ink", F_or.round(0), "white ink", F_wh.round(0))

def unmix(F):
    v = F - B
    a = np.clip(((C - B) @ v) / (v @ v), 0, 1)
    res = np.linalg.norm(C - (B + a[..., None] * v), axis=2)
    return a, res
a_o, r_o = unmix(F_or); a_w, r_w = unmix(F_wh)
use_o = r_o < r_w
a = np.where(use_o, a_o, a_w)
F = np.where(use_o[..., None], F_or, F_wh)
a = np.where(a < 0.05, 0, a)                       # JPEG noise in the backdrop
# colour: the original pixel, un-mixed from the backdrop where it is mostly ink;
# the measured ink colour at thin anti-aliased edges (noise would blow up there)
with np.errstate(divide="ignore", invalid="ignore"):
    own = np.clip((C - (1 - a[..., None]) * B) / np.maximum(a[..., None], 1e-6), 0, 255)
w = np.clip((a - 0.55) / 0.35, 0, 1)[..., None]
rgb = own * w + F * (1 - w)
out = np.dstack([rgb, a * 255]).round().astype(np.uint8)
Image.fromarray(out, "RGBA").save(OUT, optimize=True)
print("wrote", OUT)

# check: re-composited on the original backdrop it must match the source
back = rgb * a[..., None] + B * (1 - a[..., None])
err = np.abs(back - C)
print("re-composite error vs source: mean %.2f, 99th pct %.2f (0-255)" % (err.mean(), np.percentile(err, 99)))
