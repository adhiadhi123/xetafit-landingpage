"""Smaller copies of the large page images, for srcset on phones.

    python tools/make_responsive.py
"""
from pathlib import Path
from PIL import Image

IMG = Path(__file__).resolve().parents[1] / "assets" / "images"
JOBS = [  # source, output, width
    ("lifestyle-workspace.webp", "lifestyle-workspace-768.webp", 768),
    ("final-product-drink.webp", "final-product-drink-768.webp", 768),
    ("pack4.webp", "pack4-640.webp", 640),
]

for src, out, w in JOBS:
    im = Image.open(IMG / src)
    h = round(im.height * w / im.width)
    im.resize((w, h), Image.LANCZOS).save(IMG / out, "WEBP", quality=84, method=6)
    print(out, (w, h), (IMG / out).stat().st_size // 1024, "KB")
