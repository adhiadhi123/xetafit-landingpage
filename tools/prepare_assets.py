"""
XETAFIT asset preparation
=========================

NOTE: the pages now use the product renders made by tools/render_product.py
(tube-*.webp, pack4.webp, tablet-a/b.webp). Only the certificate previews this
script makes are still in use; its storyboard product cut-outs are legacy.

Builds the web images used by index.html / certificate.html from the supplied
source files. The source files are only READ - they are never modified.

    python tools/prepare_assets.py <storyboard.png> <certificate.pdf>

Requires: pillow, numpy, opencv-python(-headless), pypdfium2

What it produces (assets/images/):
    product-front.webp   front view cut-out           (storyboard panel "Front View")
    product-angle.webp   front 45 deg cut-out         (storyboard panel "Front 45 View")
    product-side.webp    left side cut-out            (storyboard panel "Left Side View")
    product-tilt.webp    tilted / dynamic cut-out     (storyboard panel "Tilted View")
    tablet.webp          effervescent tablet cut-out  (storyboard panel "Tablet Close-Up")
    product-pack4.webp   four-tube composition built from product-front / product-angle
    certificate-preview.webp / certificate-preview-sm.webp
                         raster preview of the ORIGINAL certificate PDF (page 1)

The storyboard is a generated reference (1536 x 1024). Cut-outs are upscaled 2x,
so they are softer than real packshots. Replace them with photographed /
rendered transparent PNGs when the manufacturer artwork is available - keep the
same file names and the CSS needs no changes (see README.md).
"""
import sys
import os
import numpy as np
import cv2
from PIL import Image, ImageFilter, ImageEnhance

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "images")
SCALE = 2  # upscale factor applied before masking

# Panel rectangles in the 1536 x 1024 storyboard (left, top, right, bottom)
PANELS = {
    "front": (5, 5, 321, 470),
    "angle": (326, 5, 617, 470),
    "side":  (622, 5, 912, 470),
    "tilt":  (595, 524, 917, 960),
    "tablet": (1190, 524, 1532, 960),
}


def load_panel(sb, box):
    im = sb.crop(box)
    im = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    return im


def hsv_arrays(rgb):
    a = rgb.astype(np.float32) / 255.0
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return sat, mx, mn


def tube_mask(rgb, cap_margin_frac=0.16, base_margin_frac=0.018):
    """Convex-hull mask of a tube: saturated label/body pixels + the white cap
    found along the tube axis (towards the cap end only, so the floor shadow is
    excluded)."""
    sat, mx, mn = hsv_arrays(rgb)
    green = (sat > 0.32) & (mx > 0.25)
    green = cv2.morphologyEx(green.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # The white label splits the green print into several regions (top band,
    # lower panel, side strips) - keep every sizeable region, drop specks.
    n, lab, stats, _ = cv2.connectedComponentsWithStats(green)
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i, a in enumerate(areas) if a > 0.02 * areas.max()]
    green = np.isin(lab, keep)
    ys, xs = np.nonzero(green)
    pts = np.stack([xs, ys], axis=1).astype(np.float32)
    mean = pts.mean(axis=0)
    cov = np.cov((pts - mean).T)
    evals, evecs = np.linalg.eigh(cov)
    axis = evecs[:, np.argmax(evals)]
    if axis[1] > 0:  # make the axis point "up" (towards the cap)
        axis = -axis
    perp = np.array([-axis[1], axis[0]])
    proj = (pts - mean) @ axis
    pdist = (pts - mean) @ perp
    length = proj.max() - proj.min()
    radius = np.percentile(np.abs(pdist), 99.5)

    # candidate non-background pixels (anything visibly darker than the white sweep)
    nonbg = (mn < 0.955) | (sat > 0.10)
    yy, xx = np.nonzero(nonbg)
    q = np.stack([xx, yy], axis=1).astype(np.float32)
    qp = (q - mean) @ axis
    qd = np.abs((q - mean) @ perp)
    cap = (qp > proj.max() - 2) & (qp < proj.max() + cap_margin_frac * length) & (qd < radius * 1.06)
    base = (qp < proj.min() + 2) & (qp > proj.min() - base_margin_frac * length) & (qd < radius * 0.98)
    allpts = np.concatenate([pts, q[cap], q[base]]).astype(np.int32)
    hull = cv2.convexHull(allpts)
    m = np.zeros(rgb.shape[:2], np.uint8)
    cv2.fillConvexPoly(m, hull, 255)
    return m


