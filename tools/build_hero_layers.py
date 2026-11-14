"""Builds the separate layers for the hero opening animation (01 Hero).

    python tools/build_hero_layers.py            # tube layers + tablet frame strips (~2-3 min)
    python tools/build_hero_layers.py --tubes    # tube layers only (a few seconds)

Everything comes from the same studio packshot as the rest of the site
(assets/source/xetafit-tube-front.png) and the same ray-marched tablet model as
tools/render_product.py, so the label, the light and the tablets match.

Tube layers (all the same canvas as the closed tube, so they register exactly):
  hero-tube.webp         closed tube, full source resolution (+ hero-tube-190.webp for 1x screens)
  hero-cap.webp          the white cap alone, cut along the real cap/label seam
  hero-tube-open.webp    the tube without its cap: label, front wall and front lip of the opening
                         (the opening itself is transparent, so tablets can sit inside it)
  hero-tube-inner.webp   what is seen through the opening: back half of the rim + inner wall

  The source never shows the tube under its cap. The open tube is therefore built
  from geometry, not invented artwork: the camera elevation is measured from the
  cap's top ellipse (about 8 deg), the opening is that same ellipse at the body
  radius, the label's own top green band continues up to the rim, and the rim and
  inner wall are shaded with the studio light measured on the white label paper.
  No printed packaging detail is created or changed.

Tablet frame strips (hero-tablet-1.webp, hero-tablet-2.webp):
  N square frames, each the same tablet ray-marched at an orientation between
  "lying flat in the tube" (tilt = camera elevation) and its final resting angle,
  eased. CSS steps through them while the tablet flies out. The last frame is the
  resting state (and the only frame shown with reduced motion).

Geometry for the CSS (in % of the tube canvas) is written to tools/hero-layers.json.
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_product as rp  # noqa: E402

ROOT = rp.ROOT
OUT = rp.OUT
FRAMES = 16
FRAME_PX = 320
WALL = 4.5            # tube wall thickness at the rim, source px
NECK_EDGE = 172.0     # rim centre row (source px); chosen so the whole rim hides under the cap
SS = 4                # supersampling for the rim / opening edges


def save_box(path, rgb, alpha, box, quality=95):
    x0, y0, x1, y1 = box
    rgba = np.dstack([np.clip(rgb[y0:y1, x0:x1], 0, 1), np.clip(alpha[y0:y1, x0:x1], 0, 1)])
    img = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")
    img.save(path, "WEBP", quality=quality, method=6, alpha_quality=100)
    print(f"  wrote {os.path.relpath(path, ROOT)}  {img.size[0]}x{img.size[1]}  {os.path.getsize(path) // 1024} KB")
    return img


def seam_rows(a, geo):
    """Per column: the first row of the green label under the cap (float, smoothed)."""
    x0, R = geo["x0"], geo["R"]
    W = geo["W"]
    seam = np.full(W, np.nan, np.float32)
    for x in range(int(x0 - R) - 1, int(x0 + R) + 2):
        col = a[150:260, x]
        g = (col[:, 1] - col[:, 0]) - 0.2           # >0 inside the green label
        g2 = (col[:, 1] - col[:, 2]) - 0.3
        gr = np.minimum(g, g2)
        idx = np.where(gr > 0)[0]
        if not len(idx):
            continue
        i = idx[0]
        # sub-pixel: where the "greenness" ramp crosses zero
        prev = gr[i - 1] if i > 0 else -1.0
        frac = float(np.clip(-prev / max(gr[i] - prev, 1e-3), 0, 1))
        seam[x] = 150 + i - 1 + frac
    good = ~np.isnan(seam)
    xs = np.arange(W)
    seam = np.interp(xs, xs[good], seam[good]).astype(np.float32)
    seam = cv2.GaussianBlur(seam.reshape(1, -1), (0, 0), sigmaX=2.5).ravel()
    return seam


def build_tubes():
    print("source:", os.path.relpath(rp.DEFAULT_SRC, ROOT))
    a = np.asarray(Image.open(rp.DEFAULT_SRC).convert("RGB")).astype(np.float32) / 255.0
    geo, d, obj = rp.measure(a)
    bg = np.array(geo["bg"], np.float32)
    alpha = rp.tube_alpha(a, geo, d, obj)
    rgb = rp.decontaminate(a, alpha, bg)
    th_tab, S_tab = rp.shading_profile(a, geo)
    H, W = geo["H"], geo["W"]
    x0, R = geo["x0"], geo["R"]

    ys, xs = np.where(alpha > 0.002)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    bw, bh = box[2] - box[0], box[3] - box[1]

    # ---- closed tube -------------------------------------------------------------
    closed = save_box(os.path.join(OUT, "hero-tube.webp"), rgb, alpha, box)
    small_h = round(bh * 190 / bw)
    closed.resize((190, small_h), Image.LANCZOS).save(os.path.join(OUT, "hero-tube-190.webp"), "WEBP",
                                                       quality=95, method=6, alpha_quality=100)
    print(f"  wrote assets/images/hero-tube-190.webp  190x{small_h}")

    # ---- cap: everything above the seam (all of the skirt that overhangs the body) -
    seam = seam_rows(a, geo)
    Y = np.arange(H, dtype=np.float32)[:, None]
    X = np.arange(W, dtype=np.float32)[None, :]
    cut_above = np.clip(seam[None, :] - Y, 0, 1)
    in_body = np.abs(X + 0.5 - x0) <= R
    # lowest row of the skirt where it overhangs the body
    over = [y for y in range(int(geo["body_start"]) - 20, int(geo["body_start"]) + 40)
            if np.ptp(np.where(obj[y])[0]) > 2 * R + 6]
    skirt_bottom = float(max(over)) + 1.0
    side_cut = np.clip(skirt_bottom - Y, 0, 1)
    cap_a = alpha * np.where(in_body, cut_above, side_cut)
    save_box(os.path.join(OUT, "hero-cap.webp"), rgb, cap_a, box)

    # ---- the opening: rim ellipse at the body radius, camera elevation from the cap -
    sin_e = geo["cap_ry"] / geo["cap_rx"]
    elev = math.degrees(math.asin(sin_e))
    Yr = NECK_EDGE
    rx_o, ry_o = R, R * sin_e
    rx_i = R - WALL
    ry_i = rx_i * sin_e

    # work on a supersampled strip around the rim
    y_a, y_b = int(Yr - ry_o - 6), int(max(seam[int(x0 - R):int(x0 + R)].max(), Yr + ry_o) + 8)
    x_a, x_b = int(x0 - R - 3), int(x0 + R + 4)
    sy = (np.arange((y_b - y_a) * SS, dtype=np.float32) + 0.5) / SS + y_a
    sx = (np.arange((x_b - x_a) * SS, dtype=np.float32) + 0.5) / SS + x_a
    SY, SX = np.meshgrid(sy, sx, indexing="ij")
    u = (SX - x0) / rx_o
    ui = (SX - x0) / rx_i
    e_out = u ** 2 + ((SY - Yr) / ry_o) ** 2          # <1 inside the outer ellipse
    e_in = ui ** 2 + ((SY - Yr) / ry_i) ** 2          # <1 inside the inner ellipse (the hole)
    c_out = np.sqrt(np.clip(1 - u ** 2, 0, 1))
    inside_body = np.abs(u) <= 1
    below_back_arc = SY >= Yr - ry_o * c_out          # under the outer ellipse's far edge
    tube_proj = inside_body & below_back_arc
    hole = e_in < 1
    ring = (e_out < 1) & ~hole
    back_ring = ring & (SY < Yr)
    front = tube_proj & ~hole & ~back_ring

    # colours
    th = np.arcsin(np.clip(u, -1, 1))
    S = rp.eval_S(th_tab, S_tab, th)                  # studio shading of white paper at this column
    seam_ss = np.interp(SX, np.arange(W) + 0.5, seam)
    # green band continued up to the rim: the label colour a few rows under the seam, per column
    band_rows = np.clip((seam + 7).astype(int), 0, H - 1)
    band = rgb[band_rows, np.arange(W)]               # (W, 3)
    band = cv2.GaussianBlur(band.reshape(1, -1, 3), (0, 0), sigmaX=1.2).reshape(-1, 3)
    band_ss = np.stack([np.interp(SX, np.arange(W) + 0.5, band[:, ch]) for ch in range(3)], -1)
    # the top of the band is a touch lighter (light from above catching the rim), with a fine shadow line under the lip
    y_front = Yr + ry_o * c_out
    t_from_rim = np.clip((SY - y_front) / 10.0, 0, 1)
    neck = band_ss * (0.96 + 0.06 * t_from_rim[..., None])
    neck *= 1 - 0.18 * np.exp(-((SY - y_front - 1.4) / 0.9) ** 2)[..., None]

    plastic = np.array([0.965, 0.962, 0.955], np.float32)
    lip = np.clip(S / np.maximum(S.max(), 1e-3), 0.55, 1.0) * plastic * 1.02
    lip = np.clip(lip, 0, 1)
    # inner wall: lit near the rim, falling off with depth; slightly darker towards the sides
    y_back_in = Yr - ry_i * np.sqrt(np.clip(1 - ui ** 2, 0, 1))
    depth = np.clip(SY - y_back_in, 0, None) / math.cos(math.radians(elev))
    side = 1 - 0.25 * np.abs(ui) ** 2
    inner_l = (0.18 + 0.62 * np.exp(-depth / 9.0)) * side
    inner = np.stack([inner_l * 0.96, inner_l * 0.965, inner_l * 0.95], -1)
    # a soft contact shadow just inside the far rim edge
    inner *= (1 - 0.25 * np.exp(-(depth / 1.2) ** 2))[..., None]

    def down(mask, col=None):
        m = cv2.resize(mask.astype(np.float32), (x_b - x_a, y_b - y_a), interpolation=cv2.INTER_AREA)
        if col is None:
            return m
        pc = cv2.resize((col * mask[..., None]).astype(np.float32), (x_b - x_a, y_b - y_a), interpolation=cv2.INTER_AREA)
        return m, pc

    # FRONT layer: label body below the seam as photographed; green band + lip above it
    below_seam = SY >= seam_ss
    front_col = np.where(below_seam[..., None], 0, np.where(ring[..., None], lip[None, ...] if lip.ndim == 2 else lip, neck))
    f_a_ss = front & ~below_seam
    fa, fpc = down(f_a_ss, front_col)

    open_a = alpha.copy()
    open_rgb = rgb.copy()
    # remove the cap and the skirt overhang: keep only body pixels below the seam
    keep = np.where(in_body, 1 - cut_above, np.clip(Y - skirt_bottom - 3, 0, 1))   # no skirt slivers beside the body
    open_a = open_a * keep
    # composite the synthesised strip (premultiplied) over what is left
    sl = (slice(y_a, y_b), slice(x_a, x_b))
    base_pc = open_rgb[sl] * open_a[sl][..., None]
    out_pc = fpc + base_pc * (1 - fa[..., None])
    out_a = fa + open_a[sl] * (1 - fa)
    open_rgb[sl] = rp.unpremul(out_pc, out_a)
    open_a[sl] = out_a
    save_box(os.path.join(OUT, "hero-tube-open.webp"), open_rgb, open_a, box)

    # BACK layer: far half of the rim + the inner wall seen through the opening
    back_col = np.where(hole[..., None], inner, lip)
    b_ss = back_ring | hole
    ba, bpc = down(b_ss, back_col)
    inner_rgb = np.zeros((H, W, 3), np.float32)
    inner_a = np.zeros((H, W), np.float32)
    inner_rgb[sl] = rp.unpremul(bpc, ba)
    inner_a[sl] = ba
    save_box(os.path.join(OUT, "hero-tube-inner.webp"), inner_rgb, inner_a, box)

    seam_c = float(seam[int(round(x0))])
    cap_rows = np.where(cap_a.max(axis=1) > 0.01)[0]
    g = dict(
        canvas=[bw, bh], elevation_deg=round(elev, 2),
        rim_cx=round((x0 - box[0]) / bw * 100, 3), rim_cy=round((Yr - box[1]) / bh * 100, 3),
        rim_rx_w=round(rx_o / bw * 100, 3), rim_ry_h=round(ry_o / bh * 100, 3),
        inner_rx_w=round(rx_i / bw * 100, 3), inner_ry_h=round(ry_i / bh * 100, 3),
        seam_center_h=round((seam_c - box[1]) / bh * 100, 3),
        cap_top_h=round((cap_rows.min() - box[1]) / bh * 100, 3), cap_bottom_h=round((cap_rows.max() - box[1]) / bh * 100, 3),
        body_halfwidth_w=round(R / bw * 100, 3),
    )
    return g, geo, box


def render_strip(name, seed, spin, tilt0, tilt1, roll1):
    """N frames of one tablet turning from flat-in-the-tube to its resting angle."""
    frames = []
    captured = {}

    def grab(path, rgb, alpha, quality=92):
        captured["rgb"], captured["a"] = rgb, alpha
        return (0, 0, rgb.shape[1], rgb.shape[0])

    orig = rp.save_rgba
    rp.save_rgba = grab
    try:
        for i in range(FRAMES):
            t = i / (FRAMES - 1)
            e = t * t * (3 - 2 * t)                    # ease in-out
            rp.render_tablet(None, tilt_deg=tilt0 + (tilt1 - tilt0) * e, roll_deg=roll1 * e,
                             spin_deg=spin, seed=seed, size=FRAME_PX, ss=3)
            frames.append(np.dstack([captured["rgb"], captured["a"]]))
            print(f"    {name} frame {i + 1}/{FRAMES}", end="\r")
    finally:
        rp.save_rgba = orig
    strip = np.concatenate(frames, axis=1)
    img = Image.fromarray((np.clip(strip, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    path = os.path.join(OUT, name)
    img.save(path, "WEBP", quality=82, method=6, alpha_quality=90)
    print(f"  wrote {os.path.relpath(path, ROOT)}  {img.size[0]}x{img.size[1]}  {os.path.getsize(path) // 1024} KB")


def main():
    g, geo, box = build_tubes()
    if "--tubes" not in sys.argv:
        elev = g["elevation_deg"]
        print("  rendering tablet frame strips ...")
        # the same tablets (seed, spin) and resting angles as tablet-a / tablet-b
        render_strip("hero-tablet-1.webp", seed=7, spin=20, tilt0=elev, tilt1=58, roll1=-18)
        render_strip("hero-tablet-2.webp", seed=11, spin=110, tilt0=elev, tilt1=34, roll1=24)
        g["tablet_frames"] = FRAMES
        g["tablet_span"] = 1.32          # frame half-width in tablet radii (render_tablet)
        g["tablet_half_thickness"] = 0.24
    path = os.path.join(ROOT, "tools", "hero-layers.json")
    with open(path, "w") as f:
        json.dump(g, f, indent=2)
    print("  geometry:", json.dumps(g))


if __name__ == "__main__":
    main()