def tablet_mask(rgb):
    """Every tablet pixel leans green (G > B), while the floor shadow is a
    neutral / violet grey (B >= G) - that separates the pale tablet face from
    both the white sweep and its own cast shadow."""
    f = rgb.astype(np.int16)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    t = ((g - b) > 7) & (g > 120) & ((g - r) > 2)
    t = cv2.morphologyEx(t.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    t = cv2.morphologyEx(t, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(t)
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    ys, xs = np.nonzero(lab == biggest)
    hull = cv2.convexHull(np.stack([xs, ys], axis=1).astype(np.int32))
    m = np.zeros(rgb.shape[:2], np.uint8)
    cv2.fillConvexPoly(m, hull, 255)
    # The contact shadow right under the tablet is green-tinted too, so clip
    # the hull with an ellipse fitted to the clean upper 70% of the outline.
    pts = hull.reshape(-1, 2)
    cnt, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = cnt[0].reshape(-1, 2)
    y0, y1 = c[:, 1].min(), c[:, 1].max()
    upper = c[c[:, 1] < y0 + 0.70 * (y1 - y0)]
    ell = cv2.fitEllipse(upper.astype(np.float32))
    e = np.zeros_like(m)
    cv2.ellipse(e, ell, 255, -1)
    return cv2.bitwise_and(m, e)


def finish(img, mask, erode=3, feather=1.6, pad=12):
    """Erode to drop the white fringe, feather, crop tight, return RGBA."""
    m = cv2.erode(mask, np.ones((erode, erode), np.uint8))
    m = cv2.GaussianBlur(m, (0, 0), feather)
    rgba = np.dstack([np.asarray(img), m])
    ys, xs = np.nonzero(m > 8)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, m.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, m.shape[1])
    return Image.fromarray(rgba[y0:y1, x0:x1], "RGBA")


def save_webp(im, name, quality=90):
    path = os.path.join(OUT, name)
    im.save(path, "WEBP", quality=quality, method=6)
    print(f"  {name:28s} {im.size[0]}x{im.size[1]}  {os.path.getsize(path)//1024} KB")


def build_pack4(front, angle):
    """Four-tube group: hero tube in front, three tubes receding to the right.
    Geometry mirrors the CSS "mates" layout in css/style.css (.tv-mate--2/3/4):
    x offset in tube widths, scale k, bottom raise r (fraction of tube height)."""
    H, w = front.height, front.width
    ROW = [(1.92, 0.73, 0.14, 0.70), (1.36, 0.81, 0.10, 0.80), (0.72, 0.90, 0.055, 0.90)]
    W = int(w * (1 + 1.92 + 0.2))
    canvas = Image.new("RGBA", (W, int(H * 1.02)), (0, 0, 0, 0))

    def shade(im, k):
        rgb = ImageEnhance.Brightness(im.convert("RGB")).enhance(k)
        out = rgb.convert("RGBA")
        out.putalpha(im.getchannel("A"))
        return out

    def place(im, scale, cx, bottom, k):
        t = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        t = shade(t, k)
        canvas.alpha_composite(t, (int(cx - t.width / 2), int(bottom - t.height)))

    base = canvas.height - 4
    lead_cx = w * 0.55
    for dx, k, r, light in ROW:                       # back to front
        place(front, k, lead_cx + dx * w, base - r * H, light)
    place(front, 1.0, lead_cx, base, 1.0)             # hero tube
    return canvas.crop(canvas.getbbox())


def main(storyboard, pdf_path):
    os.makedirs(OUT, exist_ok=True)
    sb = Image.open(storyboard).convert("RGB")
    print("Cut-outs:")
    cut = {}
    for key in ("front", "angle", "side", "tilt"):
        img = load_panel(sb, PANELS[key])
        rgb = np.asarray(img)
        cut[key] = finish(img, tube_mask(rgb))
    img = load_panel(sb, PANELS["tablet"])
    cut["tablet"] = finish(img, tablet_mask(np.asarray(img)), erode=3, feather=1.4)

    # Normalise the three upright views to the same height so cross-fades line up
    h = cut["front"].height
    for key in ("angle", "side"):
        im = cut[key]
        cut[key] = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

    save_webp(cut["front"], "product-front.webp")
    save_webp(cut["angle"], "product-angle.webp")
    save_webp(cut["side"], "product-side.webp")
    save_webp(cut["tilt"], "product-tilt.webp")
    t = cut["tablet"]
    t = t.resize((360, round(t.height * 360 / t.width)), Image.LANCZOS)
    save_webp(t, "tablet.webp")
    save_webp(build_pack4(cut["front"], cut["angle"]), "product-pack4.webp")

    print("Certificate preview (rendered from the original PDF, unaltered):")
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[0].render(scale=2.2).to_pil().convert("RGB")
    big = page.resize((1200, round(page.height * 1200 / page.width)), Image.LANCZOS)
    save_webp(big, "certificate-preview.webp", quality=88)
    sm = page.resize((620, round(page.height * 620 / page.width)), Image.LANCZOS)
    save_webp(sm, "certificate-preview-sm.webp", quality=86)
    # first-panel crop (header + results table) for the in-page document frame
    crop = page.crop((0, 0, page.width, int(page.height * 0.58)))
    crop = crop.resize((900, round(crop.height * 900 / crop.width)), Image.LANCZOS)
    save_webp(crop, "certificate-crop.webp", quality=86)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
